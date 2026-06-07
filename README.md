<p align="center">
  <img src="assets/logo.png" alt="FluentYTDL Logo" width="128" height="128">
</p>

<h1 align="center">FluentYTDL</h1>

<p align="center">
  <strong>深度对抗 YouTube 风控机制的专业级视频下载器<br/>以工程级容错与 Fluent Design 美学，交付无人值守的极致下载体验</strong>
</p>

<p align="center">
  <a href="#-核心设计与创新">核心创新</a> •
  <a href="#-功能全景图">功能全景</a> •
  <a href="#-设计亮点与-uiux">设计亮点</a> •
  <a href="#-技术栈地图">技术栈</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-目录结构">目录结构</a> •
  <a href="docs/FAQ.md">FAQ</a> •
  <a href="#-致谢">致谢</a>
</p>

<p align="center">
  <a href="https://github.com/SakuraForgot/FluentYTDL/releases/latest">
    <img src="https://img.shields.io/github/v/release/SakuraForgot/FluentYTDL?style=flat-square&color=blue&label=Release" alt="Release">
  </a>
  <a href="https://github.com/SakuraForgot/FluentYTDL/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-GPLv3-blue.svg?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/Python-3.10+-green?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/平台-Windows-blue?style=flat-square&logo=windows&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/code%20style-Ruff-orange?style=flat-square" alt="Code Style">
  <img src="https://img.shields.io/github/stars/SakuraForgot/FluentYTDL?style=flat-square&color=yellow" alt="Stars">
</p>

> [!WARNING]
> **🛑 重要声明**
> 1. [《品牌商标与防盗卖政策》](TRADEMARK.md)：**严禁**任何团队或个人在不更改软件名称和图标的情况下，对本软件进行二次分发或商业售卖。违者将被追究法律责任并全网下架。
> 2. [《反学术抄袭声明》](ACADEMIC_HONESTY.md)：除作者本人以外，**绝对禁止**将本仓库的全部或部分源码用于提交高校课程作业或毕业设计。本仓库已被各大查重系统收录，一经查实将向涉事高校发出实名举报。

---

## 📖 项目简介

YouTube 拥有互联网上最严格的反爬体系——签名 URL 动态过期、Bot Check 机器人检测、IP 风控限速、Chromium v130+ 的 DPAPI App-Bound Encryption Cookie 锁定……传统视频下载器在面对这些挑战时，往往只是给命令行套了一层薄壳：崩溃即失败，无法恢复；批量下载留下满屏碎片；VR 内容无法正常播放；多音轨视频随机选择配音。

**FluentYTDL** 从底层重新设计了整条下载管线。它不是简单的 GUI 包装器，而是一个拥有 **148 个 Python 源文件、约 5 万行代码**的完整工程系统——具备风控感知的质量守卫引擎、三层优先级的播放列表懒加载调度器、基于语言学分析的智能音轨打分系统、支持 VR 全景投影转码的后处理管道、以及能从 Chromium DPAPI 死锁中突围的 WebView2 沙盒鉴权系统。

**一句话定位：** 面向内容创作者、视频搬运工和数字仓鼠的生产力工具，在 YouTube 日益收紧的围墙花园中撕开一道可靠的裂缝。

---

## 💡 核心设计与创新

FluentYTDL 在底层做出了许多深入 YouTube 视频交付策略和风控机制的开创性设计：

### 1. 🛡️ Quality Guard — 下载质量风控引擎

网络波动和 YouTube 的反爬策略常导致批量下载意外中断或静默降级（请求 4K 却只拿到 720p）。FluentYTDL 的 **Quality Guard** 引擎在下载管线的首尾两端设置了双重关卡：

- **预检校验 (Preflight Check)** — 在 yt-dlp 执行前，扫描可用格式列表，与用户的目标分辨率进行预匹配。若最高可用分辨率无法满足目标，立即发出偏差警告并给出降级建议，而非盲目下载
- **后验校验 (Post-Verify)** — 下载完成后，从进度日志中提取实际分辨率，对比初始目标。支持可选的 FFprobe 精确验证（直接读取输出文件的视频流元数据）
- **连续异常熔断** — `QualityGuardManager` 全局跟踪连续质量降级的任务计数。当连续失败次数达到可配置阈值（默认 3 次）时，判定为遭遇 YouTube 风控，自动将所有排队任务 **"挂起 (Suspended)"** 至安全队列，并通过消息中心推送 `risk_control` 级别的严重通知。环境恢复后可一键复活

