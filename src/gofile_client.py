#!/usr/bin/env python3
"""
GoFile.io API client.
"""

import os
import re
import time
import requests
import urllib.parse
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from typing import Dict, Any, Optional
import mimetypes
from .utils import format_time, format_size, format_speed, BLUE, END
from tqdm import tqdm
from .logging_utils import get_logger

logger = get_logger(__name__)

# Constants for retry logic
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2  # seconds
DEFAULT_TIMEOUT = 30  # seconds for API calls (not uploads)


class GoFileClient:
    """GoFile.io API client for uploading files and managing folders."""

    BASE_URL = "https://api.gofile.io"
    GLOBAL_UPLOAD_URL = "https://upload.gofile.io/uploadfile"

    def __init__(
        self,
        account_token: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: int = DEFAULT_RETRY_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        Initialize the GoFile client.

        Args:
            account_token: Optional API token for authenticated requests
            max_retries: Maximum number of retry attempts for failed uploads
            retry_delay: Delay in seconds between retry attempts
            timeout: Timeout in seconds for API calls (not uploads)
        """
        self.session = requests.Session()
        self.account_token = account_token
        self._current_server = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

    def get_server(self) -> str:
        """
        Get the best server for uploading.

        Returns:
            str: The best server for uploading.
        """
        if self._current_server:
            return self._current_server

        try:
            response = self.session.get(f"{self.BASE_URL}/servers")
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                server = data.get("data", {}).get("servers", [])[0].get("name", "")
                if not server:
                    logger.error("No valid server found in response")
                    raise Exception("No valid server found in response")
                logger.info(f"Using server: {server}")
                self._current_server = server  # Cache the server
                return server
            else:
                logger.error(f"Failed to get server: {data.get('status')}")
                raise Exception(f"Failed to get server: {data.get('status')}")
        except Exception as e:
            logger.error(f"Error getting server: {str(e)}")
            raise

    def create_folder(
        self, folder_name: str, parent_folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new folder on GoFile.

        Args:
            folder_name: Name of the folder to create
            parent_folder_id: Optional ID of the parent folder

        Returns:
            Dict with folder information including ID
        """
        if not self.account_token:
            account_data = self.create_account()
            self.account_token = account_data.get("token")
            logger.info(f"Created guest account with token: {self.account_token}")

        try:
            headers = {}
            if self.account_token:
                headers["Authorization"] = f"Bearer {self.account_token}"

            data = {"name": folder_name, "parentFolderId": parent_folder_id or "root"}

            response = self.session.put(
                f"{self.BASE_URL}/folders", headers=headers, json=data
            )
            response.raise_for_status()
            result = response.json()

            if result.get("status") == "ok":
                folder_data = result.get("data", {})
                logger.info(
                    f"Created folder: {folder_name} with ID: {folder_data.get('id')}"
                )
                return folder_data
            else:
                logger.error(f"Failed to create folder: {result.get('status')}")
                raise Exception(f"Failed to create folder: {result.get('status')}")
        except Exception as e:
            logger.error(f"Error creating folder: {str(e)}")
            raise

    def create_account(self) -> Dict[str, Any]:
        """
        Create a guest account on GoFile.

        Returns:
            Dict with account information including token
        """
        try:
            response = self.session.get(f"{self.BASE_URL}/accounts/guest")
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                return data.get("data", {})
            else:
                logger.error(f"Failed to create guest account: {data.get('status')}")
                raise Exception(f"Failed to create guest account: {data.get('status')}")
        except Exception as e:
            logger.error(f"Error creating guest account: {str(e)}")
            raise

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename for safer uploads.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        logger.debug(f"Original filename: {filename}")
        url_encoded = urllib.parse.quote(filename)
        sanitized = re.sub(r"[^\w\-\.]", "_", filename)
        sanitized = re.sub(r"[_\-\.]{2,}", "_", sanitized)
        self._last_encoded_filename = url_encoded

        if not sanitized or sanitized == ".":
            sanitized = "file"

        if sanitized != filename:
            logger.debug(f"Sanitized filename from '{filename}' to '{sanitized}'")

        return sanitized

    def _is_retryable_error(self, exception: Exception) -> bool:
        """
        Determine if an error is retryable.

        Args:
            exception: The exception that occurred

        Returns:
            bool: True if the error is retryable, False otherwise
        """
        if isinstance(exception, (requests.exceptions.ConnectionError,
                                   requests.exceptions.Timeout,
                                   requests.exceptions.ChunkedEncodingError)):
            return True

        if isinstance(exception, requests.exceptions.HTTPError):
            if exception.response is not None and 500 <= exception.response.status_code < 600:
                return True

        return False

    def upload_file(
        self, file_path: str, folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to GoFile.io with automatic retry on transient failures.

        Args:
            file_path: Path to the file to upload
            folder_id: Optional folder ID to upload to (creates new folder if None)

        Returns:
            Dict[str, Any]: The response data containing the download link

        Raises:
            FileNotFoundError: If the file does not exist
            Exception: If upload fails after all retries
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        url = self.GLOBAL_UPLOAD_URL
        original_file_name = os.path.basename(file_path)
        file_name = self.sanitize_filename(original_file_name)

        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return self._perform_upload(file_path, file_name, url, folder_id)
            except KeyboardInterrupt:
                # Don't retry on user interrupt
                raise
            except Exception as e:
                last_exception = e

                if not self._is_retryable_error(e):
                    # Non-retryable error, fail immediately
                    logger.error(f"Upload failed (non-retryable): {e}")
                    raise

                if attempt < self.max_retries:
                    logger.warning(
                        f"Upload attempt {attempt}/{self.max_retries} failed: {e}. "
                        f"Retrying in {self.retry_delay}s..."
                    )
                    time.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"Upload failed after {self.max_retries} attempts: {e}"
                    )

        # All retries exhausted
        raise last_exception

    def _perform_upload(
        self, file_path: str, file_name: str, url: str, folder_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Internal method to perform the actual upload with progress tracking.
        """
        file_size = os.path.getsize(file_path)
        start_time = time.time()
        
        form_data = {}
        if self.account_token:
            form_data["token"] = self.account_token
        if folder_id:
            form_data["folderId"] = folder_id

        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        logger.debug(f"Using MIME type {mime_type} for file {file_name}")

        with open(file_path, "rb") as file_obj:
            encoder = MultipartEncoder(
                fields={**form_data, "file": (file_name, file_obj, mime_type)}
            )
            
            with tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=f"↑ {file_name}",
                bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]{postfix}",
            ) as pbar:
                last_bytes = [0]
                
                def on_progress(monitor):
                    delta = monitor.bytes_read - last_bytes[0]
                    if delta > 0:
                        pbar.update(delta)
                        last_bytes[0] = monitor.bytes_read
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            pbar.set_postfix_str(format_speed(monitor.bytes_read / elapsed))

                monitor = MultipartEncoderMonitor(encoder, on_progress)
                
                response = self.session.post(
                    url,
                    data=monitor,
                    headers={"Content-Type": monitor.content_type},
                )
                response.raise_for_status()
                
                if pbar.n < file_size:
                    pbar.update(file_size - pbar.n)

        elapsed_time = time.time() - start_time
        speed = file_size / elapsed_time if elapsed_time > 0 else 0
        data = response.json()

        if data.get("status") != "ok":
            error_msg = f"Upload failed: {data.get('status')}"
            logger.error(error_msg)
            raise Exception(error_msg)

        response_data = data.get("data", {})
        download_page = response_data.get("downloadPage", "")
        file_id = response_data.get("fileId", "") or response_data.get("code", "")
        returned_folder_id = response_data.get("parentFolder", "")

        file_size_fmt = format_size(file_size)
        speed_fmt = format_speed(speed)
        print(
            f"Successfully uploaded {file_name} ({file_size_fmt}) in "
            f"{format_time(elapsed_time)} at {speed_fmt}"
        )
        print(f"Download link: {BLUE}{download_page}{END}")

        response_data["file_id"] = file_id
        response_data["folder_id"] = returned_folder_id
        response_data["file_size_formatted"] = file_size_fmt
        response_data["speed_formatted"] = speed_fmt
        response_data["file_name"] = file_name

        if "accountId" in response_data and not self.account_token:
            logger.info(f"Guest account ID: {response_data['accountId']}")
            response_data["account_id"] = response_data["accountId"]

        return response_data

    def get_folder_content(self, folder_id: str) -> Dict[str, Any]:
        """
        Get the contents of a folder.

        Args:
            folder_id: The ID of the folder to get content for

        Returns:
            Dict with folder content information
        """
        try:
            headers = {}
            if self.account_token:
                headers["Authorization"] = f"Bearer {self.account_token}"

            response = self.session.get(
                f"{self.BASE_URL}/contents/{folder_id}", headers=headers
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                return data.get("data", {})
            else:
                logger.error(f"Failed to get folder content: {data.get('status')}")
                raise Exception(f"Failed to get folder content: {data.get('status')}")
        except Exception as e:
            logger.error(f"Error getting folder content: {str(e)}")
            raise

    def delete_contents(self, contents_id: str) -> bool:
        """
        Delete file(s) from GoFile server.

        Args:
            contents_id: Comma-separated list of content IDs to delete

        Returns:
            bool: True if deletion was successful, False otherwise

        Raises:
            Exception: If the API call fails or unauthorized
        """
        if not self.account_token:
            logger.error("Account token required for deletion")
            raise Exception("Account token required for deletion")

        try:
            headers = {
                "Authorization": f"Bearer {self.account_token}",
                "Content-Type": "application/json",
            }

            data = {"contentsId": contents_id}

            response = self.session.delete(
                f"{self.BASE_URL}/contents", headers=headers, json=data
            )
            response.raise_for_status()
            result = response.json()

            if result.get("status") == "ok":
                logger.debug(f"Successfully deleted content ID(s): {contents_id}")
                return True
            else:
                error_message = result.get("message", "Unknown error")
                logger.error(f"Failed to delete content: {error_message}")
                return False

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_message = ""
            try:
                error_data = e.response.json()
                error_message = error_data.get("message", str(e))
            except ValueError:
                error_message = str(e)

            if status_code == 401 or status_code == 403:
                logger.error(f"Unauthorized to delete this content: {error_message}")
                raise Exception(f"Unauthorized to delete this content: {error_message}")
            else:
                logger.error(f"HTTP error deleting content: {error_message}")
                raise Exception(f"Error deleting content: {error_message}")

        except Exception as e:
            logger.error(f"Error deleting content: {str(e)}")
            raise
