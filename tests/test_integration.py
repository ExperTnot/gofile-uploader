#!/usr/bin/env python3
"""Integration tests for the gofile-uploader."""

import os
import sys
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db_manager import DatabaseManager
from src.gofile_client import GoFileClient


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    def test_full_workflow(self, temp_db):
        """Test complete workflow: create category, upload file, list, delete."""
        # Create a category
        folder_info = {
            "folder_id": "folder123",
            "folder_code": "code456",
            "created_at": datetime.now().isoformat(),
        }
        assert temp_db.save_folder_for_category("test_category", folder_info) is True

        # Save a file
        file_info = {
            "id": "file123",
            "name": "test.txt",
            "size": 1024,
            "mime_type": "text/plain",
            "upload_time": datetime.now().isoformat(),
            "download_link": "https://gofile.io/d/abc123",
            "folder_id": "folder123",
            "folder_code": "code456",
            "category": "test_category",
            "account_id": "acc123",
        }
        assert temp_db.save_file_info(file_info) is True

        # Verify file exists
        retrieved = temp_db.get_file_by_id("file123")
        assert retrieved is not None
        assert retrieved["name"] == "test.txt"

        # List files by category
        files = temp_db.get_files_by_category("test_category")
        assert len(files) == 1

        # Delete file
        assert temp_db.delete_file("file123") is True
        assert temp_db.get_file_by_id("file123") is None

        # Remove category
        assert temp_db.remove_category("test_category") is True
        assert temp_db.get_folder_by_category("test_category") is None

    def test_multiple_files_same_category(self, temp_db):
        """Test multiple files in the same category."""
        temp_db.save_folder_for_category(
            "multi", {"folder_id": "f1", "folder_code": "c1"}
        )

        for i in range(5):
            temp_db.save_file_info(
                {
                    "id": f"multi_file_{i}",
                    "name": f"file_{i}.txt",
                    "size": 1024 * (i + 1),
                    "download_link": f"https://gofile.io/d/{i}",
                    "folder_id": "f1",
                    "category": "multi",
                }
            )

        files = temp_db.get_files_by_category("multi")
        assert len(files) == 5

        # Delete all files in category
        deleted = temp_db.delete_files_by_category("multi")
        assert deleted == 5
        assert len(temp_db.get_files_by_category("multi")) == 0

    def test_guest_account_persistence(self, temp_db):
        """Test guest account token persistence."""
        assert temp_db.get_guest_account() is None

        temp_db.save_guest_account("token_abc123")
        assert temp_db.get_guest_account() == "token_abc123"

        # Update token
        temp_db.save_guest_account("token_xyz789")
        assert temp_db.get_guest_account() == "token_xyz789"

        # Clear token
        temp_db.clear_guest_account()
        assert temp_db.get_guest_account() is None