### 2. 🎯 六大解析模式 — 精确萃取与快速频道下载

摒弃传统下载器只能"全盘下载"的笨重逻辑，FluentYTDL 为不同场景设计了六种独立的解析-下载流程：

| 模式 | 用途 | 下载路径 | 沙箱 | Feature 管道 |
|------|------|----------|------|-------------|
| **🎬 Video** | 标准单视频下载 | 完整（Executor + Strategy） | ✅ | 全部 5 个 Feature |
| **🥽 VR** | VR/360° 视频，`android_vr` 客户端 | 完整 + VR 后处理 | ✅ | 全部 + VRFeature |
| **📺 Channel** | 频道标签页列表，视口感知懒加载 | 完整（逐条目） | ✅ | 全部 |
| **📋 Playlist** | 播放列表批量下载 | 完整（逐条目） | ✅ | 全部 |
| **📝 Subtitle** | 仅提取全语种字幕 | 轻量（无 Executor） | ❌ | 无 |
| **🖼️ Cover** | 仅提取封面图 | 直链 / 轻量 | ❌ | 无 |

- **频道/播放列表极速解析** — 首阶段使用 `extract_flat` + `lazy_playlist` 模式，跳过冗长的 Authcheck 步骤，瞬间枚举整个频道或数百条目的播放列表。详细元数据由 `PlaylistScheduler` 的三层优先队列按需深度提取
- **三层优先队列** — 前台队列（视口可见条目，最高优先）→ 执行队列（管道门控，限制 3 并发）→ 后台队列（400ms 定时爬取），视口条目始终抢占后台工作
- **独立物料萃取** — 针对创作者和搬运工，支持 **"仅提取封面图"** 或 **"仅提取全语种字幕"**，完全无需下载巨大的视频本体，走最精简的子进程路径
- **多任务与多线程分片加速** — 既支持多个视频并发下载（可配置最大并发数），也支持单视频内部多分片并行拉取 (Concurrent Fragments)，彻底榨干带宽潜力

### 3. 🔊 智能音轨打分与降级引擎

面对 MrBeast 等创作者的多语种视频（可能含数十条音轨），传统下载器只能靠码率高低随机选择。FluentYTDL 在 `format_scorer.py` 中实现了基于等差加权的音轨评分算法：

- **原生音轨 (+50,000 分)** — 标记为 `original` 或 `default` 的原汁原味音轨，无条件置顶
- **人工配音 (+10,000 分)** — 优质真人配音 (`dubbed`)，仅次于原声
- **AI 合成配音 (-50,000 分)** — 检测 `auto`、`translated`、`ai` 关键词的机器合成配音，施加极度惩罚，仅作走投无路时的兜底
- **BCP-47 语言别名扩展** — `zh-Hans` 自动匹配 `zh-CN`、`zh-SG` 等变体；`en` 覆盖 `en-US`、`en-GB`、`en-AU`、`en-CA`
- **容器亲和性补偿** — 当目标容器为 MP4 时，对 `m4a`/`aac` 音频流额外加 2000 分，避免选择需要转封装的 WebM/Opus 流
- **用户自定义优先序列** — 支持配置如 `["orig", "zh-Hans", "en"]` 的偏好列表，按等差间距 (10,000,000) 递减赋权

### 4. 🔐 突破死锁的鉴权系统

传统 Cookie 提取工具极易因浏览器进程锁定（尤其 Chromium v130+ 的 App-Bound Encryption）而失败。FluentYTDL 构建了完整的认证生命周期：

