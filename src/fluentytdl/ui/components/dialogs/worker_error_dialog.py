"""
后台任务错误挂起面板
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from qfluentwidgets import BodyLabel, MessageBoxBase, PushButton, StrongBodyLabel, TextEdit


class WorkerErrorDialog(MessageBoxBase):
    """
    后台任务错误面板，用于展示 `diagnose_error` 产生的结构化错误。
    提供【去设置页排查】和【重试所有挂起任务】功能。
    """

    # 信号
    retry_all_requested = Signal()
    go_settings_requested = Signal()
    fetch_cookie_requested = Signal()
    update_ytdlp_requested = Signal()

    def __init__(self, err_data: dict[str, Any], parent=None):
        super().__init__(parent)
        self.err_data = err_data
        self._setup_ui()

    def _setup_ui(self):
        self.widget.setMinimumWidth(500)

        # 标题
        title_text = self.err_data.get("user_title", self.tr("下载遇到错误"))
        self.title_label = StrongBodyLabel(f"❌ {title_text}", self)
        self.title_label.setStyleSheet("font-size: 16px;")
        self.viewLayout.addWidget(self.title_label)

        # 错误信息
        content_text = self.err_data.get("user_message", self.tr("未知错误"))
        self.content_label = BodyLabel(content_text, self)
        self.content_label.setWordWrap(True)
        self.viewLayout.addWidget(self.content_label)

        # 修复建议
        suggestion_text = self.err_data.get("suggestion", "")
        if suggestion_text:
            self.suggestion_label = BodyLabel(self.tr("💡 修复建议：\n") + suggestion_text, self)
            self.suggestion_label.setWordWrap(True)
            self.viewLayout.addWidget(self.suggestion_label)

        # 错误详情
        tech_detail = self.err_data.get("technical_detail", "")
        if tech_detail:
            self.tech_edit = TextEdit(self)
            self.tech_edit.setReadOnly(True)
            self.tech_edit.setPlainText(tech_detail)
            self.tech_edit.setMaximumHeight(100)
            self.viewLayout.addWidget(self.tech_edit)

        self.viewLayout.setSpacing(16)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)

        # 配置按钮
        self.yesButton.setText(self.tr("重试所有挂起任务"))
        self.cancelButton.setText(self.tr("稍后处理 (关闭)"))

        # 添加一个去设置的自定义按钮
        self.settings_btn = PushButton(self.tr("去设置页排查"), self)
        self.buttonLayout.insertWidget(0, self.settings_btn)

        # 快捷修复：获取新的cookie
        self.fetch_cookie_btn = PushButton(self.tr("快速获取新的cookie"), self)
        self.buttonLayout.insertWidget(1, self.fetch_cookie_btn)

        # 快捷修复：更新yt-dlp
        self.update_ytdlp_btn = PushButton(self.tr("更新 yt-dlp 并重试"), self)
        self.buttonLayout.insertWidget(2, self.update_ytdlp_btn)

        self.settings_btn.clicked.connect(self._on_settings_clicked)
        self.fetch_cookie_btn.clicked.connect(self._on_fetch_cookie_clicked)
        self.update_ytdlp_btn.clicked.connect(self._on_update_ytdlp_clicked)

        # 覆盖 yesButton 事件
        self.yesButton.clicked.disconnect()
        self.yesButton.clicked.connect(self._on_yes_clicked)

    def _on_yes_clicked(self):
        self.retry_all_requested.emit()
        self.accept()

    def _on_settings_clicked(self):
        self.go_settings_requested.emit()
        self.reject()

    def _on_fetch_cookie_clicked(self):
        self.fetch_cookie_requested.emit()
        self.reject()

    def _on_update_ytdlp_clicked(self):
        self.update_ytdlp_requested.emit()
        self.accept()
