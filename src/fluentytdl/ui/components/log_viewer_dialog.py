"""
日志查看器对话框

实时显示应用日志，支持级别过滤和搜索
"""

from __future__ import annotations

import os
from collections import deque

from PySide6.QtCore import Slot
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPlainTextEdit,
    QSizePolicy,
    QWidget,
)
from qfluentwidgets import (
    ComboBox,
    FluentIcon,
    MessageBoxBase,
    SearchLineEdit,
    SubtitleLabel,
    ToolButton,
    ToolTipFilter,
    ToolTipPosition,
)

from ...utils.log_signal_handler import log_signal_handler
from ...utils.logger import LOG_DIR

# 日志级别颜色映射
LEVEL_COLORS = {
    "DEBUG": "#888888",
    "INFO": "#2196F3",
    "SUCCESS": "#4CAF50",
    "WARNING": "#FF9800",
    "ERROR": "#F44336",
    "CRITICAL": "#9C27B0",
}

# 日志级别排序（用于过滤）
LEVEL_ORDER = ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]


class LogViewerDialog(MessageBoxBase):
    """实时日志查看器对话框"""

    MAX_LINES = 1000  # 最大显示行数

    def __init__(self, parent=None):
        super().__init__(parent)

        self._log_buffer: deque[tuple[str, str, str, str]] = deque(maxlen=self.MAX_LINES)
        self._current_filter_level = self.tr("全部")
        self._current_search = ""
        self._auto_scroll = True

        self._setup_ui()
        self._connect_signals()
        self._start_log_capture()
        self._load_existing_logs()

    def _load_existing_logs(self):
        """加载今日已有的日志文件"""
        try:
            from datetime import date

            today = date.today().strftime("%Y-%m-%d")
            log_file = os.path.join(LOG_DIR, f"app_{today}.log")

            if os.path.exists(log_file):
                # 只加载最后 500 行避免过长
                with open(log_file, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                # 取最后 500 行
                recent_lines = lines[-500:] if len(lines) > 500 else lines

                for line in recent_lines:
                    line = line.strip()
                    if not line:
                        continue
                    # 尝试解析日志格式: HH:MM:SS | LEVEL | module:func:line - message
                    # 简化处理：直接显示原始行
                    self._log_buffer.append(("--:--:--", "INFO", "file", line))
                    if self._should_show("INFO", line):
                        self._append_log_line("--:--:--", "INFO", "file", line)
        except Exception:
            pass  # 加载失败不影响实时日志

    def _setup_ui(self):
        """构建 UI"""
        # 设置对话框大小
        self.widget.setMinimumWidth(900)
        self.widget.setMinimumHeight(600)

        # 标题
        self.titleLabel = SubtitleLabel(self.tr("📋 运行日志"), self.widget)
        self.viewLayout.addWidget(self.titleLabel)

        # 工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 8, 0, 8)

        # 级别过滤
        self.levelCombo = ComboBox()
        self.levelCombo.addItems([self.tr("全部"), "DEBUG", "INFO", "WARNING", "ERROR"])
        self.levelCombo.setCurrentText("INFO")
        self._current_filter_level = "INFO"
        toolbar_layout.addWidget(self.levelCombo)

        # 搜索框
        self.searchEdit = SearchLineEdit()
        self.searchEdit.setPlaceholderText(self.tr("搜索日志..."))
        self.searchEdit.setFixedWidth(200)
        toolbar_layout.addWidget(self.searchEdit)

        toolbar_layout.addStretch()

        # 清屏按钮
        self.clearBtn = ToolButton(FluentIcon.DELETE)
        self.clearBtn.setToolTip(self.tr("清屏"))
        self.clearBtn.installEventFilter(
            ToolTipFilter(self.clearBtn, showDelay=300, position=ToolTipPosition.BOTTOM)
        )
        toolbar_layout.addWidget(self.clearBtn)

        # 打开目录按钮
        self.openDirBtn = ToolButton(FluentIcon.FOLDER)
        self.openDirBtn.setToolTip(self.tr("打开日志目录"))
        self.openDirBtn.installEventFilter(
            ToolTipFilter(self.openDirBtn, showDelay=300, position=ToolTipPosition.BOTTOM)
        )
        toolbar_layout.addWidget(self.openDirBtn)

        self.viewLayout.addWidget(toolbar)

        # 日志显示区
        self.logView = QPlainTextEdit()
        self.logView.setReadOnly(True)
        log_font = QFont("Consolas")
        log_font.setPointSize(10)
        self.logView.setFont(log_font)
        self.logView.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.logView.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        self.logView.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.viewLayout.addWidget(self.logView)

        # 状态栏
        status_layout = QHBoxLayout()
        self.statusLabel = SubtitleLabel(f"日志目录: {LOG_DIR}")
        self.statusLabel.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self.statusLabel)
        status_layout.addStretch()

        self.lineCountLabel = SubtitleLabel(self.tr("0 行"))
        self.lineCountLabel.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self.lineCountLabel)

        status_widget = QWidget()
        status_widget.setLayout(status_layout)
        self.viewLayout.addWidget(status_widget)

        # 隐藏默认按钮
        self.yesButton.hide()
        self.cancelButton.setText(self.tr("关闭"))

    def _connect_signals(self):
        """连接信号"""
        self.levelCombo.currentTextChanged.connect(self._on_filter_changed)
        self.searchEdit.textChanged.connect(self._on_search_changed)
        self.clearBtn.clicked.connect(self._clear_log)
        self.openDirBtn.clicked.connect(self._open_log_dir)

        # 滚动检测（用户滚动时暂停自动滚动）
        self.logView.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _start_log_capture(self):
        """开始捕获日志"""
        log_signal_handler.install()
        log_signal_handler.log_received.connect(self._on_log_received)

    def _stop_log_capture(self):
        """停止捕获日志"""
        try:
            log_signal_handler.log_received.disconnect(self._on_log_received)
        except RuntimeError:
            pass

    @Slot(str, str, str, str)
    def _on_log_received(self, time: str, level: str, module: str, message: str):
        """接收日志"""
        self._log_buffer.append((time, level, module, message))

        # 检查是否需要显示
        if self._should_show(level, message):
            self._append_log_line(time, level, module, message)

    def _should_show(self, level: str, message: str) -> bool:
        """检查日志是否应该显示"""
        # 级别过滤
        if self._current_filter_level != self.tr("全部"):
            try:
                filter_idx = LEVEL_ORDER.index(self._current_filter_level)
                log_idx = LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 1
                if log_idx < filter_idx:
                    return False
            except ValueError:
                pass

        # 搜索过滤
        if self._current_search:
            if self._current_search.lower() not in message.lower():
                return False

        return True

    def _append_log_line(self, time: str, level: str, module: str, message: str):
        """追加一行日志"""
        color = LEVEL_COLORS.get(level, "#d4d4d4")

        # 格式化日志行
        module_short = module.split(".")[-1] if module else ""
        if module_short:
            line = f"[{time}] [{level:8}] [{module_short}] {message}"
        else:
            line = f"[{time}] [{level:8}] {message}"

        # 使用 HTML 着色
        cursor = self.logView.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(line + "\n", fmt)

        # 自动滚动
        if self._auto_scroll:
            self.logView.verticalScrollBar().setValue(self.logView.verticalScrollBar().maximum())

        # 更新行数
        self._update_line_count()

    def _update_line_count(self):
        """更新行数显示"""
        count = self.logView.document().lineCount()
        self.lineCountLabel.setText(f"{count} 行")

    @Slot(str)
    def _on_filter_changed(self, level: str):
        """级别过滤变化"""
        self._current_filter_level = level
        self._refresh_display()

    @Slot(str)
    def _on_search_changed(self, text: str):
        """搜索变化"""
        self._current_search = text
        self._refresh_display()

    def _refresh_display(self):
        """刷新显示（重新应用过滤）"""
        self.logView.clear()

        for time, level, module, message in self._log_buffer:
            if self._should_show(level, message):
                self._append_log_line(time, level, module, message)

    @Slot()
    def _clear_log(self):
        """清屏"""
        self._log_buffer.clear()
        self.logView.clear()
        self._update_line_count()

    @Slot()
    def _open_log_dir(self):
        """打开日志目录"""
        try:
            if os.name == "nt":
                os.startfile(LOG_DIR)
            else:
                import subprocess

                subprocess.run(["xdg-open", LOG_DIR])
        except Exception:
            pass

    @Slot(int)
    def _on_scroll(self, value: int):
        """滚动事件处理"""
        sb = self.logView.verticalScrollBar()
        # 如果用户滚动到接近底部，恢复自动滚动
        self._auto_scroll = (sb.maximum() - value) < 50

    def closeEvent(self, event):
        """关闭事件"""
        self._stop_log_capture()
        super().closeEvent(event)

    def reject(self):
        """取消/关闭"""
        self._stop_log_capture()
        super().reject()
