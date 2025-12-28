#!/usr/bin/env python3
"""Tests for file_manager module."""

import os
import sys
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.file_manager import (
    find_file,
    delete_file_from_db,
    list_files,
    sort_by_name,
    sort_by_size,
    sort_by_date,
    sort_by_category,
    sort_by_expiry,
    sort_by_link,
)
from src.utils import DAYS


@pytest.fixture
def mock_db():
    """Create a mock database manager."""
    db = Mock()
    db.get_all_files.return_value = []
    db.get_file_by_id.return_value = None
    db.get_files_by_category.return_value = []
    db.get_folder_by_category.return_value = None
    return db


@pytest.fixture
def sample_files():
    """Create sample file data for testing."""
    now = datetime.now()
    return [
        {
            "id": "file1",
            "name": "alpha.txt",
            "size": 1024,
            "category": "docs",
            "upload_time": (now - timedelta(days=5)).isoformat(),
            "download_link": "https://gofile.io/d/abc123",
        },
        {
            "id": "file2",
            "name": "beta.pdf",
            "size": 2048,
            "category": "docs",
            "upload_time": (now - timedelta(days=3)).isoformat(),
            "download_link": "https://gofile.io/d/def456",
        },
        {
            "id": "file3",
            "name": "gamma.jpg",
            "size": 512,
            "category": "images",
            "upload_time": (now - timedelta(days=1)).isoformat(),
            "download_link": "https://gofile.io/d/ghi789",
        },
    ]


class TestFindFile:
    """Tests for find_file function."""

    def test_find_by_id(self, mock_db, sample_files):
        """Should find file by ID."""
        mock_db.get_all_files.return_value = sample_files
        mock_db.get_file_by_id.return_value = sample_files[0]

        result = find_file(mock_db, "file1")
        assert result is not None
        assert result["actual_id"] == "file1"
        assert result["name"] == "alpha.txt"

    def test_find_by_serial_id(self, mock_db, sample_files):
        """Should find file by serial ID."""
        mock_db.get_all_files.return_value = sample_files
        mock_db.get_file_by_id.return_value = None

        result = find_file(mock_db, "1")
        assert result is not None
        assert result["name"] == "alpha.txt"

    def test_find_by_name_single_match(self, mock_db, sample_files):
        """Should find file by exact name with single match."""
        mock_db.get_all_files.return_value = sample_files
        mock_db.get_file_by_id.return_value = None

        result = find_file(mock_db, "alpha.txt")
        assert result is not None
        assert result["name"] == "alpha.txt"

    def test_find_nonexistent_file(self, mock_db):
        """Should return None for nonexistent file."""
        mock_db.get_all_files.return_value = []
        mock_db.get_file_by_id.return_value = None

        result = find_file(mock_db, "nonexistent")
        assert result is None

    def test_find_nonexistent_serial_id(self, mock_db, sample_files):
        """Should return None for nonexistent serial ID."""
        mock_db.get_all_files.return_value = sample_files
        mock_db.get_file_by_id.return_value = None

        result = find_file(mock_db, "999")
        assert result is None


class TestDeleteFileFromDb:
    """Tests for delete_file_from_db function."""

    def test_delete_success(self, mock_db):
        """Should return True on successful deletion."""
        mock_db.delete_file.return_value = True

        result = delete_file_from_db(mock_db, "file123")
        assert result is True
        mock_db.delete_file.assert_called_once_with("file123")

    def test_delete_failure(self, mock_db):
        """Should return False on failed deletion."""
        mock_db.delete_file.return_value = False

        result = delete_file_from_db(mock_db, "nonexistent")
        assert result is False


