import re

file_path = r'e:\YouTube\FluentYTDL\src\fluentytdl\ui\components\selection_dialog.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Imports
content = content.replace(
    'from ..delegates.playlist_delegate import PlaylistItemDelegate\nfrom ..models.playlist_model import PlaylistListModel, PlaylistModelRoles',
    'from .playlist_item_card import PlaylistItemCard'
)

# 2. _PlaylistModelRowProxy
content = re.sub(
    r'class _PlaylistModelRowProxy:.*?def set_loading.*?self\._model\.dataChanged\.emit\(idx, idx, \[PlaylistModelRoles\.TaskObjectRole\]\)\n\n',
    '',
    content,
    flags=re.DOTALL
)

# 3. __init__ vars
content = content.replace(
    'self._list_view: QListView | None = None\n        self._playlist_model: PlaylistListModel | None = None\n        self._playlist_delegate: PlaylistItemDelegate | None = None',
    'self._scroll_area: SmoothScrollArea | None = None\n        self._scroll_widget: QWidget | None = None\n        self._scroll_layout: QVBoxLayout | None = None\n        self._cards: list[PlaylistItemCard] = []'
)

# 4. setup_playlist_ui List View init
old_list_view_init = '''        # ── ListView (virtual rendering, no widget-per-row) ──────────────────
        list_view = ListView(self.contentWidget)
        list_view.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        list_view.setMouseTracking(True)
        list_view.setUniformItemSizes(True)  # optimisation: all rows same height
        # 恢复 Fluent UI 原生平滑滚动
        list_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        list_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        playlist_model = PlaylistListModel(list_view)
        playlist_delegate = PlaylistItemDelegate(list_view)
        list_view.setModel(playlist_model)
        list_view.setItemDelegate(playlist_delegate)

        # 修复B: 滚动事件节流——50ms 合并，避免每像素触发重入队 + dataChanged 轰炸
        self._scroll_throttle_timer = QTimer(self)
        self._scroll_throttle_timer.setSingleShot(True)
        self._scroll_throttle_timer.setInterval(50)
        self._scroll_throttle_timer.timeout.connect(self._on_scroll_throttled)
        list_view.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)
        list_view.clicked.connect(self._on_list_item_clicked)

        self._list_view = list_view
        self._playlist_model = playlist_model
        self._playlist_delegate = playlist_delegate

        # AsyncExtractManager: 3 concurrent workers, FIFO queue
        self._extract_manager = AsyncExtractManager(max_concurrent=3, parent=self)

        self.contentLayout.addWidget(list_view)'''

new_scroll_area_init = '''        # ── SmoothScrollArea (Widget-based virtual scrolling) ──────────────────
        self._scroll_area = SmoothScrollArea(self.contentWidget)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._scroll_widget = QWidget()
        self._scroll_widget.setObjectName("scrollWidget")
        self._scroll_widget.setStyleSheet("#scrollWidget { background: transparent; }")
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self._scroll_layout.setContentsMargins(0, 0, 16, 0)
        self._scroll_layout.setSpacing(0)
        self._scroll_layout.addStretch(1)
        self._scroll_area.setWidget(self._scroll_widget)

        self._scroll_throttle_timer = QTimer(self)
        self._scroll_throttle_timer.setSingleShot(True)
        self._scroll_throttle_timer.setInterval(50)
        self._scroll_throttle_timer.timeout.connect(self._on_scroll_throttled)
        self._scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)

        self._extract_manager = AsyncExtractManager(max_concurrent=3, parent=self)

        self.contentLayout.addWidget(self._scroll_area)'''

content = content.replace(old_list_view_init, new_scroll_area_init)

# 5. _build_playlist_rows clearing
content = content.replace(
    '''        model = self._playlist_model
        if model is None:
            return

        model.clear()''',
    '''        # 彻底清空旧的 cards
        while self._scroll_layout.count() > 0:
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        self._cards.clear()'''
)

# 6. _process_next_build_chunk model check
content = content.replace(
    '''        model = self._playlist_model
        if model is None:
            return

        from ...models.video_task import VideoTask''',
    '''        from ...models.video_task import VideoTask'''
)

