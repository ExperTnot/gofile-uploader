#!/usr/bin/env python3
"""Tests for GoFileClient class with mocked API responses."""

import os
import sys
import tempfile
import pytest
from unittest.mock import Mock, patch
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.gofile_client import GoFileClient


@pytest.fixture
def client():
    """Create a GoFileClient instance for testing."""
    return GoFileClient(account_token="test_token")


@pytest.fixture
def client_no_token():
    """Create a GoFileClient instance without a token."""
    return GoFileClient()


@pytest.fixture
def temp_file():
    """Create a temporary file for upload testing."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.write(fd, b"Test file content for upload testing")
    os.close(fd)
    yield path
    os.unlink(path)


class TestClientInitialization:
    """Tests for client initialization."""

    def test_default_initialization(self):
        """Should initialize with default values."""
        client = GoFileClient()
        assert client.account_token is None
        assert client.max_retries == 3
        assert client.retry_delay == 2
        assert client.timeout == 30

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        client = GoFileClient(
            account_token="my_token",
            max_retries=5,
            retry_delay=1,
            timeout=60,
        )
        assert client.account_token == "my_token"
        assert client.max_retries == 5
        assert client.retry_delay == 1
        assert client.timeout == 60


class TestGetServer:
    """Tests for server selection."""

    @patch.object(requests.Session, "get")
    def test_get_server_success(self, mock_get, client):
        """Should return server name on success."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"servers": [{"name": "store1"}]},
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        server = client.get_server()
        assert server == "store1"

    @patch.object(requests.Session, "get")
    def test_get_server_caches_result(self, mock_get, client):
        """Should cache server result."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"servers": [{"name": "store1"}]},
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client.get_server()
        client.get_server()

        assert mock_get.call_count == 1

    @patch.object(requests.Session, "get")
    def test_get_server_failure(self, mock_get, client):
        """Should raise exception on API failure."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "error"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(Exception):
            client.get_server()

    @patch.object(requests.Session, "get")
    def test_get_server_empty_servers(self, mock_get, client):
        """Should raise exception when no servers available."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"servers": [{"name": ""}]},
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(Exception):
            client.get_server()


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_normal_filename(self, client):
        """Should keep normal filenames unchanged."""
        assert client.sanitize_filename("test.txt") == "test.txt"
        assert client.sanitize_filename("my-file_v2.pdf") == "my-file_v2.pdf"

    def test_special_characters(self, client):
        """Should replace special characters with underscores."""
        assert (
            client.sanitize_filename("file with spaces.txt") == "file_with_spaces.txt"
        )
        # Consecutive special chars get collapsed
        result = client.sanitize_filename("file@#$.txt")
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result

    def test_consecutive_special_chars(self, client):
        """Should collapse consecutive special characters."""
        result = client.sanitize_filename("file---name.txt")
        assert "__" not in result or result.count("_") <= 2

    def test_empty_result(self, client):
        """Should return 'file' for results that would be empty or just a dot."""
        # Special chars become underscores, not empty
        result = client.sanitize_filename("@#$%")
        assert result  # Not empty
        assert client.sanitize_filename(".") == "file"

    def test_unicode_filename(self, client):
        """Should handle unicode characters."""
        result = client.sanitize_filename("文件.txt")
        assert result.endswith(".txt")

    def test_stores_url_encoded(self, client):
        """Should store URL-encoded version."""
        client.sanitize_filename("test file.txt")
        assert hasattr(client, "_last_encoded_filename")


class TestIsRetryableError:
    """Tests for retry logic."""

    def test_connection_error_is_retryable(self, client):
        """Connection errors should be retryable."""
        error = requests.exceptions.ConnectionError()
        assert client._is_retryable_error(error) is True

    def test_timeout_is_retryable(self, client):
        """Timeout errors should be retryable."""
        error = requests.exceptions.Timeout()
        assert client._is_retryable_error(error) is True

    def test_chunked_encoding_error_is_retryable(self, client):
        """ChunkedEncodingError should be retryable."""
        error = requests.exceptions.ChunkedEncodingError()
        assert client._is_retryable_error(error) is True

    def test_500_error_is_retryable(self, client):
        """HTTP 500 errors should be retryable."""
        response = Mock()
        response.status_code = 500
        error = requests.exceptions.HTTPError(response=response)
        assert client._is_retryable_error(error) is True

    def test_503_error_is_retryable(self, client):
        """HTTP 503 errors should be retryable."""
        response = Mock()
        response.status_code = 503
        error = requests.exceptions.HTTPError(response=response)
        assert client._is_retryable_error(error) is True

    def test_400_error_not_retryable(self, client):
        """HTTP 400 errors should not be retryable."""
        response = Mock()
        response.status_code = 400
        error = requests.exceptions.HTTPError(response=response)
        assert client._is_retryable_error(error) is False

    def test_404_error_not_retryable(self, client):
        """HTTP 404 errors should not be retryable."""
        response = Mock()
        response.status_code = 404
        error = requests.exceptions.HTTPError(response=response)
        assert client._is_retryable_error(error) is False

    def test_generic_exception_not_retryable(self, client):
        """Generic exceptions should not be retryable."""
        error = ValueError("test error")
        assert client._is_retryable_error(error) is False


class TestUploadFile:
    """Tests for file upload functionality."""

    def test_file_not_found(self, client):
        """Should raise FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            client.upload_file("/nonexistent/file.txt")

    @patch.object(GoFileClient, "_perform_upload")
    def test_successful_upload(self, mock_upload, client, temp_file):
        """Should return response data on successful upload."""
        mock_upload.return_value = {
            "downloadPage": "https://gofile.io/d/abc123",
            "id": "file123",
        }

        result = client.upload_file(temp_file)
        assert "downloadPage" in result

    @patch.object(GoFileClient, "_perform_upload")
    def test_upload_with_folder_id(self, mock_upload, client, temp_file):
        """Should pass folder_id to upload."""
        mock_upload.return_value = {"downloadPage": "link", "id": "123"}

        client.upload_file(temp_file, folder_id="folder123")
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        assert call_args[0][3] == "folder123"

    @patch.object(GoFileClient, "_perform_upload")
    def test_upload_retries_on_transient_error(self, mock_upload, client, temp_file):
        """Should retry on transient errors."""
        mock_upload.side_effect = [
            requests.exceptions.ConnectionError(),
            {"downloadPage": "link", "id": "123"},
        ]

        result = client.upload_file(temp_file)
        assert mock_upload.call_count == 2
        assert result["id"] == "123"

    @patch.object(GoFileClient, "_perform_upload")
    def test_upload_fails_after_max_retries(self, mock_upload, client, temp_file):
        """Should fail after max retries exhausted."""
        client.max_retries = 2
        client.retry_delay = 0
        mock_upload.side_effect = requests.exceptions.ConnectionError()

        with pytest.raises(requests.exceptions.ConnectionError):
            client.upload_file(temp_file)

        assert mock_upload.call_count == 2

    @patch.object(GoFileClient, "_perform_upload")
    def test_upload_no_retry_on_non_retryable_error(
        self, mock_upload, client, temp_file
    ):
        """Should not retry on non-retryable errors."""
        mock_upload.side_effect = ValueError("bad request")

        with pytest.raises(ValueError):
            client.upload_file(temp_file)

        assert mock_upload.call_count == 1

    @patch.object(GoFileClient, "_perform_upload")
    def test_keyboard_interrupt_not_retried(self, mock_upload, client, temp_file):
        """Should not retry on KeyboardInterrupt."""
        mock_upload.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            client.upload_file(temp_file)

        assert mock_upload.call_count == 1


