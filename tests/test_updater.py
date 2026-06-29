"""Tests for the standalone updater module (no Qt/network dependencies)."""

import importlib.util
import os
import sys
import zipfile
from pathlib import Path

import pytest

# Load updater.py directly via importlib to avoid triggering
# fluentytdl.core.__init__ -> config_manager -> PySide6 import chain.
_updater_path = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "fluentytdl"
    / "core"
    / "updater.py"
)
_spec = importlib.util.spec_from_file_location("_updater_under_test", _updater_path)
_updater_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_updater_mod)

_move_extracted_files = _updater_mod._move_extracted_files
_verify_extraction = _updater_mod._verify_extraction
extract_archive = _updater_mod.extract_archive
request_admin_if_needed = _updater_mod.request_admin_if_needed
self_delete = _updater_mod.self_delete
wait_for_process = _updater_mod.wait_for_process


class TestWaitForProcess:
    def test_nonexistent_pid_returns_true(self):
        """A PID that doesn't exist should return True immediately."""
        result = wait_for_process(99999, timeout=2)
        assert result is True

    def test_current_pid_times_out(self):
        """The current process is alive, so waiting should time out."""
        result = wait_for_process(os.getpid(), timeout=1)
        assert result is False


class TestExtractArchive:
    def test_zip_extraction(self, tmp_path):
        """Extracting a valid zip should produce the expected file."""
        # Create a zip with a test file
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("hello.txt", "world")

        dest = tmp_path / "out"
        dest.mkdir()
        extract_archive(zip_path, dest)
        assert (dest / "hello.txt").read_text() == "world"

    def test_unsupported_format_raises(self, tmp_path):
        """A .txt file should raise ValueError."""
        txt_path = tmp_path / "file.txt"
        txt_path.write_text("not an archive")
        with pytest.raises(ValueError, match="不支持的归档格式"):
            extract_archive(txt_path, tmp_path / "out")

    def test_7z_extraction_with_py7zr(self, tmp_path):
        """If py7zr is available, test 7z extraction."""
        py7zr = pytest.importorskip("py7zr")

        archive_path = tmp_path / "test.7z"
        with py7zr.SevenZipFile(archive_path, "w") as zf:
            zf.writestr(b"hello 7z", "hello.txt")

        dest = tmp_path / "out"
        dest.mkdir()
        extract_archive(archive_path, dest)
        assert (dest / "hello.txt").exists()


class TestRequestAdminIfNeeded:
    def test_user_directory_no_elevation(self, tmp_path):
        """A non-Program-Files directory should not request elevation."""
        result = request_admin_if_needed(tmp_path)
        assert result is False

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_local_appdata_no_elevation(self):
        """LOCALAPPDATA directory should not request elevation."""
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        if local.exists():
            result = request_admin_if_needed(local / "FluentYTDL")
            assert result is False


class TestSelfDelete:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_self_delete_creates_process(self, tmp_path):
        """self_delete should spawn a cmd process without raising."""
        fake_exe = tmp_path / "fake.exe"
        fake_exe.write_bytes(b"MZ")
        # Should not raise
        self_delete(fake_exe)


class TestVerifyExtraction:
    def test_valid_extraction_passes(self, tmp_path):
        """A complete extraction with exe, _internal, and VERSION should pass."""
        (tmp_path / "FluentYTDL.exe").write_bytes(b"MZ" + b"\x00" * 100)
        internal = tmp_path / "_internal"
        internal.mkdir()
        (internal / "python311.dll").write_bytes(b"dll")
        (tmp_path / "VERSION").write_text("v-3.0.18")

        assert _verify_extraction(tmp_path, "FluentYTDL.exe") is True

    def test_missing_exe_fails(self, tmp_path):
        """Missing exe should fail verification."""
        internal = tmp_path / "_internal"
        internal.mkdir()
        (internal / "lib.dll").write_bytes(b"dll")

        assert _verify_extraction(tmp_path, "FluentYTDL.exe") is False

    def test_empty_exe_fails(self, tmp_path):
        """Zero-byte exe should fail verification."""
        (tmp_path / "FluentYTDL.exe").write_bytes(b"")
        internal = tmp_path / "_internal"
        internal.mkdir()
        (internal / "lib.dll").write_bytes(b"dll")

        assert _verify_extraction(tmp_path, "FluentYTDL.exe") is False

    def test_empty_internal_fails(self, tmp_path):
        """Empty _internal/ should fail verification."""
        (tmp_path / "FluentYTDL.exe").write_bytes(b"MZ" + b"\x00" * 100)
        (tmp_path / "_internal").mkdir()

        assert _verify_extraction(tmp_path, "FluentYTDL.exe") is False

    def test_missing_internal_fails(self, tmp_path):
        """Missing _internal/ should fail verification."""
        (tmp_path / "FluentYTDL.exe").write_bytes(b"MZ" + b"\x00" * 100)

        assert _verify_extraction(tmp_path, "FluentYTDL.exe") is False


class TestMoveExtractedFiles:
    def test_move_all_files(self, tmp_path):
        """All files from tmp_dir should be moved to dest_dir."""
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "FluentYTDL.exe").write_bytes(b"MZ")
        (src / "VERSION").write_text("v-3.0.18")
        docs = src / "docs"
        docs.mkdir()
        (docs / "README.md").write_text("hello")

        assert _move_extracted_files(src, dest) is True

        assert (dest / "FluentYTDL.exe").exists()
        assert (dest / "VERSION").read_text() == "v-3.0.18"
        assert (dest / "docs" / "README.md").read_text() == "hello"
        # Source should be empty after move
        assert not any(src.iterdir())

    def test_move_overwrites_existing(self, tmp_path):
        """Existing files in dest should be overwritten."""
        src = tmp_path / "src"
        dest = tmp_path / "dest"
        src.mkdir()
        dest.mkdir()

        (src / "VERSION").write_text("v-3.0.19")
        (dest / "VERSION").write_text("v-3.0.18")  # old version

        assert _move_extracted_files(src, dest) is True
        assert (dest / "VERSION").read_text() == "v-3.0.19"
