from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout
from qfluentwidgets import (
    Action,
    BodyLabel,
    FluentIcon,
    RoundMenu,
    TransparentDropDownToolButton,
    TransparentToolButton,
    isDarkTheme,
)


class BatchOperationPanel(QFrame):
    batch_start_requested = Signal()  # 开始选中任务
    batch_pause_requested = Signal()  # 暂停选中任务
    batch_delete_requested = Signal(bool)  # 删除选中任务, bool=是否删文件
    batch_exit_requested = Signal()  # 退出批量模式
    select_all_requested = Signal()  # 全选
    deselect_all_requested = Signal()  # 取消全选

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BatchOperationPanel")

        self.setFixedHeight(56)

        self._init_ui()
        self._update_style()

        from qfluentwidgets import qconfig

        qconfig.themeChanged.connect(self._update_style)

    def _init_ui(self):
        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(16, 0, 16, 0)
        self.h_layout.setSpacing(12)

        # === 选中计数 ===
        self.count_label = BodyLabel("已选择 0 项", self)
        self.count_label.setMinimumWidth(130)  # 防止字数多时挤压
        self.h_layout.addWidget(self.count_label)

        # === 全选按钮组 ===
        self.btn_select_all = TransparentToolButton(FluentIcon.ACCEPT, self)
        self.btn_select_all.setToolTip("全选")
        self.btn_select_all.clicked.connect(self.select_all_requested)
        self.h_layout.addWidget(self.btn_select_all)

        self.btn_deselect_all = TransparentToolButton(FluentIcon.CLEAR_SELECTION, self)
        self.btn_deselect_all.setToolTip("取消全选")
        self.btn_deselect_all.clicked.connect(self.deselect_all_requested)
        self.h_layout.addWidget(self.btn_deselect_all)

        # 分隔符
        self.separator1 = QFrame(self)
        self.separator1.setFrameShape(QFrame.Shape.VLine)
        self.separator1.setFrameShadow(QFrame.Shadow.Plain)
        self.separator1.setFixedWidth(1)
        self.h_layout.addWidget(self.separator1)

        # === 动作按钮 ===
        self.btn_start = TransparentToolButton(FluentIcon.PLAY, self)
        self.btn_start.setToolTip("开始选中")
        self.btn_start.clicked.connect(self.batch_start_requested)
        self.h_layout.addWidget(self.btn_start)

        self.btn_pause = TransparentToolButton(FluentIcon.PAUSE, self)
        self.btn_pause.setToolTip("暂停选中")
        self.btn_pause.clicked.connect(self.batch_pause_requested)
        self.h_layout.addWidget(self.btn_pause)

        # === 删除下拉菜单 ===
        self.btn_delete = TransparentDropDownToolButton(FluentIcon.DELETE, self)
        self.btn_delete.setToolTip("删除选中")

        menu = RoundMenu(parent=self)
        self.action_del_record = Action(FluentIcon.DOCUMENT, "仅删记录", self)
        self.action_del_all = Action(FluentIcon.DELETE, "连同文件一起删除", self)

        self.action_del_record.triggered.connect(lambda: self.batch_delete_requested.emit(False))
        self.action_del_all.triggered.connect(lambda: self.batch_delete_requested.emit(True))

        menu.addAction(self.action_del_record)
        menu.addAction(self.action_del_all)
        self.btn_delete.setMenu(menu)

        self.h_layout.addWidget(self.btn_delete)

        # 分隔符
        self.separator2 = QFrame(self)
        self.separator2.setFrameShape(QFrame.Shape.VLine)
        self.separator2.setFrameShadow(QFrame.Shadow.Plain)
        self.separator2.setFixedWidth(1)
        self.h_layout.addWidget(self.separator2)

        # === 退出批量 ===
        self.btn_exit = TransparentToolButton(FluentIcon.CANCEL, self)
        self.btn_exit.setToolTip("退出批量")
        self.btn_exit.clicked.connect(self.batch_exit_requested)
        self.h_layout.addWidget(self.btn_exit)

    def _update_style(self):
        bg_color = "rgba(43, 43, 43, 0.96)" if isDarkTheme() else "rgba(255, 255, 255, 0.96)"
        border_color = "rgba(255, 255, 255, 0.08)" if isDarkTheme() else "rgba(0, 0, 0, 0.06)"
        "rgba(0, 0, 0, 0.25)" if isDarkTheme() else "rgba(0, 0, 0, 0.12)"

        self.setStyleSheet(f"""
            BatchOperationPanel {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 28px;
            }}
        """)

        # 分隔线颜色
        sep_color = "rgba(255, 255, 255, 0.15)" if isDarkTheme() else "rgba(0, 0, 0, 0.1)"
        self.separator1.setStyleSheet(f"background-color: {sep_color}; border: none;")
        self.separator2.setStyleSheet(f"background-color: {sep_color}; border: none;")

        # 移除 QGraphicsDropShadowEffect 防止 Qt 在隐藏时发生 Segfault
        # 改为通过 qss 加强边框和背景来弥补视觉效果

    def update_count(self, selected_count: int, total_count: int):
        self.count_label.setText(f"已选择 {selected_count} / {total_count} 项")
