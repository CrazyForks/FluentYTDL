"""Single-video section download controls with a lightweight dual-handle timeline."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPalette
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ComboBox, LineEdit, SwitchButton

from ....core.section_download import SectionCutMode, TimeRange, parse_time_range


def _format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:d}:{secs:02d}"


class _RangeTimeline(QWidget):
    """Theme-aware, no-dependency dual-handle timeline measured in seconds."""

    rangeChanged = Signal(float, float)

    def __init__(self, duration: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._duration = max(1.0, duration)
        self._start = 0.0
        self._end = self._duration
        self._dragging = ""
        self.setMinimumHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_range(self, start: float, end: float, *, emit: bool = False) -> None:
        start = max(0.0, min(float(start), self._duration))
        end = max(start + 0.01, min(float(end), self._duration))
        if (start, end) == (self._start, self._end):
            return
        self._start, self._end = start, end
        self.update()
        if emit:
            self.rangeChanged.emit(start, end)

    def _track_rect(self) -> QRect:
        return QRect(12, self.height() // 2 - 3, max(1, self.width() - 24), 6)

    def _x_for(self, value: float) -> int:
        rect = self._track_rect()
        return rect.left() + round((value / self._duration) * rect.width())

    def _value_for(self, x: int) -> float:
        rect = self._track_rect()
        ratio = (x - rect.left()) / max(1, rect.width())
        return max(0.0, min(self._duration, ratio * self._duration))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        rect = self._track_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.Mid))
        painter.drawRoundedRect(rect, 3, 3)
        left, right = self._x_for(self._start), self._x_for(self._end)
        selected = QRect(left, rect.top(), max(1, right - left), rect.height())
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        painter.drawRoundedRect(selected, 3, 3)
        painter.setBrush(palette.color(QPalette.ColorRole.Base))
        painter.setPen(palette.color(QPalette.ColorRole.Highlight))
        for x in (left, right):
            painter.drawEllipse(QPoint(x, rect.center().y()), 7, 7)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        x = event.position().x()
        self._dragging = (
            "start"
            if abs(x - self._x_for(self._start)) <= abs(x - self._x_for(self._end))
            else "end"
        )
        self._move_handle(x)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._move_handle(event.position().x())

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        self._dragging = ""

    def _move_handle(self, x: float) -> None:
        value = self._value_for(int(x))
        if self._dragging == "start":
            self.set_range(min(value, self._end - 0.01), self._end, emit=True)
        else:
            self.set_range(self._start, max(value, self._start + 0.01), emit=True)


class SectionRangeSelector(QWidget):
    """Switchable clip selector used only for finite normal YouTube videos."""

    enabledChanged = Signal(bool)
    selectionChanged = Signal()

    def __init__(self, duration: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._duration = max(0.0, float(duration))
        self._updating = False
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        header = QHBoxLayout()
        header.addWidget(CaptionLabel(self.tr("视频裁切"), self))
        self.enable_switch = SwitchButton(self)
        self.enable_switch.checkedChanged.connect(self._on_enabled_changed)
        header.addWidget(self.enable_switch)
        header.addStretch(1)
        root.addLayout(header)

        self.options = QWidget(self)
        options = QVBoxLayout(self.options)
        options.setContentsMargins(0, 0, 0, 0)
        options.setSpacing(8)
        self.timeline = _RangeTimeline(self._duration, self.options)
        self.timeline.rangeChanged.connect(self._on_timeline_changed)
        options.addWidget(self.timeline)

        labels = QHBoxLayout()
        self.start_label = CaptionLabel("0:00", self.options)
        self.end_label = CaptionLabel(_format_time(self._duration), self.options)
        labels.addWidget(self.start_label)
        labels.addStretch(1)
        labels.addWidget(self.end_label)
        options.addLayout(labels)

        times = QHBoxLayout()
        times.addWidget(CaptionLabel(self.tr("开始"), self.options))
        self.start_edit = LineEdit(self.options)
        self.start_edit.setText("0:00")
        self.start_edit.editingFinished.connect(self._on_text_changed)
        times.addWidget(self.start_edit)
        times.addWidget(CaptionLabel(self.tr("结束"), self.options))
        self.end_edit = LineEdit(self.options)
        self.end_edit.setText(_format_time(self._duration))
        self.end_edit.editingFinished.connect(self._on_text_changed)
        times.addWidget(self.end_edit)
        times.addWidget(CaptionLabel(self.tr("模式"), self.options))
        self.mode_combo = ComboBox(self.options)
        self.mode_combo.addItem(
            self.tr("粗裁剪（快速，切点可能有偏差）"), userData=SectionCutMode.COARSE.value
        )
        self.mode_combo.addItem(
            self.tr("细裁剪（精确，需重编码）"), userData=SectionCutMode.PRECISE.value
        )
        self.mode_combo.currentIndexChanged.connect(self.selectionChanged)
        times.addWidget(self.mode_combo, 1)
        options.addLayout(times)

        self.status_label = CaptionLabel("", self.options)
        options.addWidget(self.status_label)
        root.addWidget(self.options)
        self.options.hide()

    def _on_enabled_changed(self, enabled: bool) -> None:
        self.options.setVisible(enabled)
        self.enabledChanged.emit(enabled)
        self.selectionChanged.emit()

    def _on_timeline_changed(self, start: float, end: float) -> None:
        self._updating = True
        self.start_edit.setText(_format_time(start))
        self.end_edit.setText(_format_time(end))
        self._updating = False
        self._update_status(start, end)
        self.selectionChanged.emit()

    def _on_text_changed(self) -> None:
        if self._updating:
            return
        try:
            time_range = parse_time_range(self.start_edit.text(), self.end_edit.text())
            if time_range.end_seconds is None or time_range.end_seconds > self._duration:
                raise ValueError(self.tr("时间范围必须位于视频时长内"))
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self.timeline.set_range(time_range.start_seconds, time_range.end_seconds, emit=False)
        self._update_status(time_range.start_seconds, time_range.end_seconds)
        self.selectionChanged.emit()

    def _update_status(self, start: float, end: float) -> None:
        self.start_label.setText(_format_time(start))
        self.end_label.setText(_format_time(end))
        self.status_label.setText(self.tr("将下载 {0} 的片段").format(_format_time(end - start)))

    def is_enabled(self) -> bool:
        return self.enable_switch.isChecked()

    def is_valid(self) -> bool:
        return not self.is_enabled() or self.get_time_range() is not None

    def get_time_range(self) -> TimeRange | None:
        if not self.is_enabled():
            return None
        try:
            value = parse_time_range(self.start_edit.text(), self.end_edit.text())
            if value.end_seconds is None or value.end_seconds > self._duration:
                return None
            return value
        except ValueError:
            return None

    def get_cut_mode(self) -> SectionCutMode:
        # QFluentWidgets' ComboBoxBase.currentData() may return None even when
        # userData was supplied to addItem(). Resolve via the selected index.
        value = self.mode_combo.itemData(self.mode_combo.currentIndex())
        return SectionCutMode(value or SectionCutMode.COARSE.value)