class TestCreateFolder:
    """Tests for folder creation."""

    @patch.object(requests.Session, "put")
    def test_create_folder_success(self, mock_put, client):
        """Should create folder successfully."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"id": "folder123", "name": "test_folder"},
        }
        mock_response.raise_for_status = Mock()
        mock_put.return_value = mock_response

        result = client.create_folder("test_folder")
        assert result["id"] == "folder123"

    @patch.object(requests.Session, "put")
    def test_create_folder_with_parent(self, mock_put, client):
        """Should create folder with parent ID."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok", "data": {"id": "folder123"}}
        mock_response.raise_for_status = Mock()
        mock_put.return_value = mock_response

        client.create_folder("subfolder", parent_folder_id="parent123")

        call_args = mock_put.call_args
        assert call_args[1]["json"]["parentFolderId"] == "parent123"

    @patch.object(requests.Session, "put")
    def test_create_folder_failure(self, mock_put, client):
        """Should raise exception on failure."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "error"}
        mock_response.raise_for_status = Mock()
        mock_put.return_value = mock_response

        with pytest.raises(Exception):
            client.create_folder("test_folder")


class TestCreateAccount:
    """Tests for guest account creation."""

    @patch.object(requests.Session, "get")
    def test_create_account_success(self, mock_get, client_no_token):
        """Should create guest account successfully."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"token": "guest_token_123"},
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = client_no_token.create_account()
        assert result["token"] == "guest_token_123"

    @patch.object(requests.Session, "get")
    def test_create_account_failure(self, mock_get, client_no_token):
        """Should raise exception on failure."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "error"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(Exception):
            client_no_token.create_account()


class TestDeleteContents:
    """Tests for content deletion."""

    @patch.object(requests.Session, "delete")
    def test_delete_contents_success(self, mock_delete, client):
        """Should delete content successfully."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = Mock()
        mock_delete.return_value = mock_response

        result = client.delete_contents("content123")
        assert result is True

    @patch.object(requests.Session, "delete")
    def test_delete_contents_failure(self, mock_delete, client):
        """Should return False on failure."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "error", "message": "Not found"}
        mock_response.raise_for_status = Mock()
        mock_delete.return_value = mock_response

        result = client.delete_contents("content123")
        assert result is False

    def test_delete_contents_no_token(self, client_no_token):
        """Should raise exception without token."""
        with pytest.raises(Exception) as exc_info:
            client_no_token.delete_contents("content123")
        assert "Account token required" in str(exc_info.value)

    @patch.object(requests.Session, "delete")
    def test_delete_contents_unauthorized(self, mock_delete, client):
        """Should raise exception on 401/403."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Unauthorized"}
        error = requests.exceptions.HTTPError(response=mock_response)
        mock_delete.side_effect = error

        with pytest.raises(Exception) as exc_info:
            client.delete_contents("content123")
        assert "Unauthorized" in str(exc_info.value)


class TestGetFolderContent:
    """Tests for folder content retrieval."""

    @patch.object(requests.Session, "get")
    def test_get_folder_content_success(self, mock_get, client):
        """Should retrieve folder content successfully."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "ok",
            "data": {"id": "folder123", "children": {"file1": {"name": "test.txt"}}},
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = client.get_folder_content("folder123")
        assert result["id"] == "folder123"
        assert "children" in result

    @patch.object(requests.Session, "get")
    def test_get_folder_content_failure(self, mock_get, client):
        """Should raise exception on failure."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "error"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(Exception):
            client.get_folder_content("folder123")
