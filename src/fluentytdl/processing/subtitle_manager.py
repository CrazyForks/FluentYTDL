"""
FluentYTDL 字幕管理模块

提供字幕下载、格式转换、双语合成等功能：
- 多语言字幕选择
- 格式转换 (SRT, ASS, VTT)
- 双语字幕合成
- 字幕嵌入
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from PySide6.QtCore import QT_TRANSLATE_NOOP

# 常见字幕语言代码映射
LANGUAGE_NAMES = {
    "zh-Hans": QT_TRANSLATE_NOOP("SubtitleManager", "中文(简体)"),
    "zh-Hant": QT_TRANSLATE_NOOP("SubtitleManager", "中文(繁体)"),
    "zh": QT_TRANSLATE_NOOP("SubtitleManager", "中文"),
    "en": QT_TRANSLATE_NOOP("SubtitleManager", "英语"),
    "ja": QT_TRANSLATE_NOOP("SubtitleManager", "日语"),
    "ko": QT_TRANSLATE_NOOP("SubtitleManager", "韩语"),
    "es": QT_TRANSLATE_NOOP("SubtitleManager", "西班牙语"),
    "fr": QT_TRANSLATE_NOOP("SubtitleManager", "法语"),
    "de": QT_TRANSLATE_NOOP("SubtitleManager", "德语"),
    "ru": QT_TRANSLATE_NOOP("SubtitleManager", "俄语"),
    "pt": QT_TRANSLATE_NOOP("SubtitleManager", "葡萄牙语"),
    "it": QT_TRANSLATE_NOOP("SubtitleManager", "意大利语"),
    "ar": QT_TRANSLATE_NOOP("SubtitleManager", "阿拉伯语"),
    "hi": QT_TRANSLATE_NOOP("SubtitleManager", "印地语"),
    "th": QT_TRANSLATE_NOOP("SubtitleManager", "泰语"),
    "vi": QT_TRANSLATE_NOOP("SubtitleManager", "越南语"),
    "id": QT_TRANSLATE_NOOP("SubtitleManager", "印尼语"),
    "auto": QT_TRANSLATE_NOOP("SubtitleManager", "自动生成"),
}

# UI显示用的常用语言列表（按使用频率和地区排序）
COMMON_SUBTITLE_LANGUAGES = [
    # 东亚地区（高频）
    ("zh-Hans", QT_TRANSLATE_NOOP("SubtitleManager", "中文(简体)")),
    ("zh-Hant", QT_TRANSLATE_NOOP("SubtitleManager", "中文(繁体)")),
    ("en", QT_TRANSLATE_NOOP("SubtitleManager", "英语")),
    ("ja", QT_TRANSLATE_NOOP("SubtitleManager", "日语")),
    ("ko", QT_TRANSLATE_NOOP("SubtitleManager", "韩语")),
    # 欧洲主要语言
    ("fr", QT_TRANSLATE_NOOP("SubtitleManager", "法语")),
    ("de", QT_TRANSLATE_NOOP("SubtitleManager", "德语")),
    ("es", QT_TRANSLATE_NOOP("SubtitleManager", "西班牙语")),
    ("pt", QT_TRANSLATE_NOOP("SubtitleManager", "葡萄牙语")),
    ("it", QT_TRANSLATE_NOOP("SubtitleManager", "意大利语")),
    ("ru", QT_TRANSLATE_NOOP("SubtitleManager", "俄语")),
    # 其他地区
    ("ar", QT_TRANSLATE_NOOP("SubtitleManager", "阿拉伯语")),
    ("hi", QT_TRANSLATE_NOOP("SubtitleManager", "印地语")),
    ("th", QT_TRANSLATE_NOOP("SubtitleManager", "泰语")),
    ("vi", QT_TRANSLATE_NOOP("SubtitleManager", "越南语")),
    ("id", QT_TRANSLATE_NOOP("SubtitleManager", "印尼语")),
    ("tr", QT_TRANSLATE_NOOP("SubtitleManager", "土耳其语")),
    ("nl", QT_TRANSLATE_NOOP("SubtitleManager", "荷兰语")),
    ("pl", QT_TRANSLATE_NOOP("SubtitleManager", "波兰语")),
    ("sv", QT_TRANSLATE_NOOP("SubtitleManager", "瑞典语")),
    ("no", QT_TRANSLATE_NOOP("SubtitleManager", "挪威语")),
]

# 支持的字幕格式
SUBTITLE_FORMATS = ["srt", "ass", "vtt", "lrc"]


class SubtitleSourceType(str, Enum):
    MANUAL = "manual"
    AUTO_GENERATED = "auto_generated"
    AUTO_TRANSLATED = "auto_translated"


@dataclass
class SubtitleTrack:
    """字幕轨道信息"""

    lang_code: str  # 语言代码 (如 "en", "zh-Hans")
    lang_name: str  # 语言名称 (如 "English", "中文")
    source_type: SubtitleSourceType  # 字幕来源类型
    ext: str  # 格式 (srt, vtt, ass)
    url: str | None = None  # 下载 URL
    name: str | None = None  # 显示名称
    is_original_lang: bool = False  # 是否是原语种

    @property
    def is_auto(self) -> bool:
        """向后兼容属性"""
        return self.source_type != SubtitleSourceType.MANUAL

    @property
    def quality_rank(self) -> int:
        """质量排序权重（越低越好）"""
        return {
            SubtitleSourceType.MANUAL: 0,
            SubtitleSourceType.AUTO_GENERATED: 1,
            SubtitleSourceType.AUTO_TRANSLATED: 2,
        }[self.source_type]

    @property
    def display_name(self) -> str:
        """获取显示名称"""
        from PySide6.QtCore import QCoreApplication
        name = LANGUAGE_NAMES.get(self.lang_code, self.lang_name or self.lang_code)
        
        # Translate the base language name
        translated_name = QCoreApplication.translate("SubtitleManager", name)
        
        if self.source_type == SubtitleSourceType.AUTO_GENERATED:
            translated_name += QCoreApplication.translate("SubtitleManager", " [自动生成]")
        elif self.source_type == SubtitleSourceType.AUTO_TRANSLATED:
            translated_name += QCoreApplication.translate("SubtitleManager", " [自动翻译]")
        return translated_name


def _lang_matches(lang1: str, lang2: str) -> bool:
    """简易语种匹配，忽略区域"""
    return lang1.split("-")[0].lower() == lang2.split("-")[0].lower()


def _detect_original_language(info: dict[str, Any]) -> str | None:
    """检测视频原始语种"""
    auto_caps = info.get("automatic_captions") or {}
    for lang_code in auto_caps:
        if lang_code.endswith("-orig"):
            return lang_code.replace("-orig", "")

    for lang_code, sub_list in auto_caps.items():
        if isinstance(sub_list, list) and sub_list:
            first = sub_list[0] if isinstance(sub_list[0], dict) else {}
            name = str(first.get("name", "")).lower()
            if "asr" in name or "auto-generated" in name:
                return lang_code

    lang = info.get("language")
    if isinstance(lang, str) and lang:
        return lang
    return None


def _is_asr_track(lang_code: str, sub_list: Any, original_lang: str | None) -> bool:
    """判断是否为 ASR 自动生成轨道"""
    if lang_code.endswith("-orig"):
        return True

    if original_lang and _lang_matches(lang_code, original_lang):
        return True

    if isinstance(sub_list, list) and sub_list:
        first = sub_list[0] if isinstance(sub_list[0], dict) else {}
        name = str(first.get("name", "")).lower()
        if "asr" in name or "auto-generated" in name:
            return True

    return False


def extract_subtitle_tracks(info: dict[str, Any]) -> list[SubtitleTrack]:
    """
    从视频信息中提取可用字幕轨道

    Args:
        info: yt-dlp 返回的视频信息

    Returns:
        字幕轨道列表
    """
    tracks = []

    # 检测原始语种
    original_lang = _detect_original_language(info)

    # 手动字幕
    subtitles = info.get("subtitles") or {}
    for lang_code, sub_list in subtitles.items():
        if not sub_list:
            continue
        # 取第一个格式
        sub = sub_list[0] if isinstance(sub_list, list) else sub_list
        tracks.append(
            SubtitleTrack(
                lang_code=lang_code,
                lang_name=sub.get("name", ""),
                source_type=SubtitleSourceType.MANUAL,
                ext=sub.get("ext", "vtt"),
                url=sub.get("url"),
                name=sub.get("name"),
            )
        )

    # 自动生成/翻译字幕
    auto_subs = info.get("automatic_captions") or {}
    for lang_code, sub_list in auto_subs.items():
        if not sub_list:
            continue
        sub = sub_list[0] if isinstance(sub_list, list) else sub_list
        is_asr = _is_asr_track(lang_code, sub_list, original_lang)
        source_type = (
            SubtitleSourceType.AUTO_GENERATED if is_asr else SubtitleSourceType.AUTO_TRANSLATED
        )
        tracks.append(
            SubtitleTrack(
                lang_code=lang_code,
                lang_name=sub.get("name", ""),
                source_type=source_type,
                ext=sub.get("ext", "vtt"),
                url=sub.get("url"),
                name=sub.get("name"),
                is_original_lang=(lang_code == original_lang),
            )
        )

    return tracks


def get_subtitle_languages(info: dict[str, Any]) -> list[dict[str, Any]]:
    """
    获取可用字幕语言列表（用于 UI 显示）

    Args:
        info: 视频信息

    Returns:
        [{"code": "en", "name": "英语", "auto": False}, ...]
    """
    tracks = extract_subtitle_tracks(info)

    # 去重：同一语言优先手动字幕
    seen = {}
    for t in tracks:
        key = t.lang_code
        if key not in seen or (not t.is_auto and seen[key]["auto"]):
            seen[key] = {
                "code": t.lang_code,
                "name": t.display_name,
                "auto": t.is_auto,
                "ext": t.ext,
            }

    # 排序：中文 > 英语 > 日语 > 其他
    priority = ["zh-Hans", "zh-Hant", "zh", "en", "ja", "ko"]

    def sort_key(item):
        code = item["code"]
        try:
            return (0, priority.index(code))
        except ValueError:
            return (1, code)

    return sorted(seen.values(), key=sort_key)


def convert_subtitle(
    input_path: str | Path,
    output_format: str,
    output_path: str | Path | None = None,
    ffmpeg_path: str | None = None,
) -> Path:
    """
    转换字幕格式

    Args:
        input_path: 输入字幕文件
        output_format: 目标格式 (srt, ass, vtt)
        output_path: 输出路径，None 则自动生成
        ffmpeg_path: ffmpeg 路径

    Returns:
        输出文件路径
    """
    input_path = Path(input_path)

    if output_format not in SUBTITLE_FORMATS:
        raise ValueError(f"不支持的字幕格式: {output_format}")

    if output_path is None:
        output_path = input_path.with_suffix(f".{output_format}")
    else:
        output_path = Path(output_path)

    # 使用 ffmpeg 转换
    ffmpeg = ffmpeg_path or "ffmpeg"
    cmd = [
        ffmpeg,
        "-y",  # 覆盖输出
        "-i",
        str(input_path),
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 转换失败: {result.stderr}")
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("字幕转换超时") from e

    return output_path