- **WebView2 沙盒登录** — 创造性地引入 `pywebview` + Edge WebView2 后端，在完全隔离的沙盒窗口中完成 YouTube 登录，绕过 DPAPI 文件锁，100% 可靠获取 Cookie
- **CookieSentinel 四阶段生命周期** — ① 启动时静默预提取（守护线程，2s 延迟）→ ② 下载时提供 Cookie 路径 → ③ 403 自动检测 Cookie 过期 → ④ 强制刷新（需 UAC 权限提升）
- **懒清理模式** — 核心设计原则：**在新 Cookie 提取成功前绝不删除旧 Cookie**。提取失败时进入回退模式，保留旧凭证继续工作
- **PO Token 动态引擎** — `POTManager` 管理 `bgutil-ytdlp-pot-provider` 子进程，通过 Deno 运行时生成 PO Token 突破 YouTube 极其严格的机器人检测。内置三级渐进恢复：清除缓存 (~100ms) → 清除完整性令牌 (~5s) → 完整重启 (~15s)
- **Windows Job Object 孤儿预防** — POT 提供者子进程绑定到具有 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` 的 Job Object，即使 FluentYTDL 崩溃，操作系统也会自动清理子进程，杜绝僵尸服务器

### 5. 🥽 VR/360° 内容的无缝转换

YouTube 在分发全景视频时常使用特殊的 **EAC (Equi-Angular Cubemap)** 投影格式，导致普通播放器画面扭曲。FluentYTDL 的 `VRFeature` 提供了完整的 VR 后处理管道：

- **投影格式自动探测** — 解析每个格式的 `__vr_projection` 和 `__vr_stereo_mode` 元数据
- **EAC → 等距柱状投影 (Equirectangular) 转码** — 使用 FFmpeg `v360=eac:e` 滤镜，支持 GPU 硬件加速（NVENC → QSV → AMF 优先级递降），CPU 回退使用 `libx264 -preset veryfast -crf 23`
- **Google Spatial Media 元数据注入** — 通过内置的 `spatialmedia` 工具包，向 MP4/MOV 容器注入标准的球面投影和立体声模式元数据（`top-bottom` / `left-right` / `none`），确保 Meta Quest、Pico 等 VR 头显直接获得完美沉浸式体验

---

## ✨ 功能全景图

### 🎬 极致画质与音频输出

- 自动拼合最高 **8K** 画质视频流与最佳音频流，输出 MP4 / MKV / WebM 等多种容器格式
- **智能容器决策** — 根据视频编码（H.264 优先 MP4，VP9/AV1 自动切换 MKV）、嵌入字幕数量、音轨数量，自动选择最优无损合并容器
- **非零退出双门验证** — yt-dlp 非零退出时，执行两道检查：文件 ≥ 10KB（过滤 Windows `.part-Frag` 删除失败）+ 文件 ≥ 预期大小的 50%（过滤截断下载），两门均通过则视为成功

### 📝 完善的后处理管道

- **5 阶 Feature 管道** — SponsorBlock → Metadata → Subtitle → Thumbnail → VR，采用模板方法模式，执行顺序固定不可更改
- **字幕处理** — 支持拉取多语言字幕/自动翻译字幕，双语合并，自动过滤字幕广告。嵌入时自动感知容器兼容性（WebM → 升级 MKV）
- **封面嵌入** — 三级降级策略：AtomicParsley（MP4/M4A 最可靠）→ FFmpeg（MKV/通用）→ mutagen（MP3/FLAC/OGG 音频），嵌入后自动清理外部封面文件
- **元数据注入** — 自动嵌入视频描述、作者、上传日期等高质量元数据

### 🚫 SponsorBlock 集成

- 利用 [SponsorBlock](https://sponsor.ajay.app/) 社区众包数据，自动 **移除** 或 **标记** 视频中的赞助片段、片头片尾、自我推广等内容
- 支持按类别（`sponsor`、`selfpromo`、`interaction` 等）精细配置

### 🏗️ 沙箱下载模式

- 每个下载任务在独立的 `.fluent_temp/task_{id}/` 临时目录中执行，成功后通过同文件系统的原子 `shutil.move()` 移入最终目录
- **取消/失败零残留** — 取消时先等待 1 秒（Windows 文件锁释放），然后 `rmtree` 带 5 次重试（0.5s 间隔）逐步清理，回退到逐文件删除
- 沙箱使用数据库主键 (`db_id`) 而非 UUID，确保崩溃恢复时写入同一沙箱

### 🔄 组件热更新

- **统一更新清单** — 通过 GitHub Release 的 `update-manifest.json` 统一管理 app-core 和 `bin/` 工具的版本检查
- **三版本通道** — `v-`（稳定版，GitHub Release Latest）/ `pre-`（预发布，包含所有 Release）/ `beta-`（测试版，锁定更新）
- **SHA256 完整性校验** — 下载时逐块计算哈希，完成后与清单中的预期值比对
- 支持代理和 GHProxy 镜像加速

### 🩺 三层错误诊断引擎

- **第 1 层 — JSON 级诊断** — 解析 yt-dlp 的结构化错误输出（如 `premium_only`）
- **第 2 层 — 16 条正则规则** — 覆盖 Bot Check、会员专属、年龄限制、私有视频、网络错误、SSL、DNS、HTTP 429/403、地理限制、首映未开始、FFmpeg 缺失、磁盘已满等场景，首匹配获胜
- **第 3 层 — 回退兜底** — 提取 `ERROR:` 行并截断至 97 字符
- **12 种 ErrorCode** — 每种错误码附带严重性等级（致命/可恢复/警告）、用户友好标题、修复动作建议（如 `extract_cookie`、`switch_proxy`）和恢复提示

### 🔁 崩溃恢复与任务持久化

- **SQLite WAL 模式** — 任务状态通过专用的 `TaskDBWriter` 异步写入线程持久化，主线程零 I/O 阻塞
- **启动时自动恢复** — 读取所有未完成任务，将 `running`/`downloading`/`parsing` 状态安全降级为 `paused`，防止重启时的并发下载风暴
- **两层状态设计** — 持久层（SQLite）负责跨会话恢复，临时层（Worker 对象）持有实时运行时状态，`effective_state` 属性作为权威状态解析器消除竞态条件

### 💎 微软 Fluent Design 界面

- 采用 **PySide6** (Qt6) + **QFluentWidgets** 构建现代美观的用户界面
- 支持 **明暗主题动态切换**（浅色 / 深色 / 跟随系统），绝不硬编码颜色
- 全部 UI 控件使用 QFluentWidgets 组件（`FluentWindow`、`InfoBar`、`MessageBox` 等），拒绝原生 Qt 控件

---

## 🎨 设计亮点与 UI/UX

### 四层分层架构

```
┌─────────────────────────────────────────────┐
│  UI 层 (ui/)                                 │
│  53+ 文件：主窗口、页面、组件、委托、模型       │
├──────────────┬──────────────────────────────-┤
│              ↓ 依赖                          │
│  服务层                                       │
│  auth/  youtube/  download/  processing/     │
│  storage/  notification/                     │
├──────────────┬──────────────────────────────-┤
│              ↓ 依赖                          │
│  核心基础设施 (core/)                          │
│  ConfigManager、Controller、DependencyMgr    │
├──────────────┬──────────────────────────────-┤
│              ↓ 依赖                          │
│  基础层 (utils/, models/)                     │
│  无内部依赖                                    │
└─────────────────────────────────────────────┘
```

**强制规则：** UI 绝不直接调用 yt-dlp → 通过 `youtube_service`；服务层绝不从 `ui/` 导入 → 仅通过 Qt Signal 通信；Models 自包含无循环依赖。

### Qt Signal/Slot 严格解耦

所有 UI-后端通信通过 Qt Signal/Slot 机制。`DownloadWorker` 发射 6 种信号（`unified_status`、`output_path_ready`、`completed`、`error`、`cancelled`、`QThread.finished`），`DownloadManager` 通过 `QueuedConnection` 桥接到 `TaskDBWriter`，实现"单写者桥接连接"防止 SQLite 争用。

### 高性能列表渲染

- **QPainter 委托渲染** — 三个列表（播放列表、下载列表、历史记录）全部使用 QPainter 直接绘制，而非每行分配 QWidget 实例，避免大列表的内存膨胀和卡顿
- **脏行去抖** — `PlaylistListModel` 使用 200ms 前缘去抖，50 行并发更新仅发射 3-5 次 `dataChanged` 信号，将连续脏行合并为最小范围
- **延迟解析指示器** — 仅当提取耗时 > 800ms 时才显示 "加载中" 状态，避免快速提取场景下的 "待处理 → 加载中 → 格式" 三闪问题

### 分块模型填充

播放列表条目以 30 个为一块添加到模型，每块之间通过 `QTimer.singleShot(0)` 让出事件循环，保持 UI 在数千条目加载时仍然流畅响应。

---

## 🛠 技术栈地图

### UI 框架

| 技术 | 版本要求 | 用途 |
|------|---------|------|
| [PySide6](https://doc.qt.io/qtforpython-6/) | ≥ 6.10, < 6.11 | Qt6 for Python 官方绑定 |
| [QFluentWidgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) | ≥ 1.10, < 1.11 | 微软 Fluent Design 组件库 (Qt6) |

### 下载与媒体处理

| 技术 | 用途 |
|------|------|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 视频解析与下载引擎（CLI 子进程模式，非 Python API） |
| [FFmpeg](https://ffmpeg.org/) | 转码、合并、封装、VR 投影转换、封面嵌入（MKV） |
| [AtomicParsley](https://github.com/wez/atomicparsley) | MP4/M4A 封面嵌入（最可靠方案） |
| [Deno](https://deno.com/) | PO Token 生成环境（安全的 JS 运行时） |

### 鉴权与 Cookie

| 技术 | 用途 |
|------|------|
| [rookiepy](https://github.com/thewh1teagle/rookiepy) | 跨浏览器 Cookie 提取（Chromium / Firefox / Edge） |
| [pywebview](https://pywebview.flowrl.com/) | WebView2 沙盒登录环境（绕过 DPAPI 文件锁） |

### 核心依赖

| 技术 | 用途 |
|------|------|
| [loguru](https://github.com/Delgan/loguru) | 结构化日志框架 |
| [Pillow](https://github.com/python-pillow/Pillow) | 封面图像处理与缩放 |
| [requests](https://github.com/psf/requests) | HTTP 通信（更新检查、缩略图下载） |
| [psutil](https://github.com/giampaolo/psutil) | 系统进程监控、硬件检测、内存预警 |
| [markdown](https://github.com/Python-Markdown/markdown) | 更新日志渲染 |
| [Google Spatial Media](https://github.com/google/spatial-media) | VR 球面投影元数据注入工具包 |

### 存储与持久化

| 技术 | 用途 |
|------|------|
| SQLite (WAL 模式) | 任务生命周期持久化、崩溃恢复 |
| JSON | 用户配置存储 (`config.json`) |

### 构建与工具链

| 技术 | 用途 |
|------|------|
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | Python 应用打包为 Windows 可执行文件 |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Windows 安装程序生成 |
| [Ruff](https://github.com/astral-sh/ruff) | 代码检查与格式化 |
| [Pyright](https://github.com/microsoft/pyright) | 静态类型检查（咨询模式） |

---

## 🚀 快速开始

### 系统要求

| 项目 | 要求 |
|------|------|
| **操作系统** | Windows 10/11 (64-bit) |
| **Python** | 3.10 或更高版本（仅源码运行需要） |
| **内存** | 4GB RAM 或更多 |
| **存储** | 500MB 可用空间 |

### 方式一：下载安装包（推荐）

1. 前往 [Releases](https://github.com/SakuraForgot/FluentYTDL/releases) 页面
2. 下载最新版本的 `*-setup.exe` 安装程序或 `*-full.7z` 便携包
3. 运行安装程序按提示完成安装，或解压便携包到任意位置
4. 启动 FluentYTDL，开始使用！

> **⚠️ 注意：** 请务必从本仓库的 [Releases](https://github.com/SakuraForgot/FluentYTDL/releases) 页面获取，这是唯一合法的分发渠道。任何第三方下载站均非授权来源。

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/SakuraForgot/FluentYTDL.git
cd FluentYTDL

# 安装依赖
pip install -e .

# 运行应用
python main.py
```

