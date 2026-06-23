"""
PlaylistItemCard (QWidget wrapper for QPainter logic)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal, QSize
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QFontMetrics,
)
from PySide6.QtWidgets import QWidget

from qfluentwidgets import isDarkTheme, themeColor

from ...models.video_task import VideoTask
from qfluentwidgets import isDarkTheme, ToolTipFilter, ToolTipPosition


def _fluent_colors(is_dark: bool) -> dict:
    """Return a flat dict of QColor values for the current theme."""
    if is_dark:
        return {
            "text_primary": QColor(255, 255, 255),
            "text_secondary": QColor(200, 200, 200),
            "text_caption": QColor(160, 160, 160),
            "error_fg": QColor("#FF99A4"),
            "error_bg": QColor(220, 53, 69, 30),
            "muted_fg": QColor(160, 160, 160),
            "row_hover": QColor(255, 255, 255, 15),
            "row_selected": QColor(255, 255, 255, 21),
            "checkbox_border": QColor(160, 160, 160),
            "thumb_placeholder": QColor(255, 255, 255, 10),
            "thumb_border": QColor(255, 255, 255, 12),
            "btn_subtle_bg": QColor(255, 255, 255, 10),
            "btn_border": QColor(255, 255, 255, 15),
        }
    else:
        return {
            "text_primary": QColor(0, 0, 0),
            "text_secondary": QColor(96, 96, 96),
            "text_caption": QColor(128, 128, 128),
            "error_fg": QColor("#C42B1C"),
            "error_bg": QColor(220, 53, 69, 20),
            "muted_fg": QColor(128, 128, 128),
            "row_hover": QColor(0, 0, 0, 9),
            "row_selected": QColor(0, 0, 0, 15),
            "checkbox_border": QColor(128, 128, 128),
            "thumb_placeholder": QColor(0, 0, 0, 10),
            "thumb_border": QColor(0, 0, 0, 12),
            "btn_subtle_bg": QColor(0, 0, 0, 8),
            "btn_border": QColor(0, 0, 0, 15),
        }



class PlaylistItemCard(QWidget):
    """
    独立的可滚动卡片，使用 QPainter 保证极高的渲染性能，
    同时依靠 QWidget 的实体摆脱 QListView 的各种底层渲染限制。
    """

    # 点击事件，传出自己的 index
    clicked = Signal(int)

    THUMB_WIDTH = 150
    THUMB_HEIGHT = 84
    CHECKBOX_SIZE = 20
    MARGIN = 16
    SPACING = 16

    def __init__(self, task: VideoTask, row_index: int, parent=None):
        super().__init__(parent)
        
        self.task = task
        self.row_index = row_index

        self.setFixedHeight(108)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        

        self._thumb_pixmap: QPixmap | None = None
        self._scaled_pixmap: QPixmap | None = None

    def set_pixmap(self, pixmap: QPixmap | None):
        """设置并缓存缩放好的图片"""
        self._thumb_pixmap = pixmap
        if pixmap and not pixmap.isNull():
            rect_size = QSize(self.THUMB_WIDTH, self.THUMB_HEIGHT)
            self._scaled_pixmap = pixmap.scaled(
                rect_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            self._scaled_pixmap = None
        self.update()

    def mousePressEvent(self, event):
        """处理点击区域"""
        self.clicked.emit(self.row_index)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        """核心：1:1 平移原本在 Delegate 里的极致性能绘制管线"""
        painter = QPainter(self)
        rect = self.rect()

        is_dark = isDarkTheme()
        colors = _fluent_colors(is_dark)
        accent = themeColor()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # ── 1. 画整行背景（悬停、选中） ──
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)

        if self.task.selected:
            painter.setBrush(QBrush(colors["row_selected"]))
        elif self.underMouse():
            painter.setBrush(QBrush(colors["row_hover"]))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(rect, 6, 6)
        painter.restore()

        # ── 2. 画选中状态的侧边指示条 ──
        if self.task.selected:
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
            indicator_rect = QRect(rect.left(), rect.top() + 24, 3, rect.height() - 48)
            painter.drawRoundedRect(indicator_rect, 1.5, 1.5)
            painter.restore()

        # ── 3. 画 CheckBox ──
        current_x = rect.left() + self.MARGIN
        center_y = rect.top() + (rect.height() // 2)

        chk_rect = QRect(
            current_x, center_y - self.CHECKBOX_SIZE // 2, self.CHECKBOX_SIZE, self.CHECKBOX_SIZE
        )
        self._draw_checkbox(painter, chk_rect, self.task.selected, accent, colors)

        # ── 4. 画缩略图 ──
        current_x += self.CHECKBOX_SIZE + self.SPACING
        thumb_rect = QRect(
            current_x, center_y - self.THUMB_HEIGHT // 2, self.THUMB_WIDTH, self.THUMB_HEIGHT
        )
        self._draw_thumbnail(painter, thumb_rect, colors)

        # ── 5. 画按钮和文本 ──
        current_x += self.THUMB_WIDTH + self.SPACING
        right_margin = rect.right() - self.MARGIN
        action_width = 140
        action_rect = QRect(right_margin - action_width, center_y - 16, action_width, 32)

        text_rect = QRect(
            current_x,
            rect.top() + self.MARGIN,
            action_rect.left() - current_x - self.SPACING,
            rect.height() - 2 * self.MARGIN,
        )

        self._draw_text_info(painter, text_rect, colors)
        self._draw_action_btn(painter, action_rect, is_dark, accent, colors)

    def _draw_checkbox(self, painter, rect, checked, accent, colors):
        painter.save()
        if checked:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
        else:
            painter.setPen(QPen(colors["checkbox_border"], 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(rect, 4, 4)

        if checked:
            painter.setPen(
                QPen(
                    Qt.GlobalColor.white,
                    2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            path = QPainterPath()
            path.moveTo(rect.left() + 4, rect.top() + 10)
            path.lineTo(rect.left() + 8, rect.top() + 14)
            path.lineTo(rect.left() + 15, rect.top() + 5)
            painter.drawPath(path)
        painter.restore()

    def _draw_thumbnail(self, painter, rect, colors):
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        painter.setClipPath(path)

        if self._scaled_pixmap:
            x_offset = (self._scaled_pixmap.width() - rect.width()) // 2
            y_offset = (self._scaled_pixmap.height() - rect.height()) // 2
            painter.drawPixmap(
                rect.topLeft(),
                self._scaled_pixmap,
                QRect(x_offset, y_offset, rect.width(), rect.height()),
            )
        else:
            painter.fillPath(path, QBrush(colors["thumb_placeholder"]))

        painter.setClipping(False)
        painter.setPen(QPen(colors["thumb_border"], 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 6, 6)
        painter.restore()

    def _draw_text_info(self, painter, rect, colors):
        painter.save()
        title_font = painter.font()
        title_font.setPixelSize(14)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(colors["text_primary"])

        fm = QFontMetrics(title_font)
        elided_title = fm.elidedText(self.task.title, Qt.TextElideMode.ElideRight, rect.width())
        title_rect = QRect(rect.left(), rect.top() + 4, rect.width(), fm.height())
        painter.drawText(
            title_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), elided_title
        )

        meta_font = painter.font()
        meta_font.setPixelSize(12)
        meta_font.setBold(False)
        painter.setFont(meta_font)
        painter.setPen(colors["text_secondary"])

        meta_str = ""
        if self.task.has_error:
            painter.setPen(colors["error_fg"])
            meta_str = self.task.error_msg
        else:
            duration = str(self.task.duration_str or "").strip()
            if duration:
                meta_str = f"时长: {duration}"
            if self.task.upload_date and self.task.upload_date != "-":
                if meta_str:
                    meta_str += f" · 日期: {self.task.upload_date}"
                else:
                    meta_str = f"日期: {self.task.upload_date}"
            if not meta_str:
                meta_str = "待加载..."

        fm_meta = QFontMetrics(meta_font)
        elided_meta = fm_meta.elidedText(meta_str, Qt.TextElideMode.ElideRight, rect.width())
        meta_rect = QRect(
            rect.left(), rect.bottom() - fm_meta.height() - 4, rect.width(), fm_meta.height()
        )
        painter.drawText(
            meta_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), elided_meta
        )
        painter.restore()

    def _draw_action_btn(self, painter, rect, is_dark, accent, colors):
        painter.save()
        if self.task.is_parsing:
            bg = colors["btn_subtle_bg"]
            fg = colors["text_secondary"]
            text = "解析中..."
        elif self.task.has_error:
            bg = colors["error_bg"]
            fg = colors["error_fg"]
            text = "错误"
        elif self.task.custom_options.format is None:
            bg = QColor(255, 255, 255, 6) if is_dark else QColor(0, 0, 0, 5)
            fg = colors["muted_fg"]
            text = "待加载..."
        else:
            bg = QColor(colors["btn_subtle_bg"])
            fg = colors["text_primary"]
            fmt_note = self.task.custom_options.format if self.task.custom_options.format else "自动最佳"
            if len(fmt_note) > 12:
                fmt_note = fmt_note[:10] + ".."
            text = fmt_note

        painter.setBrush(QBrush(bg))
        painter.setPen(QPen(colors["btn_border"], 1))
        painter.drawRoundedRect(rect, 5, 5)

        font = painter.font()
        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(fg)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
        painter.restore()
