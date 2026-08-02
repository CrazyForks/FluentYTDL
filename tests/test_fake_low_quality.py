"""Automated regression tests for low-quality preflight detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fluentytdl.download.quality_guard import QualityGuard, QualityIntent


def test_low_quality_video_returns_actionable_warning():
    formats = [
        {"format_id": "1", "vcodec": "avc1", "acodec": "none", "height": 480},
        {"format_id": "2", "vcodec": "avc1", "acodec": "none", "height": 360},
        {"format_id": "3", "vcodec": "none", "acodec": "mp4a", "abr": 128},
    ]
    intent = QualityIntent(target_height=1080, download_type="video_audio")

    verdict = QualityGuard.preflight_quality_check(formats, intent)

    assert verdict.passed is False
    assert verdict.actual_height == 480
    assert verdict.deviation_severity == "major"
    assert "480p" in verdict.suggestion


def test_audio_only_download_ignores_video_height():
    formats = [{"format_id": "3", "vcodec": "none", "acodec": "mp4a", "abr": 128}]
    intent = QualityIntent(target_height=1080, download_type="audio_only")

    verdict = QualityGuard.preflight_quality_check(formats, intent)

    assert verdict.passed is True