class TestSortFunctions:
    """Tests for sorting functions."""

    def test_sort_by_name(self):
        """Should sort by name case-insensitively."""
        files = [
            {"name": "Zebra.txt"},
            {"name": "alpha.txt"},
            {"name": "Beta.txt"},
        ]
        sorted_files = sorted(files, key=sort_by_name)
        assert sorted_files[0]["name"] == "alpha.txt"
        assert sorted_files[1]["name"] == "Beta.txt"
        assert sorted_files[2]["name"] == "Zebra.txt"

    def test_sort_by_size(self):
        """Should sort by file size."""
        files = [
            {"size_bytes": 2048},
            {"size_bytes": 512},
            {"size_bytes": 1024},
        ]
        sorted_files = sorted(files, key=sort_by_size)
        assert sorted_files[0]["size_bytes"] == 512
        assert sorted_files[1]["size_bytes"] == 1024
        assert sorted_files[2]["size_bytes"] == 2048

    def test_sort_by_date(self):
        """Should sort by upload timestamp."""
        files = [
            {"upload_timestamp": 300},
            {"upload_timestamp": 100},
            {"upload_timestamp": 200},
        ]
        sorted_files = sorted(files, key=sort_by_date)
        assert sorted_files[0]["upload_timestamp"] == 100

    def test_sort_by_category(self):
        """Should sort by category case-insensitively."""
        files = [
            {"category": "Videos"},
            {"category": "documents"},
            {"category": "Images"},
        ]
        sorted_files = sorted(files, key=sort_by_category)
        assert sorted_files[0]["category"] == "documents"
        assert sorted_files[1]["category"] == "Images"
        assert sorted_files[2]["category"] == "Videos"

    def test_sort_by_expiry(self):
        """Should sort by expiry timestamp."""
        files = [
            {"expiry_timestamp": 300},
            {"expiry_timestamp": 100},
            {"expiry_timestamp": 200},
        ]
        sorted_files = sorted(files, key=sort_by_expiry)
        assert sorted_files[0]["expiry_timestamp"] == 100

    def test_sort_by_link(self):
        """Should sort by download link."""
        files = [
            {"download_link": "https://gofile.io/d/zzz"},
            {"download_link": "https://gofile.io/d/aaa"},
            {"download_link": "https://gofile.io/d/mmm"},
        ]
        sorted_files = sorted(files, key=sort_by_link)
        assert sorted_files[0]["download_link"].endswith("aaa")


class TestListFiles:
    """Tests for list_files function."""

    def test_list_files_empty(self, mock_db, capsys):
        """Should print message when no files found."""
        mock_db.get_all_files.return_value = []

        result = list_files(mock_db)
        assert result is False

        captured = capsys.readouterr()
        assert "No files found" in captured.out

    def test_list_files_with_data(self, mock_db, sample_files, capsys):
        """Should list files successfully."""
        mock_db.get_all_files.return_value = sample_files

        result = list_files(mock_db)
        assert result is True

        captured = capsys.readouterr()
        assert "alpha.txt" in captured.out

    def test_list_files_by_category(self, mock_db, sample_files, capsys):
        """Should filter files by category."""
        docs_files = [f for f in sample_files if f["category"] == "docs"]
        mock_db.get_files_by_category.return_value = docs_files
        mock_db.get_folder_by_category.return_value = {"folder_id": "f1"}

        result = list_files(mock_db, category="docs")
        assert result is True

    def test_list_files_nonexistent_category(self, mock_db, capsys):
        """Should show error for nonexistent category."""
        mock_db.get_folder_by_category.return_value = None

        result = list_files(mock_db, category="nonexistent")
        assert result is False

        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    def test_list_files_with_sorting(self, mock_db, sample_files):
        """Should sort files by specified field."""
        mock_db.get_all_files.return_value = sample_files

        result = list_files(mock_db, sort_field="name", sort_order="asc")
        assert result is True

    def test_list_files_descending_order(self, mock_db, sample_files):
        """Should sort files in descending order."""
        mock_db.get_all_files.return_value = sample_files

        result = list_files(mock_db, sort_field="size", sort_order="desc")
        assert result is True

    def test_list_files_pagination(self, mock_db, capsys):
        """Should paginate results."""
        many_files = [
            {
                "id": f"file{i}",
                "name": f"file{i}.txt",
                "size": 1024,
                "category": "test",
                "upload_time": datetime.now().isoformat(),
                "download_link": f"https://gofile.io/d/{i}",
            }
            for i in range(50)
        ]
        mock_db.get_all_files.return_value = many_files

        result = list_files(mock_db, page=2)
        assert result is True

        captured = capsys.readouterr()
        assert "Page 2" in captured.out

    def test_list_files_invalid_page(self, mock_db, sample_files):
        """Should handle invalid page numbers."""
        mock_db.get_all_files.return_value = sample_files

        result = list_files(mock_db, page=0)
        assert result is True

        result = list_files(mock_db, page=-1)
        assert result is True

    def test_list_files_with_max_filename_length(self, mock_db, capsys):
        """Should truncate long filenames."""
        files = [
            {
                "id": "f1",
                "name": "a" * 100 + ".txt",
                "size": 1024,
                "category": "test",
                "upload_time": datetime.now().isoformat(),
                "download_link": "https://gofile.io/d/abc",
            }
        ]
        mock_db.get_all_files.return_value = files

        result = list_files(mock_db, max_filename_length=20)
        assert result is True

    def test_list_files_with_column_selection(self, mock_db, sample_files, capsys):
        """Should display only selected columns."""
        mock_db.get_all_files.return_value = sample_files

        result = list_files(mock_db, columns=["name", "size"])
        assert result is True


