"""Regression tests for warning propagation from yt-dlp output."""

import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fluentytdl.download.executor import DownloadExecutor


@patch("fluentytdl.download.executor.resolve_yt_dlp_exe", return_value=Path("yt-dlp.exe"))
@patch("fluentytdl.download.executor.subprocess.Popen")
def test_warning_lines_reach_status_callback(mock_popen, _mock_resolve):
    output = b"\n".join(
        [
            b"[download] Destination: fake_video.mp4",
            b"WARNING: [youtube] no formats available; falling back to another format",
            b"FLUENTYTDL|download|1048576|10485760|NA|1048576|9|avc1|mp4a|mp4|fake_video.mp4",
            b"WARNING: requested format not available",
            b"FLUENTYTDL|download|10485760|10485760|NA|1048576|0|avc1|mp4a|mp4|fake_video.mp4",
        ]
    )

    process = MagicMock()
    process.stdout = BytesIO(output)
    process.wait.return_value = 0
    process.returncode = 0
    mock_popen.return_value = process

    statuses: list[str] = []
    progress_events: list[dict] = []

    result = DownloadExecutor().execute(
        url="https://youtube.com/watch?v=mock_id_456",
        ydl_opts={"format": "best_mp4"},
        on_progress=progress_events.append,
        on_status=statuses.append,
        on_path=lambda _path: None,
        cancel_check=lambda: False,
    )

    warnings = [message for message in statuses if message.startswith("⚠️ ")]
    assert warnings == [
        "⚠️ [youtube] no formats available; falling back to another format",
        "⚠️ requested format not available",
    ]
    assert [event["downloaded_bytes"] for event in progress_events] == [1048576, 10485760]
    assert result is not None and result.endswith("fake_video.mp4")
