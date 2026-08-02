<p align="center">
  <img src="assets/logo.png" alt="FluentYTDL logo" width="128" height="128">
</p>

<h1 align="center">FluentYTDL</h1>

<p align="center">
  A Windows desktop downloader for YouTube and X, built with PySide6, yt-dlp, and FFmpeg.
</p>

<p align="center">
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="#features">Features</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#development">Development</a> ·
  <a href="docs/ARCHITECTURE_EN.md">Architecture</a>
</p>

<p align="center">
  <a href="https://github.com/SakuraForgot/FluentYTDL/releases/latest"><img src="https://img.shields.io/github/v/release/SakuraForgot/FluentYTDL?style=flat-square&color=blue&label=release" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-blue.svg?style=flat-square" alt="GPL-3.0 license"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-green?style=flat-square&logo=python&logoColor=white" alt="Python 3.10 or newer">
  <img src="https://img.shields.io/badge/platform-Windows-blue?style=flat-square&logo=windows&logoColor=white" alt="Windows">
  <a href="https://github.com/SakuraForgot/FluentYTDL/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/SakuraForgot/FluentYTDL/ci.yml?branch=main&style=flat-square&label=CI" alt="CI status"></a>
</p>

FluentYTDL provides a native Fluent Design interface around a resilient media-download pipeline. It keeps yt-dlp in a subprocess boundary, coordinates FFmpeg post-processing, persists task state, and exposes format, audio-track, subtitle, cover, clipping, playlist, and VR workflows without requiring users to assemble command lines manually.

The application is developed primarily for 64-bit Windows 10 and Windows 11. YouTube has the broadest workflow coverage. X support currently targets individual post URLs; profile and timeline downloads are not advertised as supported.

## Interface preview

| Parse | Format selection | Task queue |
|:--:|:--:|:--:|
| <img src="docs/images/reference/1_quick_start/主程序界面-精确解析.png" alt="Parse page" width="460"> | <img src="docs/images/reference/1_quick_start/精确解析解析页.png" alt="Format selection dialog" width="330"> | <img src="docs/images/reference/1_quick_start/任务列表.png" alt="Task queue" width="460"> |

## Features

- **Video and audio selection** — choose resolution, container, codec, and preferred audio language, or use a simple quality preset.
- **Batch workflows** — parse YouTube playlists and channels, lazily load item metadata, and queue selected entries.
- **Resilient task handling** — configurable concurrency, persisted task state, per-task temporary directories, cancellation cleanup, and restart recovery.
- **Quality checks** — compare requested and available formats, surface quality downgrade warnings, and optionally verify output metadata with FFprobe.
- **Subtitles and covers** — download subtitles or thumbnails independently, merge bilingual subtitles, and embed supported metadata and artwork.
- **Clipping** — download a selected time range from an ordinary YouTube video, with fast and precise cut modes.
- **Post-processing** — FFmpeg-based muxing and conversion, SponsorBlock integration, thumbnail embedding, and optional VR projection conversion.
- **Authentication support** — local cookie lifecycle management and an isolated WebView2 login workflow for sites that require an authenticated session.
- **Component management** — checksum-verified updates for the application and external media tools.

## Supported scope

| Area | Current support |
|---|---|
| Operating system | Windows 10/11, 64-bit |
| YouTube | Videos, Shorts, live/video URLs, playlists, channels, subtitles, covers, and VR workflows |
| X (Twitter) | Individual post URLs with downloadable media |
| Other yt-dlp sites | Not part of the supported product scope |
| Source runtime | Python 3.10 or newer |

FluentYTDL depends on upstream services and tools. A site change, expired media URL, account restriction, region restriction, or yt-dlp regression can temporarily affect extraction or downloads.

## Installation

### Prebuilt Windows packages

Download the latest installer or portable archive from [GitHub Releases](https://github.com/SakuraForgot/FluentYTDL/releases/latest):

- `*-setup.exe` — Windows installer
- `*-full.7z` — portable package with the full runtime bundle
- `*-app-core.7z` — application-only update package

Release assets include `SHA256SUMS.txt`. Verify checksums when distributing or archiving a package. Official FluentYTDL binaries are published through this repository; third-party builds are not maintained or endorsed by the project.

### Run from source

```powershell
git clone https://github.com/SakuraForgot/FluentYTDL.git
cd FluentYTDL

# Recommended: uv
uv sync --extra dev
uv run python main.py
```

Alternatively, use a Python virtual environment and install the project with `pip install -e ".[dev]"`, then run `python main.py`.

The application manages several external components, including yt-dlp, FFmpeg, Deno, and AtomicParsley. Source checkouts may download missing components when the relevant feature is first used.

## Development

The repository uses a `src/` package layout. The UI is built with PySide6 and PySide6-Fluent-Widgets; backend work is separated into authentication, download, processing, storage, and YouTube service layers. yt-dlp is invoked as a CLI subprocess rather than imported as the download engine.

```powershell
uv sync --extra dev
uv run ruff check src tests

$env:QT_QPA_PLATFORM = "offscreen"
uv run pytest tests -q

uv run python scripts/version_manager.py check
```

Read these documents before making a substantial change:

- [Contributing guide](CONTRIBUTING.md)
- [Architecture](docs/ARCHITECTURE_EN.md)
- [Development rules](docs/RULES_EN.md)
- [yt-dlp integration notes](docs/YTDLP_KNOWLEDGE_EN.md)
- [Security policy](SECURITY.md)

## Security and responsible use

Cookies, logs, downloaded media, and local configuration can contain sensitive information. Do not attach unredacted credentials, cookies, tokens, or private URLs to issues. Report vulnerabilities through the private process described in [SECURITY.md](SECURITY.md).

Use FluentYTDL only for content you are authorized to access and download. Users are responsible for following applicable law, copyright rules, and platform terms. The project does not grant access to private or restricted content.

## Contributing and governance

Bug reports, focused pull requests, documentation improvements, and reproducible platform feedback are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md), and [MAINTAINERS.md](MAINTAINERS.md).

The source code is licensed under the [GNU General Public License v3.0](LICENSE). The separate [trademark policy](TRADEMARK.md) governs use of the FluentYTDL name and branding without reducing the permissions granted by GPL-3.0. The [academic integrity notice](ACADEMIC_HONESTY.md) explains attribution expectations and does not add license restrictions.

## Acknowledgements

FluentYTDL builds on open-source projects including [yt-dlp](https://github.com/yt-dlp/yt-dlp), [FFmpeg](https://ffmpeg.org/), [PySide6](https://doc.qt.io/qtforpython-6/), [PySide6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets), [SponsorBlock](https://sponsor.ajay.app/), and [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider). Third-party notices are collected in [`licenses/`](licenses/).