class TestExpiryCalculation:
    """Tests for file expiry date calculation in list_files."""

    def test_expired_file(self, mock_db, capsys):
        """Should show EXPIRED for expired files."""
        old_date = datetime.now() - timedelta(days=DAYS + 5)
        files = [
            {
                "id": "f1",
                "name": "old.txt",
                "size": 1024,
                "category": "test",
                "upload_time": old_date.isoformat(),
                "download_link": "https://gofile.io/d/abc",
            }
        ]
        mock_db.get_all_files.return_value = files

        list_files(mock_db)
        captured = capsys.readouterr()
        assert "EXPIRED" in captured.out

    def test_expiring_soon_file(self, mock_db, capsys):
        """Should show EXPIRES SOON for files close to expiry."""
        recent_date = datetime.now() - timedelta(days=DAYS - 2)
        files = [
            {
                "id": "f1",
                "name": "recent.txt",
                "size": 1024,
                "category": "test",
                "upload_time": recent_date.isoformat(),
                "download_link": "https://gofile.io/d/abc",
            }
        ]
        mock_db.get_all_files.return_value = files

        list_files(mock_db)
        captured = capsys.readouterr()
        assert "EXPIRES SOON" in captured.out or "days" in captured.out.lower()


class TestEdgeCases:
    """Tests for edge cases."""

    def test_file_with_missing_upload_time(self, mock_db, capsys):
        """Should handle files with missing upload time."""
        files = [
            {
                "id": "f1",
                "name": "no_time.txt",
                "size": 1024,
                "category": "test",
                "upload_time": "",
                "download_link": "https://gofile.io/d/abc",
            }
        ]
        mock_db.get_all_files.return_value = files

        result = list_files(mock_db)
        assert result is True

    def test_file_with_invalid_upload_time(self, mock_db, capsys):
        """Should handle files with invalid upload time."""
        files = [
            {
                "id": "f1",
                "name": "bad_time.txt",
                "size": 1024,
                "category": "test",
                "upload_time": "not-a-date",
                "download_link": "https://gofile.io/d/abc",
            }
        ]
        mock_db.get_all_files.return_value = files

        result = list_files(mock_db)
        assert result is True

    def test_file_with_empty_category(self, mock_db, capsys):
        """Should handle files with empty category."""
        files = [
            {
                "id": "f1",
                "name": "no_cat.txt",
                "size": 1024,
                "category": "",
                "upload_time": datetime.now().isoformat(),
                "download_link": "https://gofile.io/d/abc",
            }
        ]
        mock_db.get_all_files.return_value = files

        result = list_files(mock_db)
        assert result is True

    def test_unicode_filename_in_list(self, mock_db, capsys):
        """Should handle unicode filenames."""
        files = [
            {
                "id": "f1",
                "name": "日本語ファイル.txt",
                "size": 1024,
                "category": "test",
                "upload_time": datetime.now().isoformat(),
                "download_link": "https://gofile.io/d/abc",
            }
        ]
        mock_db.get_all_files.return_value = files

        result = list_files(mock_db)
        assert result is True

    def test_find_file_with_multiple_same_names(self, mock_db):
        """Should handle multiple files with same name."""
        files = [
            {
                "id": "f1",
                "name": "duplicate.txt",
                "category": "cat1",
                "upload_time": "2024-01-01",
            },
            {
                "id": "f2",
                "name": "duplicate.txt",
                "category": "cat2",
                "upload_time": "2024-01-02",
            },
        ]
        mock_db.get_all_files.return_value = files
        mock_db.get_file_by_id.return_value = None

        with patch("builtins.input", return_value="1"):
            result = find_file(mock_db, "duplicate.txt")
            assert result is not None

    def test_find_file_cancel_selection(self, mock_db):
        """Should return None when user cancels selection."""
        files = [
            {
                "id": "f1",
                "name": "duplicate.txt",
                "category": "cat1",
                "upload_time": "2024-01-01",
            },
            {
                "id": "f2",
                "name": "duplicate.txt",
                "category": "cat2",
                "upload_time": "2024-01-02",
            },
        ]
        mock_db.get_all_files.return_value = files
        mock_db.get_file_by_id.return_value = None

        with patch("builtins.input", return_value="q"):
            result = find_file(mock_db, "duplicate.txt")
            assert result is None
