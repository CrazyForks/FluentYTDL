#!/usr/bin/env python3
"""
FluentYTDL 更新清单生成器

在构建流程中调用，生成 update-manifest.json 供运行时更新检查使用。

用法:
    python scripts/generate_manifest.py --version v-3.0.18 --release-dir release/
    python scripts/generate_manifest.py --version v-3.0.18  # 默认 release/ 目录

输出:
    release/update-manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent


def sha256_file(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def parse_version_prefix(full_version: str) -> tuple[str, str]:
    """解析版本前缀和数字部分。
    "v-3.0.18" → ("v-", "3.0.18")
    "pre-3.0.18" → ("pre-", "3.0.18")
    "beta-0.0.5" → ("beta-", "0.0.5")
    """
    for pfx in ("v-", "pre-", "beta-"):
        if full_version.startswith(pfx):
            return pfx, full_version[len(pfx) :]
    return "v-", full_version


def detect_component_versions(release_dir: Path) -> dict[str, dict]:
    """检测 bin/ 工具版本。从 assets/bin/ 目录的 exe 文件中获取。"""
    bin_dir = ROOT / "assets" / "bin"
    components: dict[str, dict] = {}

    # 定义各工具的版本检测命令和 GitHub 仓库
    tool_defs = {
        "yt-dlp": {
            "exe": "yt-dlp/yt-dlp.exe",
            "cmd": ["--version"],
            "repo": "yt-dlp/yt-dlp",
        },
        "ffmpeg": {
            "exe": "ffmpeg/ffmpeg.exe",
            "cmd": ["-version"],
            "repo": "BtbN/FFmpeg-Builds",
        },
        "deno": {
            "exe": "deno/deno.exe",
            "cmd": ["--version"],
            "repo": "denoland/deno",
        },
        "pot-provider": {
            "exe": "pot-provider/bgutil-pot-provider.exe",
            "cmd": ["--version"],
            "repo": "jim60105/bgutil-ytdlp-pot-provider-rs",
        },
        "atomicparsley": {
            "exe": "atomicparsley/AtomicParsley.exe",
            "cmd": ["--version"],
            "repo": "wez/atomicparsley",
        },
    }

    import subprocess

    for key, defn in tool_defs.items():
        exe_path = bin_dir / defn["exe"]
        if not exe_path.exists():
            continue

        # 尝试获取本地版本
        version = None
        try:
            result = subprocess.run(
                [str(exe_path)] + defn["cmd"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = (result.stdout + result.stderr).strip()
            # 提取第一行中的版本号
            if output:
                first_line = output.split("\n")[0].strip()
                # 尝试匹配 x.y.z 或日期格式 (YYYY.MM.DD)
                import re

                match = re.search(r"(\d{4}\.\d{2}\.\d{2}|\d+\.\d+\.\d+)", first_line)
                if match:
                    version = match.group(1)
        except Exception:
            pass

        if version:
            components[key] = {
                "version": version,
                "repo": defn["repo"],
            }

    return components


def _read_changelog(full_version: str) -> str:
    """从 CHANGELOG.md 或 git tag 读取更新日志。

    优先从 docs/CHANGELOG.md 读取对应版本段落，
    回退到 git tag message。
    """
    import subprocess

    # 1. 尝试从 CHANGELOG.md 读取
    changelog_file = ROOT / "docs" / "CHANGELOG.md"
    if changelog_file.exists():
        try:
            content = changelog_file.read_text(encoding="utf-8")
            # 查找版本标题（## v-3.0.18 或 ## 3.0.18）
            import re
            numeric = re.sub(r"^[a-zA-Z\-]+", "", full_version)
            for pattern in [f"## {full_version}", f"## v{numeric}", f"## {numeric}"]:
                idx = content.find(pattern)
                if idx != -1:
                    # 截取到下一个 ## 或文件末尾
                    rest = content[idx + len(pattern):]
                    next_section = rest.find("\n## ")
                    if next_section != -1:
                        return rest[:next_section].strip()
                    return rest.strip()
        except Exception:
            pass

    # 2. 回退到 git tag message
    try:
        result = subprocess.run(
            ["git", "tag", "-l", "--format=%(contents:body)", full_version],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return ""


def generate_manifest(
    full_version: str,
    release_dir: Path,
    base_url: str,
) -> dict:
    """生成更新清单。"""
    prefix, numeric = parse_version_prefix(full_version)
    arch = "win64" if sys.maxsize > 2**32 else "win32"

    # 读取 changelog（RAW 直链无法获取 release body，需内嵌到清单中）
    changelog = _read_changelog(full_version)

    manifest: dict = {
        "manifest_version": 1,
        "app_version": full_version,
        "release_tag": full_version,
        "changelog": changelog,
        "components": {},
    }

    # app-core 组件
    app_core_name = f"FluentYTDL-{full_version}-{arch}-app-core.7z"
    app_core_path = release_dir / app_core_name
    if app_core_path.exists():
        manifest["components"]["app-core"] = {
            "version": numeric,
            "url": f"{base_url}/{app_core_name}",
            "sha256": sha256_file(app_core_path),
            "size": app_core_path.stat().st_size,
            # updater.exe 不包含在 app-core 归档中，因为 updater.exe 正在运行时无法被覆写
            # updater.exe 的更新通过延迟替换机制处理（见 main.py _cleanup_update_residuals）
            "files": [
                "FluentYTDL.exe",
                "_internal/",
                "VERSION",
                "docs/",
                "licenses/",
            ],
        }
        print(f"  app-core: {app_core_name} (SHA256 OK)")
    else:
        print(f"  ⚠ app-core 归档不存在: {app_core_name}")

    # bin/ 工具组件（从 assets/bin/ 检测版本）
    bin_versions = detect_component_versions(release_dir)
    for key, info in bin_versions.items():
        manifest["components"][f"bin/{key}"] = {
            "version": info["version"],
            "url": "",  # bin 工具由各工具的 GitHub API 提供下载 URL
            "sha256": "",
            "repo": info["repo"],
        }
        print(f"  bin/{key}: {info['version']}")

    return manifest


def main():
    parser = argparse.ArgumentParser(description="FluentYTDL 更新清单生成器")
    parser.add_argument(
        "--version",
        "-v",
        required=True,
        help="完整版本号 (如 v-3.0.18, pre-3.0.18)",
    )
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=ROOT / "release",
        help="发布资产目录 (默认: release/)",
    )
    parser.add_argument(
        "--base-url",
        default="https://github.com/SakuraForgot/FluentYTDL/releases/download/{version}",
        help="下载 URL 前缀模板，{version} 会被替换为版本号",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出文件路径 (默认: release-dir/update-manifest.json)",
    )

    args = parser.parse_args()

    base_url = args.base_url.format(version=args.version)
    output_path = args.output or (args.release_dir / "update-manifest.json")

    print(f"生成更新清单: {args.version}")
    print(f"  发布目录: {args.release_dir}")
    print(f"  下载基址: {base_url}")

    manifest = generate_manifest(args.version, args.release_dir, base_url)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\n✓ 清单已生成: {output_path}")
    print(f"  组件数量: {len(manifest['components'])}")


if __name__ == "__main__":
    main()