# 7. Add PlaylistItemCard inside loop
old_proxy = '''            # Proxy acts as the PlaylistActionWidget so _auto_apply_row_preset
            # writes straight into the model without any code changes.
            proxy = _PlaylistModelRowProxy(row, model)
            self._action_widget_by_row[row] = proxy

        # Batch insert this chunk
        model.addTasks(tasks)'''

new_proxy = '''            card = PlaylistItemCard(task, row, self._scroll_widget)
            card.clicked.connect(self._on_list_item_clicked)
            self._cards.append(card)
            
            # 插入到弹簧前面
            self._scroll_layout.insertWidget(self._scroll_layout.count() - 1, card)
            self._action_widget_by_row[row] = card'''

content = content.replace(old_proxy, new_proxy)

# 8. _on_list_item_clicked signature and body
old_click = '''    def _on_list_item_clicked(self, index: QModelIndex) -> None:
        if self._playlist_model is None:
            return
        row = index.row()
        idx = self._playlist_model.index(row, 0)
        task = self._playlist_model.get_task(idx)
        if task is None:
            return

        task.selected = not task.selected
        self._playlist_model.dataChanged.emit(idx, idx, [PlaylistModelRoles.TaskObjectRole])
        self._update_download_btn_state()'''

new_click = '''    def _on_list_item_clicked(self, row: int) -> None:
        if row < 0 or row >= len(self._cards):
            return
        card = self._cards[row]
        task = card.task
        
        task.selected = not task.selected
        card.update()
        self._update_download_btn_state()'''
content = content.replace(old_click, new_click)

# 9. _on_scroll_throttled
old_scroll = '''    def _on_scroll_throttled(self) -> None:
        if self._is_closing:
            return
        if self._playlist_delegate is None or self._list_view is None:
            return

        viewport = self._list_view.viewport()
        visible_rows = []
        for i in range(self._playlist_model.rowCount()):
            index = self._playlist_model.index(i, 0)
            rect = self._list_view.visualRect(index)
            if rect.bottom() >= 0 and rect.top() <= viewport.height():
                visible_rows.append(i)

        if not visible_rows:
            return

        self._load_thumbnails_for_rows(visible_rows)'''

new_scroll = '''    def _on_scroll_throttled(self) -> None:
        if self._is_closing or not self._cards:
            return

        vbar = self._scroll_area.verticalScrollBar()
        y = vbar.value()
        height = self._scroll_area.viewport().height()
        
        # Every card is 108px high, plus layout margins and spacing (0)
        first = max(0, y // 108)
        last = min(len(self._cards) - 1, (y + height) // 108 + 1)
        
        visible_rows = list(range(first, last + 1))
        
        if not visible_rows:
            return

        self._load_thumbnails_for_rows(visible_rows)'''
content = content.replace(old_scroll, new_scroll)

# 10. _load_thumbnails_for_rows
# Wait, no changes needed for the loop itself, just the pixmap applying

# 11. _handle_extract_success
old_success = '''        if self._playlist_model is not None:
            idx = self._playlist_model.index(row, 0)
            task = self._playlist_model.get_task(idx)
            if task is not None:
                task.is_parsing = False
                task.duration_str = _format_duration(info.get("duration"))
                task.upload_date = _format_upload_date(info.get("upload_date"))
                task.custom_options.format = format_id

                self._playlist_model.dataChanged.emit(idx, idx, [PlaylistModelRoles.TaskObjectRole])'''

new_success = '''        if row < len(self._cards):
            card = self._cards[row]
            task = card.task
            task.is_parsing = False
            task.duration_str = _format_duration(info.get("duration"))
            task.upload_date = _format_upload_date(info.get("upload_date"))
            task.custom_options.format = format_id
            card.update()'''
content = content.replace(old_success, new_success)

# 12. _handle_extract_error
old_error = '''        if self._playlist_model is not None:
            idx = self._playlist_model.index(row, 0)
            task = self._playlist_model.get_task(idx)
            if task is not None:
                task.is_parsing = False
                task.has_error = True
                task.error_msg = error_msg
                self._playlist_model.dataChanged.emit(idx, idx, [PlaylistModelRoles.TaskObjectRole])'''

new_error = '''        if row < len(self._cards):
            card = self._cards[row]
            task = card.task
            task.is_parsing = False
            task.has_error = True
            task.error_msg = error_msg
            card.update()'''
content = content.replace(old_error, new_error)

