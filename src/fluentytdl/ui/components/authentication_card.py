"""
FluentYTDL 身份验证卡片组件

统一的身份验证 UI，包含：
- 验证源选择（浏览器/文件）
- 状态显示
- 刷新按钮
- 高级配置入口
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QVBoxLayout,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    FluentIcon,
    IconWidget,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    StrongBodyLabel,
    SwitchButton,
)

from ...auth.auth_service import (
    AuthSourceType,
    AuthStatus,
    auth_service,
)


class AuthenticationCard(CardWidget):
    """
    身份验证设置卡片

    简洁的 UI 设计：
    - 一个下拉框选择验证源
    - 状态指示器
    - 刷新按钮
    - 高级配置入口
    """

    sourceChanged = Signal(AuthSourceType)  # 验证源变更
    statusUpdated = Signal(AuthStatus)  # 状态更新

    def __init__(self, parent=None):
        super().__init__(parent)

        # 设置卡片固定高度，避免内容被裁剪
        self.setFixedHeight(140)

        self._init_ui()
        self._load_current_state()
        self._connect_signals()

        # 启动时自动刷新 Cookie（延迟执行，避免阻塞 UI 初始化）
        QTimer.singleShot(500, self._startup_refresh)

    def _init_ui(self):
        """初始化 UI"""
        # 主布局
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(20, 16, 20, 16)
        self.mainLayout.setSpacing(12)

        # === 标题行：图标 + 标题 + 描述 ===
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setSpacing(12)

        self.iconWidget = IconWidget(FluentIcon.FINGERPRINT, self)
        self.iconWidget.setFixedSize(20, 20)
        self.headerLayout.addWidget(self.iconWidget)

        self.titleLabel = StrongBodyLabel("身份验证", self)
        self.headerLayout.addWidget(self.titleLabel)

        self.descLabel = CaptionLabel("用于下载会员专属或年龄限制内容", self)
        self.descLabel.setStyleSheet("color: #888;")
        self.headerLayout.addWidget(self.descLabel)

        self.headerLayout.addStretch()

        self.mainLayout.addLayout(self.headerLayout)

        # === 控制行：验证源选择 + 操作按钮 ===
        self.controlLayout = QHBoxLayout()
        self.controlLayout.setSpacing(16)

        # === 第一行：验证源选择 + 刷新按钮 ===
        self.topRow = QHBoxLayout()
        self.topRow.setSpacing(16)

        # 验证源选择
        self.sourceLabel = CaptionLabel("验证源", self)
        self.topRow.addWidget(self.sourceLabel)

        self.sourceCombo = ComboBox(self)
        self.sourceCombo.setMinimumWidth(180)
        self._populate_source_combo()
        self.topRow.addWidget(self.sourceCombo)

        # 文件选择按钮（仅在选择"手动导入"时显示）
        self.fileSelectBtn = PushButton("选择文件", self)
        self.fileSelectBtn.setIcon(FluentIcon.FOLDER)
        self.fileSelectBtn.setFixedWidth(100)
        self.fileSelectBtn.setVisible(False)
        self.topRow.addWidget(self.fileSelectBtn)

        self.topRow.addStretch()

        # 自动刷新开关
        self.autoRefreshLabel = CaptionLabel("自动刷新", self)
        self.topRow.addWidget(self.autoRefreshLabel)

        self.autoRefreshSwitch = SwitchButton(self)
        self.autoRefreshSwitch.setChecked(auth_service.auto_refresh)
        self.topRow.addWidget(self.autoRefreshSwitch)

        # 刷新按钮
        self.refreshBtn = PrimaryPushButton("刷新", self)
        self.refreshBtn.setIcon(FluentIcon.SYNC)
        self.refreshBtn.setFixedWidth(90)
        self.topRow.addWidget(self.refreshBtn)

        self.mainLayout.addLayout(self.topRow)

        # === 第二行：状态显示 ===
        self.statusRow = QHBoxLayout()
        self.statusRow.setSpacing(8)

        self.statusIcon = IconWidget(FluentIcon.INFO, self)
        self.statusIcon.setFixedSize(16, 16)
        self.statusRow.addWidget(self.statusIcon)

        self.statusLabel = BodyLabel("未验证", self)
        self.statusRow.addWidget(self.statusLabel)

        self.statusRow.addSpacing(16)

        self.lastUpdateLabel = CaptionLabel("", self)
        self.lastUpdateLabel.setStyleSheet("color: #888;")
        self.statusRow.addWidget(self.lastUpdateLabel)

        self.statusRow.addStretch()

        self.mainLayout.addLayout(self.statusRow)

    def _populate_source_combo(self):
        """填充验证源下拉框"""
        # QFluentWidgets ComboBox 不支持 itemData，使用索引映射
        # Chromium 内核浏览器需要管理员权限，Firefox 内核无需管理员权限
        self._source_map = [
            AuthSourceType.EDGE,
            AuthSourceType.CHROME,
            AuthSourceType.CHROMIUM,
            AuthSourceType.BRAVE,
            AuthSourceType.OPERA,
            AuthSourceType.OPERA_GX,
            AuthSourceType.VIVALDI,
            AuthSourceType.ARC,
            AuthSourceType.FIREFOX,
            AuthSourceType.LIBREWOLF,
            AuthSourceType.FILE,
        ]
        self.sourceCombo.addItem("🌐 Edge 浏览器 (需管理员)")
        self.sourceCombo.addItem("🌐 Chrome 浏览器 (⚠️不稳定)")
        self.sourceCombo.addItem("🌐 Chromium 浏览器 (需管理员)")
        self.sourceCombo.addItem("🦁 Brave 浏览器 (需管理员)")
        self.sourceCombo.addItem("🌐 Opera 浏览器 (需管理员)")
        self.sourceCombo.addItem("🎮 Opera GX 浏览器 (需管理员)")
        self.sourceCombo.addItem("🌐 Vivaldi 浏览器 (需管理员)")
        self.sourceCombo.addItem("🌐 Arc 浏览器 (需管理员)")
        self.sourceCombo.addItem("🦊 Firefox 浏览器")
        self.sourceCombo.addItem("🦊 LibreWolf 浏览器")
        self.sourceCombo.addItem("📄 手动导入 (cookies.txt)")

    def _get_source_at_index(self, index: int) -> AuthSourceType | None:
        """获取指定索引的验证源类型"""
        if 0 <= index < len(self._source_map):
            return self._source_map[index]
        return None

    def _get_index_for_source(self, source: AuthSourceType) -> int:
        """获取验证源对应的索引"""
        try:
            return self._source_map.index(source)
        except ValueError:
            return 0

    def _load_current_state(self):
        """加载当前状态"""
        # 设置当前选中的验证源
        current = auth_service.current_source
        index = self._get_index_for_source(current)
        self.sourceCombo.setCurrentIndex(index)

        # 更新状态显示
        self._update_status_display(auth_service.last_status)

        # 显示/隐藏文件选择按钮
        self.fileSelectBtn.setVisible(current == AuthSourceType.FILE)

    def _startup_refresh(self):
        """启动时自动刷新 Cookie"""
        from ...utils.admin_utils import is_admin

        current_source = auth_service.current_source

        # 如果是 Edge/Chrome 且非管理员，显示提示但不弹对话框（启动时不打扰用户）
        if current_source.value in ["edge", "chrome"] and not is_admin():
            browser_name = auth_service.current_source_display
            self.statusLabel.setText(f"⚠️ {browser_name} 需要管理员权限")
            self.refreshBtn.setEnabled(True)
            # 发射信号通知需要管理员权限
            self.statusUpdated.emit(
                AuthStatus(
                    valid=False, message=f"{browser_name} v130+ 需要管理员权限才能提取 Cookie"
                )
            )
            return

        # 显示正在刷新状态
        self.statusLabel.setText("正在自动获取 Cookie...")
        self.refreshBtn.setEnabled(False)

        # 异步执行刷新
        QTimer.singleShot(100, self._perform_startup_refresh)

    def _perform_startup_refresh(self):
        """执行启动时刷新"""
        try:
            status = auth_service.startup_refresh()
            self._update_status_display(status)
            self.statusUpdated.emit(status)

            if status.valid:
                self._show_success("Cookie 验证成功")
            else:
                # 不显示错误提示，只更新状态
                pass
        except Exception as e:
            self._update_status_display(AuthStatus(valid=False, message=str(e)))
        finally:
            self.refreshBtn.setEnabled(True)

    def _connect_signals(self):
        """连接信号"""
        self.sourceCombo.currentIndexChanged.connect(self._on_source_changed)
        self.refreshBtn.clicked.connect(self._on_refresh_clicked)
        self.fileSelectBtn.clicked.connect(self._on_file_select_clicked)
        self.autoRefreshSwitch.checkedChanged.connect(self._on_auto_refresh_changed)

    def _on_source_changed(self, index: int):
        """验证源变更"""
        source = self._get_source_at_index(index)
        if source is None:
            return

        # 显示/隐藏文件选择按钮
        self.fileSelectBtn.setVisible(source == AuthSourceType.FILE)

        if source == AuthSourceType.FILE:
            # 手动导入模式：等待用户选择文件
            self.statusLabel.setText("请选择 cookies.txt 文件")
            self._update_status_icon(False)
        else:
            # 浏览器模式：检查 rookiepy
            if not auth_service.available:
                self._show_error("rookiepy 未安装，无法从浏览器提取 Cookie")
                self.sourceCombo.setCurrentIndex(0)
                return

            # 设置并尝试刷新
            auth_service.set_source(source, auto_refresh=self.autoRefreshSwitch.isChecked())
            self._do_refresh()

        self.sourceChanged.emit(source)

    def _on_refresh_clicked(self):
        """刷新按钮点击"""
        # 确保使用当前 UI 选中的验证源
        current_index = self.sourceCombo.currentIndex()
        source = self._get_source_at_index(current_index)

        if source is None:
            self._show_warning("请先选择验证源")
            return

        if source == AuthSourceType.FILE:
            self._show_warning("文件模式不支持刷新，请重新选择文件")
            return

        # 确保 AuthService 使用当前选中的验证源
        if auth_service.current_source != source:
            auth_service.set_source(source, auto_refresh=self.autoRefreshSwitch.isChecked())

        self._do_refresh()

    def _do_refresh(self):
        """执行刷新"""
        self.refreshBtn.setEnabled(False)
        self.statusLabel.setText("正在刷新...")

        # 使用 QTimer 避免阻塞 UI
        QTimer.singleShot(100, self._perform_refresh)

    def _perform_refresh(self):
        """实际执行刷新"""
        try:
            status = auth_service.refresh_now()
            self._update_status_display(status)
            self.statusUpdated.emit(status)

            if status.valid:
                self._show_success("Cookie 刷新成功")
            else:
                self._show_warning(status.message)

        except Exception as e:
            self._show_error(f"刷新失败: {e}")
            self._update_status_display(AuthStatus(valid=False, message=str(e)))
        finally:
            self.refreshBtn.setEnabled(True)

    def _on_file_select_clicked(self):
        """选择文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Cookies 文件",
            "",
            "Cookie Files (*.txt);;All Files (*)",
        )

        if not file_path:
            return

        # 验证并导入文件到缓存
        status = auth_service.import_manual_cookie_file(file_path)

        if status.valid:
            # 设置验证源
            auth_service.set_source(
                AuthSourceType.FILE,
                file_path=file_path,
                auto_refresh=False,
            )
            self._update_status_display(status)
            self._show_success("Cookie 文件已导入")
        else:
            self._show_error(status.message)

    def _on_auto_refresh_changed(self, checked: bool):
        """自动刷新开关变更"""
        current = auth_service.current_source
        file_path = auth_service._current_file_path
        auth_service.set_source(current, file_path=file_path, auto_refresh=checked)

    def _update_status_display(self, status: AuthStatus):
        """更新状态显示"""
        self.statusLabel.setText(status.message)
        self._update_status_icon(status.valid)

        if status.last_updated:
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(status.last_updated)
                self.lastUpdateLabel.setText(f"更新于 {dt.strftime('%H:%M:%S')}")
            except Exception:
                self.lastUpdateLabel.setText("")
        else:
            self.lastUpdateLabel.setText("")

        # 显示账户提示
        if status.account_hint:
            self.statusLabel.setText(f"{status.message} ({status.account_hint})")

    def _update_status_icon(self, valid: bool):
        """更新状态图标"""
        if valid:
            from qfluentwidgets import themeColor

            self.statusIcon.setIcon(FluentIcon.ACCEPT)
            self.statusIcon.setStyleSheet(f"color: {themeColor().name()};")
        else:
            self.statusIcon.setIcon(FluentIcon.INFO)
            self.statusIcon.setStyleSheet("color: #797775;")

    def _show_success(self, message: str):
        """显示成功提示"""
        InfoBar.info(
            title="成功",
            content=message,
            duration=2000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    def _show_warning(self, message: str):
        """显示警告提示"""
        InfoBar.warning(
            title="警告",
            content=message,
            duration=3000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    def _show_error(self, message: str):
        """显示错误提示"""
        InfoBar.error(
            title="错误",
            content=message,
            duration=4000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )
