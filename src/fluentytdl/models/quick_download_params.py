from dataclasses import dataclass, field
from typing import Literal


@dataclass
class QuickDownloadParams:
    """快速下载模式的参数配置。"""

    # 基础类型
    download_type: Literal["video_audio", "video_only", "audio_only"] = "video_audio"

    # 质量控制
    max_height: int | None = None

    # 容器与格式（"自动推断" 或 None 时不强制）
    container: str | None = None
    audio_format: str | None = None
    audio_quality: int | None = None

    # 元数据
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    download_thumbnail: bool = False

    # 字幕
    subtitle_enabled: bool = False
    subtitle_languages: list[str] = field(default_factory=lambda: ["zh-Hans", "en"])
    subtitle_auto_captions: bool = False
    subtitle_embed: bool = True

    # SponsorBlock
    sponsorblock_enabled: bool = False
    sponsorblock_action: Literal["remove", "mark"] = "mark"
    sponsorblock_categories: str = "sponsor,intro,outro,selfpromo,interaction"

    # 播放列表
    playlist_strategy: Literal["auto", "single_worker", "expand_all"] = "auto"

    # 下载位置
    download_dir: str | None = None
