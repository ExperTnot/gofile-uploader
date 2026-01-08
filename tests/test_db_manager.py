#!/usr/bin/env python3
"""Tests for DatabaseManager class."""

import os
import sys
import tempfile
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db_manager import DatabaseManager


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = DatabaseManager(path)
    yield db
    db.close()
    os.unlink(path)


class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_creates_database_file(self, temp_db):
        """Database file should be created on initialization."""
        assert os.path.exists(temp_db.db_file)

    def test_creates_categories_table(self, temp_db):
        """Categories table should exist after initialization."""
        cursor = temp_db.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
        )
        assert cursor.fetchone() is not None

    def test_creates_files_table(self, temp_db):
        """Files table should exist after initialization."""
        cursor = temp_db.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
        )
        assert cursor.fetchone() is not None

    def test_creates_settings_table(self, temp_db):
        """Settings table should exist after initialization."""
        cursor = temp_db.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
        )
        assert cursor.fetchone() is not None


class TestCategoryOperations:
    """Tests for category-related operations."""

    def test_save_folder_for_category(self, temp_db):
        """Should save folder information for a category."""
        folder_info = {
            "folder_id": "abc123",
            "folder_code": "xyz789",
            "created_at": datetime.now().isoformat(),
        }
        result = temp_db.save_folder_for_category("test_category", folder_info)
        assert result is True

    def test_get_folder_by_category(self, temp_db):
        """Should retrieve folder information by category name."""
        folder_info = {
            "folder_id": "folder123",
            "folder_code": "code456",
            "created_at": datetime.now().isoformat(),
        }
        temp_db.save_folder_for_category("my_category", folder_info)

        retrieved = temp_db.get_folder_by_category("my_category")
        assert retrieved is not None
        assert retrieved["folder_id"] == "folder123"
        assert retrieved["folder_code"] == "code456"

    def test_get_folder_by_nonexistent_category(self, temp_db):
        """Should return None for nonexistent category."""
        result = temp_db.get_folder_by_category("nonexistent")
        assert result is None

    def test_list_categories_empty(self, temp_db):
        """Should return empty list when no categories exist."""
        categories = temp_db.list_categories()
        assert categories == []

    def test_list_categories(self, temp_db):
        """Should return list of category names."""
        temp_db.save_folder_for_category(
            "cat1", {"folder_id": "f1", "folder_code": "c1"}
        )
        temp_db.save_folder_for_category(
            "cat2", {"folder_id": "f2", "folder_code": "c2"}
        )

        categories = temp_db.list_categories()
        assert len(categories) == 2
        assert "cat1" in categories
        assert "cat2" in categories

    def test_remove_category(self, temp_db):
        """Should remove a category from the database."""
        temp_db.save_folder_for_category(
            "to_remove", {"folder_id": "f1", "folder_code": "c1"}
        )
        assert temp_db.remove_category("to_remove") is True
        assert temp_db.get_folder_by_category("to_remove") is None

    def test_remove_nonexistent_category(self, temp_db):
        """Should return False when removing nonexistent category."""
        result = temp_db.remove_category("nonexistent")
        assert result is False

    def test_get_categories_info(self, temp_db):
        """Should return detailed info for all categories."""
        temp_db.save_folder_for_category(
            "cat1", {"folder_id": "f1", "folder_code": "c1"}
        )
        temp_db.save_folder_for_category(
            "cat2", {"folder_id": "f2", "folder_code": "c2"}
        )

        info = temp_db.get_categories_info()
        assert len(info) == 2
        assert info[0]["name"] == "cat1"
        assert info[0]["folder_id"] == "f1"

    def test_save_folder_invalid_category(self, temp_db):
        """Should return False for invalid category name."""
        result = temp_db.save_folder_for_category("", {"folder_id": "f1"})
        assert result is False

        result = temp_db.save_folder_for_category(None, {"folder_id": "f1"})
        assert result is False

    def test_save_folder_invalid_folder_info(self, temp_db):
        """Should return False for invalid folder info."""
        result = temp_db.save_folder_for_category("cat", None)
        assert result is False

        result = temp_db.save_folder_for_category("cat", "not_a_dict")
        assert result is False


