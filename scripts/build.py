#!/usr/bin/env python3
"""
FluentYTDL Build System - 现代化构建编排器
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
RELEASE_DIR = ROOT / "release"
ASSETS_BIN = ROOT / "assets" / "bin"
INSTALLER_DIR = ROOT / "installer"
LICENSES_DIR = ROOT / "licenses"

# 版本解析统一走 version_manager，避免出现第二份规则实现
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_tools import load_tool_versions  # noqa: E402
from version_manager import parse_version, strip_v_prefix, tag_for  # noqa: E402

# ============================================================================
# 工具函数
# ============================================================================


def _build_timestamp() -> str:
    """构建时刻（UTC, ISO 8601）。

    尊重 SOURCE_DATE_EPOCH —— 可复现构建的事实标准，设置后同一份源码
    两次构建的 BUILD_INFO.json 完全一致。
    """
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and epoch.isdigit():
        dt = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit() -> str:
    """当前 HEAD 的短 commit；非 git 环境（如从 sdist 构建）返回 unknown。"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if proc.returncode != 0:
        return "unknown"
    return (proc.stdout or "").strip() or "unknown"


def _dist_version(name: str) -> str:
    """已安装发行包的版本；未安装返回 unknown。"""
    try:
        import importlib.metadata

        return importlib.metadata.version(name)
    except Exception:
        return "unknown"


def _terminate_processes(exe_names: list[str]) -> None:
    for exe in exe_names:
        try:
            subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, timeout=5)
        except Exception:
            pass


def _safe_rmtree(path: Path, retries: int = 3, delay: float = 1.0) -> bool:
    if not path.exists():
        return True
    for attempt in range(retries):
        try:
            shutil.rmtree(path, ignore_errors=False)
            return True
        except PermissionError:
            if attempt < retries - 1:
                _terminate_processes(["FluentYTDL.exe", "yt-dlp.exe", "ffmpeg.exe", "deno.exe"])
                time.sleep(delay)
                delay *= 2
            else:
                return False
        except Exception:
            return False
    return False


