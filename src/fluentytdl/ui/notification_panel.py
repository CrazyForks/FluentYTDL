from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon,
    FlyoutViewBase,
    IconWidget,
    PushButton,
    ScrollArea,
    TransparentToolButton,
)

from ..notification import Notification, notification_center


class NotificationCard(QFrame):
    """单条通知卡片"""

    def __init__(self, notif: Notification, parent=None):
        super().__init__(parent=parent)
        self.notif = notif
        self.setObjectName("NotificationCard")

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(12, 12, 12, 12)
        self.vBoxLayout.setSpacing(8)

        # 头部：图标 + 标题 + 时间 + 删除
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setContentsMargins(0, 0, 0, 0)

        icon = FluentIcon.INFO
        color = None
        if notif.severity == "critical":
            icon = FluentIcon.ERROR
            color = "#D32F2F"  # 危险红
        elif notif.severity == "warning":
            icon = FluentIcon.INFO
            color = "#D7A100"  # 警告黄

        self.iconWidget = IconWidget(icon, self)
        self.iconWidget.setFixedSize(16, 16)

        self.titleLabel = BodyLabel(notif.title, self)
        self.titleLabel.setWordWrap(False)
        if notif.severity in ("warning", "critical") and color:
            self.titleLabel.setStyleSheet(f"color: {color}; font-weight: bold;")
        elif not notif.is_read:
            self.titleLabel.setStyleSheet("font-weight: bold;")

        # 时间格式化
        dt = datetime.fromtimestamp(notif.timestamp)
        time_str = dt.strftime("%m-%d %H:%M")
        self.timeLabel = CaptionLabel(time_str, self)
        self.timeLabel.setTextColor(Qt.GlobalColor.gray, Qt.GlobalColor.darkGray)

        self.deleteBtn = TransparentToolButton(FluentIcon.CLOSE, self)
        self.deleteBtn.setFixedSize(24, 24)
        self.deleteBtn.setIconSize(self.deleteBtn.iconSize() * 0.8)
        self.deleteBtn.clicked.connect(self._on_delete)

        self.headerLayout.addWidget(self.iconWidget)
        self.headerLayout.addWidget(self.titleLabel, 1)
        self.headerLayout.addWidget(self.timeLabel)
        self.headerLayout.addWidget(self.deleteBtn)

        # 内容
        self.msgLabel = CaptionLabel(notif.message, self)
        self.msgLabel.setWordWrap(True)
        if not notif.is_read:
            self.msgLabel.setStyleSheet("font-weight: bold;")

        self.vBoxLayout.addLayout(self.headerLayout)
        self.vBoxLayout.addWidget(self.msgLabel)

        # 设置样式
        self.setStyleSheet("""
            NotificationCard {
                background-color: transparent;
                border-radius: 6px;
                border: 1px solid rgba(0, 0, 0, 0.05);
            }
            NotificationCard:hover {
                background-color: rgba(0, 0, 0, 0.02);
            }
        """)

    def _on_delete(self):
        notification_center.delete_notification(self.notif.id)

    def mousePressEvent(self, event):
        if not self.notif.is_read:
            notification_center.mark_as_read(self.notif.id)
        super().mousePressEvent(event)


class NotificationFlyoutView(FlyoutViewBase):
    """通知中心浮窗"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(16, 16, 16, 16)
        self.vBoxLayout.setSpacing(12)
        self.setFixedWidth(360)

        # 头部
        self.headerLayout = QHBoxLayout()
        self.titleLabel = BodyLabel("消息中心", self)
        self.titleLabel.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.clearAllBtn = PushButton("全部已读", self)
        self.clearAllBtn.setFixedSize(80, 28)
        self.clearAllBtn.clicked.connect(self._on_clear_all)

        self.headerLayout.addWidget(self.titleLabel)
        self.headerLayout.addStretch(1)
        self.headerLayout.addWidget(self.clearAllBtn)

        self.vBoxLayout.addLayout(self.headerLayout)

        # 滚动区
        self.scrollArea = ScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setStyleSheet("background: transparent;")

        self.scrollWidget = QWidget()
        self.scrollLayout = QVBoxLayout(self.scrollWidget)
        self.scrollLayout.setContentsMargins(0, 0, 8, 0)
        self.scrollLayout.setSpacing(8)
        self.scrollLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scrollArea.setWidget(self.scrollWidget)
        self.vBoxLayout.addWidget(self.scrollArea)

        self.emptyLabel = BodyLabel("暂无通知", self)
        self.emptyLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emptyLabel.setTextColor(Qt.GlobalColor.gray, Qt.GlobalColor.darkGray)
        self.vBoxLayout.addWidget(self.emptyLabel)
        self.emptyLabel.hide()

        self._load_notifications()

        # 监听更新
        notification_center.notification_added.connect(self._on_update)
        notification_center.notification_updated.connect(self._on_update)

    def _load_notifications(self):
        # 清理旧卡片
        while self.scrollLayout.count():
            item = self.scrollLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        notifs = notification_center.get_all(limit=50)
        if not notifs:
            self.scrollArea.hide()
            self.emptyLabel.show()
            if not self.isVisible():
                self.setFixedHeight(120)
        else:
            self.emptyLabel.hide()
            self.scrollArea.show()
            if not self.isVisible():
                self.setFixedHeight(min(450, 80 + len(notifs) * 80))
            for notif in notifs:
                card = NotificationCard(notif, self)
                self.scrollLayout.addWidget(card)

    def _on_clear_all(self):
        notification_center.mark_all_as_read()

    def _on_update(self, *args):
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, self._load_notifications)