class TestGuestAccountOperations:
    """Tests for guest account operations."""

    def test_save_guest_account(self, temp_db):
        """Should save guest account token."""
        result = temp_db.save_guest_account("token123")
        assert result is True

    def test_get_guest_account(self, temp_db):
        """Should retrieve saved guest account token."""
        temp_db.save_guest_account("my_token")
        token = temp_db.get_guest_account()
        assert token == "my_token"

    def test_get_guest_account_when_none(self, temp_db):
        """Should return None when no guest account is saved."""
        token = temp_db.get_guest_account()
        assert token is None

    def test_clear_guest_account(self, temp_db):
        """Should clear the guest account token."""
        temp_db.save_guest_account("token_to_clear")
        result = temp_db.clear_guest_account()
        assert result is True
        assert temp_db.get_guest_account() is None

    def test_clear_guest_account_when_none(self, temp_db):
        """Should return False when no guest account to clear."""
        result = temp_db.clear_guest_account()
        assert result is False

    def test_save_guest_account_invalid(self, temp_db):
        """Should return False for invalid account ID."""
        assert temp_db.save_guest_account("") is False
        assert temp_db.save_guest_account(None) is False


class TestFileOperations:
    """Tests for file-related operations."""

    def test_save_file_info(self, temp_db):
        """Should save file information."""
        file_info = {
            "id": "file123",
            "name": "test.txt",
            "size": 1024,
            "mime_type": "text/plain",
            "upload_time": datetime.now().isoformat(),
            "download_link": "https://gofile.io/d/abc123",
            "folder_id": "folder1",
            "folder_code": "code1",
            "category": "documents",
            "account_id": "acc123",
            "upload_speed": 1000.0,
            "upload_duration": 1.0,
        }
        result = temp_db.save_file_info(file_info)
        assert result is True

    def test_get_file_by_id(self, temp_db):
        """Should retrieve file by ID."""
        file_info = {
            "id": "unique_id",
            "name": "myfile.txt",
            "size": 2048,
            "download_link": "https://gofile.io/d/xyz",
            "folder_id": "f1",
        }
        temp_db.save_file_info(file_info)

        retrieved = temp_db.get_file_by_id("unique_id")
        assert retrieved is not None
        assert retrieved["name"] == "myfile.txt"
        assert retrieved["size"] == 2048

    def test_get_file_by_nonexistent_id(self, temp_db):
        """Should return None for nonexistent file ID."""
        result = temp_db.get_file_by_id("nonexistent")
        assert result is None

    def test_get_all_files(self, temp_db):
        """Should return all files."""
        for i in range(3):
            temp_db.save_file_info(
                {
                    "id": f"file{i}",
                    "name": f"file{i}.txt",
                    "download_link": f"https://gofile.io/d/{i}",
                    "folder_id": "f1",
                }
            )

        files = temp_db.get_all_files()
        assert len(files) == 3

    def test_get_files_by_category(self, temp_db):
        """Should return files filtered by category."""
        temp_db.save_file_info(
            {
                "id": "f1",
                "name": "a.txt",
                "download_link": "link1",
                "folder_id": "f1",
                "category": "docs",
            }
        )
        temp_db.save_file_info(
            {
                "id": "f2",
                "name": "b.txt",
                "download_link": "link2",
                "folder_id": "f1",
                "category": "images",
            }
        )
        temp_db.save_file_info(
            {
                "id": "f3",
                "name": "c.txt",
                "download_link": "link3",
                "folder_id": "f1",
                "category": "docs",
            }
        )

        docs = temp_db.get_files_by_category("docs")
        assert len(docs) == 2

    def test_delete_file(self, temp_db):
        """Should delete a file by ID."""
        temp_db.save_file_info(
            {
                "id": "to_delete",
                "name": "delete_me.txt",
                "download_link": "link",
                "folder_id": "f1",
            }
        )

        result = temp_db.delete_file("to_delete")
        assert result is True
        assert temp_db.get_file_by_id("to_delete") is None

    def test_delete_nonexistent_file(self, temp_db):
        """Should return False when deleting nonexistent file."""
        result = temp_db.delete_file("nonexistent")
        assert result is False

    def test_delete_files_by_category(self, temp_db):
        """Should delete all files in a category."""
        for i in range(3):
            temp_db.save_file_info(
                {
                    "id": f"cat_file{i}",
                    "name": f"file{i}.txt",
                    "download_link": f"link{i}",
                    "folder_id": "f1",
                    "category": "to_delete_cat",
                }
            )

        deleted = temp_db.delete_files_by_category("to_delete_cat")
        assert deleted == 3
        assert len(temp_db.get_files_by_category("to_delete_cat")) == 0

    def test_get_file_count(self, temp_db):
        """Should return correct file count."""
        for i in range(5):
            temp_db.save_file_info(
                {
                    "id": f"count{i}",
                    "name": f"file{i}.txt",
                    "download_link": f"link{i}",
                    "folder_id": "f1",
                }
            )

        count = temp_db.get_file_count()
        assert count == 5

    def test_get_file_count_by_category(self, temp_db):
        """Should return correct file count for a category."""
        temp_db.save_file_info(
            {
                "id": "f1",
                "name": "a.txt",
                "download_link": "l1",
                "folder_id": "f1",
                "category": "cat_a",
            }
        )
        temp_db.save_file_info(
            {
                "id": "f2",
                "name": "b.txt",
                "download_link": "l2",
                "folder_id": "f1",
                "category": "cat_a",
            }
        )
        temp_db.save_file_info(
            {
                "id": "f3",
                "name": "c.txt",
                "download_link": "l3",
                "folder_id": "f1",
                "category": "cat_b",
            }
        )

        count = temp_db.get_file_count("cat_a")
        assert count == 2

    def test_save_file_missing_required_fields(self, temp_db):
        """Should return False when required fields are missing."""
        result = temp_db.save_file_info({"name": "test.txt"})
        assert result is False

        result = temp_db.save_file_info({"id": "123"})
        assert result is False

    def test_get_category_count(self, temp_db):
        """Should return correct category count."""
        temp_db.save_folder_for_category("c1", {"folder_id": "f1", "folder_code": "x"})
        temp_db.save_folder_for_category("c2", {"folder_id": "f2", "folder_code": "y"})

        count = temp_db.get_category_count()
        assert count == 2