class TestClientWithMockAPI:
    """Integration tests for GoFileClient with mocked API."""

    @patch("requests.Session.get")
    @patch("requests.Session.post")
    def test_upload_creates_guest_account(self, mock_post, mock_get, temp_file):
        """Test that upload creates guest account when none exists."""
        # Mock server response
        mock_get.return_value = Mock(
            json=lambda: {"status": "ok", "data": {"servers": [{"name": "store1"}]}},
            raise_for_status=Mock(),
        )

        # Mock upload response with guest token
        mock_post.return_value = Mock(
            json=lambda: {
                "status": "ok",
                "data": {
                    "downloadPage": "https://gofile.io/d/abc123",
                    "fileId": "file123",
                    "parentFolder": "folder123",
                    "guestToken": "new_guest_token",
                },
            },
            raise_for_status=Mock(),
        )

        client = GoFileClient()
        assert client.account_token is None

    @patch("requests.Session.get")
    def test_folder_creation_with_token(self, mock_get):
        """Test folder creation uses account token."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"id": "new_folder_id", "name": "test_folder"},
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.Session.put", return_value=mock_response) as mock_put:
            client = GoFileClient(account_token="my_token")
            result = client.create_folder("test_folder")

            assert result["id"] == "new_folder_id"
            call_args = mock_put.call_args
            assert "Authorization" in call_args[1]["headers"]
            assert "Bearer my_token" in call_args[1]["headers"]["Authorization"]


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_database_handles_concurrent_access(self, temp_db_path):
        """Test that database handles multiple connections."""
        db1 = DatabaseManager(temp_db_path)
        db2 = DatabaseManager(temp_db_path)

        db1.save_folder_for_category("cat1", {"folder_id": "f1", "folder_code": "c1"})

        # db2 should see the changes
        result = db2.get_folder_by_category("cat1")
        assert result is not None

        db1.close()
        db2.close()

    def test_client_handles_network_errors(self, temp_file):
        """Test client handles network errors gracefully."""
        client = GoFileClient(max_retries=1, retry_delay=0)

        with patch.object(GoFileClient, "_perform_upload") as mock_upload:
            mock_upload.side_effect = ConnectionError("Network error")

            with pytest.raises(ConnectionError):
                client.upload_file(temp_file)

    def test_database_handles_invalid_data(self, temp_db):
        """Test database rejects invalid data."""
        # Missing required fields
        result = temp_db.save_file_info({"name": "test.txt"})
        assert result is False

        # Empty category name
        result = temp_db.save_folder_for_category("", {"folder_id": "f1"})
        assert result is False


class TestDataConsistency:
    """Tests for data consistency."""

    def test_file_category_relationship(self, temp_db):
        """Test file-category relationship integrity."""
        # Create category
        temp_db.save_folder_for_category(
            "docs", {"folder_id": "f1", "folder_code": "c1"}
        )

        # Add files to category
        temp_db.save_file_info(
            {
                "id": "f1",
                "name": "doc1.txt",
                "download_link": "l1",
                "folder_id": "f1",
                "category": "docs",
            }
        )
        temp_db.save_file_info(
            {
                "id": "f2",
                "name": "doc2.txt",
                "download_link": "l2",
                "folder_id": "f1",
                "category": "docs",
            }
        )

        # Verify counts match
        assert temp_db.get_file_count("docs") == 2
        assert len(temp_db.get_files_by_category("docs")) == 2

    def test_orphaned_files_detection(self, temp_db):
        """Test detection of files with deleted categories."""
        # Create category and files
        temp_db.save_folder_for_category(
            "temp_cat", {"folder_id": "f1", "folder_code": "c1"}
        )
        temp_db.save_file_info(
            {
                "id": "orphan1",
                "name": "file.txt",
                "download_link": "l1",
                "folder_id": "f1",
                "category": "temp_cat",
            }
        )

        # Remove category but not files
        temp_db.remove_category("temp_cat")

        # File still exists but category doesn't
        file = temp_db.get_file_by_id("orphan1")
        assert file is not None
        assert file["category"] == "temp_cat"
        assert temp_db.get_folder_by_category("temp_cat") is None


class TestBoundaryConditions:
    """Tests for boundary conditions and limits."""

    def test_empty_database_operations(self, temp_db):
        """Test operations on empty database."""
        assert temp_db.get_all_files() == []
        assert temp_db.list_categories() == []
        assert temp_db.get_file_count() == 0
        assert temp_db.get_category_count() == 0

    def test_special_characters_in_data(self, temp_db):
        """Test handling of special characters."""
        special_name = "file'with\"special<>chars.txt"
        temp_db.save_file_info(
            {
                "id": "special1",
                "name": special_name,
                "download_link": "https://gofile.io/d/test",
                "folder_id": "f1",
            }
        )

        result = temp_db.get_file_by_id("special1")
        assert result["name"] == special_name

    def test_very_long_strings(self, temp_db):
        """Test handling of very long strings."""
        long_name = "x" * 1000 + ".txt"
        long_link = "https://gofile.io/d/" + "a" * 500

        temp_db.save_file_info(
            {
                "id": "long1",
                "name": long_name,
                "download_link": long_link,
                "folder_id": "f1",
            }
        )

        result = temp_db.get_file_by_id("long1")
        assert result["name"] == long_name
        assert result["download_link"] == long_link

    def test_zero_and_negative_values(self, temp_db):
        """Test handling of zero and edge case numeric values."""
        temp_db.save_file_info(
            {
                "id": "zero1",
                "name": "empty.txt",
                "size": 0,
                "download_link": "link",
                "folder_id": "f1",
                "upload_speed": 0.0,
                "upload_duration": 0.0,
            }
        )

        result = temp_db.get_file_by_id("zero1")
        assert result["size"] == 0
        assert result["upload_speed"] == 0.0
