#!/usr/bin/env python3
"""
GoFile Uploader - Command Line Interface

A tool for uploading files to GoFile.io with progress tracking and category management.
"""

import argparse

from .gofile_client import GoFileClient
from .db_manager import DatabaseManager
from .logging_utils import setup_logging, get_logger
from .config import config
from .commands import (
    handle_list_categories_command,
    handle_list_files_command,
    handle_delete_file_command,
    handle_purge_files_command,
    handle_clear_orphaned_command,
    handle_remove_category_command,
    handle_upload_command,
    handle_import_token_command,
    handle_import_category_command,
)
from .utils import DAYS

# Get logger for this module
logger = get_logger(__name__)


def _create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Upload files to GoFile.io with category management for free Gofile accounts",
        epilog=f"NOTE: This tool works with free Gofile accounts only. Due to API limitations, file records are stored locally rather than retrieved from Gofile servers. Files on Gofile.io will expire after {DAYS} days in free accounts.",
    )

    # File upload arguments
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

    # Category management
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

    # File management
    parser.add_argument(
        "-lf",
        "--list-files",
        nargs="?",
        const="all",
        help="List all uploaded files or files for a specific category (use 'all' or a category name, default is 'all')",
    )
    parser.add_argument(
        "-df",
        "--delete-file",
        help="Delete a file from GoFile servers and the local database by ID or exact filename",
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

    # File listing options
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

    # Force flag
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="When used with -df, -pf, -rm and --clear, deletes the file entry only from local database without attempting remote deletion",
    )

    # Account management
    parser.add_argument(
        "-it",
        "--import-token",
        help="Import a GoFile account token (replaces existing one, requires confirmation)",
    )

    parser.add_argument(
        "-ic",
        "--import-category",
        help="Import category mapping(s) in format 'name|folder_id|folder_code' (comma separated for multiple, requires confirmation if exists)",
    )

    return parser


def _initialize_application(args) -> tuple[DatabaseManager, GoFileClient]:
    """
    Initialize the application components.

    Args:
        args: Parsed command line arguments

    Returns:
        Tuple of (db_manager, client)
    """
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

    # Get guest account from database if available
    guest_account = db_manager.get_guest_account()

    # Initialize the client with any stored account token
    client = GoFileClient(account_token=guest_account)

    return db_manager, client


def main():
    """Main function to handle command line arguments and route to appropriate handlers."""
    parser = _create_argument_parser()
    args = parser.parse_args()

    # Initialize application
    db_manager, client = _initialize_application(args)

    # Route to appropriate command handler
    if args.list:
        handle_list_categories_command(db_manager)
        return

    if args.import_token:
        handle_import_token_command(db_manager, args.import_token)
        return

    if args.import_category:
        handle_import_category_command(db_manager, args.import_category)
        return

    if args.purge_files:
        handle_purge_files_command(db_manager, args.purge_files, args.force)
        return

    if args.clear:
        handle_clear_orphaned_command(db_manager, args.force)
        return

    if args.remove:
        handle_remove_category_command(db_manager, args.remove, args.force)
        return

    if args.list_files:
        category = args.list_files if args.list_files != "all" else None
        columns = (
            [col.strip() for col in args.columns.split(",")] if args.columns else None
        )

        handle_list_files_command(
            db_manager,
            category=category,
            sort_field=args.sort,
            sort_order=args.order,
            page=max(1, args.page),
            max_filename_length=args.max_filename,
            columns=columns,
        )
        return

    if args.delete_file:
        handle_delete_file_command(db_manager, args.delete_file, args.force)
        return

    # Handle file upload
    if not args.files:
        parser.print_help()
        return

    handle_upload_command(
        db_manager,
        client,
        args.files,
        category=args.category,
        recursive=args.recursive,
        quiet=args.quiet,
    )


if __name__ == "__main__":
    main()
