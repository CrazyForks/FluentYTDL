"""
统一任务列表页面

使用 Pivot 过滤器 + 单一 ScrollArea 实现任务管理。
替代原有的四页面分散管理方案。
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListView,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    SubtitleLabel,
)

from .delegates.download_item_delegate import DownloadItemDelegate
from .models.download_list_model import DownloadListModel


class DownloadFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter = "all"

    def set_filter(self, status: str):
        self._filter = status
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self._filter == "all":
            return True

        model = self.sourceModel()
        if not hasattr(model, "get_task"):
            return True

        task = model.get_task(source_row)
        if not task:
            return False

        worker = task.get("worker")
        if not worker:
            return False

        state = worker.effective_state

        return state == self._filter

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        # 因为在 DownloadListModel 中新任务始终插入在 row=0，
        # 所以 row 越小，任务越新。按照 row 的大小排序即可代表添加时间的先后。
        return left.row() < right.row()


class UnifiedTaskListPage(QWidget):
    """
    统一任务列表页面

    特性:
    - 单一 ScrollArea 容纳所有任务卡片
    - Pivot 顶部过滤器切换显示
    - 空状态占位符
    - 新任务插入顶部
    """

    # Signals: User actions from delegate
    card_remove_requested = Signal(int)
    card_resume_requested = Signal(int)
    card_folder_requested = Signal(int)

    card_pause_resume_requested = Signal(list)  # 列表[int], 批量可能多个
    card_open_folder_requested = Signal(list)
    card_delete_requested = Signal(list)

    batch_start_requested = Signal(list)
    batch_pause_requested = Signal(list)
    batch_delete_requested = Signal(list, bool)

    # Navbar trigger
    route_to_parse = Signal()
    selection_mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("unifiedTaskListPage")

        self.model = DownloadListModel(self)
        self.proxy_model = DownloadFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setDynamicSortFilter(True)
        self.proxy_model.sort(0, Qt.SortOrder.AscendingOrder)

        self.delegate = DownloadItemDelegate(self)

        self._current_filter: str = "all"
        self._is_batch_mode: bool = False

        self._init_ui()

        # Connect internal model changes to empty state updates
        # Note: dataChanged is NOT connected here — it only indicates
        # property changes on existing rows (e.g. progress) and never
        # affects row count, so it cannot change the empty/non-empty state.
        # Connecting it caused full-list flicker on every progress tick.
        self.model.rowsInserted.connect(self._update_empty_state)
        self.model.rowsRemoved.connect(self._update_empty_state)
        self.model.modelReset.connect(self._update_empty_state)

        # Connect proxy model signals as well, ensuring filter changes trigger updates
        self.proxy_model.rowsInserted.connect(self._update_empty_state)
        self.proxy_model.rowsRemoved.connect(self._update_empty_state)
        self.proxy_model.modelReset.connect(self._update_empty_state)

        # force initial empty state
        self._update_empty_state()

        # Delegate signals
        self.delegate.delete_clicked.connect(self._on_delegate_delete)
        self.delegate.pause_resume_clicked.connect(self._on_delegate_pause_resume)
        self.delegate.open_folder_clicked.connect(self._on_delegate_open_folder)
        self.delegate.selection_toggled.connect(self._on_delegate_selection)

        # Image Loader signals
        from ..utils.image_loader import get_image_loader

        get_image_loader().loaded_with_url.connect(self._on_image_loaded)

    def _on_image_loaded(self, url: str, pixmap: QPixmap) -> None:
        self.delegate.set_pixmap(url, pixmap)
        # Repaint only the rows whose thumbnail matches this url,
        # instead of invalidating the entire viewport.
        if not hasattr(self, "list_view"):
            return
        model = self.proxy_model
        for row in range(model.rowCount()):
            idx = model.index(row, 0)
            data = idx.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and data.get("thumbnail") == url:
                self.list_view.update(idx)
                break  # thumbnails are unique per task

    def _on_delegate_delete(self, proxy_row: int):
        src_idx = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0))
        self.card_remove_requested.emit(src_idx.row())

    def _on_delegate_pause_resume(self, proxy_row: int):
        src_idx = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0))
        self.card_resume_requested.emit(src_idx.row())

    def _on_delegate_open_folder(self, proxy_row: int):
        src_idx = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0))
        self.card_folder_requested.emit(src_idx.row())

    def _on_delegate_selection(self, proxy_row: int):
        src_idx = self.proxy_model.mapToSource(self.proxy_model.index(proxy_row, 0))
        self.model.toggle_selection(src_idx.row())

    def _init_ui(self) -> None:
        """初始化 UI 布局"""
        self.v_layout = QVBoxLayout(self)
        self.v_layout.setContentsMargins(20, 20, 20, 20)
        self.v_layout.setSpacing(16)

        # === 标题 ===
        self.title_label = SubtitleLabel(self.tr("任务列表"), self)
        self.v_layout.addWidget(self.title_label)

        # === 用于筛选的 SegmentedWidget (胶囊样式) ===
        from PySide6.QtWidgets import QHBoxLayout
        from qfluentwidgets import ComboBox, SegmentedWidget

        from ..core.config_manager import config_manager

        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(0, 0, 0, 0)

        self.pivot = SegmentedWidget(self)
        self.pivot.addItem(routeKey="all", text=self.tr("全部任务"))
        self.pivot.addItem(routeKey="running", text=self.tr("下载中"))
        self.pivot.addItem(routeKey="queued", text=self.tr("排队中"))
        self.pivot.addItem(routeKey="paused", text=self.tr("已暂停"))
        self.pivot.addItem(routeKey="quality_guard", text=self.tr("质量守卫"))
        self.pivot.addItem(routeKey="completed", text=self.tr("已完成"))
        self.pivot.addItem(routeKey="error", text=self.tr("已失败"))
        self.pivot.currentItemChanged.connect(self._on_pivot_changed)
        self.pivot.setCurrentItem("all")

        self.header_layout.addWidget(self.pivot)
        self.header_layout.addStretch(1)  # 强制左对齐
        from PySide6.QtCore import Qt

        # === 并发数控制 ===
        self.concurrent_label = BodyLabel(self.tr("并发下载数:"), self)
        self.header_layout.addWidget(self.concurrent_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self.concurrent_box = ComboBox(self)
        self.concurrent_box.addItems([str(i) for i in range(1, 11)])
        # Fetch initial value from config
        current_max = int(config_manager.get("max_concurrent_downloads", 3) or 3)
        self.concurrent_box.setCurrentIndex(max(0, min(9, current_max - 1)))
        self.concurrent_box.setFixedWidth(65)
        self.concurrent_box.setFixedHeight(32)  # 防止被拉伸
        self.concurrent_box.currentIndexChanged.connect(self._on_concurrent_changed)
        self.header_layout.addWidget(self.concurrent_box, 0, Qt.AlignmentFlag.AlignVCenter)

        self.header_layout.addSpacing(16)
        
        # === 排序切换按钮 ===
        from qfluentwidgets import ToolButton
        self.sort_button = ToolButton(FluentIcon.UP, self)
        self.sort_button.setToolTip(self.tr("切换排序 (最新/最早)"))
        self.sort_button.clicked.connect(self._on_sort_clicked)
        self.header_layout.addWidget(self.sort_button, 0, Qt.AlignmentFlag.AlignVCenter)

        # === 动作按钮扩展槽 ===
        self.header_layout.addSpacing(16)
        self.action_layout = QHBoxLayout()
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.addLayout(self.action_layout)

        self.v_layout.addLayout(self.header_layout)

        # SegmentedWidget 自带容器背景，不再需要额外的分割线，或者保留分割线作为区域划分
        # 用户建议: self.tr("去掉下划线...那个蓝绿色的下划线就可以去掉了") -> SegmentedWidget 没有下划线
        # 用户建议: self.tr("下方可以有一条贯穿全宽的细分割线") -> 保留分割线作为区域划分

        # === 分割线 (保留以区分区域) ===
        self.pivot_line = QFrame(self)
        self.pivot_line.setFrameShape(QFrame.Shape.HLine)
        self.pivot_line.setFrameShadow(QFrame.Shadow.Plain)
        self.v_layout.addWidget(self.pivot_line)

        # === 堆叠视图 (StackedWidget) 防止错位 ===
        from PySide6.QtWidgets import QStackedWidget

        self.stack = QStackedWidget(self)
        self.v_layout.addWidget(self.stack, 1)

        # === 任务列表 ListView ===
        from qfluentwidgets import ListView

        self.list_view = ListView(self)
        self.list_view.setModel(self.proxy_model)
        self.list_view.setItemDelegate(self.delegate)
        self.list_view.setFrameShape(QFrame.Shape.NoFrame)
        self.list_view.setStyleSheet("background: transparent;")
        self.list_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.list_view.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.list_view.setSpacing(8)
        self.list_view.setMouseTracking(True)  # 重要：启用鼠标追踪以支持 Delegate 悬停状态

        self.stack.addWidget(self.list_view)

        # === 空状态占位符 (增强版) ===
        from qfluentwidgets import PrimaryPushButton

        self.empty_placeholder = QWidget(self)
        empty_layout = QVBoxLayout(self.empty_placeholder)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(16)

        # 使用更大的图标 (FluentIcon.LIBRARY 或自定义图)
        # 这里模拟插画效果，使用较大的 Icon
        self.empty_icon = QLabel(self.empty_placeholder)
        # 实际项目中应加载 SVG/PNG 插画
        # self.empty_icon.setPixmap(...)
        # 暂时用大号 Emoji 或 Icon 替代
        self.empty_icon.setText("🍃")
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_container = QWidget(self.empty_placeholder)
        text_layout = QVBoxLayout(text_container)
        text_layout.setSpacing(4)

        self.empty_title = SubtitleLabel(self.tr("暂无任务"), text_container)
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_desc = BodyLabel(self.tr("点击下方按钮新建下载任务"), text_container)
        self.empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_desc.setTextColor(
            QColor(96, 96, 96), QColor(206, 206, 206)
        )  # Secondary text color

        text_layout.addWidget(self.empty_title)
        text_layout.addWidget(self.empty_desc)

        # 行动点按钮 (!Action)
        self.empty_action_btn = PrimaryPushButton(
            FluentIcon.ADD, self.tr("新建任务"), self.empty_placeholder
        )
        self.empty_action_btn.setFixedWidth(160)
        # 连接到跳转信号
        self.empty_action_btn.clicked.connect(self.route_to_parse.emit)

        empty_layout.addStretch(1)
        empty_layout.addWidget(self.empty_icon)
        empty_layout.addWidget(text_container)
        empty_layout.addWidget(self.empty_action_btn)
        empty_layout.addStretch(1)

        self.stack.addWidget(self.empty_placeholder)
        self.stack.setCurrentWidget(self.list_view)

        # === 悬浮批量操作面板 ===
        from .batch_operation_panel import BatchOperationPanel

        self.batch_panel = BatchOperationPanel(self)

        # 连接面板信号 → 页面信号
        self.batch_panel.select_all_requested.connect(self.select_all)
        self.batch_panel.deselect_all_requested.connect(lambda: self.model.set_all_selected(False))
        self.batch_panel.batch_start_requested.connect(
            lambda: self.batch_start_requested.emit(self.get_selected_rows())
        )
        self.batch_panel.batch_pause_requested.connect(
            lambda: self.batch_pause_requested.emit(self.get_selected_rows())
        )
        self.batch_panel.batch_delete_requested.connect(
            lambda delete_files: self.batch_delete_requested.emit(
                self.get_selected_rows(), delete_files
            )
        )
        self.batch_panel.batch_exit_requested.connect(lambda: self.set_selection_mode(False))

        # 选中状态变化时更新面板计数
        self.model.selection_changed.connect(self._update_batch_count)

        # 初始隐藏
        self.batch_panel.hide()

        from qfluentwidgets import qconfig

        qconfig.themeChanged.connect(self._update_style)
        self._update_style()

        # 响应配制改变，同步并发数数值
        from ..core.config_manager import config_manager

        config_manager.configChanged.connect(self._on_global_config_changed)

    def _on_global_config_changed(self, key: str, value: Any) -> None:
        if key == "max_concurrent_downloads":
            try:
                val_int = int(value)
                index_target = max(0, min(9, val_int - 1))
                if self.concurrent_box.currentIndex() != index_target:
                    self.concurrent_box.setCurrentIndex(index_target)
            except (ValueError, TypeError):
                pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 固定悬浮面板到底部中央
        if hasattr(self, "batch_panel"):
            w = self.batch_panel.sizeHint().width() + 20
            h = self.batch_panel.height()
            # 距底部 30 像素
            self.batch_panel.setGeometry((self.width() - w) // 2, self.height() - h - 30, w, h)

    def _update_style(self):
        from qfluentwidgets import isDarkTheme

        line_color = "rgba(255, 255, 255, 0.08)" if isDarkTheme() else "rgba(0, 0, 0, 0.08)"
        self.pivot_line.setStyleSheet(f"color: {line_color};")

        empty_color = "rgba(255, 255, 255, 0.1)" if isDarkTheme() else "rgba(0, 0, 0, 0.1)"
        self.empty_icon.setStyleSheet(f"font-size: 64px; color: {empty_color};")

    def set_selection_mode(self, enabled: bool) -> None:
        """启用或禁用多选模式"""
        if self._is_batch_mode == enabled:
            return

        self._is_batch_mode = enabled
        self.delegate.set_selection_mode(enabled)

        # 控制底层悬浮面板显示
        if enabled:
            # 取消之前的所有选中状态，避免残留
            self.model.set_all_selected(False)
            self.batch_panel.show()
            self.batch_panel.raise_()
            self._update_batch_count()
        else:
            self.batch_panel.hide()
            # 安全地通知所有行重绘以隐藏复选框
            self.model.set_all_selected(False)

        self.selection_mode_changed.emit(enabled)

    def _update_batch_count(self) -> None:
        """更新批量面板的选中计数"""
        if hasattr(self, "batch_panel"):
            selected = len(self.model.get_selected_rows())
            total = self.model.rowCount()
            self.batch_panel.update_count(selected, total)

    def select_all(self) -> None:
        """选择所有可见的卡片"""
        self.model.set_all_selected(True)

    def get_selected_rows(self) -> list[int]:
        """获取所有选中的行的 source indexing"""
        return self.model.get_selected_rows()

    def _on_pivot_changed(self, route_key: str) -> None:
        """Pivot 切换时调用"""
        self.set_filter(route_key)

    def _on_concurrent_changed(self, index: int) -> None:
        """并发数改变时更新配置并通知管理器"""
        from ..core.config_manager import config_manager
        from ..download.download_manager import download_manager

        value = index + 1
        config_manager.set("max_concurrent_downloads", value)
        # Force manager to evaluate queued items based on new limit
        download_manager.pump()

    def _on_sort_clicked(self):
        from PySide6.QtCore import Qt
        from qfluentwidgets import FluentIcon
        if self.proxy_model.sortOrder() == Qt.SortOrder.AscendingOrder:
            self.proxy_model.sort(0, Qt.SortOrder.DescendingOrder)
            self.sort_button.setIcon(FluentIcon.DOWN)
        else:
            self.proxy_model.sort(0, Qt.SortOrder.AscendingOrder)
            self.sort_button.setIcon(FluentIcon.UP)

    def set_filter(self, status: str) -> None:
        """设置过滤条件"""
        self._current_filter = status
        self.proxy_model.set_filter(status)
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        """检查并更新空状态显示 (延迟执行以防止在模型更新过程中抛出异常)"""
        from PySide6.QtCore import QTimer

        def _do_update():
            # 确保对象还没被回收
            if not hasattr(self, "proxy_model") or not hasattr(self, "stack"):
                return

            visible_count = self.proxy_model.rowCount()

            if visible_count == 0:
                self.stack.setCurrentWidget(self.empty_placeholder)

                # 根据当前过滤器显示不同文案
                messages = {
                    "all": ("🍃", self.tr("暂无任务"), self.tr("点击「新建任务」开始下载")),
                    "running": ("⏳", self.tr("没有正在下载的任务"), self.tr("当前无活跃下载")),
                    "queued": ("📋", self.tr("没有排队中的任务"), self.tr("所有任务已开始")),
                    "paused": ("⏸️", self.tr("没有暂停的任务"), self.tr("所有任务运行中")),
                    "completed": ("✅", self.tr("没有已完成的任务"), self.tr("完成的任务会显示在这里")),
                    "error": ("❌", self.tr("没有失败的任务"), self.tr("太棒了，一切顺利！")),
                }
                icon, title, subtitle = messages.get(self._current_filter, ("🍃", self.tr("暂无任务"), ""))
                self.empty_icon.setText(icon)
                self.empty_title.setText(title)
                self.empty_desc.setText(subtitle)

                # 仅在 'all' 过滤器下显示行动按钮
                self.empty_action_btn.setVisible(self._current_filter == "all")
            else:
                self.stack.setCurrentWidget(self.list_view)

        QTimer.singleShot(0, _do_update)

    def count(self) -> int:
        """返回卡片总数"""
        return self.model.rowCount()

    def visible_count(self) -> int:
        """返回当前可见卡片数"""
        return self.proxy_model.rowCount()

    def get_counts_by_state(self) -> dict[str, int]:
        """获取各状态的任务计数"""
        return self.model.get_counts_by_state()