# 13. set_pixmap
content = content.replace(
    '''        if self._playlist_delegate is not None and self._playlist_model is not None:
            self._playlist_delegate.set_pixmap(url, pix)
            idx = self._playlist_model.index(row, 0)
            self._playlist_model.dataChanged.emit(idx, idx, [PlaylistModelRoles.TaskObjectRole])''',
    '''        if row < len(self._cards):
            self._cards[row].set_pixmap(pix)'''
)

content = content.replace(
    '''        if self._playlist_delegate is not None:
            self._playlist_delegate.set_pixmap(u, pixmap)

        if self._playlist_model is not None:
            for row in rows:
                idx = self._playlist_model.index(row, 0)
                self._playlist_model.dataChanged.emit(idx, idx, [PlaylistModelRoles.TaskObjectRole])''',
    '''        for row in rows:
            if row < len(self._cards):
                self._cards[row].set_pixmap(pixmap)'''
)

# 14. select_all etc
content = content.replace(
    '''        model = self._playlist_model
        if model is None:
            return
        for i in range(model.rowCount()):
            idx = model.index(i, 0)
            task = model.get_task(idx)
            if task:
                task.selected = True
        model.dataChanged.emit(
            model.index(0, 0),
            model.index(model.rowCount() - 1, 0),
            [PlaylistModelRoles.TaskObjectRole],
        )''',
    '''        for card in self._cards:
            card.task.selected = True
            card.update()'''
)

content = content.replace(
    '''        model = self._playlist_model
        if model is None:
            return
        for i in range(model.rowCount()):
            idx = model.index(i, 0)
            task = model.get_task(idx)
            if task:
                task.selected = False
        model.dataChanged.emit(
            model.index(0, 0),
            model.index(model.rowCount() - 1, 0),
            [PlaylistModelRoles.TaskObjectRole],
        )''',
    '''        for card in self._cards:
            card.task.selected = False
            card.update()'''
)

content = content.replace(
    '''    def _invert_select(self) -> None:
        if self._playlist_model is None:
            return
        for row in range(self._playlist_model.rowCount()):
            idx = self._playlist_model.index(row, 0)
            task = self._playlist_model.get_task(idx)
            if task:
                task.selected = not task.selected
        self._playlist_model.dataChanged.emit(
            self._playlist_model.index(0, 0),
            self._playlist_model.index(self._playlist_model.rowCount() - 1, 0),
            [PlaylistModelRoles.TaskObjectRole],
        )''',
    '''    def _invert_select(self) -> None:
        for card in self._cards:
            card.task.selected = not card.task.selected
            card.update()'''
)

# 15. get_selected_rows
content = content.replace(
    '''    def _get_selected_rows(self) -> list[int]:
        if self._playlist_model is None:
            return []
        rows = []
        for i in range(self._playlist_model.rowCount()):
            idx = self._playlist_model.index(i, 0)
            task = self._playlist_model.get_task(idx)
            if task and task.selected:
                rows.append(i)
        return rows''',
    '''    def _get_selected_rows(self) -> list[int]:
        rows = []
        for i, card in enumerate(self._cards):
            if card.task.selected:
                rows.append(i)
        return rows'''
)

# 16. dataChanged in apply_preset_to_selected
content = content.replace(
    '''            if modified:
                if self._playlist_model is not None:
                    idx = self._playlist_model.index(row, 0)
                    task = self._playlist_model.get_task(idx)
                    if task is not None:
                        task.custom_options.format = row_data["override_text"]
                        self._playlist_model.dataChanged.emit(idx, idx, [PlaylistModelRoles.TaskObjectRole])''',
    '''            if modified and row < len(self._cards):
                card = self._cards[row]
                card.task.custom_options.format = row_data["override_text"]
                card.update()'''
)

# 17. dataChanged in _auto_apply_row_preset
content = content.replace(
    '''        if self._playlist_model is not None:
            idx = self._playlist_model.index(row, 0)
            task = self._playlist_model.get_task(idx)
            if task is not None:
                task.custom_options.format = final_text
                self._playlist_model.dataChanged.emit(idx, idx, [PlaylistModelRoles.TaskObjectRole])''',
    '''        if row < len(self._cards):
            card = self._cards[row]
            card.task.custom_options.format = final_text
            card.update()'''
)


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
