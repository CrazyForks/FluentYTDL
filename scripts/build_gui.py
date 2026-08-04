#!/usr/bin/env python3
"""
FluentYTDL 打包工具 GUI

基于 PySide6 的图形化构建界面，是 ``scripts/build.py`` 的前端外壳 ——
所有实际构建逻辑都在 build.py 里，这里只负责拼命令行、跑子进程、渲染日志。

功能：
- 选择构建目标（全部 / 便携版 / 安装向导），并明示每个目标的实际产物清单
- 构建前环境自检（PyInstaller / 7z / ISCC / 外部工具）
- 实时流式日志与进度提示
- 可中断（杀整棵进程树，不留孤儿 PyInstaller/ISCC）
- 构建完成后列出 release/ 下的产物与体积

用法:
    python scripts/build_gui.py

--------------------------------------------------------------------------
关于 UI 框架的说明（CLAUDE.md §3 的显式豁免）
--------------------------------------------------------------------------
CLAUDE.md 要求所有 UI 必须使用 QFluentWidgets。本文件**刻意**使用原生 QtWidgets：

  这是一个开发者构建工具，不随产品分发，也不属于 src/fluentytdl 包。
  打包器反向依赖被打包程序的 UI 库会造成循环：QFluentWidgets 一旦损坏或
  版本冲突，连打包工具本身都起不来，无法构建出修复版本。

因此这里的原生 Qt + 硬编码深色配色是经评估后保留的选择，不是遗漏。
新增 UI 组件时请继续使用原生 QtWidgets，不要引入 qfluentwidgets。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# 确保可以导入项目模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QObject, QThread, Signal  # noqa: E402
from PySide6.QtGui import QFont, QIcon, QTextCursor  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ============================================================================
# 构建目标定义
#   文案必须与 build.py run_all() 的真实行为一致 —— 历史上这里只写了
#   "7z 包 + 安装向导"，漏掉了 app-core / update-manifest / SHA256SUMS，
#   导致用户以为产物缺失。
# ============================================================================

TARGETS = [
    {
        "value": "all",
        "label": "全部 (all) — 便携完整版 + 安装向导",
        "outputs": [
            "FluentYTDL-{v}-win64-full.7z（便携完整版，首要发布产物）",
            "FluentYTDL-{v}-win64-app-core.7z（增量更新包，供程序内自动更新）",
            "FluentYTDL-{v}-win64-setup.exe（Inno Setup 安装向导，需要 ISCC）",
            "update-manifest.json（更新清单）",
            "SHA256SUMS.txt（全部产物的校验和）",
        ],
        "needs_iscc": True,
    },
    {
        "value": "7z",
        "label": "便携版 (7z / full) — 仅免安装包",
        "outputs": [
            "FluentYTDL-{v}-win64-full.7z（便携完整版）",
            "FluentYTDL-{v}-win64-app-core.7z（增量更新包）",
            "update-manifest.json（更新清单）",
            "SHA256SUMS.txt（全部产物的校验和）",
        ],
        "needs_iscc": False,
    },
    {
        "value": "setup",
        "label": "安装向导 (setup) — 仅 Inno Setup 安装包",
        "outputs": [
            "FluentYTDL-{v}-win64-setup.exe（Inno Setup 安装向导）",
            "SHA256SUMS.txt（全部产物的校验和）",
        ],
        "needs_iscc": True,
    },
]

# VERSION 文件的格式约束，与 version_manager.parse_version 保持一致
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-(?:rc|beta)\.\d+)?$")

ISCC_CANDIDATES = [
    Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Inno Setup 6/ISCC.exe",
    Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
    Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
]


def read_version_file() -> str:
    """读 VERSION 文件（唯一 source of truth）。"""
    version_file = ROOT / "VERSION"
    if version_file.exists():
        return version_file.read_text(encoding="utf-8").strip()
    return ""


def find_iscc() -> Path | None:
    return next((p for p in ISCC_CANDIDATES if p.exists()), None)


# ============================================================================
# 工作线程
# ============================================================================


class BuildSignals(QObject):
    """构建信号"""

    output = Signal(str)
    finished = Signal(int)  # exit code
    progress = Signal(str)  # status message


class BuildWorker(QThread):
    """后台构建工作线程"""

    def __init__(self, command: list[str], cwd: Path | None = None):
        super().__init__()
        # signals 必须是实例属性。作为类属性时所有 worker 共享同一个信号对象，
        # 每次构建又 connect 一遍 → 第二次日志翻倍、第三次三倍。
        self.signals = BuildSignals()
        self.command = command
        self.cwd = cwd or ROOT
        self._process: subprocess.Popen | None = None

    def run(self):
        try:
            # PYTHONUNBUFFERED: 管道模式下 Python 默认块缓冲，不设这个日志会成块蹦出
            # PYTHONIOENCODING: 子进程里的 emoji / 中文在 GBK 控制台会炸
            env = {
                **os.environ,
                "PYTHONUNBUFFERED": "1",
                "PYTHONIOENCODING": "utf-8",
            }

            # CREATE_NO_WINDOW: 否则每个子进程闪一个黑控制台
            # CREATE_NEW_PROCESS_GROUP: 便于取消时按进程组处理
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

            self._process = subprocess.Popen(
                self.command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(self.cwd),
                bufsize=1,
                env=env,
                creationflags=creationflags,
                start_new_session=sys.platform != "win32",
            )

            if self._process.stdout:
                for line in iter(self._process.stdout.readline, ""):
                    if line:
                        self.signals.output.emit(line.rstrip())
                        # 检测进度关键词（更全面）
                        lower_line = line.lower()
                        progress_keywords = [
                            "构建",
                            "building",
                            "打包",
                            "packaging",
                            "编译",
                            "compiling",
                            "生成",
                            "generating",
                            "下载",
                            "downloading",
                            "提取",
                            "extracting",
                            "压缩",
                            "compressing",
                            "复制",
                            "copying",
                            "校验",
                        ]
                        if any(kw in lower_line for kw in progress_keywords):
                            self.signals.progress.emit(line.strip()[:50])

            self._process.wait()
            self.signals.finished.emit(self._process.returncode or 0)

        except Exception as e:
            self.signals.output.emit(f"❌ 错误: {e}")
            self.signals.finished.emit(1)

    def terminate_process(self):
        """杀掉整棵进程树。

        只 terminate() 父 Python 进程是不够的 —— PyInstaller / ISCC / 7z 是它的
        子进程，会继续跑并占住 dist/，让下一次构建的 rmtree 失败。
        """
        proc = self._process
        if not proc or proc.poll() is not None:
            return

        if sys.platform == "win32":
            # /T 连子孙进程一起杀，/F 强制
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=10,
                )
            except Exception:
                proc.terminate()
        else:
            import signal

            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                proc.terminate()

        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


# ============================================================================
# 环境自检
# ============================================================================


def check_environment(target: str) -> list[tuple[bool, str]]:
    """构建前环境自检。

    返回 [(是否致命, 描述)]。致命项会在启动构建前拦截 —— 以前全靠 build.py
    跑到一半才失败，用户得翻几百行日志才知道是缺了 ISCC。

    是否致命取决于构建目标：只做便携包时缺 ISCC 无所谓。
    """
    spec = next(t for t in TARGETS if t["value"] == target)
    results: list[tuple[bool, str]] = []

    # PyInstaller —— 任何目标都必须有
    try:
        import importlib.metadata

        ver = importlib.metadata.version("pyinstaller")
        results.append((False, f"✓ PyInstaller {ver}"))
    except Exception:
        results.append(
            (
                True,
                "❌ 未安装 PyInstaller —— 运行 `uv sync --extra dev` 或 `pip install pyinstaller`",
            )
        )

    # 压缩器：7z 命令行优先，py7zr 是纯 Python 回退
    sevenzip = shutil.which("7z") or shutil.which("7za")
    if sevenzip:
        results.append((False, f"✓ 7-Zip: {sevenzip}"))
    else:
        try:
            import importlib

            importlib.import_module("py7zr")
            results.append((False, "✓ py7zr（未找到 7z 命令行，将走纯 Python 回退，速度较慢）"))
        except ImportError:
            fatal = spec["value"] in ("all", "7z")
            results.append(
                (
                    fatal,
                    "❌ 既没有 7z 命令行也没有 py7zr —— 安装 7-Zip 或 `pip install py7zr`",
                )
            )

    # Inno Setup —— 只有含 setup 的目标才需要
    if spec["needs_iscc"]:
        iscc = find_iscc()
        if iscc:
            results.append((False, f"✓ Inno Setup: {iscc}"))
        else:
            results.append(
                (
                    True,
                    "❌ 未找到 ISCC.exe —— 安装 Inno Setup 6 (https://jrsoftware.org/isdl.php)，"
                    "或改选「便携版 (7z)」目标",
                )
            )
    else:
        results.append((False, "· 当前目标不需要 Inno Setup，跳过"))

    # 外部工具 —— setup 目标同样要打进安装包，所以一律检查
    tools_lock = ROOT / "scripts" / "TOOLS.lock.json"
    missing_tools = [
        name
        for name, rel in [
            ("yt-dlp", "yt-dlp/yt-dlp.exe"),
            ("ffmpeg", "ffmpeg/ffmpeg.exe"),
            ("deno", "deno/deno.exe"),
            ("AtomicParsley", "atomicparsley/AtomicParsley.exe"),
            ("POT Provider", "pot-provider/bgutil-pot-provider.exe"),
        ]
        if not (ROOT / "assets" / "bin" / rel).exists()
    ]
    if missing_tools:
        results.append(
            (
                False,
                f"⚠ assets/bin 缺少 {', '.join(missing_tools)} —— 构建时会自动下载"
                "（点「📥 下载工具」可提前拉取）",
            )
        )
    else:
        results.append((False, "✓ assets/bin 外部工具齐备"))

    if tools_lock.exists():
        results.append((False, "✓ scripts/TOOLS.lock.json 存在，构建时会校验工具哈希"))
    else:
        results.append((False, "⚠ 无 scripts/TOOLS.lock.json —— 首次构建会生成初始锁文件"))

    # 版本文件
    version = read_version_file()
    if version and VERSION_PATTERN.match(version):
        results.append((False, f"✓ VERSION = {version}"))
    elif version:
        results.append((True, f"❌ VERSION 文件内容不符合规范: '{version}'（期望 X.Y.Z[-rc.N]）"))
    else:
        results.append((True, "❌ VERSION 文件缺失或为空"))

    # 环境污染黑名单（与 build.py _check_hygiene 同源，这里只提示不拦截）
    try:
        import importlib.metadata

        installed = {d.metadata["Name"].lower() for d in importlib.metadata.distributions()}
        polluted = installed & {"torch", "pandas", "tensorflow", "scipy", "matplotlib"}
        if polluted:
            results.append(
                (
                    False,
                    f"⚠ 环境中存在重型依赖 {', '.join(sorted(polluted))} —— "
                    "会显著增大产物体积，build.py 会拦截（可勾选 --skip-hygiene 强行打包）",
                )
            )
        else:
            results.append((False, "✓ 未发现黑名单重型依赖"))
    except Exception:
        pass

    return results


# ============================================================================
# 主窗口
# ============================================================================


class BuildGUI(QMainWindow):
    """构建工具主窗口"""

    def __init__(self):
        super().__init__()
        self.worker: BuildWorker | None = None
        # 取消标志：worker 被杀掉后仍会发 finished(1)，不加这个的话
        # _on_finished 会把"已取消"覆写成"构建失败 (code: 1)"
        self._cancelled = False
        self._setup_ui()
        self._connect_signals()
        self._on_target_changed(0)

    def _setup_ui(self):
        self.setWindowTitle("FluentYTDL 打包工具")
        self.setMinimumSize(760, 620)

        # 尝试设置图标
        icon_path = ROOT / "assets" / "FluentYTDL_v2.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # 主布局
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # === 构建目标区域 ===
        target_group = QGroupBox("📦 构建目标")
        target_layout = QVBoxLayout(target_group)

        # 目标选择
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("发布产物:"))
        self.target_combo = QComboBox()
        self.target_combo.addItems([t["label"] for t in TARGETS])
        self.target_combo.setMinimumWidth(380)
        target_row.addWidget(self.target_combo)
        target_row.addStretch()
        target_layout.addLayout(target_row)

        # 该目标的实际产出清单 —— 直接对齐 build.py run_all() 的行为
        self.outputs_label = QLabel()
        self.outputs_label.setWordWrap(True)
        self.outputs_label.setStyleSheet(
            "color: #9cdcfe; background-color: #252526; border: 1px solid #3c3c3c;"
            " border-radius: 4px; padding: 8px;"
        )
        target_layout.addWidget(self.outputs_label)

        # 打包配置选项
        options_row = QHBoxLayout()
        self.skip_hygiene_cb = QCheckBox("跳过环境污染体检 (--skip-hygiene)")
        self.skip_hygiene_cb.setToolTip(
            "开启后，即使环境中安装了黑名单依赖（如 torch, pandas）也将强行打包"
        )
        options_row.addWidget(self.skip_hygiene_cb)

        self.strict_tools_cb = QCheckBox("锁定外部工具版本 (--strict-tools)")
        self.strict_tools_cb.setToolTip(
            "要求 assets/bin 下的工具版本与 scripts/TOOLS.lock.json 完全一致。\n"
            "上游发新版会导致构建失败，需先运行 fetch_tools.py --update-lock 确认升级。"
        )
        options_row.addWidget(self.strict_tools_cb)
        options_row.addStretch()
        target_layout.addLayout(options_row)

        # 版本号
        version_row = QHBoxLayout()
        version_row.addWidget(QLabel("版本号:"))
        self.version_edit = QLineEdit()
        current = read_version_file() or "未知"
        # 留空 = 不传 --version = build.py 不回写 VERSION 文件（见 P0-1 守卫）
        self.version_edit.setPlaceholderText(f"留空则使用 VERSION 文件 ({current})")
        self.version_edit.setToolTip(
            "裸版本号，不带 v 前缀。格式: X.Y.Z / X.Y.Z-rc.N / X.Y.Z-beta.N\n"
            "留空时不会改写 VERSION 文件；填了则会同步写入所有版本载体。"
        )
        self.version_edit.setMaximumWidth(240)
        version_row.addWidget(self.version_edit)
        version_row.addStretch()
        target_layout.addLayout(version_row)

        layout.addWidget(target_group)

        # === 快捷操作区域 ===
        actions_group = QGroupBox("🔧 快捷操作")
        actions_layout = QHBoxLayout(actions_group)

        self.btn_env_check = QPushButton("🩺 环境自检")
        self.btn_env_check.setToolTip("检查 PyInstaller / 7z / Inno Setup / 外部工具是否就绪")
        actions_layout.addWidget(self.btn_env_check)

        self.btn_fetch_tools = QPushButton("📥 下载工具")
        self.btn_fetch_tools.setToolTip("下载并校验 yt-dlp / ffmpeg / deno / AtomicParsley / POT")
        actions_layout.addWidget(self.btn_fetch_tools)

        self.btn_collect_licenses = QPushButton("📄 收集许可证")
        self.btn_collect_licenses.setToolTip("收集第三方许可证")
        actions_layout.addWidget(self.btn_collect_licenses)

        self.btn_gen_checksums = QPushButton("🔐 生成校验和")
        self.btn_gen_checksums.setToolTip("生成 SHA256SUMS.txt")
        actions_layout.addWidget(self.btn_gen_checksums)

        self.btn_open_release = QPushButton("📂 打开输出目录")
        self.btn_open_release.setToolTip("打开 release 文件夹")
        actions_layout.addWidget(self.btn_open_release)

        actions_layout.addStretch()
        layout.addWidget(actions_group)

        # === 日志区域 ===
        log_group = QGroupBox("📋 构建日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        # === 状态栏 ===
        status_layout = QHBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定进度
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(20)
        status_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #888;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.btn_build = QPushButton("🚀 开始构建")
        self.btn_build.setMinimumWidth(120)
        self.btn_build.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #888;
            }
        """)
        status_layout.addWidget(self.btn_build)

        self.btn_cancel = QPushButton("⏹ 取消")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #d83b01;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #ea4a1f;
            }
        """)
        status_layout.addWidget(self.btn_cancel)

        layout.addLayout(status_layout)

    def _connect_signals(self):
        self.btn_build.clicked.connect(self._start_build)
        self.btn_cancel.clicked.connect(self._cancel_build)
        self.btn_env_check.clicked.connect(lambda: self._run_env_check(interactive=True))
        self.btn_fetch_tools.clicked.connect(lambda: self._run_script("fetch_tools.py"))
        self.btn_collect_licenses.clicked.connect(lambda: self._run_script("collect_licenses.py"))
        self.btn_gen_checksums.clicked.connect(lambda: self._run_script("checksums.py"))
        self.btn_open_release.clicked.connect(self._open_release_dir)
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)

    def _on_target_changed(self, index: int):
        """切换目标时更新产物清单说明。"""
        spec = TARGETS[index]
        version = read_version_file() or "{version}"
        lines = "<br>".join(f"　• {o.format(v=version)}" for o in spec["outputs"])
        self.outputs_label.setText(f"<b>产出到 release/：</b><br>{lines}")

    def _log(self, text: str, color: str | None = None):
        """添加日志"""
        if color:
            text = f'<span style="color:{color}">{text}</span>'
        self.log_text.append(text)
        # 滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def _set_ui_running(self, running: bool):
        """设置 UI 运行状态"""
        self.btn_build.setEnabled(not running)
        self.btn_build.setVisible(not running)
        self.btn_cancel.setVisible(running)
        self.progress_bar.setVisible(running)
        self.target_combo.setEnabled(not running)
        self.skip_hygiene_cb.setEnabled(not running)
        self.strict_tools_cb.setEnabled(not running)
        self.version_edit.setEnabled(not running)
        self.btn_env_check.setEnabled(not running)
        self.btn_fetch_tools.setEnabled(not running)
        self.btn_collect_licenses.setEnabled(not running)
        self.btn_gen_checksums.setEnabled(not running)

    def _get_target(self) -> str:
        """获取选择的构建目标"""
        return TARGETS[self.target_combo.currentIndex()]["value"]

    def _run_env_check(self, interactive: bool = False) -> bool:
        """执行环境自检并把结果逐条写进日志。返回是否全部通过。"""
        target = self._get_target()
        if interactive:
            self.log_text.clear()
        self._log(f"🩺 环境自检（目标: {target}）", "#4ec9b0")

        results = check_environment(target)
        for fatal, message in results:
            if fatal:
                self._log(f"   {message}", "#f14c4c")
            elif message.startswith("⚠"):
                self._log(f"   {message}", "#cca700")
            elif message.startswith("·"):
                self._log(f"   {message}", "#808080")
            else:
                self._log(f"   {message}", "#6a9955")

        blockers = [m for fatal, m in results if fatal]
        if blockers:
            self._log(f"\n❌ 自检未通过：{len(blockers)} 项必须先解决", "#f14c4c")
            self.status_label.setText("❌ 环境自检未通过")
            self.status_label.setStyleSheet("color: #f14c4c;")
        else:
            self._log("\n✅ 环境自检通过", "#6a9955")
            if interactive:
                self.status_label.setText("✅ 环境自检通过")
                self.status_label.setStyleSheet("color: #6a9955;")
        self._log("")
        return not blockers

    def _validate_version(self, version: str) -> str | None:
        """校验版本框输入，返回错误信息（None 表示通过）。"""
        if version.startswith("v"):
            return (
                f"版本号不能带 v 前缀：'{version}'\n\n"
                f"v 只存在于 Git tag 里。请填 '{version.lstrip('v')}'。"
            )
        if not VERSION_PATTERN.match(version):
            return (
                f"版本号格式不合规：'{version}'\n\n"
                "期望 X.Y.Z / X.Y.Z-rc.N / X.Y.Z-beta.N\n"
                "例如: 3.5.6、3.5.6-rc.1、3.6.0-beta.2"
            )
        return None

    def _start_build(self):
        """开始构建"""
        target = self._get_target()
        version = self.version_edit.text().strip()
        skip_hygiene = self.skip_hygiene_cb.isChecked()
        strict_tools = self.strict_tools_cb.isChecked()

        # 版本格式先在这里拦，别把非法值丢给 build.py 再让用户翻日志
        if version:
            error = self._validate_version(version)
            if error:
                QMessageBox.warning(self, "版本号无效", error)
                self.version_edit.setFocus()
                self.version_edit.selectAll()
                return

        self.log_text.clear()

        # 构建前自检：缺 ISCC 之类的问题在启动前就拦下来
        if not self._run_env_check():
            QMessageBox.critical(
                self,
                "环境自检未通过",
                "构建所需的组件缺失，详见日志区。\n请先解决标红项再开始构建。",
            )
            self._set_ui_running(False)
            return

        self._log(f"🚀 开始执行编排流水线: 目标 {target}", "#4ec9b0")
        if version:
            self._log(f"   覆盖版本号: {version}（将写入 VERSION 及全部版本载体）", "#cca700")
        else:
            self._log(f"   使用 VERSION 文件: {read_version_file()}（不会改写）", "#808080")
        if skip_hygiene:
            self._log("   ! 警告: 已跳过无菌环境体检", "#cca700")
        if strict_tools:
            self._log("   外部工具锁定模式: 版本须与 TOOLS.lock.json 一致", "#808080")
        self._log("")

        cmd = [sys.executable, str(ROOT / "scripts" / "build.py"), "--target", target]
        if version:
            cmd.extend(["--version", version])
        if skip_hygiene:
            cmd.append("--skip-hygiene")
        if strict_tools:
            cmd.append("--strict-tools")

        self._is_build = True
        self._run_command(cmd)

    def _run_script(self, script_name: str):
        """运行指定脚本"""
        self.log_text.clear()
        self._log(f"🔧 运行: {script_name}", "#4ec9b0")
        self._log("")

        cmd = [sys.executable, str(ROOT / "scripts" / script_name)]
        self._is_build = False
        self._run_command(cmd)

    def _run_command(self, cmd: list[str]):
        """运行命令"""
        self._cancelled = False
        self._set_ui_running(True)
        self.status_label.setText("正在执行...")
        self.status_label.setStyleSheet("color: #888;")

        self.worker = BuildWorker(cmd)
        self.worker.signals.output.connect(self._on_output)
        self.worker.signals.progress.connect(self._on_progress)
        self.worker.signals.finished.connect(self._on_finished)
        self.worker.start()

    def _cancel_build(self):
        """取消构建"""
        if self.worker:
            self._cancelled = True
            self._log("\n⏹ 用户取消，正在结束进程树...", "#d7ba7d")
            self.worker.terminate_process()
            self.worker.quit()
            self.worker.wait(15000)

            # 重置UI状态
            self._set_ui_running(False)
            self.status_label.setText("已取消")
            self.status_label.setStyleSheet("color: #cca700;")

    def _on_output(self, text: str):
        """处理输出"""
        # 颜色化输出
        if text.startswith("✓") or text.startswith("✅"):
            self._log(text, "#6a9955")
        elif text.startswith("❌") or "错误" in text or "Error" in text:
            self._log(text, "#f14c4c")
        elif text.startswith("⚠") or "警告" in text or "Warning" in text:
            self._log(text, "#cca700")
        elif text.startswith("🔨") or text.startswith("📦"):
            self._log(text, "#4fc1ff")
        elif text.startswith("🔒") or text.startswith("🔄"):
            self._log(text, "#d7ba7d")
        elif text.startswith("==="):
            self._log(text, "#c586c0")
        else:
            self._log(text)

    def _on_progress(self, text: str):
        """处理进度"""
        self.status_label.setText(text[:40] + "..." if len(text) > 40 else text)

    def _list_artifacts(self):
        """构建成功后列出 release/ 下的实际产物与体积。"""
        release_dir = ROOT / "release"
        if not release_dir.exists():
            return
        files = sorted(
            (f for f in release_dir.iterdir() if f.is_file()),
            key=lambda f: f.stat().st_size,
            reverse=True,
        )
        if not files:
            return
        self._log("\n📂 release/ 产物：", "#4fc1ff")
        for f in files:
            self._log(f"   {f.name:<52} {f.stat().st_size / 1024 / 1024:>8.2f} MB", "#9cdcfe")

    def _on_finished(self, exit_code: int):
        """构建完成"""
        # worker 被 taskkill 之后仍会走到这里并带非零退出码。
        # 不判断 _cancelled 的话，"已取消" 会被覆写成 "构建失败 (code: 1)"。
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

        if self._cancelled:
            return

        self._set_ui_running(False)

        if exit_code == 0:
            self._log("\n🎉 执行成功!", "#6a9955")
            self.status_label.setText("✅ 执行成功")
            self.status_label.setStyleSheet("color: #6a9955;")
            if getattr(self, "_is_build", False):
                self._list_artifacts()
                # 成功后把「打开输出目录」高亮，引导下一步
                self.btn_open_release.setStyleSheet(
                    "QPushButton { background-color: #0078d4; color: white;"
                    " border: none; border-radius: 4px; padding: 6px 12px; font-weight: bold; }"
                    "QPushButton:hover { background-color: #1084d8; }"
                )
        else:
            self._log(f"\n❌ 执行失败 (exit code: {exit_code})", "#f14c4c")
            self.status_label.setText(f"❌ 执行失败 (code: {exit_code})")
            self.status_label.setStyleSheet("color: #f14c4c;")

    def _open_release_dir(self):
        """打开输出目录（跨平台）"""
        release_dir = ROOT / "release"
        release_dir.mkdir(exist_ok=True)

        try:
            if sys.platform == "win32":
                os.startfile(str(release_dir))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(release_dir)], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", str(release_dir)], check=False)
        except Exception as e:
            QMessageBox.warning(self, "无法打开目录", f"请手动打开: {release_dir}\n\n错误: {e}")


# ============================================================================
# 入口
# ============================================================================


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 深色主题
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #2d2d2d;
            color: #d4d4d4;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #3c3c3c;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 4px;
        }
        QComboBox, QLineEdit {
            background-color: #3c3c3c;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 6px;
            color: #d4d4d4;
        }
        QComboBox:hover, QLineEdit:focus {
            border-color: #0078d4;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QCheckBox {
            color: #d4d4d4;
        }
        QPushButton {
            background-color: #3c3c3c;
            border: 1px solid #555;
            border-radius: 4px;
            padding: 6px 12px;
            color: #d4d4d4;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
            border-color: #666;
        }
        QPushButton:pressed {
            background-color: #333;
        }
        QProgressBar {
            border: 1px solid #555;
            border-radius: 4px;
            background-color: #3c3c3c;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 3px;
        }
        QLabel {
            color: #d4d4d4;
        }
    """)

    window = BuildGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
