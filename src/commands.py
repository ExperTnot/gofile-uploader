#!/usr/bin/env python3
"""
Command Handlers Module

Contains handler functions for each CLI command.
Separates command routing from business logic.
"""

import logging
from typing import Optional

from .gofile_client import GoFileClient
from .db_manager import DatabaseManager
from .file_manager import list_files
from .services import DeletionService, CategoryService, UploadService
from .utils import print_info, confirm_action, print_success, print_warning

logger = logging.getLogger("gofile_uploader")


def handle_list_categories_command(db_manager: DatabaseManager) -> None:
    """
    Handle the list categories command.

    Args:
        db_manager: Database manager instance
    """
    category_service = CategoryService(db_manager)
    category_service.list_categories()


def handle_list_files_command(
    db_manager: DatabaseManager,
    category: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_order: str = "asc",
    page: int = 1,
    max_filename_length: Optional[int] = None,
    columns: Optional[list] = None,
) -> None:
    """
    Handle the list files command.

    Args:
        db_manager: Database manager instance
        category: Optional category to filter by
        sort_field: Optional field to sort by
        sort_order: Sort order (asc or desc)
        page: Page number for pagination
        max_filename_length: Maximum filename display width
        columns: Optional list of columns to display
    """
    list_files(
        db_manager,
        category=category,
        sort_field=sort_field,
        sort_order=sort_order,
        page=page,
        max_filename_length=max_filename_length,
        columns=columns,
    )


def handle_delete_file_command(
    db_manager: DatabaseManager, file_id_or_name: str, force: bool = False
) -> None:
    """
    Handle the delete file command.

    Args:
        db_manager: Database manager instance
        file_id_or_name: ID or name of file to delete
        force: If True, only delete from local database
    """
    deletion_service = DeletionService(db_manager)
    deletion_service.delete_file(file_id_or_name, force)


def handle_purge_files_command(
    db_manager: DatabaseManager, category_pattern: str, force: bool = False
) -> None:
    """
    Handle the purge category files command.

    Args:
        db_manager: Database manager instance
        category_pattern: Category name or pattern
        force: If True, only delete from local database
    """
    category_service = CategoryService(db_manager)
    deletion_service = DeletionService(db_manager)

    # Resolve category name
    category_name = category_service.resolve_category(category_pattern)
    if not category_name:
        return  # User cancelled or no match

    # Delete all files in the category
    deletion_service.delete_category_files(category_name, force)


def handle_clear_orphaned_command(
    db_manager: DatabaseManager, force: bool = False
) -> None:
    """
    Handle the clear orphaned files command.

    Args:
        db_manager: Database manager instance
        force: If True, only delete from local database
    """
    deletion_service = DeletionService(db_manager)
    deletion_service.delete_orphaned_files(force)


def handle_remove_category_command(
    db_manager: DatabaseManager, category_pattern: str, force: bool = False
) -> None:
    """
    Handle the remove category command.

    Args:
        db_manager: Database manager instance
        category_pattern: Category name or pattern
        force: If True, only delete from local database
    """
    category_service = CategoryService(db_manager)
    deletion_service = DeletionService(db_manager)

    # Resolve category name
    category_name = category_service.resolve_category(category_pattern)
    if not category_name:
        return  # User cancelled or no match

    # Remove the category
    category_service.remove_category(category_name, deletion_service, force)