def sha256_file(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


VERSION_INFO_TEMPLATE = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '080404b0',
          [
            StringStruct('CompanyName', '{company}'),
            StringStruct('FileDescription', '{description}'),
            StringStruct('FileVersion', '{version}'),
            StringStruct('InternalName', '{internal_name}'),
            StringStruct('LegalCopyright', '{copyright}'),
            StringStruct('OriginalFilename', '{original_filename}'),
            StringStruct('ProductName', '{product_name}'),
            StringStruct('ProductVersion', '{version}'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""


def generate_version_info(
    version: str,
    output_path: Path,
    company: str = "FluentYTDL Team",
    description: str = "FluentYTDL - 专业 YouTube 下载器",
    product_name: str = "FluentYTDL",
    copyright_text: str = "Copyright (C) 2024-2026 FluentYTDL Team",
    internal_name: str = "FluentYTDL",
    original_filename: str = "FluentYTDL.exe",
) -> Path:
    # 兼容 beta0.0.1, v1.2.3, 1.2.3-beta 等任意格式版本号
    nums = re.findall(r"\d+", version)
    major = int(nums[0]) if len(nums) > 0 else 0
    minor = int(nums[1]) if len(nums) > 1 else 0
    patch = int(nums[2]) if len(nums) > 2 else 0

    content = VERSION_INFO_TEMPLATE.format(
        major=major,
        minor=minor,
        patch=patch,
        version=version.lstrip("v"),
        company=company,
        description=description,
        product_name=product_name,
        copyright=copyright_text,
        internal_name=internal_name,
        original_filename=original_filename,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ============================================================================
# 构建编排器
# ============================================================================


class Builder:
    def __init__(
        self,
        override_version: str | None = None,
        skip_hygiene: bool = False,
        strict_tools: bool = False,
    ):
        self.arch = "win64" if sys.maxsize > 2**32 else "win32"
        self.skip_hygiene = skip_hygiene
        self.strict_tools = strict_tools
        self.config = self._load_config()
        # 是否由调用方显式指定版本 —— 决定 VERSION 文件是否可被回写（见 _sync_version_to_all）
        self._version_overridden = override_version is not None
        # 完整版本（含 -rc.N / -beta.N 后缀），不带 "v" 前缀
        raw_version = override_version or self.config.get("version", "0.0.0")
        try:
            numeric, channel = parse_version(raw_version)
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)
        self._full_version = strip_v_prefix(raw_version)
        self.channel = channel
        self.version = numeric  # PE 资源 / Inno Setup 用的纯数字版本
        self.tag = tag_for(self._full_version)

    def _load_config(self) -> dict:
        """读取构建配置。

        版本号来源是 VERSION 文件（唯一 source of truth），而不是 pyproject.toml —
        后者由 version_manager 派生，一旦回落读它就会在 _sync_version_to_all 里
        把派生值写回 VERSION，造成 source of truth 被静默改写。
        """
        cfg: dict = {}

        version_file = ROOT / "VERSION"
        if version_file.exists():
            content = version_file.read_text(encoding="utf-8").strip()
            if content:
                cfg["version"] = content

        pyproject = ROOT / "pyproject.toml"
        if not pyproject.exists():
            return cfg

        try:
            import tomllib

            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
                cfg.setdefault("version", data.get("project", {}).get("version", "0.0.0"))
                b_cfg = data.get("tool", {}).get("fluentytdl", {}).get("build", {})
                cfg.update(b_cfg)
                return cfg
        except ImportError:
            # Fallback 粗糙解析
            content = pyproject.read_text(encoding="utf-8")
            in_build = False
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("version =") and not in_build:
                    cfg.setdefault("version", line.split("=", 1)[1].strip(" '\""))
                if line == "[tool.fluentytdl.build]":
                    in_build = True
                    continue
                elif line.startswith("["):
                    in_build = False
                if in_build and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if v == "true":
                        cfg[k] = True
                    elif v == "false":
                        cfg[k] = False
                    elif v.startswith("[") and v.endswith("]"):
                        items = [x.strip(" '\"") for x in v[1:-1].split(",") if x.strip()]
                        cfg[k] = items
                    else:
                        cfg[k] = v.strip(" '\"")
            return cfg

    def _check_hygiene(self):
        """确保在一个干净的打包环境中"""
        if self.skip_hygiene or not self.config.get("strict_env_check", True):
            print("  ⚠️ 已跳过环境污染检测")
            return

        print("🩺 正在进行环境体检...")
        import importlib.metadata

        installed = {dist.metadata["Name"].lower() for dist in importlib.metadata.distributions()}
        blacklist = set(pkg.lower() for pkg in self.config.get("env_blacklist", []))

        found = installed.intersection(blacklist)
        if found:
            print(f"  ❌ 严重警告: 构建环境被污染！发现黑名单依赖: {', '.join(found)}")
            print("  这会导致打包产物极其臃肿并有可能引起杀软误报。")
            print("  请在干净的 venv 环境中重试。")
            print("  （如需无视警告强行打包，请传递 --skip-hygiene 参数）")
            sys.exit(1)
        print("  ✓ 环境干净，准许打包")

    def _sync_version_to_all(self) -> None:
        """将版本号同步到所有需要版本号的文件。

        VERSION / __init__.py / pyproject.toml 写完整版本（含 -rc.N 后缀），
        .iss 只写 X.Y.Z（Inno Setup 的 VersionInfoVersion 只接受纯数字）。

        VERSION 文件只在调用方显式传了 --version 时才回写。没传版本时版本本来
        就是从 VERSION 读出来的，回写除了制造 source of truth 被改写的风险外
        没有任何收益 —— 历史上正是这条路径把 VERSION 里的内容悄悄换掉的。
        """
        full = self._full_version
        numeric = self.version

        # 1. VERSION 文件 (source of truth) — 仅在显式指定版本时写入
        if self._version_overridden:
            (ROOT / "VERSION").write_text(full + "\n", encoding="utf-8")
        else:
            print("  ℹ 未指定 --version，保持 VERSION 文件原样")

        # 2. __init__.py — 运行时动态读 VERSION 时无需写入
        init_file = ROOT / "src" / "fluentytdl" / "__init__.py"
        if init_file.exists():
            content = init_file.read_text(encoding="utf-8")
            if "_read_version()" not in content:
                content = re.sub(
                    r'^__version__\s*=\s*["\'][^"\']+["\']',
                    f'__version__ = "{full}"',
                    content,
                    flags=re.MULTILINE,
                )
                init_file.write_text(content, encoding="utf-8")

        # 3. pyproject.toml — 完整版本（"3.5.6-rc.1" 规范化为 PEP 440 的 3.5.6rc1）
        pyproject = ROOT / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            content = re.sub(
                r'^version\s*=\s*["\'][^"\']+["\']',
                f'version = "{full}"',
                content,
                flags=re.MULTILINE,
            )
            # 如果使用 dynamic，替换为固定 version
            if 'dynamic = ["version"]' in content:
                content = content.replace('dynamic = ["version"]', "")
                content = re.sub(
                    r"\[project\]",
                    f'[project]\nversion = "{full}"',
                    content,
                    count=1,
                )
                content = re.sub(r"\[tool\.setuptools\.dynamic\]\n[^\[]*", "", content)
            pyproject.write_text(content, encoding="utf-8")

        # 4. FluentYTDL.iss — 纯数字版本（Inno Setup 要求）
        iss_file = ROOT / "installer" / "FluentYTDL.iss"
        if iss_file.exists():
            content = iss_file.read_text(encoding="utf-8")
            content = re.sub(
                r'#define\s+MyAppVersion\s+"[^"]+"',
                f'#define MyAppVersion "{numeric}"',
                content,
            )
            iss_file.write_text(content, encoding="utf-8")

        print(f"  ✓ 版号已同步至所有位置: {full} (数字: {numeric}, tag: {self.tag})")

    def clean(self) -> None:
        print("🧹 清理历史构建...")
        _terminate_processes(["FluentYTDL.exe", "yt-dlp.exe", "ffmpeg.exe", "deno.exe"])
        time.sleep(0.5)
        for d in [DIST_DIR, ROOT / "build"]:
            if d.exists() and _safe_rmtree(d):
                print(f"  ✓ 已删除: {d.name}")

    def ensure_tools(self) -> None:
        """确保 assets/bin 下的外部工具就位，并校验 TOOLS.lock.json。

        这里无条件调用 fetch_tools —— 它自己判断该下载还是只校验。
        以前只在文件缺失时才调用，等于工具一旦存在就永远不校验哈希，
        而"工具已存在但被替换过"正是锁文件要挡的场景。

        --strict-tools 会把"上游版本与锁文件不一致"也升级为硬失败，
        用于需要完全可复现的正式发布构建。
        """
        fetch_script = ROOT / "scripts" / "fetch_tools.py"
        if not fetch_script.exists():
            raise FileNotFoundError(f"工具下载脚本不存在: {fetch_script}")

        cmd = [sys.executable, str(fetch_script)]
        if self.strict_tools:
            cmd.append("--strict")

        print("\n🔧 校验外部工具与 TOOLS.lock.json...")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError(
                "外部工具校验失败（见上方输出）。\n"
                "  确认上游升级无误后运行: python scripts/fetch_tools.py --update-lock"
            )

    def build_spec(self) -> Path:
        """根据 FluentYTDL.spec 核心蓝图进行构建。

        这里刻意不调用 ensure_tools()：assets/bin 下的外部工具是 bundle_tools()
        的输入，.spec 蓝图并不引用它们。分开之后 CI 可以只跑 --target spec 验证
        PyInstaller 配置，不必先下载上百 MB 的 ffmpeg。
        """
        self._sync_version_to_all()
        self.clean()
        self._check_hygiene()

        # 编译翻译文件
        print("🌐 正在编译多语言翻译文件...")
        i18n_script = ROOT / "scripts" / "i18n_release.py"
        if i18n_script.exists():
            subprocess.run([sys.executable, str(i18n_script)], check=True)
        else:
            print("  ⚠️ 未找到翻译构建脚本，跳过...")

        version_file = ROOT / "build" / "version_info.txt"
        generate_version_info(self.version, version_file)

        spec_file = ROOT / "scripts" / "FluentYTDL.spec"
        if not spec_file.exists():
            raise FileNotFoundError(f"缺少打包蓝图: {spec_file}")

        # 将 TOML 配置投射到系统环境变量中以通信给 .spec 文件
        env = os.environ.copy()
        env["FLUENTYTDL_VERSION_FILE"] = str(version_file)
        env["FLUENTYTDL_QT_EXCLUDES"] = ",".join(self.config.get("qt_excludes", []))

        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--workpath",
            str(ROOT / "build"),
            "--distpath",
            str(ROOT / "dist"),
            str(spec_file),
        ]

        print(f"🔨 使用 PyInstaller 编译 (版本: {self.version})...")
        subprocess.run(cmd, env=env, check=True, cwd=ROOT)

        output = DIST_DIR / "FluentYTDL"
        if not output.exists():
            raise ChildProcessError("构建异常：未生成对应文件夹。")

        # 清理 PyInstaller 未能通过 excludes 彻底拦截的 Qt 残留
        self.strip_qt_bloat(output)

        print(f"✓ .spec 构建落地: {output}")
        return output

    def strip_qt_bloat(self, target_dir: Path) -> None:
        """清理 _internal/PySide6 中确定不需要的文件。

        PyInstaller 的 excludes 只能阻止 Python 模块（.pyd）被收集，
        但无法阻止对应的 C++ DLL 和资源文件被拖入。
        此函数在构建后物理删除这些残留。
        """
        pyside_dir = target_dir / "_internal" / "PySide6"
        if not pyside_dir.exists():
            print("  ⚠️ 未找到 PySide6 目录，跳过清理")
            return

        saved = 0

        # ── 1. WebEngine 相关（最大头，约 390 MB） ──
        webengine_patterns = [
            "Qt6WebEngine*.dll",
            "qtwebengine_*.pak",
            "QtWebEngine*.pyd",
            "QtWebChannel.pyd",
            "v8_context_snapshot*.bin",
            "icudtl.dat",  # ICU 数据（WebEngine 专用）
            "vk_swiftshader*.dll",  # Vulkan 软件渲染
            "libGLESv2.dll",
            "libEGL.dll",
        ]
        for pattern in webengine_patterns:
            for f in pyside_dir.glob(pattern):
                sz = f.stat().st_size
                f.unlink(missing_ok=True)
                saved += sz

        # ── 2. QML / Quick（约 32 MB） ──
        qml_dir = pyside_dir / "qml"
        if qml_dir.exists():
            sz = sum(f.stat().st_size for f in qml_dir.rglob("*") if f.is_file())
            shutil.rmtree(qml_dir, ignore_errors=True)
            saved += sz

        quick_patterns = [
            "Qt6Quick*.dll",
            "Qt6Qml*.dll",
            "QtQuick*.pyd",
            "QtQml*.pyd",
            "qtquickcontrols2*.dll",
        ]
        for pattern in quick_patterns:
            for f in pyside_dir.glob(pattern):
                sz = f.stat().st_size
                f.unlink(missing_ok=True)
                saved += sz

        # ── 3. 3D 模块（约 7 MB） ──
        for f in pyside_dir.glob("Qt63D*.dll"):
            sz = f.stat().st_size
            f.unlink(missing_ok=True)
            saved += sz

        # ── 4. 软件 OpenGL 渲染器（20 MB） ──
        sw_gl = pyside_dir / "opengl32sw.dll"
        if sw_gl.exists():
            saved += sw_gl.stat().st_size
            sw_gl.unlink()

        # ── 5. Qt 内置 FFmpeg（已有外部 ffmpeg，约 16 MB） ──
        for pattern in [
            "avcodec-*.dll",
            "avformat-*.dll",
            "avutil-*.dll",
            "swresample-*.dll",
            "swscale-*.dll",
        ]:
            for f in pyside_dir.glob(pattern):
                sz = f.stat().st_size
                f.unlink(missing_ok=True)
                saved += sz

        # ── 6. PDF / Charts / Graphs / ShaderTools 等 DLL ──
        misc_patterns = [
            "Qt6Pdf*.dll",
            "Qt6Charts*.dll",
            "Qt6DataVisualization*.dll",
            "Qt6Graphs*.dll",
            "Qt6ShaderTools.dll",
            "Qt6Bluetooth*.dll",
            "Qt6Nfc*.dll",
            "Qt6SerialPort*.dll",
            "Qt6Sensors*.dll",
            "Qt6Positioning*.dll",
            "Qt6Location*.dll",
            "Qt6RemoteObjects*.dll",
            "Qt6Designer*.dll",
            "Qt6Help*.dll",
            "Qt6Test*.dll",
            "Qt6Sql*.dll",
            "QtOpenGL.pyd",
            "Qt6OpenGL.dll",
        ]
        for pattern in misc_patterns:
            for f in pyside_dir.glob(pattern):
                sz = f.stat().st_size
                f.unlink(missing_ok=True)
                saved += sz

        # ── 7. 翻译文件：只保留中文和英文 ──
        tr_dir = pyside_dir / "translations"
        if tr_dir.exists():
            keep_prefixes = ("qtbase_zh", "qt_zh", "qtbase_en", "qt_en")
            for f in tr_dir.iterdir():
                if f.is_file() and f.suffix == ".qm":
                    if not any(f.name.startswith(p) for p in keep_prefixes):
                        saved += f.stat().st_size
                        f.unlink()

        # ── 8. resources 目录中的 WebEngine 资源 ──
        res_dir = pyside_dir / "resources"
        if res_dir.exists():
            for f in res_dir.iterdir():
                if f.is_file() and ("webengine" in f.name.lower() or "devtools" in f.name.lower()):
                    saved += f.stat().st_size
                    f.unlink()

        # ── 9. plugins 中不需要的插件 ──
        plugins_dir = pyside_dir / "plugins"
        if plugins_dir.exists():
            unwanted_plugins = [
                "multimedia",
                "qmltooling",
                "qmllint",
                "position",
                "sensors",
                "sqldrivers",
                "designer",
                "webview",
            ]
            for name in unwanted_plugins:
                plugin_subdir = plugins_dir / name
                if plugin_subdir.exists():
                    sz = sum(f.stat().st_size for f in plugin_subdir.rglob("*") if f.is_file())
                    shutil.rmtree(plugin_subdir, ignore_errors=True)
                    saved += sz

        saved_mb = saved / (1024 * 1024)
        print(f"🧹 Qt 瘦身完成：清理了 {saved_mb:.1f} MB 的无用文件")

    def bundle_tools(self, target_dir: Path) -> None:
        excluded_tool_dirs = {"dle_user", "dle_profile", "profile", "profiles", "cookies"}
        bin_dest = target_dir / "bin"
        if ASSETS_BIN.exists():

            def _ignore_tool_user_data(_src: str, names: list[str]) -> set[str]:
                return {name for name in names if name.lower() in excluded_tool_dirs}

            shutil.copytree(ASSETS_BIN, bin_dest, dirs_exist_ok=True, ignore=_ignore_tool_user_data)
            print("✓ 捆绑工具至 bin (已排除会话数据)")

        if LICENSES_DIR.exists():
            shutil.copytree(LICENSES_DIR, target_dir / "licenses", dirs_exist_ok=True)

        for doc in ["LICENSE", "README.md", "TRADEMARK.md", "ACADEMIC_HONESTY.md"]:
            src_doc = ROOT / doc
            if src_doc.exists():
                shutil.copy2(src_doc, target_dir / doc)
        print("✓ 捆绑核心说明与法律协议文档")

        self.write_build_info(target_dir)

    def write_build_info(self, target_dir: Path) -> Path:
        """在产物根目录写 BUILD_INFO.json。

        用户拿到的是一个 7z 包，包里此前没有任何东西能回答"这个包内置的
        yt-dlp / ffmpeg 是哪个版本、构建自哪个 commit"。排障时只能靠猜。
        这份清单让 issue 里贴一个文件就能对证。

        构建时间取 SOURCE_DATE_EPOCH（若已设置），使可复现构建能得到一致的输出。
        """
        info = {
            "app_version": self._full_version,
            "numeric_version": self.version,
            "channel": self.channel,
            "release_tag": self.tag,
            "arch": self.arch,
            "built_at_utc": _build_timestamp(),
            "git_commit": _git_commit(),
            "python_version": platform.python_version(),
            "pyinstaller_version": _dist_version("pyinstaller"),
            "pyside6_version": _dist_version("PySide6"),
            "bundled_tools": load_tool_versions(),
        }

        out = target_dir / "BUILD_INFO.json"
        out.write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"✓ 生成构建溯源清单: {out.name} (commit={info['git_commit']})")
        return out

    def create_7z(self, source_dir: Path, output_name: str) -> Path:
        RELEASE_DIR.mkdir(exist_ok=True)
        output_path = RELEASE_DIR / f"{output_name}.7z"
        if output_path.exists():
            output_path.unlink()

        sevenzip = shutil.which("7z") or shutil.which("7za")
        if sevenzip:
            subprocess.run(
                [sevenzip, "a", "-t7z", "-mx=9", "-mmt=on", str(output_path), "."],
                check=True,
                cwd=source_dir,
            )
        else:
            import importlib

            py7zr = importlib.import_module("py7zr")
            with py7zr.SevenZipFile(output_path, "w") as archive:
                archive.writeall(source_dir, arcname=".")

        print(f"📦 压缩包: {output_path.name}")
        return output_path

    def build_setup(self, source_dir: Path) -> Path:
        iss_file = INSTALLER_DIR / "FluentYTDL.iss"
        if not iss_file.exists():
            raise FileNotFoundError(
                f"Inno Setup 脚本不存在: {iss_file}\n"
                "  安装包目标需要该脚本；若只想产出便携包请改用 --target 7z"
            )

        iscc_paths = [
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
            / "Inno Setup 6/ISCC.exe",
            Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
            Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
        ]
        iscc = next((p for p in iscc_paths if p.exists()), None)
        if not iscc:
            raise FileNotFoundError(
                "未找到 Inno Setup 编译器 ISCC.exe，无法生成安装包。\n"
                "  已查找: " + "; ".join(str(p) for p in iscc_paths) + "\n"
                "  请安装 Inno Setup 6 (https://jrsoftware.org/isdl.php)，\n"
                "  或改用 --target 7z 只产出便携包。"
            )

        RELEASE_DIR.mkdir(exist_ok=True)
        out_name = f"FluentYTDL-{self._full_version}-{self.arch}-setup"
        cmd = [
            str(iscc),
            f"/DMyAppVersion={self.version}",
            f"/DSourceDir={source_dir}",
            f"/DOutputDir={RELEASE_DIR}",
            f"/DOutputBaseFilename={out_name}",
            str(iss_file),
        ]

        print("📦 正在编译安装向导程序...")
        subprocess.run(cmd, check=True)
        print(f"📦 安装包: {out_name}.exe")
        return RELEASE_DIR / f"{out_name}.exe"

    def run_all(self, target: str = "all") -> None:
        # "full" 是 "7z" 的别名
        effective_target = {"full": "7z"}.get(target, target)

        print(f"========== FluentYTDL Pipelined Build {self._full_version} ==========")

        # 1. 编译核心依赖
        app_dir = self.build_spec()

        # "spec" 只验证 PyInstaller 蓝图能否落地（CI 用），不产出发布物
        if effective_target == "spec":
            print(f"\n✅ .spec 验证通过: {app_dir}")
            return

        # 2. 拉取外部工具（bundle_tools 的输入）
        self.ensure_tools()

        # 3. 构建 updater.exe 并复制到应用目录
        self.build_updater(copy_to=app_dir)

        # 4. 注入二进制工具
        self.bundle_tools(app_dir)

        # 5. 产物分发
        print("\n========== Release 打包 ==========")
        results = []

        # 完整绿化包
        if effective_target in ("all", "7z"):
            full_archive = self.create_7z(
                app_dir, f"FluentYTDL-{self._full_version}-{self.arch}-full"
            )
            results.append(full_archive)

        # app-core 归档（仅主程序，用于增量更新）
        if effective_target in ("all", "7z"):
            app_core_archive = self.create_app_core_7z(app_dir)
            if app_core_archive.exists():
                results.append(app_core_archive)

        # Inno 安装包
        if effective_target in ("all", "setup"):
            setup_exe = self.build_setup(app_dir)
            if setup_exe and setup_exe.exists():
                results.append(setup_exe)

        # 生成更新清单
        self.generate_update_manifest()

        # 计算全局指纹
        self.generate_checksums()

        # 校验目标要求的产物是否真的落盘 —— 否则"构建成功"是假的
        self._assert_expected_artifacts(effective_target)

        print("\n✅ 流水线完成！")
        for res in results:
            size_mb = res.stat().st_size / 1024 / 1024
            print(f"   ► {res.name} ({size_mb:.1f} MB)")

    def _assert_expected_artifacts(self, effective_target: str) -> None:
        """断言目标对应的产物都已生成。

        历史上 build_setup() 在缺少 ISCC 时静默返回空路径，流水线照样打印
        "✅ 流水线完成"，导致零产物的构建被当成成功。
        """
        expected: list[Path] = []
        base = f"FluentYTDL-{self._full_version}-{self.arch}"

        if effective_target in ("all", "7z"):
            expected.append(RELEASE_DIR / f"{base}-full.7z")
            expected.append(RELEASE_DIR / f"{base}-app-core.7z")
        if effective_target in ("all", "setup"):
            expected.append(RELEASE_DIR / f"{base}-setup.exe")

        missing = [p for p in expected if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "构建目标 '"
                + effective_target
                + "' 要求的产物缺失:\n"
                + "\n".join(f"  ✗ {p.name}" for p in missing)
            )

    def generate_checksums(self):
        checksums = []
        for file in sorted(RELEASE_DIR.iterdir()):
            if file.is_file() and file.suffix in {".exe", ".7z", ".zip"}:
                hash_value = sha256_file(file)
                checksums.append(f"{hash_value}  {file.name}")

        checksum_file = RELEASE_DIR / "SHA256SUMS.txt"
        checksum_file.write_text("\n".join(checksums) + "\n", encoding="utf-8")

    def build_updater(self, copy_to: Path | None = None) -> Path:
        """构建 updater.exe（独立更新器）。"""
        spec_file = ROOT / "scripts" / "updater.spec"
        if not spec_file.exists():
            raise FileNotFoundError(
                f"updater.spec 不存在: {spec_file}\n"
                "updater.exe 是自动更新功能的必要组件，请确保 scripts/updater.spec 已提交到仓库。"
            )

        print("🔨 构建 updater.exe ...")
        cmd = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--workpath",
            str(ROOT / "build" / "updater"),
            "--distpath",
            str(ROOT / "dist"),
            str(spec_file),
        ]
        subprocess.run(cmd, check=True, cwd=ROOT)

        updater_exe = ROOT / "dist" / "updater.exe"
        if not updater_exe.exists():
            raise ChildProcessError(
                "updater.exe 构建失败：PyInstaller 运行完成但未生成 updater.exe，请检查构建日志。"
            )

        # 复制到目标目录
        if copy_to:
            dest = copy_to / "updater.exe"
            shutil.copy2(updater_exe, dest)
            print(f"✓ updater.exe 已复制到 {dest}")

        print(f"✓ updater.exe 构建完成: {updater_exe}")
        return updater_exe

    def create_app_core_7z(self, source_dir: Path) -> Path:
        """创建 app-core 归档（仅主程序，不含 bin/ 工具）。"""
        RELEASE_DIR.mkdir(exist_ok=True)
        output_name = f"FluentYTDL-{self._full_version}-{self.arch}-app-core"
        output_path = RELEASE_DIR / f"{output_name}.7z"
        if output_path.exists():
            output_path.unlink()

        # 创建临时目录，只包含 app-core 文件
        import tempfile

        with tempfile.TemporaryDirectory(prefix="fluentytdl_appcore_") as tmp_dir:
            tmp_path = Path(tmp_dir)

            # 复制主程序文件（排除 bin/ 和 updater.exe）
            # updater.exe 不包含在 app-core 归档中，因为 updater.exe 正在运行时
            # 无法被覆写（onefile 模式进程锁定 exe）。updater.exe 的更新通过
            # 延迟替换机制处理（见 main.py _cleanup_update_residuals）
            for item in source_dir.iterdir():
                if item.name == "bin":
                    continue  # 排除 bin/ 工具目录
                if item.name == "updater.exe":
                    continue  # 排除 updater.exe（运行时锁死）
                dest = tmp_path / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

            # 压缩
            sevenzip = shutil.which("7z") or shutil.which("7za")
            if sevenzip:
                subprocess.run(
                    [sevenzip, "a", "-t7z", "-mx=9", "-mmt=on", str(output_path), "."],
                    check=True,
                    cwd=tmp_path,
                )
            else:
                import importlib

                py7zr = importlib.import_module("py7zr")
                with py7zr.SevenZipFile(output_path, "w") as archive:
                    archive.writeall(tmp_path, arcname=".")

        print(f"📦 app-core 归档: {output_path.name}")
        return output_path

    def generate_update_manifest(self) -> Path:
        """生成更新清单 update-manifest.json。"""
        manifest_script = ROOT / "scripts" / "generate_manifest.py"
        if not manifest_script.exists():
            print("⚠ generate_manifest.py 不存在，跳过清单生成")
            return Path()

        print("📋 生成更新清单...")
        cmd = [
            sys.executable,
            str(manifest_script),
            "--version",
            self._full_version,
            # 下载 URL 用的是 Release 的 tag（v3.5.5），不是版本号（3.5.5）
            "--tag",
            self.tag,
            "--release-dir",
            str(RELEASE_DIR),
        ]
        subprocess.run(cmd, check=True, cwd=ROOT)

        manifest_path = RELEASE_DIR / "update-manifest.json"
        if manifest_path.exists():
            print(f"✓ 更新清单: {manifest_path.name}")
        return manifest_path


# ============================================================================
# Entry Point
# ============================================================================


def main():
    parser = argparse.ArgumentParser(description="FluentYTDL 构建中枢系统")
    parser.add_argument(
        "--target",
        "-t",
        choices=["all", "7z", "setup", "full", "spec"],
        default="all",
        help="构建目标 (默认: all; full=7z; spec=只验证 PyInstaller 蓝图，不产出发布物)",
    )
    parser.add_argument("--version", "-v", help="覆盖打包版本号")
    parser.add_argument("--skip-hygiene", action="store_true", help="强制无视黑名单环境污染告警")
    parser.add_argument(
        "--strict-tools",
        action="store_true",
        help="外部工具版本与 scripts/TOOLS.lock.json 不一致时直接失败（完全可复现构建）",
    )

    args = parser.parse_args()

    builder = Builder(
        override_version=args.version,
        skip_hygiene=args.skip_hygiene,
        strict_tools=args.strict_tools,
    )

    try:
        builder.run_all(target=args.target)
    except Exception as e:
        print(f"\n❌ 流水线崩溃: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
