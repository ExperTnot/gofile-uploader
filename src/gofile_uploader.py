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
from datetime import datetime, timedelta
from .gofile_client import GoFileClient
from .db_manager import DatabaseManager
from .logging_utils import setup_logging, get_logger
from .config import load_config, migrate_legacy_db
from .file_manager import (
    handle_file_deletion, 
    list_files
)

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


def remove_category(db_manager, category):
    """Remove a category."""
    if db_manager.remove_category(category):
        print(f"Category '{category}' removed successfully.")
    else:
        print(f"Failed to remove category '{category}'.")


# Function moved to file_manager.py


def main():
    """Main function to handle command line arguments and start the upload."""
    parser = argparse.ArgumentParser(
        description="Upload files to GoFile.io with category management"
    )
    parser.add_argument("files", nargs="*", help="Files to upload")
    parser.add_argument("-c", "--category", help="Category to upload files to")
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress summary output"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="List all available categories"
    )
    parser.add_argument(
        "-rm", "--remove", help="Remove a category (requires confirmation)"
    )
    parser.add_argument(
        "-lf",
        "--list-files",
        nargs="?",
        const="all",
        help="List all uploaded files or files for a specific category",
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
        "-df",
        "--delete-file",
        help="Delete a file entry from the database by ID or exact filename (will not delete from GoFile servers)",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config()

    # Check for legacy database
    migrate_legacy_db(config)

    # Configure logging
    setup_logging(
        log_folder=config["log_folder"],
        log_basename=config["log_basename"],
        max_bytes=config["max_log_size_mb"] * 1024 * 1024,
        backup_count=config["max_log_backups"],
        verbose=args.verbose,
    )

    # Initialize the database manager
    db_manager = DatabaseManager(config["database_path"])

    # List categories if requested
    if args.list:
        list_categories(db_manager)
        return

    # Handle category removal with confirmation
    if args.remove:
        category = args.remove
        # Check if category exists
        if not db_manager.get_folder_by_category(category):
            print(f"Error: Category '{category}' does not exist.")
            return

        # Ask for confirmation
        confirmation = input(
            f"Are you sure you want to remove category '{category}'? This cannot be undone. (yes/no): "
        )
        if confirmation.lower() == "yes":
            db_manager.remove_category(category)
            print(f"Category '{category}' has been removed.")
        else:
            print("Category removal cancelled.")
        return

    # List uploaded files if requested
    if args.list_files:
        category = args.list_files if args.list_files != "all" else None
        sort_field = args.sort if hasattr(args, 'sort') else None
        sort_order = args.order if hasattr(args, 'order') else "asc"
        
        # Use the list_files function from file_manager module
        list_files(db_manager, category, sort_field, sort_order)
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
    for file_path in args.files:
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
            if new_folder_id and args.category and not folder_id and not new_category_folder_created:
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
                logger.info(f"Using folder ID {folder_id} for remaining files in category '{args.category}'")
                print(f"Created new folder for category '{args.category}'\n")

            # Only proceed with file info storage if we have a valid download link and file ID
            # This ensures the upload truly succeeded
            if download_link and file_id:
                # Save detailed file information to the database
                file_size = os.path.getsize(file_path)
                file_name = os.path.basename(file_path)
                mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    
                # Calculate upload speed (bytes per second)
                file_size = os.path.getsize(file_path)
                upload_speed_bps = (
                    file_size / duration_seconds if duration_seconds > 0 else 0.0
                )
    
                # Calculate expiry date (14 days from upload)
                upload_time = datetime.now()
                expiry_date = upload_time + timedelta(days=14)
                
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
                    config["log_folder"], f"{config['log_basename']}_0.log"
                )
                with open(log_file, "a") as log:
                    log_entry = {
                        "timestamp": datetime.now().isoformat(),
                        "filename": os.path.basename(file_path),
                        "filesize": os.path.getsize(file_path),
                        "filesize_formatted": response_data.get("file_size_formatted", ""),
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
                    print(f"Download link: {download_link}")
                    print(f"Expires on: {expiry_date.strftime('%Y-%m-%d')}")
                    print("-" * 50)
            else:
                # Somehow we got a response but no valid download link or file ID
                logger.warning(f"Upload of {file_path} received incomplete data from server")
                print(f"Warning: Upload may not have completed successfully for {os.path.basename(file_path)}")

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