def handle_upload_command(
    db_manager: DatabaseManager,
    client: GoFileClient,
    files: list,
    category: Optional[str] = None,
    recursive: bool = False,
    quiet: bool = False,
) -> None:
    """
    Handle the file upload command.

    Args:
        db_manager: Database manager instance
        client: GoFile API client instance
        files: List of file paths or patterns
        category: Optional category name
        recursive: If True, recursively process directories
        quiet: If True, suppress console output
    """
    category_service = CategoryService(db_manager)
    upload_service = UploadService(db_manager, client)

    # Resolve category if provided
    if category:
        resolved_category = category_service.resolve_category(category)
        if resolved_category is None:
            return
        category = resolved_category
        print_info(f"Uploading to category: {category}")

    # Prepare files for upload
    final_files = upload_service.prepare_files(files, recursive)

    if not final_files:
        print_info("No valid files found to upload.")
        return

    # Check for MPEG-TS files
    final_files = upload_service.check_mpegts_files(final_files)

    if not final_files:
        print_info("No files to upload after filtering.")
        return

    # Get guest account from database if available
    guest_account = db_manager.get_guest_account()
    logger.debug(f"Using account token: {guest_account if guest_account else 'None (New Guest)'}")

    # Get folder ID for category if it exists
    folder_id = None
    if category:
        folder_info = db_manager.get_folder_by_category(category)
        if folder_info:
            folder_id = folder_info.get("folder_id")
            logger.debug(
                f"Using existing folder for category '{category}': {folder_id}"
            )
        else:
            logger.debug(
                f"New category '{category}' - will associate it with the upload folder"
            )

    # Upload each file
    new_category_folder_created = False
    for file_path in final_files:
        try:
            upload_info = upload_service.upload_file(
                file_path, folder_id, category, guest_account, quiet
            )

            # Save guest account if we got a new token
            if upload_info["guest_token"] and guest_account is None:
                upload_service.save_guest_account(upload_info["guest_token"])
                guest_account = upload_info["guest_token"]

            # Handle category folder mapping for new categories
            if not new_category_folder_created and category and not folder_id:
                folder_id = upload_service.handle_category_folder(
                    category,
                    folder_id,
                    upload_info["folder_id"],
                    upload_info["folder_code"],
                )
                new_category_folder_created = True

        except KeyboardInterrupt:
            logger.warning(f"Upload of {file_path} cancelled by user")
            return
        except Exception as e:
            # Error already logged in upload_service
            continue


def handle_import_token_command(db_manager: DatabaseManager, token: str) -> None:
    """
    Handle the import account token command.

    Args:
        db_manager: Database manager instance
        token: The account token to import
    """
    existing_token = db_manager.get_guest_account()

    if existing_token:
        print_warning(f"An account token already exists: {existing_token}")
        print_info(
            "If you overwrite it, make sure you have saved the old one if needed."
        )

        if not confirm_action(
            "Do you want to overwrite the existing token? (yes/no):", require_yes=True
        ):
            print_info("Import cancelled.")
            return

    if db_manager.save_guest_account(token):
        print_success(f"Successfully imported account token: {token}")
    else:
        print_info("Failed to save the account token to the database.", prefix="ERROR")


def handle_import_category_command(
    db_manager: DatabaseManager, category_data: str
) -> None:
    """
    Handle the import category command.
    Accepts pipe-separated values for a category, potentially multiple comma-separated.

    Args:
        db_manager: Database manager instance
        category_data: String containing name|id|code (comma separated for multiple)
    """
    if not category_data:
        print_info("No category data provided.", prefix="ERROR")
        return

    # Split by comma to handle multiple categories
    category_list = [c.strip() for c in category_data.split(",")]

    for category_str in category_list:
        parts = [p.strip() for p in category_str.split("|")]
        if len(parts) != 3:
            print_warning(
                f"Invalid format for category entry: '{category_str}'. Expected 'name|folder_id|folder_code'."
            )
            continue

        name, folder_id, folder_code = parts
        existing = db_manager.get_folder_by_category(name)

        if existing:
            print_warning(f"Category '{name}' already exists:")
            print_info(f"  Old Folder ID: {existing.get('folder_id')}")
            print_info(f"  Old Folder Code: {existing.get('folder_code')}")
            print_info(f"  Created At: {existing.get('created_at')}")

            if not confirm_action(
                f"Do you want to overwrite category '{name}'? (yes/no):",
                require_yes=True,
            ):
                print_info(f"Skipping category '{name}'.")
                continue

        folder_info = {
            "folder_id": folder_id,
            "folder_code": folder_code,
        }

        if db_manager.save_folder_for_category(name, folder_info):
            print_success(
                f"Successfully imported category '{name}': ID={folder_id}, Code={folder_code}"
            )
        else:
            print_info(
                f"Failed to save category '{name}' to the database.", prefix="ERROR"
            )