> **💡 提示：** FFmpeg 和 Deno 运行时会在首次启动时**自动下载**，无需手动安装。如果自动下载失败，请手动将对应文件放入 `bin/` 目录。

---

## 📁 目录结构

```
FluentYTDL/
├── main.py                     # 应用入口：QApplication 创建、主题/字体设置、POT 预热、主窗口启动
├── pyproject.toml              # 项目元数据、依赖声明、Ruff/Pyright 配置
├── VERSION                     # 版本单一真相源（格式: v-3.0.27 / pre-X.X.X / beta-X.X.X）
├── config.json                 # 用户配置（.gitignore，不提交）
│
├── src/fluentytdl/             # 核心包 (148 个 .py 文件)
│   ├── auth/                   # 🔐 Cookie 生命周期、CookieSentinel、WebView2 提供者
│   │   └── providers/          #    DLE 提供者（Chrome 扩展注入）、WebView2 提供者（pywebview）
│   ├── core/                   # ⚙️ ConfigManager (JSON+Signal)、Controller、DependencyManager、
│   │                           #    ComponentUpdateManager、HardwareManager、进程管理
│   ├── download/               # 📥 DownloadManager (队列+并发)、DownloadExecutor (子进程)、
│   │                           #    DownloadWorker (QThread)、Feature 管道 (5个)、QualityGuard、
│   │                           #    AsyncExtractManager、策略引擎 (SPEED/STABLE/HARSH)
│   ├── models/                 # 📦 DTO: YtMediaDTO (防腐层)、VideoTask (UI 领域模型)、ErrorCode
│   │   └── mappers/            #    原始 yt-dlp dict → 类型化 DTO 转换器
│   ├── notification/           # 🔔 消息中心 (风控通知、质量预警)
│   ├── processing/             # 🎛️ 音频处理、字幕合并、封面嵌入、SponsorBlock 集成
│   ├── storage/                # 💾 TaskDB (SQLite WAL)、TaskDBWriter (异步写入)、历史服务
│   ├── ui/                     # 🖥️ 53+ 文件的 UI 层
│   │   ├── components/         #    28 个可复用控件 (含 DownloadConfigWindow ~3600 行)
│   │   ├── delegates/          #    QPainter 列表项渲染器 (播放列表/下载/历史)
│   │   ├── dialogs/            #    模态对话框
│   │   ├── models/             #    Qt 列表模型 (PlaylistListModel，含脏行去抖)
│   │   ├── pages/              #    页面容器
│   │   └── settings/           #    设置子模块
│   ├── utils/                  # 🔧 路径、日志、error_parser (16规则)、format_scorer、验证器
│   │   └── spatialmedia/       #    Google 空间媒体工具包 (第三方, Apache 2.0)
│   ├── youtube/                # 🌐 YoutubeService (yt-dlp CLI 封装)、POTManager、节点诊断
│   └── yt_dlp_plugins_ext/     # 🔌 yt-dlp PO Token 提供者插件 (随应用捆绑)
│
├── assets/                     # Logo、图标等资源文件
├── bin/                        # 外置二进制工具 (yt-dlp、FFmpeg、Deno、AtomicParsley)
├── scripts/                    # 构建脚本、版本管理、规则同步
├── installer/                  # Inno Setup 安装程序脚本
├── tests/                      # pytest 测试
├── docs/                       # 架构文档、开发规则、yt-dlp 排障知识库
└── licenses/                   # 第三方许可证
```

