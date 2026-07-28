import os
import sys
from io import BytesIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.fluentytdl.core.section_download import (
    SectionCutMode,
    build_section_cli_args,
    build_section_opts,
    parse_time_range,
    section_filename_suffix,
)
from src.fluentytdl.download.executor import _iter_process_output
from src.fluentytdl.download.output_parser import YtDlpOutputParser
from src.fluentytdl.utils.clean_logger import CleanLogger
from src.fluentytdl.youtube.yt_dlp_cli import ydl_opts_to_cli_args


def test_section_modes_build_expected_yt_dlp_options():
    time_range = parse_time_range("1:00", "1:30")

    coarse = build_section_opts(time_range, SectionCutMode.COARSE)
    precise = build_section_opts(time_range, SectionCutMode.PRECISE)

    assert coarse["download_sections"] == "*60.0-90.0"
    assert coarse["__fluentytdl_section_cut_mode"] == "coarse"
    assert "force_keyframes_at_cuts" not in coarse
    assert precise["force_keyframes_at_cuts"] is True
    assert build_section_cli_args(time_range, SectionCutMode.COARSE) == [
        "--download-sections",
        "*60.0-90.0",
    ]
    assert (
        build_section_cli_args(time_range, SectionCutMode.PRECISE)[-1]
        == "--force-keyframes-at-cuts"
    )
    assert section_filename_suffix(time_range) == " [clip 00-01-00-00-01-30]"

    assert "--force-keyframes-at-cuts" not in ydl_opts_to_cli_args(coarse)
    assert "--force-keyframes-at-cuts" in ydl_opts_to_cli_args(precise)


def test_postprocess_parser_keeps_machine_readable_lifecycle():
    parsed = YtDlpOutputParser().parse_line("FLUENTYTDL|postprocess|started|ModifyChapters")

    assert parsed.type == "postprocess"
    assert parsed.postprocessor == "ModifyChapters"
    assert parsed.postprocessor_status == "started"


def test_ffmpeg_parser_keeps_written_bytes_and_media_time():
    parsed = YtDlpOutputParser().parse_line(
        "frame= 900 fps=0.0 q=-1.0 size=   12345kB time=00:10:00.00 bitrate= 168.5kbits/s speed=2.50x"
    )

    assert parsed.type == "ffmpeg_progress"
    assert parsed.progress.info_dict["time_sec"] == 600.0
    assert parsed.progress.info_dict["output_bytes"] == 12_345_000
    assert parsed.progress.info_dict["speed"] == "2.50x"


def test_process_output_reader_emits_carriage_return_ffmpeg_updates():
    frames = list(_iter_process_output(BytesIO(b"first\rsize= 1kB time=00:00:01.00 speed=1.0x\r")))

    assert frames == [b"first", b"size= 1kB time=00:00:01.00 speed=1.0x"]


def test_clean_logger_uses_clip_duration_only_for_precise_modify_chapters():
    events = []
    logger = CleanLogger(
        lambda state, pct, text: events.append((state, pct, text)),
        duration=3600,
        section_cut_mode="precise",
        section_duration=60,
    )

    logger.handle_progress(
        {"status": "postprocess", "postprocessor": "Merger", "pp_status": "started"}
    )
    logger.handle_progress({"status": "ffmpeg_progress", "time_sec": 30, "speed": "2.0x"})
    assert "精确裁切" not in events[-1][2]

    logger.handle_progress(
        {"status": "postprocess", "postprocessor": "ModifyChapters", "pp_status": "started"}
    )
    logger.handle_progress({"status": "ffmpeg_progress", "time_sec": 30, "speed": "2.0x"})
    assert events[-1][0] == "processing"
    assert events[-1][1] == 97.0
    assert "精确裁切与重编码 50.0%" in events[-1][2]


def test_clean_logger_reports_ffmpeg_coarse_section_as_download_progress():
    events = []
    logger = CleanLogger(
        lambda state, pct, text: events.append((state, pct, text)),
        section_cut_mode="coarse",
        section_duration=60,
        section_start=120,
    )

    logger.handle_progress(
        {"status": "ffmpeg_progress", "time_sec": 150, "speed": "1.5x", "output_bytes": 2_000_000}
    )

    assert events[-1][0] == "downloading"
    assert events[-1][1] == 47.5
    assert "裁切下载 · 媒体流 50.0%" in events[-1][2]
    assert "已写入 1.91MB" in events[-1][2]


def test_clean_logger_falls_back_to_part_file_progress_when_ffmpeg_is_silent():
    events = []
    logger = CleanLogger(
        lambda state, pct, text: events.append((state, pct, text)),
        section_cut_mode="coarse",
        section_stream_layout="video_audio",
        section_estimated_bytes=4_000_000,
    )

    logger.handle_progress(
        {"status": "section_file_progress", "output_bytes": 2_000_000, "speed": 500_000}
    )

    assert events[-1][0] == "downloading"
    assert events[-1][1] == 47.5
    assert "视频 + 音频分流" in events[-1][2]
    assert "488.28KB/s" in events[-1][2]
