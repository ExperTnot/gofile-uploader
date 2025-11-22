#!/usr/bin/env python3
"""
GoFile.io API client.
"""

import os
import re
import requests
import urllib.parse
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from typing import Dict, Any, Optional
import mimetypes
from .utils import upload_with_progress, format_time, BLUE, END
from .logging_utils import get_logger

logger = get_logger(__name__)


class GoFileClient:
    """GoFile.io API client for uploading files and managing folders."""

    BASE_URL = "https://api.gofile.io"
    GLOBAL_UPLOAD_URL = "https://upload.gofile.io/uploadfile"

    def __init__(self, account_token: Optional[str] = None):
        """
        Initialize the GoFile client.

        Args:
            account_token: Optional API token for authenticated requests
        """
        self.session = requests.Session()
        self.account_token = account_token
        self._current_server = None

    def get_server(self) -> str:
        """
        Get the best server for uploading.

        Returns:
            str: The best server for uploading.
        """
        # Use cached server if available
        if self._current_server:
            return self._current_server

        try:
            response = self.session.get(f"{self.BASE_URL}/servers")
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "ok":
                # Get the first server from the servers list
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
            # Create a guest account if we don't have a token
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
        # Log the original filename for debugging
        logger.debug(f"Original filename: {filename}")

        # First, URL encode the filename to handle special characters
        url_encoded = urllib.parse.quote(filename)

        # Replace problematic characters with underscores
        # Keep alphanumeric, periods, hyphens, and underscores
        sanitized = re.sub(r"[^\w\-\.]", "_", filename)

        # Make sure we don't have too many consecutive special chars
        sanitized = re.sub(r"[_\-\.]{2,}", "_", sanitized)

        # Save the URL-encoded version for potential API usage
        self._last_encoded_filename = url_encoded

        # If the name became empty, provide a default
        if not sanitized or sanitized == ".":
            sanitized = "file"

        # If filename changed, log it
        if sanitized != filename:
            logger.debug(f"Sanitized filename from '{filename}' to '{sanitized}'")

        return sanitized

    def upload_file(
        self, file_path: str, folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to GoFile.io.

        Args:
            file_path: Path to the file to upload
            folder_id: Optional folder ID to upload to (creates new folder if None)

        Returns:
            Dict[str, Any]: The response data containing the download link
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # Using the global upload endpoint which works better for folder management
            url = self.GLOBAL_UPLOAD_URL
            original_file_name = os.path.basename(file_path)

            # Sanitize the filename for upload
            file_name = self.sanitize_filename(original_file_name)

            # Define the upload function to work with proper progress tracking
            def perform_upload(
                file_obj, filename, form_data, chunk_size, progress_callback
            ):
                # Add required parameters to form_data
                if self.account_token:
                    form_data["token"] = self.account_token

                if folder_id:
                    form_data["folderId"] = folder_id

                # Create session for connection pooling
                session = requests.Session()

                # Get MIME type using Python's built-in mimetypes
                mime_type, _ = mimetypes.guess_type(filename)
                mime_type = mime_type or "application/octet-stream"

                logger.debug(f"Using MIME type {mime_type} for file {filename}")

                # Create the multipart form data with the file
                encoder = MultipartEncoder(
                    fields={**form_data, "file": (filename, file_obj, mime_type)}
                )

                # Define a callback that will be invoked as upload progresses
                def progress_monitor_callback(monitor):
                    # This is called with the actual bytes uploaded to the server
                    progress_callback(monitor.bytes_read)

                # Create a monitor that will track actual upload progress
                monitor = MultipartEncoderMonitor(encoder, progress_monitor_callback)

                # Make the POST request with progress monitoring
                try:
                    response = session.post(
                        url,
                        data=monitor,  # Use the monitor instead of the encoder directly
                        headers={"Content-Type": monitor.content_type},
                    )

                    # Check for errors
                    response.raise_for_status()

                    # Return the response JSON
                    return response.json()

                except KeyboardInterrupt:
                    # Catch interrupt here to cancel the request
                    session.close()
                    raise
                except Exception:
                    # Log the error and rethrow
                    session.close()
                    raise

            # Upload the file with progress tracking
            upload_result = upload_with_progress(file_path, perform_upload)
            data = upload_result["result"]

            # Check the response status
            if data.get("status") == "ok":
                # Get the download page URL and file info from the response
                response_data = data.get("data", {})
                download_page = response_data.get("downloadPage", "")
                file_id = response_data.get("fileId", "") or response_data.get(
                    "code", ""
                )
                folder_id = response_data.get("parentFolder", "")

                # Log the successful upload
                human_readable_time = format_time(upload_result["elapsed_time"])
                print(
                    f"Successfully uploaded {file_name} ({upload_result['file_size_formatted']}) in "
                    f"{human_readable_time} at {upload_result['speed_formatted']}"
                )
                print(f"Download link: {BLUE}{download_page}{END}")

                # Add additional information to the result
                response_data["file_id"] = file_id
                response_data["folder_id"] = folder_id
                response_data["file_size_formatted"] = upload_result[
                    "file_size_formatted"
                ]
                response_data["speed_formatted"] = upload_result["speed_formatted"]
                response_data["file_name"] = file_name

                # Extract account ID if available (for guest uploads)
                if "accountId" in response_data and not self.account_token:
                    logger.info(f"Guest account ID: {response_data['accountId']}")
                    response_data["account_id"] = response_data["accountId"]

                return response_data
            else:
                logger.error(f"Upload failed: {data.get('status')}")
                raise Exception(f"Upload failed: {data.get('status')}")
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise

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

            # Prepare request body with contentsId parameter
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
