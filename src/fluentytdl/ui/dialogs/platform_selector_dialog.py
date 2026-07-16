
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget
from qfluentwidgets import ComboBox, MessageBoxBase, SubtitleLabel


class PlatformSelectorDialog(MessageBoxBase):
    """
    平台选择对话框，用于在手动导入 Cookie 或浏览器提取时指定目标平台。
    """

    def __init__(self, parent: QWidget | None = None, title: str = ""):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title or QCoreApplication.translate("PlatformSelectorDialog", "选择目标平台"), self)
        
        # 平台下拉框
        self.combo = ComboBox(self)
        self.combo.addItem("YouTube", userData="youtube")
        self.combo.addItem("X (Twitter)", userData="twitter")
        
        # 将组件添加到布局
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.combo)
        
        self.viewLayout.setSpacing(16)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        
        self.widget.setMinimumWidth(320)

    def get_selected_platform(self) -> str:
        """获取用户选择的平台标识"""
        return self.combo.currentData()
