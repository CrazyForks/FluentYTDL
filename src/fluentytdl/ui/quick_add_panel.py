from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    ScrollArea,
    SubtitleLabel,
    SwitchButton,
    TextEdit,
    ToolButton,
)

from ..core.config_manager import config_manager
from ..models.quick_download_params import QuickDownloadParams


class QuickAddPanel(QWidget):
    """
    快速下载面板 (批量导入)
    提供预设的下载选项，跳过解析详情直接开始。
    """

    download_requested = Signal(list, object)  # urls, params

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("quickAddPanel")

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(30, 30, 30, 30)
        self.vBoxLayout.setSpacing(20)

        # Container inside ScrollArea
        self.scrollArea = ScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setStyleSheet(
            "QScrollArea { background-color: transparent; border: none; }"
        )
        self.scrollArea.viewport().setStyleSheet("background-color: transparent;")

        self.scrollWidget = QWidget()
        self.scrollWidget.setObjectName("scrollWidget")
        self.scrollWidget.setStyleSheet("#scrollWidget { background-color: transparent; }")
        self.scrollLayout = QVBoxLayout(self.scrollWidget)
        self.scrollLayout.setContentsMargins(0, 0, 0, 0)
        self.scrollLayout.setSpacing(20)
        self.scrollLayout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.scrollArea.setWidget(self.scrollWidget)
        self.vBoxLayout.addWidget(self.scrollArea)

        self.scrollLayout.addStretch(1)

        # 1. 顶部标题
        self.titleLabel = SubtitleLabel("快速下载 (批量)", self)
        self.scrollLayout.addWidget(self.titleLabel)

        # 2. 核心操作区 (卡片风格)
        self.inputCard = CardWidget(self)
        self.inputCard.setMaximumWidth(760)
        self.cardLayout = QVBoxLayout(self.inputCard)
        self.cardLayout.setContentsMargins(20, 20, 20, 20)
        self.cardLayout.setSpacing(15)

        self.instructionLabel = BodyLabel(
            "每行输入一个链接，可粘贴多个 YouTube 视频/频道/播放列表链接", self
        )
        self.cardLayout.addWidget(self.instructionLabel)

        self.urlInput = TextEdit(self)
        self.urlInput.setPlaceholderText(
            "https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/playlist?list=..."
        )
        self.urlInput.setMinimumHeight(120)
        self.urlInput.setAcceptRichText(False)
        self.cardLayout.addWidget(self.urlInput)

        # 预设参数区
        self.presetLayout = QVBoxLayout()
        self.presetLayout.setSpacing(12)

        # 行 1: 下载类型 & 画质
        row1 = QHBoxLayout()

        self.typeCombo = ComboBox()
        self.typeCombo.addItem("音视频", userData="video_audio")
        self.typeCombo.addItem("仅视频", userData="video_only")
        self.typeCombo.addItem("仅音频", userData="audio_only")
        row1.addWidget(BodyLabel("类型:"), 0)
        row1.addWidget(self.typeCombo, 1)

        self.qualityCombo = ComboBox()
        self.qualityCombo.addItem("最佳 (自动)", userData=None)
        self.qualityCombo.addItem("4K (2160p)", userData=2160)
        self.qualityCombo.addItem("1080p", userData=1080)
        self.qualityCombo.addItem("720p", userData=720)
        row1.addWidget(BodyLabel("画质上限:"), 0)
        row1.addWidget(self.qualityCombo, 1)

        self.containerCombo = ComboBox()
        self.containerCombo.addItem("最佳兼容 (自动)", userData=None)
        self.containerCombo.addItem("MP4", userData="mp4")
        self.containerCombo.addItem("MKV", userData="mkv")
        row1.addWidget(BodyLabel("格式:"), 0)
        row1.addWidget(self.containerCombo, 1)

        self.presetLayout.addLayout(row1)

        # 行 1.5: 音频设置
        row_audio = QHBoxLayout()

        self.audioFormatCombo = ComboBox()
        self.audioFormatCombo.addItem("自动推断", userData=None)
        self.audioFormatCombo.addItem("M4A", userData="m4a")
        self.audioFormatCombo.addItem("MP3", userData="mp3")
        self.audioFormatCombo.addItem("FLAC", userData="flac")
        self.audioFormatCombo.addItem("WAV", userData="wav")
        row_audio.addWidget(BodyLabel("音频格式:"), 0)
        row_audio.addWidget(self.audioFormatCombo, 1)

        self.audioQualityCombo = ComboBox()
        self.audioQualityCombo.addItem("最佳 (自动)", userData=None)
        self.audioQualityCombo.addItem("320 kbps", userData=320)
        self.audioQualityCombo.addItem("256 kbps", userData=256)
        self.audioQualityCombo.addItem("192 kbps", userData=192)
        self.audioQualityCombo.addItem("128 kbps", userData=128)
        row_audio.addWidget(BodyLabel("音频比特率:"), 0)
        row_audio.addWidget(self.audioQualityCombo, 1)

        self.presetLayout.addLayout(row_audio)

        # 行 2: 开关选项
        row2 = QHBoxLayout()

        self.metaSwitch = SwitchButton()
        self.metaSwitch.setOnText("嵌入元数据")
        self.metaSwitch.setOffText("嵌入元数据")
        self.metaSwitch.setChecked(True)
        row2.addWidget(self.metaSwitch)

        self.thumbSwitch = SwitchButton()
        self.thumbSwitch.setOnText("嵌入封面")
        self.thumbSwitch.setOffText("嵌入封面")
        self.thumbSwitch.setChecked(True)
        row2.addWidget(self.thumbSwitch)

        self.subSwitch = SwitchButton()
        self.subSwitch.setOnText("下载字幕")
        self.subSwitch.setOffText("下载字幕")
        row2.addWidget(self.subSwitch)

        row2.addStretch(1)
        self.presetLayout.addLayout(row2)

        # 行 3: 播放列表策略 & 下载位置
        row3 = QHBoxLayout()

        self.strategyCombo = ComboBox()
        self.strategyCombo.addItem("自动判断", userData="auto")
        self.strategyCombo.addItem("单任务整包", userData="single_worker")
        self.strategyCombo.addItem("强制展开", userData="expand_all")
        row3.addWidget(BodyLabel("播放列表:"), 0)
        row3.addWidget(self.strategyCombo, 1)

        row3.addWidget(BodyLabel("保存到:"), 0)
        self.dirInput = LineEdit()
        self.dirInput.setPlaceholderText("默认下载目录")
        self.dirInput.setMinimumWidth(200)
        row3.addWidget(self.dirInput, 2)

        self.browseBtn = ToolButton(FluentIcon.FOLDER)
        self.browseBtn.clicked.connect(self._browse_dir)
        row3.addWidget(self.browseBtn, 0)

        self.presetLayout.addLayout(row3)

        self.cardLayout.addLayout(self.presetLayout)

        # 按钮行 (右对齐)
        self.btnLayout = QHBoxLayout()
        self.btnLayout.addStretch(1)

        self.startBtn = PrimaryPushButton(FluentIcon.DOWNLOAD, "直接下载", self)
        self.startBtn.setMinimumWidth(120)
        self.startBtn.clicked.connect(self.on_start_clicked)

        self.btnLayout.addWidget(self.startBtn)
        self.cardLayout.addLayout(self.btnLayout)

        self.scrollLayout.addWidget(self.inputCard)
        self.scrollLayout.addStretch(1)

        # 绑定类型改变事件
        self.typeCombo.currentIndexChanged.connect(self._on_type_changed)
        self._on_type_changed()  # 初始化状态

        # 初始化与持久化
        config_manager.init_quick_mode_defaults()
        self._init_from_config()
        self._connect_signals_for_save()

    def _browse_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择下载目录", self.dirInput.text() or "")
        if folder:
            self.dirInput.setText(folder)

    def _init_from_config(self):
        def set_combo_by_data(combo: ComboBox, val):
            for i in range(combo.count()):
                if combo.itemData(i) == val:
                    combo.setCurrentIndex(i)
                    return

        set_combo_by_data(self.typeCombo, config_manager.get("quick_download_type", "video_audio"))
        set_combo_by_data(self.qualityCombo, config_manager.get("quick_video_quality", None))
        set_combo_by_data(self.containerCombo, config_manager.get("quick_container", None))
        set_combo_by_data(self.audioFormatCombo, config_manager.get("quick_audio_format", None))

        self.metaSwitch.setChecked(config_manager.get("quick_embed_metadata", True))
        self.thumbSwitch.setChecked(config_manager.get("quick_embed_thumbnail", True))
        self.subSwitch.setChecked(config_manager.get("quick_subtitle_enabled", False))

        set_combo_by_data(self.strategyCombo, config_manager.get("quick_playlist_strategy", "auto"))
        self.dirInput.setText(config_manager.get("quick_download_dir", ""))

    def _connect_signals_for_save(self):
        self.typeCombo.currentIndexChanged.connect(self._save_to_config)
        self.qualityCombo.currentIndexChanged.connect(self._save_to_config)
        self.containerCombo.currentIndexChanged.connect(self._save_to_config)
        self.audioFormatCombo.currentIndexChanged.connect(self._save_to_config)

        self.metaSwitch.checkedChanged.connect(self._save_to_config)
        self.thumbSwitch.checkedChanged.connect(self._save_to_config)
        self.subSwitch.checkedChanged.connect(self._save_to_config)

        self.strategyCombo.currentIndexChanged.connect(self._save_to_config)
        self.dirInput.textChanged.connect(self._save_to_config)

    def _save_to_config(self):
        config_manager.set("quick_download_type", self.typeCombo.currentData())
        config_manager.set("quick_video_quality", self.qualityCombo.currentData())
        config_manager.set("quick_container", self.containerCombo.currentData())
        config_manager.set("quick_audio_format", self.audioFormatCombo.currentData())

        config_manager.set("quick_embed_metadata", self.metaSwitch.isChecked())
        config_manager.set("quick_embed_thumbnail", self.thumbSwitch.isChecked())
        config_manager.set("quick_subtitle_enabled", self.subSwitch.isChecked())

        config_manager.set("quick_playlist_strategy", self.strategyCombo.currentData())
        config_manager.set("quick_download_dir", self.dirInput.text())

    def _on_type_changed(self):
        dt = self.typeCombo.currentData()
        if dt == "audio_only":
            self.qualityCombo.setEnabled(False)
            self.containerCombo.setEnabled(False)
            self.subSwitch.setEnabled(False)
            self.audioFormatCombo.setEnabled(True)
            self.audioQualityCombo.setEnabled(True)
        elif dt == "video_only":
            self.qualityCombo.setEnabled(True)
            self.containerCombo.setEnabled(True)
            self.subSwitch.setEnabled(True)
            self.audioFormatCombo.setEnabled(False)
            self.audioQualityCombo.setEnabled(False)
        else:
            self.qualityCombo.setEnabled(True)
            self.containerCombo.setEnabled(True)
            self.subSwitch.setEnabled(True)
            self.audioFormatCombo.setEnabled(True)
            self.audioQualityCombo.setEnabled(True)

    def on_start_clicked(self):
        text = self.urlInput.toPlainText().strip()
        if not text:
            InfoBar.warning(
                title="输入为空",
                content="请先输入或粘贴需要下载的链接。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window(),
            )
            return

        urls = []
        for line in text.split("\n"):
            line = line.strip()
            # 允许 ytsearch: 等 yt-dlp 支持的前缀，或者 http 链接
            if line and (
                line.startswith("http://")
                or line.startswith("https://")
                or line.startswith("ytsearch")
            ):
                urls.append(line)

        if not urls:
            InfoBar.warning(
                title="没有检测到有效链接",
                content="请确保每行包含以 http:// 或 https:// 开头的有效网址。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window(),
            )
            return

        params = QuickDownloadParams()
        params.download_type = self.typeCombo.currentData()
        params.max_height = self.qualityCombo.currentData()
        params.container = self.containerCombo.currentData()
        params.audio_format = self.audioFormatCombo.currentData()
        params.audio_quality = self.audioQualityCombo.currentData()

        params.embed_metadata = self.metaSwitch.isChecked()
        params.embed_thumbnail = self.thumbSwitch.isChecked()
        params.subtitle_enabled = self.subSwitch.isChecked()

        params.playlist_strategy = self.strategyCombo.currentData()
        dir_text = self.dirInput.text().strip()
        params.download_dir = dir_text if dir_text else None

        self.download_requested.emit(urls, params)
        self.urlInput.clear()
