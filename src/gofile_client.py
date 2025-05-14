#!/usr/bin/env python3
"""
GoFile.io API client.
"""

import os
import requests
from typing import Dict, Any, Optional
from .utils import upload_with_progress
from .logging_utils import get_logger

logger = get_logger(__name__)


class GoFileClient:
    """GoFile.io API client for uploading files and managing folders."""

    BASE_URL = "https://api.gofile.io"
    GLOBAL_UPLOAD_URL = "https://upload.gofile.io/uploadFile"

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
            url = "https://upload.gofile.io/uploadFile"
            file_name = os.path.basename(file_path)

            # Define the upload function to work with MultipartEncoderMonitor
            def perform_upload(monitor, content_type):
                # For the data section we need to include token and folderId
                # We DON'T use headers or params like before
                form_data = {}

                # Include token if available
                if self.account_token:
                    form_data["token"] = self.account_token

                # Include folderId if specified
                if folder_id:
                    form_data["folderId"] = folder_id

                # Make the POST request with the monitor for file data
                # and form_data for the token and folder ID
                response = requests.post(
                    url, files={"file": (file_name, monitor)}, data=form_data
                )
                response.raise_for_status()
                return response.json()

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
                logger.info(
                    f"Successfully uploaded {file_name} ({upload_result['file_size_formatted']}) in "
                    f"{upload_result['elapsed_time']:.2f}s at {upload_result['speed_formatted']}"
                )
                logger.info(f"Download link: {download_page}")

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
