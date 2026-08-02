"""Regression coverage for errors presented by the download error panel."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fluentytdl.models.errors import ErrorCode, YtDlpExecutionError
from fluentytdl.utils.error_parser import diagnose_error


def test_execution_error_context_maps_to_diagnosed_error():
    execution_error = YtDlpExecutionError(
        1,
        "ERROR: HTTP Error 403: Forbidden",
        {"error": {"_type": "DownloadError"}},
    )

    diagnosis = diagnose_error(
        execution_error.exit_code,
        execution_error.stderr,
        execution_error.parsed_json,
    )

    assert diagnosis.code == ErrorCode.HTTP_ERROR
    assert diagnosis.severity == "fatal"
    assert diagnosis.fix_action == "switch_proxy"
    assert "403" in diagnosis.user_title