---

## 🤝 贡献指南

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细的贡献流程。

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行代码检查
ruff check src/

# 运行测试
pytest
```

> **📏 代码风格：** 项目使用 [Ruff](https://github.com/astral-sh/ruff) 进行代码检查和格式化（`target-version = "py310"`, `line-length = 100`）。提交前请运行 `ruff check` 确保代码风格一致。

---

## 📄 许可证

本项目基于 [GNU General Public License v3.0 (GPLv3)](LICENSE) 开源。

这意味着你可以自由地学习、修改和分发本项目的代码，但任何基于本项目的衍生作品**必须同样以 GPLv3 协议开源**。详细的品牌使用限制请参阅 [TRADEMARK.md](TRADEMARK.md)。

---

## 🙏 致谢

FluentYTDL 的诞生离不开以下优秀的开源项目和服务：

| 项目 | 简介 |
|------|------|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 强大的视频下载引擎 |
| [PySide6](https://doc.qt.io/qtforpython-6/) | Qt6 for Python 官方绑定 |
| [QFluentWidgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) | 微软 Fluent Design UI 组件库 (Qt6) |
| [FFmpeg](https://ffmpeg.org/) | 全能多媒体处理工具 |
| [Deno](https://deno.com/) | 安全的 JavaScript/TypeScript 运行时 |
| [rookiepy](https://github.com/thewh1teagle/rookiepy) | 跨平台浏览器 Cookie 提取 |
| [pywebview](https://pywebview.flowrl.com/) | 轻量级跨平台 WebView 组件 |
| [SponsorBlock](https://sponsor.ajay.app/) | 社区驱动的视频广告跳过数据库 |
| [AtomicParsley](https://github.com/wez/atomicparsley) | MP4/M4A 元数据与封面嵌入工具 |
| [loguru](https://github.com/Delgan/loguru) | 优雅的 Python 日志框架 |
| [Pillow](https://github.com/python-pillow/Pillow) | Python 图像处理库 |
| [requests](https://github.com/psf/requests) | 简洁优雅的 HTTP 请求库 |
| [psutil](https://github.com/giampaolo/psutil) | 跨平台系统进程与资源监控 |
| [Spatial Media](https://github.com/google/spatial-media) | Google VR 空间媒体元数据工具 |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | Python 应用打包工具 |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | Windows 安装程序制作工具 |
| [Shields.io](https://shields.io/) | 开源项目徽章服务 |

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/SakuraForgot">SakuraForgot</a>
</p>
