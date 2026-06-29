"""
FluentYTDL 统一组件更新协调器

协调 app-core 和 bin/ 工具的版本检查与更新。
通过 GitHub Release 的 update-manifest.json 统一管理所有组件版本。

版本通道:
  - v- (stable): 检查 /releases/latest，只接收稳定版
  - pre- (pre-release): 检查 /releases，可接收 pre 和 v 更新
  - beta-: 锁定更新，弹窗提示
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from ..utils.logger import logger
from ..utils.paths import frozen_app_dir, is_frozen
from .config_manager import config_manager

# ─── 常量 ────────────────────────────────────────────────

REPO_OWNER = "SakuraForgot"
REPO_NAME = "FluentYTDL"
GITHUB_API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"

MANIFEST_FILENAME = "update-manifest.json"
# RAW 直链：releases/latest/download/ 会自动 302 重定向到最新 release 的 asset
# 完全绕过 GitHub API 速率限制（无 token 时 60 次/小时）
MANIFEST_RAW_URL = (
    f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest/download/{MANIFEST_FILENAME}"
)

# ─── 版本比较 ────────────────────────────────────────────


def _parse_version(ver: str) -> tuple[int, ...]:
    """将 '3.0.0' 或 'v3.0.0' 解析为可比较的整数元组"""
    clean = re.sub(r"^(v-?|pre-|beta-)", "", str(ver).strip())
    clean = clean.split("-")[0]
    parts: list[int] = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _parse_version_prefix(full_version: str) -> tuple[str, str]:
    """解析版本前缀和数字部分。
    "v-3.0.18" → ("v-", "3.0.18")
    "pre-3.0.18" → ("pre-", "3.0.18")
    "beta-0.0.5" → ("beta-", "0.0.5")
    """
    for pfx in ("v-", "pre-", "beta-"):
        if full_version.startswith(pfx):
            return pfx, full_version[len(pfx) :]
    return "v-", full_version


def _get_update_channel() -> str:
    """根据当前版本前缀确定更新通道。

    仅 stable（v- 前缀）支持自动更新。
    beta 和 pre 统一为 locked，提示用户去 GitHub 手动下载。
    """
    from fluentytdl import __version__

    if __version__.startswith("v-"):
        return "stable"
    return "locked"  # beta- 和 pre- 统一为 locked


def _get_proxies() -> dict[str, str]:
    """从 config 构建代理字典。"""
    proxy_mode = str(config_manager.get("proxy_mode") or "off").lower()
    proxy_url = str(config_manager.get("proxy_url") or "")

    if proxy_mode in ("http", "socks5") and proxy_url:
        scheme = "socks5h" if proxy_mode == "socks5" else "http"
        url = proxy_url if "://" in proxy_url else f"{scheme}://{proxy_url}"
        return {"http": url, "https": url}
    return {}


def _get_mirror_url(url: str) -> str:
    """根据配置应用镜像。"""
    source = str(config_manager.get("update_source") or "github").lower()
    if source == "ghproxy" and url.startswith("https://github.com/"):
        mirror = "https://ghfast.top/"
        return mirror + url
    return url


# ─── 清单获取线程 ────────────────────────────────────────


class _ManifestWorker(QThread):
    """后台线程：获取 update-manifest.json

    使用 RAW 直链 (releases/latest/download/) 替代 GitHub API，
    彻底绕过 API 速率限制（无 token 时 60 次/小时）。
    失败时回退到本地缓存清单（7 天有效期）。
    """

    finished = Signal(dict)  # manifest dict
    error = Signal(str)

    def __init__(self, release_tag: str = ""):
        super().__init__()
        self.release_tag = release_tag

    def run(self) -> None:
        try:
            import json

            import requests

            from ..utils.paths import user_data_dir

            proxies = _get_proxies()

            # RAW 直链下载 — 一步到位，无需 API 调用
            manifest_url = _get_mirror_url(MANIFEST_RAW_URL)
            sep = "&" if "?" in manifest_url else "?"
            final_url = f"{manifest_url}{sep}t={int(time.time())}"

            resp = requests.get(final_url, proxies=proxies, timeout=15)
            resp.raise_for_status()
            manifest = resp.json()

            # 本地缓存（离线回退用）
            try:
                cache_path = user_data_dir() / "update_manifest_cache.json"
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(
                    json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
                )
            except Exception:
                pass

            self.finished.emit(manifest)

        except Exception as e:
            # 回退到本地缓存清单
            try:
                import json

                from ..utils.paths import user_data_dir

                cache_path = user_data_dir() / "update_manifest_cache.json"
                if cache_path.exists():
                    age = time.time() - cache_path.stat().st_mtime
                    if age < 7 * 86400:  # 7 天有效期
                        manifest = json.loads(cache_path.read_text(encoding="utf-8"))
                        logger.info(
                            f"[ComponentUpdate] 网络失败，使用缓存清单（{int(age / 3600)}小时前）"
                        )
                        self.finished.emit(manifest)
                        return
            except Exception:
                pass

            logger.error(f"[ComponentUpdate] 清单获取失败: {e}")
            self.error.emit(str(e))


# ─── 下载线程 ────────────────────────────────────────────


class _DownloadWorker(QThread):
    """后台线程：下载更新文件"""

    progress = Signal(int)  # 0-100
    finished = Signal(str)  # 本地文件路径
    error = Signal(str)

    def __init__(self, url: str, expected_sha256: str = ""):
        super().__init__()
        self.url = url
        self.expected_sha256 = expected_sha256

    def run(self) -> None:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = self._download_once()
                if result:
                    self.finished.emit(result)
                    return
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s
                    logger.warning(
                        f"[ComponentUpdate] 下载失败（尝试 {attempt + 1}/{max_retries}），"
                        f"{wait}s 后重试: {e}"
                    )
                    self.progress.emit(0)
                    time.sleep(wait)
                else:
                    logger.error(f"[ComponentUpdate] 下载失败（已重试 {max_retries} 次）: {e}")
                    self.error.emit(str(e))
                    return

    def _download_once(self) -> str | None:
        """单次下载尝试。成功返回文件路径，失败抛异常。"""
        import hashlib
        import tempfile

        import requests

        final_url = _get_mirror_url(self.url)
        proxies = _get_proxies()

        tmp_dir = Path(tempfile.mkdtemp(prefix="fluentytdl_update_"))
        filename = self.url.rsplit("/", 1)[-1]
        dest = tmp_dir / filename

        resp = requests.get(final_url, proxies=proxies, timeout=600, stream=True)
        resp.raise_for_status()

        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        sha256 = hashlib.sha256()

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                f.write(chunk)
                sha256.update(chunk)
                downloaded += len(chunk)
                if total > 0:
                    self.progress.emit(int(downloaded / total * 100))

        if self.expected_sha256:
            actual = sha256.hexdigest().lower()
            expected = self.expected_sha256.strip().lower()
            if actual != expected:
                dest.unlink(missing_ok=True)
                raise ValueError(f"SHA256 校验失败\n预期: {expected}\n实际: {actual}")

        self.progress.emit(100)
        return str(dest)


# ─── 主管理器 ────────────────────────────────────────────


class ComponentUpdateManager(QObject):
    """统一组件更新协调器"""

    # 清单信号
    manifest_fetched = Signal(dict)
    manifest_error = Signal(str)

    # app-core 信号
    app_update_available = Signal(dict)  # {version, tag, changelog, url, sha256, is_prerelease}
    app_no_update = Signal()
    app_check_error = Signal(str)

    # 下载信号
    download_progress = Signal(int)
    download_finished = Signal(str)  # 本地路径
    download_error = Signal(str)

    # 通用信号
    check_complete = Signal(list)  # 所有组件检查结果列表

    def __init__(self) -> None:
        super().__init__()
        self._manifest: dict | None = None
        self._manifest_worker: _ManifestWorker | None = None
        self._download_worker: _DownloadWorker | None = None

    @property
    def manifest(self) -> dict | None:
        return self._manifest

    # ── 清单获取 ──────────────────────────────────────────

    def fetch_manifest(self) -> None:
        """异步获取更新清单。"""
        channel = _get_update_channel()
        if channel == "locked":
            logger.info("[ComponentUpdate] locked 通道，跳过清单获取")
            return

        worker = _ManifestWorker(release_tag="")
        worker.finished.connect(self._on_manifest_fetched)
        worker.error.connect(self._on_manifest_error)
        self._manifest_worker = worker
        worker.start()

    def _on_manifest_fetched(self, manifest: dict) -> None:
        self._manifest = manifest
        logger.info(f"[ComponentUpdate] 清单获取成功: {manifest.get('app_version', '?')}")
        self.manifest_fetched.emit(manifest)

    def _on_manifest_error(self, msg: str) -> None:
        logger.warning(f"[ComponentUpdate] 清单获取失败: {msg}")
        self.manifest_error.emit(msg)

    # ── 统一检查 ──────────────────────────────────────────

    def check_all(self) -> None:
        """检查所有组件更新（app-core + bin/ 工具）。"""
        channel = _get_update_channel()

        if channel == "locked":
            # locked 通道（beta/pre）不检查更新
            return

        # 先获取清单
        self.fetch_manifest()

    def check_app_update(self) -> None:
        """仅检查 app-core 更新。"""
        channel = _get_update_channel()

        if channel == "locked":
            self.app_check_error.emit("locked")
            return

        if self._manifest:
            self._compare_app_version()
        else:
            # 需要先获取清单，使用一次性连接
            self._manifest_app_check_conn = True
            self.manifest_fetched.connect(self._on_manifest_for_app_check)
            self.fetch_manifest()

    def _on_manifest_for_app_check(self, _manifest: dict) -> None:
        """清单获取完成后比对 app 版本（一次性回调）。"""
        try:
            self.manifest_fetched.disconnect(self._on_manifest_for_app_check)
        except RuntimeError:
            pass
        self._compare_app_version()

    def _compare_app_version(self) -> None:
        """比对 app-core 版本（仅 stable 通道）。"""
        if not self._manifest:
            self.app_check_error.emit("清单未获取")
            return

        try:
            from fluentytdl import __version__
        except ImportError:
            self.app_check_error.emit("无法获取当前版本")
            return

        manifest_version = self._manifest.get("app_version", "")
        manifest_tag = self._manifest.get("release_tag", manifest_version)

        # 确保版本号带前缀（v-3.1.4 格式），防止清单中缺少前缀
        prefix, numeric = _parse_version_prefix(manifest_version)
        manifest_version = f"{prefix}{numeric}"

        current = _parse_version(__version__)
        latest = _parse_version(manifest_version)

        if latest <= current:
            self.app_no_update.emit()
            return

        # 检查跳过版本（仅 stable）
        skipped = str(config_manager.get("skipped_stable_version") or "")
        if skipped and _parse_version(skipped) >= latest:
            self.app_no_update.emit()
            return

        # 获取 app-core 组件信息
        app_core = self._manifest.get("components", {}).get("app-core", {})

        self.app_update_available.emit(
            {
                "version": manifest_version,
                "tag": manifest_tag,
                "changelog": self._manifest.get("changelog", ""),
                "url": app_core.get("url", ""),
                "sha256": app_core.get("sha256", ""),
                "size": app_core.get("size", 0),
                "is_prerelease": False,
            }
        )

    # ── 下载 app-core 更新 ────────────────────────────────

    def download_app_update(self, url: str, sha256: str = "") -> None:
        """下载 app-core 更新归档。"""
        if not url:
            self.download_error.emit("下载 URL 为空")
            return

        worker = _DownloadWorker(url, sha256)
        worker.progress.connect(self.download_progress)
        worker.finished.connect(self._on_download_done)
        worker.error.connect(self.download_error)
        self._download_worker = worker
        worker.start()

    def _on_download_done(self, path: str) -> None:
        self.download_finished.emit(path)

    # ── 应用 app-core 更新 ────────────────────────────────

    @staticmethod
    def apply_app_core_update(archive_path: str) -> None:
        """启动 updater.exe 并退出主程序。"""
        app_dir = frozen_app_dir()
        exe_name = Path(sys.executable).name if is_frozen() else "FluentYTDL.exe"
        pid = os.getpid()

        # updater.exe 位于应用目录根目录
        updater_path = app_dir / "updater.exe"
        if not updater_path.exists():
            # 回退：检查 _internal/ 目录
            updater_path = app_dir / "_internal" / "updater.exe"

        if not updater_path.exists():
            logger.error(f"[ComponentUpdate] updater.exe 不存在: {updater_path}")
            raise FileNotFoundError(f"updater.exe 不存在: {updater_path}")

        logger.info(
            f"[ComponentUpdate] 启动 updater.exe: pid={pid}, archive={archive_path}, dest={app_dir}"
        )

        cmd = [
            str(updater_path),
            "--pid",
            str(pid),
            "--archive",
            str(archive_path),
            "--dest",
            str(app_dir),
            "--exe",
            exe_name,
        ]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW

        subprocess.Popen(cmd, creationflags=creationflags)
        sys.exit(0)

    # ── 版本通道工具 ──────────────────────────────────────

    @staticmethod
    def get_update_channel() -> str:
        """获取当前更新通道。"""
        return _get_update_channel()

    @staticmethod
    def is_beta() -> bool:
        """已弃用，使用 is_locked()。"""
        return ComponentUpdateManager.is_locked()

    @staticmethod
    def is_locked() -> bool:
        """是否为锁定版本（beta/pre），不支持自动更新。"""
        return _get_update_channel() == "locked"

    def get_manifest_component(self, key: str) -> dict | None:
        """从缓存清单中获取指定组件信息。"""
        if not self._manifest:
            return None
        return self._manifest.get("components", {}).get(key)


# ── 单例 ──
component_update_manager = ComponentUpdateManager()