class TestContextManager:
    """Tests for context manager functionality."""

    def test_context_manager(self):
        """Should work as context manager."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        with DatabaseManager(path) as db:
            db.save_folder_for_category(
                "test", {"folder_id": "f1", "folder_code": "c1"}
            )
            assert db.get_folder_by_category("test") is not None

        os.unlink(path)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_unicode_category_name(self, temp_db):
        """Should handle unicode characters in category names."""
        temp_db.save_folder_for_category(
            "日本語カテゴリ", {"folder_id": "f1", "folder_code": "c1"}
        )
        result = temp_db.get_folder_by_category("日本語カテゴリ")
        assert result is not None

    def test_unicode_filename(self, temp_db):
        """Should handle unicode characters in filenames."""
        temp_db.save_file_info(
            {
                "id": "unicode_file",
                "name": "文件名.txt",
                "download_link": "link",
                "folder_id": "f1",
            }
        )
        result = temp_db.get_file_by_id("unicode_file")
        assert result["name"] == "文件名.txt"

    def test_special_characters_in_category(self, temp_db):
        """Should handle special characters in category names."""
        temp_db.save_folder_for_category(
            "cat-with_special.chars", {"folder_id": "f1", "folder_code": "c1"}
        )
        result = temp_db.get_folder_by_category("cat-with_special.chars")
        assert result is not None

    def test_very_long_filename(self, temp_db):
        """Should handle very long filenames."""
        long_name = "a" * 500 + ".txt"
        temp_db.save_file_info(
            {
                "id": "long_name_file",
                "name": long_name,
                "download_link": "link",
                "folder_id": "f1",
            }
        )
        result = temp_db.get_file_by_id("long_name_file")
        assert result["name"] == long_name

    def test_zero_size_file(self, temp_db):
        """Should handle zero-size files."""
        temp_db.save_file_info(
            {
                "id": "zero_size",
                "name": "empty.txt",
                "size": 0,
                "download_link": "link",
                "folder_id": "f1",
            }
        )
        result = temp_db.get_file_by_id("zero_size")
        assert result["size"] == 0

    def test_large_file_size(self, temp_db):
        """Should handle large file sizes."""
        large_size = 10 * 1024 * 1024 * 1024  # 10 GB
        temp_db.save_file_info(
            {
                "id": "large_file",
                "name": "big.bin",
                "size": large_size,
                "download_link": "link",
                "folder_id": "f1",
            }
        )
        result = temp_db.get_file_by_id("large_file")
        assert result["size"] == large_size

    def test_duplicate_file_id(self, temp_db):
        """Should handle duplicate file IDs (should fail on insert)."""
        temp_db.save_file_info(
            {
                "id": "dup_id",
                "name": "first.txt",
                "download_link": "link1",
                "folder_id": "f1",
            }
        )
        # Second insert with same ID should fail
        result = temp_db.save_file_info(
            {
                "id": "dup_id",
                "name": "second.txt",
                "download_link": "link2",
                "folder_id": "f1",
            }
        )
        assert result is False

    def test_category_update(self, temp_db):
        """Should update existing category folder info."""
        temp_db.save_folder_for_category(
            "update_cat", {"folder_id": "old_id", "folder_code": "old_code"}
        )
        temp_db.save_folder_for_category(
            "update_cat", {"folder_id": "new_id", "folder_code": "new_code"}
        )

        result = temp_db.get_folder_by_category("update_cat")
        assert result["folder_id"] == "new_id"
        assert result["folder_code"] == "new_code"
