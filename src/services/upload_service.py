#!/usr/bin/env python3
"""
Upload Service Module

Handles file upload workflow for the GoFile uploader.
"""

import os
import json
import glob
import logging
import mimetypes
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from requests.exceptions import HTTPError

from ..gofile_client import GoFileClient
from ..db_manager import DatabaseManager
from ..config import config
from ..utils import (
    is_mpegts_file,
    confirm_action,
    print_info,
    print_warning,
    DAYS,
    BLUE,
    END,
)

logger = logging.getLogger("gofile_uploader")


class UploadService:
    """Service for handling file upload operations."""

    def __init__(self, db_manager: DatabaseManager, client: GoFileClient):
        """
        Initialize the upload service.

        Args:
            db_manager: Database manager instance
            client: GoFile API client instance
        """
        self.db_manager = db_manager
        self.client = client

    def prepare_files(
        self, file_patterns: List[str], recursive: bool = False
    ) -> List[str]:
        """
        Prepare files for upload by expanding globs and processing directories.

        Args:
            file_patterns: List of file paths or patterns
            recursive: If True, recursively process directories

        Returns:
            List of file paths ready for upload
        """
        # Expand any glob patterns in the file list
        expanded_files = []
        for pattern in file_patterns:
            # Check if the pattern contains any glob special characters
            if any(char in pattern for char in ["*", "?", "["]):
                # Escape special characters to treat them literally
                safe_pattern = glob.escape(pattern)
                matched_files = glob.glob(safe_pattern)
                if not matched_files:
                    print_warning(
                        f"Warning: No files found matching pattern: {pattern}"
                    )
                    continue
                expanded_files.extend(matched_files)
            else:
                # If it's not a pattern, just add the file if it exists
                if os.path.exists(pattern):
                    expanded_files.append(pattern)
                else:
                    print_warning(f"Warning: File not found: {pattern}")

        if not expanded_files:
            return []

        # Process directories based on recursive flag
        final_files = []
        for file_path in expanded_files:
            if os.path.isdir(file_path):
                if recursive:
                    # Recursively gather all files from the directory
                    logger.info(f"Recursively processing directory: {file_path}")
                    for root, _, files in os.walk(file_path):
                        for filename in files:
                            final_files.append(os.path.join(root, filename))
                    print_info(
                        f"Added {len(final_files)} files from directory {file_path}"
                    )
                else:
                    print_info(
                        f"No files found in directory {file_path} (use -r flag to upload directories recursively)"
                    )
            else:
                final_files.append(file_path)

        return final_files

    def check_mpegts_files(self, files: List[str]) -> List[str]:
        """
        Check for MPEG-TS files and ask user for confirmation.

        Args:
            files: List of file paths to check

        Returns:
            List of files to upload (with MPEG-TS files removed if user declined)
        """
        skipped_files = []
        for file_path in files:
            # Check if file is MPEG-TS format
            if is_mpegts_file(file_path):
                print_warning(
                    f"'{os.path.basename(file_path)}' appears to be an MPEG-TS (.ts) file."
                )
                print_warning(
                    "These files may not play correctly in browsers when shared via GoFile."
                )
                if not confirm_action(
                    "Do you still want to upload this file? (yes/no):",
                    require_yes=False,
                ):
                    print_info(f"Skipping '{os.path.basename(file_path)}'")
                    skipped_files.append(file_path)
                    logger.info(
                        f"Skipping MPEG-TS file: {file_path} based on user request"
                    )

        # Remove skipped files from the list
        return [f for f in files if f not in skipped_files]

    def upload_file(
        self,
        file_path: str,
        folder_id: Optional[str],
        category: Optional[str],
        guest_account: Optional[str],
        quiet: bool = False,
    ) -> Dict[str, Any]:
        """
        Upload a single file and process the response.

        Args:
            file_path: Path to the file to upload
            folder_id: Optional folder ID to upload to
            category: Optional category name
            guest_account: Optional guest account token
            quiet: If True, suppress console output

        Returns:
            Dictionary with upload result information
        """
        try:
            # Record start time for duration calculation
            start_time = datetime.now()

            # Upload the file to the specified folder (if any)
            response_data = self.client.upload_file(file_path, folder_id=folder_id)

            # Calculate upload duration
            duration_seconds = (datetime.now() - start_time).total_seconds()

            # Process the upload response
            upload_info = self._process_upload_response(
                response_data,
                file_path,
                duration_seconds,
                category,
                guest_account,
            )

            # Save to database and log
            if upload_info["success"]:
                self._save_upload_info(upload_info, category, guest_account)

                # Print information to the console
                if not quiet:
                    self._print_upload_summary(upload_info, category)

            return upload_info

        except KeyboardInterrupt:
            logger.warning(f"Upload of {file_path} cancelled by user")
            raise
        except HTTPError as e:
            if e.response.status_code == 500:
                logger.error(f"Error uploading {file_path}")
                print(
                    "Note: This often happens when the folder doesn't exist or got deleted."
                )
                print(
                    "      Please check the folder link in a browser and try again. (get folder link with -l)"
                )
            else:
                logger.error(f"Error uploading {file_path}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error uploading {file_path}", exc_info=True)
            logger.error(f"{e}")
            print(f"Error uploading: {str(e)}")
            raise

    def handle_category_folder(
        self,
        category: str,
        folder_id: Optional[str],
        new_folder_id: str,
        folder_code: str,
    ) -> str:
        """
        Handle category-to-folder mapping for new categories.

        Args:
            category: Category name
            folder_id: Current folder ID (None for new categories)
            new_folder_id: Folder ID from upload response
            folder_code: Folder code from upload response

        Returns:
            The folder ID to use for subsequent uploads
        """
        # If this is a new category and we have a folder ID, save the mapping
        if new_folder_id and category and not folder_id:
            logger.debug(f"Saving folder information for category '{category}'")
            folder_info = {
                "folder_id": new_folder_id,
                "folder_code": folder_code,
                "category": category,
                "created_at": datetime.now().isoformat(),
            }
            self.db_manager.save_folder_for_category(category, folder_info)

            logger.info(
                f"Using folder ID {new_folder_id} for remaining files in category '{category}'"
            )
            print(f"Created new folder for category '{category}'\n")

            return new_folder_id

        return folder_id

    def save_guest_account(self, guest_token: str) -> None:
        """
        Save guest account token if not already saved.

        Args:
            guest_token: Guest account token from upload response
        """
        logger.debug(f"Saving guest token for future uploads: {guest_token}")
        self.db_manager.save_guest_account(guest_token)
        # Update the client with the new token
        self.client.account_token = guest_token

    def _process_upload_response(
        self,
        response_data: Dict[str, Any],
        file_path: str,
        duration_seconds: float,
        category: Optional[str],
        guest_account: Optional[str],
    ) -> Dict[str, Any]:
        """
        Process the upload response and extract relevant information.

        Args:
            response_data: Response from GoFile API
            file_path: Path to the uploaded file
            duration_seconds: Upload duration in seconds
            category: Optional category name
            guest_account: Optional guest account token

        Returns:
            Dictionary with processed upload information
        """
        # Extract data from the nested 'data' object if present
        if "data" in response_data and isinstance(response_data["data"], dict):
            response_detail = response_data["data"]
        else:
            response_detail = response_data

        # Log the full response for debugging
        logger.debug(f"Full response: {response_data}")

        # Extract download link
        download_link = (
            response_detail.get("downloadPage")
            or response_detail.get("directLink")
            or ""
        )

        # Extract file ID
        file_id = response_detail.get("id") or response_detail.get("file_id", "")

        # Extract folder information
        new_folder_id = response_detail.get("parentFolder", "")
        folder_code = response_detail.get("parentFolderCode", "")

        # Get the guest token
        guest_token = response_detail.get("guestToken", "")

        # Check if upload was successful
        success = bool(download_link and file_id)

        if not success:
            logger.warning(
                f"Upload of {file_path} received incomplete data from server"
            )
            print(
                f"Warning: Upload may not have completed successfully for {os.path.basename(file_path)}"
            )

        # Calculate file information
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        upload_speed_bps = file_size / duration_seconds if duration_seconds > 0 else 0.0

        upload_time = datetime.now()
        expiry_date = upload_time + timedelta(days=DAYS)

        return {
            "success": success,
            "file_id": file_id,
            "file_name": file_name,
            "file_path": file_path,
            "file_size": file_size,
            "mime_type": mime_type,
            "download_link": download_link,
            "folder_id": new_folder_id,
            "folder_code": folder_code,
            "guest_token": guest_token,
            "upload_time": upload_time,
            "expiry_date": expiry_date,
            "upload_speed_bps": upload_speed_bps,
            "duration_seconds": duration_seconds,
            "response_data": response_data,
        }

    def _save_upload_info(
        self,
        upload_info: Dict[str, Any],
        category: Optional[str],
        guest_account: Optional[str],
    ) -> None:
        """
        Save upload information to database and log file.

        Args:
            upload_info: Processed upload information
            category: Optional category name
            guest_account: Optional guest account token
        """
        # Save file information to the database
        file_info = {
            "id": upload_info["file_id"],
            "name": upload_info["file_name"],
            "size": upload_info["file_size"],
            "mime_type": upload_info["mime_type"],
            "upload_time": upload_info["upload_time"].isoformat(),
            "expiry_date": upload_info["expiry_date"].isoformat(),
            "download_link": upload_info["download_link"],
            "folder_id": upload_info["folder_id"],
            "folder_code": upload_info["folder_code"],
            "category": category,
            "account_id": guest_account or upload_info["guest_token"],
            "upload_speed": upload_info["upload_speed_bps"],
            "upload_duration": upload_info["duration_seconds"],
        }

        self.db_manager.save_file_info(file_info)

        # Add entry to log file
        log_file = os.path.join(
            config.get("log_folder"), f"{config.get('log_basename')}_0.log"
        )
        with open(log_file, "a") as log:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "filename": upload_info["file_name"],
                "filesize": upload_info["file_size"],
                "filesize_formatted": upload_info["response_data"].get(
                    "file_size_formatted", ""
                ),
                "upload_speed": upload_info["response_data"].get("speed_formatted", ""),
                "download_link": upload_info["download_link"],
                "file_id": upload_info["file_id"],
                "folder_id": upload_info["folder_id"],
                "category": category,
            }
            log.write(json.dumps(log_entry) + "\n")

    def _print_upload_summary(
        self, upload_info: Dict[str, Any], category: Optional[str]
    ) -> None:
        """
        Print upload summary to console.

        Args:
            upload_info: Processed upload information
            category: Optional category name
        """
        print(f"\nFile: {upload_info['file_name']}")
        if category:
            print(f"Category: {category}")
        print(f"Size: {upload_info['response_data'].get('file_size_formatted', '')}")
        print(
            f"Upload speed: {upload_info['response_data'].get('speed_formatted', '')}"
        )
        print(f"Download link: {BLUE}{upload_info['download_link']}{END}")
        print(f"Expires on: {upload_info['expiry_date'].strftime('%Y-%m-%d')}")
        print("-" * 50)
