"""
PlaylistItemCard (Redesigned Fluent version)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout
from qfluentwidgets import CaptionLabel, CheckBox, StrongBodyLabel

from ...models.video_task import VideoTask


class PlaylistItemCard(QFrame):
    """
    独立的可滚动卡片，严格遵循 Fluent Design 规范。
    完全重写绘制逻辑，脱离 qfluentwidgets 内置容器的主题判定缺陷，
    保证在暗色模式下完美显示真正的深色，而不是亮白色。
    """

    clicked = Signal(int)

    def __init__(self, task: VideoTask, row_index: int, parent=None):
        super().__init__(parent)

        self.task = task
        self.row_index = row_index

        self.setMinimumHeight(84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 启用自动绘制背景
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(16, 12, 16, 12)
        self.h_layout.setSpacing(16)

        # 1. 选择框
        self.checkbox = CheckBox(self)
        self.checkbox.setChecked(self.task.selected)
        self.checkbox.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.h_layout.addWidget(self.checkbox)

        # 2. 缩略图
        self.thumb = QLabel(self)
        self.thumb.setFixedSize(112, 63)  # 16:9 标准比例
        self.thumb.setScaledContents(True)
        # 用样式表实现完美圆角
        self.thumb.setStyleSheet(
            "QLabel { border-radius: 6px; background-color: rgba(0, 0, 0, 0.1); }"
        )
        self.h_layout.addWidget(self.thumb)

        # 3. 文本区
        info_layout = QVBoxLayout()
        info_layout.setSpacing(6)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = StrongBodyLabel(task.title or self.tr("未知标题"), self)
        self.title_label.setWordWrap(False)
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred
        )

        # Meta 构建
        meta_str = ""
        if task.has_error:
            meta_str = task.error_msg
        else:
            duration = str(task.duration_str or "").strip()
            if duration:
                meta_str = self.tr("时长: {}").format(duration)
            if task.upload_date and task.upload_date != "-":
                meta_str += (
                    self.tr(" · 日期: {}").format(task.upload_date) if meta_str else self.tr("日期: {}").format(task.upload_date)
                )
            if not meta_str:
                meta_str = self.tr("待加载...")

        self.meta_label = CaptionLabel(meta_str, self)
        if task.has_error:
            self.meta_label.setTextColor(QColor("#C42B1C"), QColor("#FF99A4"))
        else:
            self.meta_label.setTextColor(QColor(120, 120, 120), QColor(150, 150, 150))

        font = self.meta_label.font()
        font.setFamily("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.meta_label.setFont(font)

        info_layout.addWidget(self.title_label)
        info_layout.addWidget(self.meta_label)

        self.h_layout.addLayout(info_layout)
        self.h_layout.addStretch(1)

        # 4. 右侧状态/图标预留区
        self.status_label = CaptionLabel("", self)
        self.status_label.setFixedWidth(80)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.h_layout.addWidget(self.status_label)

        self._is_hover = False
        self._is_pressed = False
        self._update_style()

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        if not pixmap.isNull():
            self.thumb.setPixmap(pixmap)

    def set_selected(self, selected: bool) -> None:
        self.task.selected = selected
        self.checkbox.setChecked(selected)

    def is_selected(self) -> bool:
        return self.checkbox.isChecked()

    def update_status(self, is_parsing: bool = False, error: bool = False, msg: str = "") -> None:
        if error:
            self.status_label.setText(msg or self.tr("解析失败"))
            self.status_label.setTextColor(QColor("#C42B1C"), QColor("#FF99A4"))
            self.title_label.setTextColor(QColor("#C42B1C"), QColor("#FF99A4"))
        elif is_parsing:
            self.status_label.setText(msg or self.tr("解析中..."))
            self.status_label.setTextColor(QColor(120, 120, 120), QColor(150, 150, 150))
            self.title_label.setTextColor(QColor(0, 0, 0), QColor(255, 255, 255))
        else:
            self.status_label.setText(msg or self.tr("待下载"))
            self.status_label.setTextColor(QColor(0, 120, 212), QColor(118, 185, 237))
            self.title_label.setTextColor(QColor(0, 0, 0), QColor(255, 255, 255))

    def _is_dark(self) -> bool:
        return True

    def _update_style(self):
        dark = self._is_dark()

        # 基础颜色
        bg_color = "rgba(255, 255, 255, 0.05)" if dark else "rgba(255, 255, 255, 0.7)"
        border_color = "rgba(255, 255, 255, 0.08)" if dark else "rgba(0, 0, 0, 0.06)"

        # 交互颜色
        if self._is_pressed:
            bg_color = "rgba(255, 255, 255, 0.03)" if dark else "rgba(0, 0, 0, 0.03)"
            border_color = "rgba(255, 255, 255, 0.04)" if dark else "rgba(0, 0, 0, 0.04)"
        elif self._is_hover:
            bg_color = "rgba(255, 255, 255, 0.08)" if dark else "rgba(255, 255, 255, 0.9)"
            border_color = "rgba(255, 255, 255, 0.12)" if dark else "rgba(0, 0, 0, 0.1)"

        self.setStyleSheet(f"""
            PlaylistItemCard {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
        """)

    def enterEvent(self, event):
        self._is_hover = True
        self._update_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hover = False
        self._is_pressed = False
        self._update_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = True
            self._update_style()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_pressed = False
            self._update_style()
            # 只有在鼠标仍在控件内释放时才算作点击
            if self.rect().contains(event.pos()):
                self.set_selected(not self.is_selected())
                self.clicked.emit(self.row_index)
        super().mouseReleaseEvent(event)
