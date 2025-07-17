#!/usr/bin/env python3
"""
GoFile Uploader

This script uploads files to GoFile.io and logs the file information and download links.
It displays a progress bar and upload speed during the upload process.
Supports categorizing files and uploading to specific folders.
"""

import os
import json
import mimetypes
import argparse
from requests.exceptions import HTTPError
import glob
import shutil
from datetime import datetime, timedelta
import builtins
from .gofile_client import GoFileClient
from .db_manager import DatabaseManager
from .logging_utils import setup_logging, get_logger
from .config import config
from .file_manager import find_file, delete_file_from_db, list_files
from .utils import (
    is_mpegts_file,
    DAYS,
    BLUE,
    END,
    resolve_category,
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

# Get logger for this module
logger = get_logger(__name__)


def handle_file_deletion(db_manager, file_id_or_name, force=False):
    """
    Handle file deletion from both GoFile server and local database.

    Finds the file by ID or name, confirms with the user, and performs
    deletion from both GoFile server (unless force=True) and local database.

    Args:
        db_manager: The database manager instance
        file_id_or_name: ID or name of file to delete
        force: If True, only delete from local database without attempting remote deletion

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    # Find the file to delete
    file_info = find_file(db_manager, file_id_or_name)

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
    if force:
        message = "This will ONLY delete the file record locally and NOT from GoFile servers. Are you sure? (yes/no):"
        if not confirm_action(message, require_yes=True):
            print_info("Deletion cancelled.")
            return False

        # Delete from local database only
        return delete_file_from_db(db_manager, actual_id, name)
    else:
        # Regular deletion including remote server
        message = "Delete file from GoFile servers and local database? (yes/no):"
        if not confirm_action(message, require_yes=True):
            print_info("Deletion cancelled.")
            return False

        # Try remote deletion first
        try:
            # Get necessary information for API call
            download_link = file_data.get("download_link", "")
            account_id = file_data.get("account_id", "")

            if not account_id:
                logger.error(
                    f"No account token found for file '{name}'. Cannot delete from GoFile server."
                )
                print("Use -f/--force to delete just the local database entry.")
                return False

            # Initialize GoFile client with the account token
            client = GoFileClient(account_token=account_id)

            # Try to delete file from GoFile server
            remote_delete_success = client.delete_contents(actual_id)

            if remote_delete_success:
                logger.info(f"File '{name}' successfully deleted from GoFile server.")
                # Now delete from local database
                if delete_file_from_db(db_manager, actual_id, name):
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
                logger.error(f"Failed to delete file '{name}' from GoFile server.")
                if download_link:
                    logger.error(
                        f"You may need to check its status manually via your browser at: {download_link}"
                    )
                return False

        except HTTPError as e:
            logger.error(
                f"HTTP error deleting file '{name}' from GoFile server: {str(e)}"
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
                f"Unexpected error deleting file '{name}' from GoFile server: {str(e)}"
            )
            if download_link:
                logger.error(
                    f"You may need to check its status manually via your browser at: {download_link}"
                )
            return False


def list_categories(db_manager):
    """List all available categories with their folder links in a multi-column layout."""
    categories_info = db_manager.get_categories_info()
    if not categories_info:
        print_info("No categories found. Start uploading with -c to create categories.")
        return

    print_info("Available categories:")

    try:
        term_width = shutil.get_terminal_size().columns
    except (AttributeError, ImportError, OSError):
        term_width = 90

    formatted_entries = []
    max_width = 0

    for category in categories_info:
        name = category["name"]
        folder_code = category["folder_code"]

        if folder_code:
            folder_link = f"{BLUE}https://gofile.io/d/{folder_code}{END}"
        else:
            folder_link = "<No folder link>"

        entry_width = max(len(name), len(folder_link) - len(BLUE) - len(END)) + 4
        max_width = max(max_width, entry_width)

        formatted_entries.append((name, folder_link))

    num_cols = max(1, term_width // max_width)

    num_rows = (len(formatted_entries) + num_cols - 1) // num_cols

    for row in range(num_rows):
        name_line = ""
        for col in range(num_cols):
            idx = col * num_rows + row
            if idx < len(formatted_entries):
                name = formatted_entries[idx][0]
                name_line += f"{name:{max_width}}"
        print(name_line)

        url_line = ""
        for col in range(num_cols):
            idx = col * num_rows + row
            if idx < len(formatted_entries):
                url = formatted_entries[idx][1]
                raw_length = (
                    len(url) - len(BLUE) - len(END) if BLUE in url else len(url)
                )
                padding = max_width - raw_length
                url_line += url + " " * padding
        print(url_line)


def purge_category_files(db_manager, category_pattern, force=False):
    """Delete all file entries for a specific category from the database and GoFile servers.

    This function is for purging files from a category that may or may not still exist.
    It supports wildcard matching and respects the --force flag to skip remote deletion.

    Args:
        db_manager: The database manager instance
        category_pattern (str): The name or pattern of the category to purge files from.
        force (bool): If True, only delete from the local database.
    """
    category_name = resolve_category(db_manager, category_pattern)
    if not category_name:
        return False  # User cancelled or no match

    files = db_manager.get_files_by_category(category_name)
    file_count = len(files)

    if file_count == 0:
        print_info(f"No files found for category '{category_name}'.")
        return False

    # Get confirmation for the irreversible action
    message = print_confirmation_message("delete", file_count, f"file entries for category '{category_name}'", force)
    
    if not confirm_action(message):
        print_info("Purge cancelled.")
        return False

    # Process each file individually using handle_file_deletion
    deleted_count = 0
    failed_count = 0
    print_operation_header("Deleting", file_count, "files from category '" + category_name + "'")

    original_input = builtins.input
    try:
        for file in files:
            file_id = file["id"]
            builtins.input = lambda prompt: "yes"  # Auto-confirm for this iteration

            try:
                result = handle_file_deletion(db_manager, file_id, force)
                if result:
                    deleted_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error deleting file {file_id}: {str(e)}")
                failed_count += 1
    finally:
        builtins.input = original_input

    print_file_count_summary(deleted_count, failed_count, "deleted")
    return deleted_count > 0


def clear_orphaned_files(db_manager, force=False):
    """Remove all file entries whose categories no longer exist from both GoFile server and database.

    Args:
        db_manager: The database manager instance
        force: If True, only delete from local database without attempting remote deletion
    """
    # First, get all files and check which ones have orphaned categories
    all_files = db_manager.get_all_files()
    categories = set(db_manager.list_categories())

    orphaned_files = []
    for file in all_files:
        if file["category"] and file["category"] not in categories:
            orphaned_files.append(file)

    if not orphaned_files:
        print_info("No orphaned files found.")
        return False

    # Display summary of orphaned files
    print_file_list_summary(orphaned_files, show_sample=True)

    # Get confirmation for the irreversible action
    message = print_confirmation_message("delete", len(orphaned_files), "orphaned file entries", force)
    
    if not confirm_action(message):
        print_info("Cleanup cancelled.")
        return False

    # Get final confirmation
    if not confirm_action("Are you ABSOLUTELY sure? This cannot be undone. (yes/no):"):
        print_info("Cleanup cancelled.")
        return False

    # Process each file individually using handle_file_deletion
    deleted_count = 0
    failed_count = 0
    print_operation_header("Deleting", len(orphaned_files), "orphaned files")

    # Group files by category for better output organization
    files_by_category = {}
    for file in orphaned_files:
        category = file["category"]
        if category not in files_by_category:
            files_by_category[category] = []
        files_by_category[category].append(file)

    # Original input function to restore later
    original_input = builtins.input

    try:
        # Process each category
        for category, files in files_by_category.items():
            print_operation_header("Processing", len(files), f"files from orphaned category '{category}'")
            category_success = 0
            category_failed = 0

            for file in files:
                file_id = file["id"]

                # Skip confirmation since we already got it for this iteration
                builtins.input = lambda prompt: "yes"  # Auto-confirm

                try:
                    result = handle_file_deletion(db_manager, file_id, force)
                    if result:
                        deleted_count += 1
                        category_success += 1
                    else:
                        failed_count += 1
                        category_failed += 1
                except Exception as e:
                    logger.error(f"Error deleting file {file_id}: {str(e)}")
                    failed_count += 1
                    category_failed += 1

            print_info(f"Completed: {category_success} deleted, {category_failed} failed for category '{category}'")
    finally:
        builtins.input = original_input

    # Print summary
    print_file_count_summary(deleted_count, failed_count, "removed")
    return deleted_count > 0


def remove_category(db_manager, category_pattern, force=False):
    """Remove a category and optionally its associated files from the database and GoFile servers.

    Supports wildcard matching (e.g. Test*) for partial matching using resolve_category.
    Respects the --force flag to skip remote deletion.

    Args:
        db_manager: The database manager instance
        category_pattern: The category name or pattern to remove
        force (bool): If True, only delete from the local database.
    """
    category_name = resolve_category(db_manager, category_pattern)
    if not category_name:
        return False  # Exited by user or no match found

    # Confirm removal of the category itself
    if not confirm_action(f"Are you sure you want to remove category '{category_name}'? (yes/no):"):
        print_info("Category removal cancelled.")
        return False

    # Check for associated files and ask about deleting them
    files_to_delete = db_manager.get_files_by_category(category_name)
    if files_to_delete:
        if confirm_action(f"Category '{category_name}' contains {len(files_to_delete)} file(s). Do you want to delete them as well? (yes/no):"):
            # Get confirmation for file deletion
            message = print_confirmation_message("delete", len(files_to_delete), f"files for category '{category_name}'", force)
            
            if confirm_action(message):
                deleted_count = 0
                failed_count = 0
                print_operation_header("Deleting", len(files_to_delete), f"files for category '{category_name}'")

                original_input = builtins.input
                try:
                    for file in files_to_delete:
                        file_id = file["id"]
                        builtins.input = lambda prompt: "yes"  # Auto-confirm

                        try:
                            result = handle_file_deletion(db_manager, file_id, force)
                            if result:
                                deleted_count += 1
                            else:
                                failed_count += 1
                        except Exception as e:
                            logger.error(
                                f"Error deleting file {file['name']} ({file_id}): {str(e)}"
                            )
                            failed_count += 1
                finally:
                    builtins.input = original_input

                print_file_count_summary(deleted_count, failed_count, "deleted")

    # Remove the category itself from the database
    if db_manager.remove_category(category_name):
        print_success(f"Category '{category_name}' removed successfully.")
        return True
    else:
        print_error(f"Failed to remove category '{category_name}'.")
        return False


def main():
    """Main function to handle command line arguments and start the upload."""
    parser = argparse.ArgumentParser(
        description="Upload files to GoFile.io with category management for free Gofile accounts",
        epilog=f"NOTE: This tool works with free Gofile accounts only. Due to API limitations, file records are stored locally rather than retrieved from Gofile servers. Files on Gofile.io will expire after {DAYS} days in free accounts.",
    )
    parser.add_argument("files", nargs="*", help="Path to file(s) you want to upload")
    parser.add_argument(
        "-c",
        "--category",
        help="Category name to organize your uploads (will create a folder on Gofile). Use '*' suffix (e.g., 'docs*' -> 'documents') for partial matching.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively upload files in directories",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress summary output"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )
    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List all available categories you've created",
    )
    parser.add_argument(
        "-rm",
        "--remove",
        help="Remove a category from local database (requires confirmation, doesn't remove folders on Gofile)",
    )
    parser.add_argument(
        "-pf",
        "--purge-files",
        type=str,
        help="Delete all file entries for a specific category from database and GoFile servers (irreversible, requires confirmation)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove all file entries from GoFile servers and the local database for which the associated categories have been deleted (irreversible, requires confirmation)",
    )
    parser.add_argument(
        "-lf",
        "--list-files",
        nargs="?",
        const="all",
        help="List all uploaded files or files for a specific category (use 'all' or a category name, default is 'all')",
    )
    parser.add_argument(
        "-s",
        "--sort",
        choices=["name", "size", "date", "category", "expiry", "link"],
        help="Sort listed files by: name, size, date (upload date), category, expiry, or link",
    )
    parser.add_argument(
        "-o",
        "--order",
        choices=["asc", "desc"],
        default="asc",
        help="Sort order: asc (ascending) or desc (descending), default is ascending",
    )
    parser.add_argument(
        "-p",
        "--page",
        type=int,
        default=1,
        help="Page number for file listings (default: 1)",
    )
    parser.add_argument(
        "-mfn",
        "--max-filename",
        nargs="?",
        type=int,
        const=80,  # Default when flag is used without value
        default=None,  # Default when flag is not used at all
        help="Maximum filename width in characters (default: no limit, 80 if flag is used without value)",
    )
    parser.add_argument(
        "-col",
        "--columns",
        type=str,
        help="Comma-separated list of columns to display (id,name,category,size,date,expiry,link)",
    )
    parser.add_argument(
        "-df",
        "--delete-file",
        help="Delete a file from GoFile servers and the local database by ID or exact filename",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="When used with -df, -pf, -rm and --clear, deletes the file entry only from local database without attempting remote deletion",
    )

    args = parser.parse_args()

    # Ensure database is properly initialized
    config.ensure_database_initialized()

    # Configure logging
    setup_logging(
        log_folder=config.get("log_folder"),
        log_basename=config.get("log_basename"),
        max_bytes=config.get("max_log_size_mb", 5) * 1024 * 1024,
        backup_count=config.get("max_log_backups", 10),
        verbose=args.verbose,
    )

    # Initialize the database manager
    db_manager = DatabaseManager(config.get("database_path"))

    # List categories if requested
    if args.list:
        list_categories(db_manager)
        return

    # Handle purge files for a category request
    if args.purge_files:
        purge_category_files(db_manager, args.purge_files, args.force)
        return

    # Handle clear orphaned files request
    if args.clear:
        clear_orphaned_files(db_manager, args.force)
        return

    # Handle remove category request
    if args.remove:
        remove_category(db_manager, args.remove, args.force)
        return

    # List uploaded files if requested
    if args.list_files:
        category = args.list_files if args.list_files != "all" else None
        sort_field = args.sort if hasattr(args, "sort") else None
        sort_order = args.order if hasattr(args, "order") else "asc"
        page = max(1, args.page) if hasattr(args, "page") else 1
        max_filename = (
            args.max_filename
            if hasattr(args, "max_filename") and args.max_filename is not None
            else None
        )

        # Parse columns if specified
        columns = None
        if hasattr(args, "columns") and args.columns:
            columns = [col.strip() for col in args.columns.split(",")]

        # Use the list_files function from file_manager module
        list_files(
            db_manager,
            category=category,
            sort_field=sort_field,
            sort_order=sort_order,
            page=page,
            max_filename_length=max_filename,
            columns=columns,
        )
        return

    # Handle file deletion if requested
    if args.delete_file:
        handle_file_deletion(db_manager, args.delete_file, args.force)
        return

    # Verify we have files to upload
    if not args.files:
        parser.print_help()
        return

    # Expand any glob patterns in the file list
    expanded_files = []
    for pattern in args.files:
        # Check if the pattern contains any glob special characters
        if any(char in pattern for char in ["*", "?", "["]):
            # Escape special characters to treat them literally
            safe_pattern = glob.escape(pattern)
            matched_files = glob.glob(safe_pattern)
            if not matched_files:
                print_warning(f"Warning: No files found matching pattern: {pattern}")
                continue
            expanded_files.extend(matched_files)
        else:
            # If it's not a pattern, just add the file if it exists
            if os.path.exists(pattern):
                expanded_files.append(pattern)
            else:
                print_warning(f"Warning: File not found: {pattern}")

    if not expanded_files:
        print_info("No valid files found to upload.")
        return

    # Handle category resolution if provided
    if args.category:
        resolved_category = resolve_category(db_manager, args.category)
        if resolved_category is None:
            return
        args.category = resolved_category
        print_info(f"Uploading to category: {args.category}")

    # Process directories based on recursive flag
    final_files = []
    for file_path in expanded_files:
        if os.path.isdir(file_path):
            if args.recursive:
                # Recursively gather all files from the directory
                logger.info(f"Recursively processing directory: {file_path}")
                for root, _, files in os.walk(file_path):
                    for filename in files:
                        final_files.append(os.path.join(root, filename))
                print_info(f"Added {len(final_files)} files from directory {file_path}")
            else:
                print_info(
                    f"No files found in directory {file_path} (use -r flag to upload directories recursively)"
                )
        else:
            final_files.append(file_path)

    if not final_files:
        print_info("No valid files found to upload after directory processing.")
        return

    # Replace the original file list with the processed one
    args.files = final_files

    # Get guest account from database if available
    guest_account = db_manager.get_guest_account()

    # Initialize the client with any stored account token
    client = GoFileClient(account_token=guest_account)

    # If a category is specified, check if we already have a folder for it
    folder_id = None
    if args.category:
        folder_info = db_manager.get_folder_by_category(args.category)

        if folder_info:
            # Use existing folder
            folder_id = folder_info.get("folder_id")
            logger.debug(
                f"Using existing folder for category '{args.category}': {folder_id}"
            )
        else:
            # If this is a new category, we'll capture the folder ID from the upload response
            logger.debug(
                f"New category '{args.category}' - will associate it with the upload folder"
            )

    # Process each file for upload
    new_category_folder_created = False
    files_to_upload = args.files.copy()  # Make a copy to allow skipping files

    # First check for MPEG-TS files and ask for confirmation
    skipped_files = []
    for i, file_path in enumerate(args.files):
        # Check if file is MPEG-TS format
        if is_mpegts_file(file_path):
            print_warning(
                f"'{os.path.basename(file_path)}' appears to be an MPEG-TS (.ts) file."
            )
            print_warning(
                "These files may not play correctly in browsers when shared via GoFile."
            )
            if not confirm_action("Do you still want to upload this file? (yes/no):", require_yes=False):
                print_info(f"Skipping '{os.path.basename(file_path)}'")
                skipped_files.append(file_path)
                logger.info(f"Skipping MPEG-TS file: {file_path} based on user request")

    # Remove skipped files from the list
    for file_path in skipped_files:
        files_to_upload.remove(file_path)

    # Now process the files that should be uploaded
    for file_path in files_to_upload:
        try:
            # Record start time for duration calculation
            start_time = datetime.now()

            # Upload the file to the specified folder (if any)
            response_data = client.upload_file(file_path, folder_id=folder_id)

            # If we reach this point, the upload was successful
            # Calculate upload duration
            duration_seconds = (datetime.now() - start_time).total_seconds()

            # Extract data from the nested 'data' object if present
            if "data" in response_data and isinstance(response_data["data"], dict):
                response_detail = response_data["data"]
            else:
                response_detail = response_data

            # Log the full response for debugging (remove in production)
            logger.debug(f"Full response: {response_data}")

            # Extract download link
            download_link = (
                response_detail.get("downloadPage")
                or response_detail.get("directLink")
                or ""
            )

            # Extract file ID
            file_id = response_detail.get("id") or response_detail.get("file_id", "")

            # Extract folder information - it's in the parentFolder field
            new_folder_id = response_detail.get("parentFolder", "")
            folder_code = response_detail.get("parentFolderCode", "")

            # Get the guest token
            guest_token = response_detail.get("guestToken", "")

            # If we have a guest token and no account saved yet, save it
            if guest_token and guest_account is None:
                logger.debug(f"Saving guest token for future uploads: {guest_token}")
                db_manager.save_guest_account(guest_token)
                # Update the client with the new token
                client.account_token = guest_token

            # If this is a new category and we have a folder ID, save the mapping
            if (
                new_folder_id
                and args.category
                and not folder_id
                and not new_category_folder_created
            ):
                logger.debug(
                    f"Saving folder information for category '{args.category}'"
                )
                folder_info = {
                    "folder_id": new_folder_id,
                    "folder_code": folder_code,
                    "category": args.category,
                    "created_at": datetime.now().isoformat(),
                }
                db_manager.save_folder_for_category(args.category, folder_info)

                # CRITICAL FIX: Update the folder_id for subsequent files in this batch
                folder_id = new_folder_id
                new_category_folder_created = True
                logger.info(
                    f"Using folder ID {folder_id} for remaining files in category '{args.category}'"
                )
                print(f"Created new folder for category '{args.category}'\n")

            # Only proceed with file info storage if we have a valid download link and file ID
            # This ensures the upload truly succeeded
            if download_link and file_id:
                # Save detailed file information to the database
                file_size = os.path.getsize(file_path)
                file_name = os.path.basename(file_path)
                mime_type = (
                    mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                )

                # Calculate upload speed (bytes per second)
                file_size = os.path.getsize(file_path)
                upload_speed_bps = (
                    file_size / duration_seconds if duration_seconds > 0 else 0.0
                )

                upload_time = datetime.now()
                expiry_date = upload_time + timedelta(days=DAYS)

                # Save file information to the database
                file_info = {
                    "id": file_id,
                    "name": file_name,
                    "size": file_size,
                    "mime_type": mime_type,
                    "upload_time": upload_time.isoformat(),
                    "expiry_date": expiry_date.isoformat(),
                    "download_link": download_link,
                    "folder_id": new_folder_id or folder_id,
                    "folder_code": folder_code,
                    "category": args.category,
                    "account_id": guest_account or guest_token,
                    "upload_speed": upload_speed_bps,
                    "upload_duration": duration_seconds,
                }

                # Only add to database if upload was complete
                db_manager.save_file_info(file_info)

                # Add entry to log file - use the same log file pattern as the rotating handler
                log_file = os.path.join(
                    config.get("log_folder"), f"{config.get('log_basename')}_0.log"
                )
                with open(log_file, "a") as log:
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "filename": os.path.basename(file_path),
                        "filesize": os.path.getsize(file_path),
                        "filesize_formatted": response_data.get(
                            "file_size_formatted", ""
                        ),
                        "upload_speed": response_data.get("speed_formatted", ""),
                        "download_link": download_link,
                        "file_id": file_id,
                        "folder_id": response_data.get(
                            "folder_id", response_data.get("parentFolder", "")
                        ),
                        "category": args.category,
                    }
                    log.write(json.dumps(log_entry) + "\n")

                # Print information to the console
                if not args.quiet:
                    print(f"\nFile: {os.path.basename(file_path)}")
                    if args.category:
                        print(f"Category: {args.category}")
                    print(f"Size: {response_data.get('file_size_formatted', '')}")
                    print(f"Upload speed: {response_data.get('speed_formatted', '')}")
                    print(f"Download link: {BLUE}{download_link}{END}")
                    print(f"Expires on: {expiry_date.strftime('%Y-%m-%d')}")
                    print("-" * 50)
            else:
                # Somehow we got a response but no valid download link or file ID
                logger.warning(
                    f"Upload of {file_path} received incomplete data from server"
                )
                print(
                    f"Warning: Upload may not have completed successfully for {os.path.basename(file_path)}"
                )

        except KeyboardInterrupt:
            logger.warning(f"Upload of {file_path} cancelled by user")
            # Do NOT add to database - return immediately
            return
        except HTTPError as e:
            if e.response.status_code == 500:
                logger.error(f"Error uploading {file_path}")
                print(
                    "Note: This often happens when the folder doesn't exist or got deleted."
                )
                print(
                    "      Please check the folder link in a browser and try again. (get folder link with -l)"
                )
                return
            logger.error(f"Error uploading {file_path}", exc_info=True)
        except Exception as e:
            logger.error(f"Error uploading {file_path}", exc_info=True)
            logger.error(f"{e}")
            print(f"Error uploading: {str(e)}")


if __name__ == "__main__":
    main()
