from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidgetItem
from qfluentwidgets import BodyLabel, MessageBoxBase, SubtitleLabel, TableWidget

if TYPE_CHECKING:
    from ...download.quality_guard import QualityVerdict


class QualityReportDialog(MessageBoxBase):
    def __init__(self, warnings: list[tuple[str, "QualityVerdict"]], parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(f"🛡️ 质量守卫报告 ({len(warnings)} 项异常)", self)
        self.viewLayout.addWidget(self.titleLabel)

        msg = "以下任务无法达到目标画质，继续下载可能会输出较低质量的视频："
        self.msgLabel = BodyLabel(msg, self)
        self.viewLayout.addWidget(self.msgLabel)

        self.table = TableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["标题", "目标", "实际", "偏差"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 60)
        self.table.setWordWrap(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setAlternatingRowColors(True)

        self.viewLayout.addWidget(self.table)

        self.widget.setMinimumWidth(600)
        self.widget.setMinimumHeight(450)

        self._populate_table(warnings)

        self.yesButton.setText("仍然下载这些任务")
        self.cancelButton.setText("取消")

    def _populate_table(self, warnings):
        self.table.setRowCount(len(warnings))
        for i, (title, v) in enumerate(warnings):
            self.table.setItem(i, 0, QTableWidgetItem(title))

            parts = v.deviation.split("→")
            target = parts[0].strip().replace("目标", "").strip() if len(parts) > 1 else "-"
            actual = f"{v.actual_height}p" if v.actual_height else "未知"

            self.table.setItem(i, 1, QTableWidgetItem(target))
            self.table.setItem(i, 2, QTableWidgetItem(actual))

            dev_item = QTableWidgetItem("⚠️" if v.deviation_severity == "major" else "ℹ️")
            dev_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 3, dev_item)
