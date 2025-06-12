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
import glob
from datetime import datetime, timedelta
from .gofile_client import GoFileClient
from .db_manager import DatabaseManager
from .logging_utils import setup_logging, get_logger
from .config import config
from .file_manager import handle_file_deletion, list_files
from .utils import is_mpegts_file, DAYS, BLUE, END

# Get logger for this module
logger = get_logger(__name__)


def list_categories(db_manager):
    """List all available categories."""
    categories = db_manager.list_categories()
    if not categories:
        print("No categories found. Start uploading with -c to create categories.")
    else:
        print("Available categories:")
        for category in sorted(categories):
            print(f"  - {category}")


def purge_category_files(db_manager, category):
    """Delete all file entries for a specific category from the database.

    This function will delete file entries even if the category itself no longer exists.
    """
    # Get count of files first to inform the user
    files = db_manager.get_files_by_category(category)
    file_count = len(files)

    if file_count == 0:
        print(f"No file entries found for category '{category}'.")
        return False

    # Get confirmation first due to irreversible action
    confirmation = input(
        f"This will delete {file_count} file entries for category '{category}'. This is IRREVERSIBLE. Continue? (yes/no): "
    )
    if confirmation.lower() != "yes":
        print("File deletion cancelled.")
        return False

    # Get final confirmation due to irreversible action
    final_confirm = input(
        f"Are you ABSOLUTELY sure you want to delete {file_count} file entries? (yes/no): "
    )
    if final_confirm.lower() != "yes":
        print("File deletion cancelled.")
        return False

    deleted_count = db_manager.delete_files_by_category(category)
    print(f"Deleted {deleted_count} file entries for category '{category}'.")
    return True


def clear_orphaned_files(db_manager):
    """Remove all file entries from the database whose categories no longer exist.

    This is an irreversible action that requires confirmation.
    """
    # First, get all files and check which ones have orphaned categories
    all_files = db_manager.get_all_files()
    categories = set(db_manager.list_categories())

    orphaned_files = []
    for file in all_files:
        if file["category"] and file["category"] not in categories:
            orphaned_files.append(file)

    if not orphaned_files:
        print("No orphaned files found.")
        return False

    # Get confirmation for the irreversible action
    print(f"Found {len(orphaned_files)} file entries with deleted categories:")
    # Display sample of orphaned files (up to 5)
    for i, file in enumerate(orphaned_files[:5]):
        print(f"  - {file['name']} (Category: '{file['category']}')")
    if len(orphaned_files) > 5:
        print(f"  ... and {len(orphaned_files) - 5} more")

    confirmation = input(
        f"\nDo you want to delete these {len(orphaned_files)} orphaned file entries? This is IRREVERSIBLE. (yes/no): "
    )
    if confirmation.lower() != "yes":
        print("Cleanup cancelled.")
        return False

    # Get final confirmation
    final_confirm = input("Are you ABSOLUTELY sure? This cannot be undone. (yes/no): ")
    if final_confirm.lower() != "yes":
        print("Cleanup cancelled.")
        return False

    # Delete files by category
    deleted_count = 0
    orphaned_categories = set(file["category"] for file in orphaned_files)

    for category in orphaned_categories:
        count = db_manager.delete_files_by_category(category)
        deleted_count += count
        print(f"Deleted {count} file entries for orphaned category '{category}'")

    print(f"\nTotal: {deleted_count} orphaned file entries removed successfully.")
    return True


def remove_category(db_manager, category):
    """Remove a category and optionally its associated files from the database."""
    # Get confirmation first
    confirmation = input(
        f"Are you sure you want to remove category '{category}'? (yes/no): "
    )
    if confirmation.lower() != "yes":
        print("Category removal cancelled.")
        return False

    # Ask if user also wants to delete all files in this category
    delete_files = input(
        f"Do you also want to delete all file entries for '{category}'? This is IRREVERSIBLE. (yes/no): "
    )

    if delete_files.lower() == "yes":
        # Get count of files first to inform the user
        files = db_manager.get_files_by_category(category)
        file_count = len(files)

        if file_count > 0:
            # Get final confirmation due to irreversible action
            final_confirm = input(
                f"This will delete {file_count} file entries for category '{category}'. Are you ABSOLUTELY sure? (yes/no): "
            )

            if final_confirm.lower() == "yes":
                deleted_count = db_manager.delete_files_by_category(category)
                print(
                    f"Deleted {deleted_count} file entries for category '{category}'."
                )
            else:
                print("File deletion cancelled.")
                # Still proceed with category removal
        else:
            print(f"No file entries found for category '{category}'.")

    # Now remove the category itself
    if db_manager.remove_category(category):
        print(f"Category '{category}' removed successfully.")
        return True
    else:
        print(f"Failed to remove category '{category}'. Category may not exist.")
        return False


# Function moved to file_manager.py


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
        help="Category name to organize your uploads (will create a folder on Gofile)",
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
        help="Delete all file entries for a specific category from database (irreversible, requires confirmation)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove all file entries for which the associated categories have been deleted (irreversible, requires confirmation)",
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
        help="Maximum filename width in characters (default: no limit, 80 if flag is used without value, 0 for no limit)",
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
        help="Delete a file entry from the local database by ID or exact filename (Note: this won't delete the file from GoFile servers)",
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
        purge_category_files(db_manager, args.purge_files)
        return

    # Handle clear orphaned files request
    if args.clear:
        clear_orphaned_files(db_manager)
        return

    # Handle remove category request
    if args.remove:
        remove_category(db_manager, args.remove)
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
        # Use the handle_file_deletion function from file_manager module
        handle_file_deletion(db_manager, args.delete_file)
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
                print(f"Warning: No files found matching pattern: {pattern}")
                continue
            expanded_files.extend(matched_files)
        else:
            # If it's not a pattern, just add the file if it exists
            if os.path.exists(pattern):
                expanded_files.append(pattern)
            else:
                print(f"Warning: File not found: {pattern}")

    if not expanded_files:
        print("No valid files found to upload.")
        return

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
                print(f"Added {len(final_files)} files from directory {file_path}")
            else:
                print(
                    f"Skipping directory: {file_path} (use -r flag to upload directories recursively)"
                )
        else:
            final_files.append(file_path)

    if not final_files:
        print("No valid files found to upload after directory processing.")
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
            print(
                f"WARNING: '{os.path.basename(file_path)}' appears to be an MPEG-TS (.ts) file."
            )
            print(
                "These files may not play correctly in browsers when shared via GoFile."
            )
            confirmation = input("Do you still want to upload this file? (yes/no): ")
            if confirmation.lower() != "yes":
                print(f"Skipping '{os.path.basename(file_path)}'")
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
        except Exception as e:
            logger.error(f"Error uploading {file_path}", exc_info=True)
            logger.error(f"{e}")
            print(f"Error uploading: {str(e)}")


if __name__ == "__main__":
    main()
