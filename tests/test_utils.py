#!/usr/bin/env python3
"""Tests for utility functions."""

import os
import sys
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import (
    format_time,
    format_size,
    format_speed,
    is_mpegts_file,
    resolve_category,
    get_visual_width,
    pad_string,
    confirm_action,
    print_file_count_summary,
    print_confirmation_message,
)


class TestFormatTime:
    """Tests for format_time function."""

    def test_seconds_only(self):
        """Should format seconds correctly."""
        assert format_time(30) == "30s"
        assert format_time(0) == "0s"
        assert format_time(59) == "59s"

    def test_minutes_and_seconds(self):
        """Should format minutes and seconds."""
        assert format_time(60) == "1m 0s"
        assert format_time(90) == "1m 30s"
        assert format_time(3599) == "59m 59s"

    def test_hours_minutes_seconds(self):
        """Should format hours, minutes, and seconds."""
        assert format_time(3600) == "1h 0m 0s"
        assert format_time(3661) == "1h 1m 1s"
        assert format_time(7325) == "2h 2m 5s"

    def test_float_input(self):
        """Should handle float input."""
        assert format_time(30.5) == "30s"
        assert format_time(90.9) == "1m 30s"


class TestFormatSize:
    """Tests for format_size function."""

    def test_bytes(self):
        """Should format bytes correctly."""
        assert format_size(0) == "0 B"
        assert format_size(512) == "512 B"
        assert format_size(1023) == "1023 B"

    def test_kilobytes(self):
        """Should format kilobytes correctly."""
        assert format_size(1024) == "1.00 KB"
        assert format_size(1536) == "1.50 KB"
        assert format_size(1024 * 1023) == "1023.00 KB"

    def test_megabytes(self):
        """Should format megabytes correctly."""
        assert format_size(1024 * 1024) == "1.00 MB"
        assert format_size(1024 * 1024 * 500) == "500.00 MB"

    def test_gigabytes(self):
        """Should format gigabytes correctly."""
        assert format_size(1024 * 1024 * 1024) == "1.00 GB"
        assert format_size(1024 * 1024 * 1024 * 2.5) == "2.50 GB"


class TestFormatSpeed:
    """Tests for format_speed function."""

    def test_bytes_per_second(self):
        """Should format B/s correctly."""
        assert format_speed(512) == "512.00 B/s"

    def test_kilobytes_per_second(self):
        """Should format KB/s correctly."""
        assert format_speed(1024) == "1.00 KB/s"
        assert format_speed(1024 * 100) == "100.00 KB/s"

    def test_megabytes_per_second(self):
        """Should format MB/s correctly."""
        assert format_speed(1024 * 1024) == "1.00 MB/s"
        assert format_speed(1024 * 1024 * 50) == "50.00 MB/s"

    def test_gigabytes_per_second(self):
        """Should format GB/s correctly."""
        assert format_speed(1024 * 1024 * 1024) == "1.00 GB/s"


class TestIsMpegtsFile:
    """Tests for MPEG-TS file detection."""

    @patch("subprocess.run")
    def test_mpegts_detected(self, mock_run):
        """Should detect MPEG-TS files."""
        mock_run.return_value = Mock(returncode=0, stdout="mpegts\nMPEG-TS")
        assert is_mpegts_file("test.ts") is True

    @patch("subprocess.run")
    def test_non_mpegts_file(self, mock_run):
        """Should return False for non-MPEG-TS files."""
        mock_run.return_value = Mock(returncode=0, stdout="mp4\nMP4")
        assert is_mpegts_file("test.mp4") is False

    @patch("subprocess.run")
    def test_ffprobe_failure(self, mock_run):
        """Should return False when ffprobe fails."""
        mock_run.return_value = Mock(returncode=1, stdout="")
        assert is_mpegts_file("test.ts") is False

    @patch("subprocess.run")
    def test_ffprobe_exception(self, mock_run):
        """Should return False on exception."""
        mock_run.side_effect = FileNotFoundError()
        assert is_mpegts_file("test.ts") is False


class TestResolveCategory:
    """Tests for category resolution."""

    def test_exact_match(self):
        """Should return exact match."""
        mock_db = Mock()
        mock_db.list_categories.return_value = ["documents", "images", "videos"]

        result = resolve_category(mock_db, "documents")
        assert result == "documents"

    def test_wildcard_single_match(self):
        """Should return single wildcard match."""
        mock_db = Mock()
        mock_db.list_categories.return_value = ["documents", "images", "videos"]

        result = resolve_category(mock_db, "doc*")
        assert result == "documents"

    def test_wildcard_no_match(self):
        """Should return None when no wildcard match."""
        mock_db = Mock()
        mock_db.list_categories.return_value = ["documents", "images"]

        result = resolve_category(mock_db, "xyz*")
        assert result is None

    def test_new_category(self):
        """Should return input for new category (no wildcard)."""
        mock_db = Mock()
        mock_db.list_categories.return_value = ["documents", "images"]

        result = resolve_category(mock_db, "new_category")
        assert result == "new_category"

    def test_empty_categories(self):
        """Should return None when no categories exist."""
        mock_db = Mock()
        mock_db.list_categories.return_value = []

        result = resolve_category(mock_db, "anything")
        assert result is None

    def test_empty_wildcard_prefix(self):
        """Should return None for empty wildcard prefix."""
        mock_db = Mock()
        mock_db.list_categories.return_value = ["documents"]

        result = resolve_category(mock_db, "*")
        assert result is None


