from typing import Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QDialogButtonBox,
    QWidget,
)
from PySide6.QtCore import Qt, QCoreApplication

class PlatformSelectorDialog(QDialog):
    """
    平台选择对话框，用于在手动导入 Cookie 或浏览器提取时指定目标平台。
    """

    def __init__(self, parent: Optional[QWidget] = None, title: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title or QCoreApplication.translate("PlatformSelectorDialog", "选择目标平台"))
        self.setFixedSize(320, 150)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 提示标签
        label = QLabel(
            QCoreApplication.translate("PlatformSelectorDialog", "请选择要导入/提取 Cookie 的平台:"), self
        )
        layout.addWidget(label)

        # 平台下拉框
        self.combo = QComboBox(self)
        self.combo.addItem("YouTube", "youtube")
        self.combo.addItem("X (Twitter)", "twitter")
        layout.addWidget(self.combo)

        layout.addStretch(1)

        # 按钮组
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_selected_platform(self) -> str:
        """获取用户选择的平台标识"""
        return self.combo.currentData()
