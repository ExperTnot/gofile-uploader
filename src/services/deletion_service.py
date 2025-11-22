#!/usr/bin/env python3
"""
Deletion Service Module

Handles all file and category deletion operations for the GoFile uploader.
Consolidates deletion logic to eliminate code duplication.
"""

import logging
from typing import Optional, List, Dict, Any
from requests.exceptions import HTTPError

from ..gofile_client import GoFileClient
from ..db_manager import DatabaseManager
from ..utils import (
    print_info,
    print_warning,
    print_error,
    print_success,
    confirm_action,
    print_file_count_summary,
    print_operation_header,
    print_file_list_summary,
    print_confirmation_message,
)
from ..file_manager import find_file

logger = logging.getLogger("gofile_uploader")


class DeletionService:
    """Service for handling file and category deletion operations."""

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the deletion service.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager

    def delete_file(
        self, file_id_or_name: str, force: bool = False, auto_confirm: bool = False
    ) -> bool:
        """
        Delete a single file from both GoFile server and local database.

        Args:
            file_id_or_name: ID or name of file to delete
            force: If True, only delete from local database without attempting remote deletion
            auto_confirm: If True, skip user confirmation prompts

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        # Find the file to delete
        file_info = find_file(self.db_manager, file_id_or_name)

        if not file_info:
            # File not found (find_file already printed an error message)
            return False

        # Display file info
        print_warning(file_info["info_str"])

        # Get file details
        file_data = file_info["file_data"]
        actual_id = file_info["actual_id"]
        name = file_info["name"]

        # Get confirmation from user with appropriate message based on force flag
        if not auto_confirm:
            if force:
                message = "This will ONLY delete the file record locally and NOT from GoFile servers. Are you sure? (yes/no):"
            else:
                message = (
                    "Delete file from GoFile servers and local database? (yes/no):"
                )

            if not confirm_action(message, require_yes=True):
                print_info("Deletion cancelled.")
                return False

        # Perform deletion
        if force:
            # Delete from local database only
            return self._delete_local(actual_id, name)
        else:
            # Delete from both remote and local
            account_id = file_data.get("account_id", "")
            download_link = file_data.get("download_link", "")

            if not account_id:
                logger.error(
                    f"No account token found for file '{name}'. Cannot delete from GoFile server."
                )
                print("Use -f/--force to delete just the local database entry.")
                return False

            # Try remote deletion first
            if self._delete_remote(actual_id, name, account_id, download_link):
                # Now delete from local database
                if self._delete_local(actual_id, name):
                    logger.info(
                        f"File '{name}' successfully deleted from local database."
                    )
                    return True
                else:
                    logger.error(
                        "File was deleted from GoFile server but could not be removed from local database."
                    )
                    return False
            else:
                return False

    def delete_file_batch(
        self, files: List[Dict[str, Any]], force: bool = False
    ) -> tuple[int, int]:
        """
        Delete multiple files with auto-confirmation.

        Args:
            files: List of file dictionaries to delete
            force: If True, only delete from local database

        Returns:
            tuple: (deleted_count, failed_count)
        """
        deleted_count = 0
        failed_count = 0

        for file in files:
            file_id = file["id"]
            try:
                result = self.delete_file(file_id, force, auto_confirm=True)
                if result:
                    deleted_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error deleting file {file_id}: {str(e)}")
                failed_count += 1

        return deleted_count, failed_count

    def delete_category_files(self, category_name: str, force: bool = False) -> bool:
        """
        Delete all files associated with a specific category.

        Args:
            category_name: The category name whose files should be deleted
            force: If True, only delete from local database

        Returns:
            bool: True if any files were deleted, False otherwise
        """
        files = self.db_manager.get_files_by_category(category_name)
        file_count = len(files)

        if file_count == 0:
            print_info(f"No files found for category '{category_name}'.")
            return False

        # Get confirmation for the irreversible action
        message = print_confirmation_message(
            "delete", file_count, f"file entries for category '{category_name}'", force
        )

        if not confirm_action(message):
            print_info("Purge cancelled.")
            return False

        # Process each file individually
        print_operation_header(
            "Deleting", file_count, "files from category '" + category_name + "'"
        )

        deleted_count, failed_count = self.delete_file_batch(files, force)

        print_file_count_summary(deleted_count, failed_count, "deleted")
        return deleted_count > 0

    def delete_orphaned_files(self, force: bool = False) -> bool:
        """
        Remove all file entries whose categories no longer exist.

        Args:
            force: If True, only delete from local database

        Returns:
            bool: True if any files were deleted, False otherwise
        """
        # Get all files and check which ones have orphaned categories
        all_files = self.db_manager.get_all_files()
        categories = set(self.db_manager.list_categories())

        orphaned_files = [
            file
            for file in all_files
            if file["category"] and file["category"] not in categories
        ]

        if not orphaned_files:
            print_info("No orphaned files found.")
            return False

        # Display summary of orphaned files
        print_file_list_summary(orphaned_files, show_sample=True)

        # Get confirmation for the irreversible action
        message = print_confirmation_message(
            "delete", len(orphaned_files), "orphaned file entries", force
        )

        if not confirm_action(message):
            print_info("Cleanup cancelled.")
            return False

        # Get final confirmation
        if not confirm_action(
            "Are you ABSOLUTELY sure? This cannot be undone. (yes/no):"
        ):
            print_info("Cleanup cancelled.")
            return False

        # Process files grouped by category
        print_operation_header("Deleting", len(orphaned_files), "orphaned files")

        # Group files by category for better output organization
        files_by_category = {}
        for file in orphaned_files:
            category = file["category"]
            if category not in files_by_category:
                files_by_category[category] = []
            files_by_category[category].append(file)

        total_deleted = 0
        total_failed = 0

        # Process each category
        for category, files in files_by_category.items():
            print_operation_header(
                "Processing", len(files), f"files from orphaned category '{category}'"
            )

            deleted_count, failed_count = self.delete_file_batch(files, force)

            print_info(
                f"Completed: {deleted_count} deleted, {failed_count} failed for category '{category}'"
            )

            total_deleted += deleted_count
            total_failed += failed_count

        # Print summary
        print_file_count_summary(total_deleted, total_failed, "removed")
        return total_deleted > 0

    def _delete_remote(
        self,
        file_id: str,
        file_name: str,
        account_token: str,
        download_link: str = "",
    ) -> bool:
        """
        Delete a file from GoFile server.

        Args:
            file_id: The file ID to delete
            file_name: The file name (for logging)
            account_token: The account token for authentication
            download_link: Optional download link for error messages

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # Initialize GoFile client with the account token
            client = GoFileClient(account_token=account_token)

            # Try to delete file from GoFile server
            remote_delete_success = client.delete_contents(file_id)

            if remote_delete_success:
                logger.info(
                    f"File '{file_name}' successfully deleted from GoFile server."
                )
                return True
            else:
                logger.error(f"Failed to delete file '{file_name}' from GoFile server.")
                if download_link:
                    logger.error(
                        f"You may need to check its status manually via your browser at: {download_link}"
                    )
                return False

        except HTTPError as e:
            logger.error(
                f"HTTP error deleting file '{file_name}' from GoFile server: {str(e)}"
            )
            if e.response is not None:
                logger.error(
                    f"Status Code: {e.response.status_code}. Message: {e.response.text}"
                )
            if download_link:
                logger.error(
                    f"This may be because the file doesn't exist on the server.\nPlease check its status or via your browser: {download_link}"
                )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error deleting file '{file_name}' from GoFile server: {str(e)}"
            )
            if download_link:
                logger.error(
                    f"You may need to check its status manually via your browser at: {download_link}"
                )
            return False

    def _delete_local(self, file_id: str, file_name: str) -> bool:
        """
        Delete a file from the local database only.

        Args:
            file_id: ID of the file to delete
            file_name: Name of the file (for display purposes)

        Returns:
            bool: True if deletion was successful, False otherwise
        """
        if self.db_manager.delete_file(file_id):
            logger.info(f"File '{file_name}' deleted from local database.")
            print_success(f"File '{file_name}' deleted successfully.")
            return True
        else:
            logger.error(f"Failed to delete file '{file_name}' from local database.")
            print_error(f"Failed to delete file '{file_name}' from local database.")
            return False