class TestGetVisualWidth:
    """Tests for visual width calculation."""

    def test_ascii_string(self):
        """Should calculate width of ASCII strings."""
        assert get_visual_width("hello") == 5
        assert get_visual_width("test123") == 7

    def test_empty_string(self):
        """Should handle empty strings."""
        assert get_visual_width("") == 0

    def test_wide_characters(self):
        """Should handle wide characters (CJK)."""
        width = get_visual_width("日本語")
        assert width == 6  # Each CJK character is 2 units wide


class TestPadString:
    """Tests for string padding."""

    def test_left_align(self):
        """Should left-align by default."""
        result = pad_string("test", 10)
        assert result == "test      "
        assert len(result) == 10

    def test_right_align(self):
        """Should right-align when specified."""
        result = pad_string("test", 10, align="right")
        assert result == "      test"

    def test_center_align(self):
        """Should center-align when specified."""
        result = pad_string("test", 10, align="center")
        assert result == "   test   "

    def test_no_padding_needed(self):
        """Should handle strings that don't need padding."""
        result = pad_string("test", 4)
        assert result == "test"

    def test_string_longer_than_width(self):
        """Should not truncate strings longer than width."""
        result = pad_string("testing", 4)
        assert result == "testing"


class TestConfirmAction:
    """Tests for user confirmation."""

    @patch("builtins.input", return_value="yes")
    def test_confirm_yes(self, mock_input):
        """Should return True for 'yes' response."""
        assert confirm_action("Confirm?") is True

    @patch("builtins.input", return_value="no")
    def test_confirm_no(self, mock_input):
        """Should return False for 'no' response."""
        assert confirm_action("Confirm?") is False

    @patch("builtins.input", return_value="y")
    def test_confirm_y_with_require_yes(self, mock_input):
        """Should return False for 'y' when require_yes=True."""
        assert confirm_action("Confirm?", require_yes=True) is False

    @patch("builtins.input", return_value="y")
    def test_confirm_y_without_require_yes(self, mock_input):
        """Should return True for 'y' when require_yes=False."""
        assert confirm_action("Confirm?", require_yes=False) is True

    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_confirm_keyboard_interrupt(self, mock_input):
        """Should return False on KeyboardInterrupt."""
        assert confirm_action("Confirm?") is False

    @patch("builtins.input", side_effect=EOFError)
    def test_confirm_eof_error(self, mock_input):
        """Should return False on EOFError."""
        assert confirm_action("Confirm?") is False


class TestPrintFileCountSummary:
    """Tests for file count summary output."""

    def test_all_successful(self, capsys):
        """Should print success message."""
        print_file_count_summary(5, 0, "deleted")
        captured = capsys.readouterr()
        assert "5/5 files deleted successfully" in captured.out

    def test_some_failed(self, capsys):
        """Should print failure count."""
        print_file_count_summary(3, 2, "processed")
        captured = capsys.readouterr()
        assert "3/5 files processed successfully" in captured.out
        assert "2 files failed" in captured.out


class TestPrintConfirmationMessage:
    """Tests for confirmation message generation."""

    def test_normal_message(self):
        """Should generate normal confirmation message."""
        msg = print_confirmation_message("delete", 5, "files")
        assert "delete" in msg
        assert "5" in msg
        assert "files" in msg
        assert "GoFile servers" in msg

    def test_force_message(self):
        """Should generate force-mode message."""
        msg = print_confirmation_message("delete", 5, "files", force=True)
        assert "LOCAL DATABASE ONLY" in msg

    def test_irreversible_warning(self):
        """Should include irreversible warning by default."""
        msg = print_confirmation_message("delete", 5, "files")
        assert "IRREVERSIBLE" in msg

    def test_no_irreversible_warning(self):
        """Should exclude irreversible warning when specified."""
        msg = print_confirmation_message("delete", 5, "files", irreversible=False)
        assert "IRREVERSIBLE" not in msg


class TestEdgeCases:
    """Tests for edge cases."""

    def test_format_size_negative(self):
        """Should handle negative sizes."""
        result = format_size(-1024)
        assert "KB" in result or "B" in result

    def test_format_speed_zero(self):
        """Should handle zero speed."""
        assert format_speed(0) == "0.00 B/s"

    def test_format_time_negative(self):
        """Should handle negative time."""
        result = format_time(-30)
        assert "s" in result

    def test_pad_string_zero_width(self):
        """Should handle zero width."""
        result = pad_string("test", 0)
        assert result == "test"

    def test_get_visual_width_with_numbers(self):
        """Should handle numbers converted to strings."""
        assert get_visual_width(12345) == 5
