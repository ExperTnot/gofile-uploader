#!/usr/bin/env python3
"""
Category Service Module

Handles category management operations for the GoFile uploader.
"""

import logging
import shutil
from typing import Optional

from ..db_manager import DatabaseManager
from ..utils import (
    print_info,
    print_success,
    print_error,
    confirm_action,
    print_file_count_summary,
    print_operation_header,
    print_confirmation_message,
    BLUE,
    END,
)

logger = logging.getLogger("gofile_uploader")


class CategoryService:
    """Service for handling category operations."""

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize the category service.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager

    def list_categories(self) -> None:
        """List all available categories with their folder links in a multi-column layout."""
        categories_info = self.db_manager.get_categories_info()
        if not categories_info:
            print_info(
                "No categories found. Start uploading with -c to create categories."
            )
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

    def remove_category(
        self, category_name: str, deletion_service, force: bool = False
    ) -> bool:
        """
        Remove a category and optionally its associated files.

        Args:
            category_name: The category name to remove
            deletion_service: DeletionService instance for file deletion
            force: If True, only delete from local database

        Returns:
            bool: True if category was removed, False otherwise
        """
        # Confirm removal of the category itself
        if not confirm_action(
            f"Are you sure you want to remove category '{category_name}'? (yes/no):"
        ):
            print_info("Category removal cancelled.")
            return False

        # Check for associated files and ask about deleting them
        files_to_delete = self.db_manager.get_files_by_category(category_name)
        if files_to_delete:
            if confirm_action(
                f"Category '{category_name}' contains {len(files_to_delete)} file(s). Do you want to delete them as well? (yes/no):"
            ):
                # Get confirmation for file deletion
                message = print_confirmation_message(
                    "delete",
                    len(files_to_delete),
                    f"files for category '{category_name}'",
                    force,
                )

                if confirm_action(message):
                    print_operation_header(
                        "Deleting",
                        len(files_to_delete),
                        f"files for category '{category_name}'",
                    )

                    deleted_count, failed_count = deletion_service.delete_file_batch(
                        files_to_delete, force
                    )

                    print_file_count_summary(deleted_count, failed_count, "deleted")

        # Remove the category itself from the database
        if self.db_manager.remove_category(category_name):
            print_success(f"Category '{category_name}' removed successfully.")
            return True
        else:
            print_error(f"Failed to remove category '{category_name}'.")
            return False

    def resolve_category(self, category_input: str) -> Optional[str]:
        """
        Resolve a category name, with wildcard support for partial matching.

        If input ends with '*': Performs prefix search (e.g., 'doc*' -> 'documents')
        Otherwise: Treats as exact category name (existing or new)

        Args:
            category_input: The category name or pattern to resolve

        Returns:
            Resolved full category name, the original name (for new categories),
            or None if unable to resolve
        """
        if not category_input:
            return None

        # Check if this is a wildcard pattern
        if category_input.endswith("*"):
            # Remove the asterisk for prefix matching
            prefix = category_input[:-1]

            if not prefix:
                print_error("Invalid category pattern: '*' alone is not allowed.")
                return None

            # Get all categories and filter by prefix
            all_categories = self.db_manager.list_categories()
            matching_categories = [
                cat for cat in all_categories if cat.startswith(prefix)
            ]

            if not matching_categories:
                print_error(f"No categories found matching pattern '{category_input}'.")
                return None
            elif len(matching_categories) == 1:
                resolved = matching_categories[0]
                print_info(f"Resolved '{category_input}' to '{resolved}'")
                return resolved
            else:
                # Multiple matches - let user choose
                print_info(f"Multiple categories match pattern '{category_input}':")
                for i, cat in enumerate(matching_categories, 1):
                    print(f"  {i}. {cat}")

                while True:
                    try:
                        choice = input(
                            "Enter number to select (or 'q' to cancel): "
                        ).strip()
                        if choice.lower() == "q":
                            print_info("Category selection cancelled.")
                            return None

                        idx = int(choice) - 1
                        if 0 <= idx < len(matching_categories):
                            resolved = matching_categories[idx]
                            print_info(f"Selected category: '{resolved}'")
                            return resolved
                        else:
                            print_error("Invalid selection. Please try again.")
                    except (ValueError, KeyboardInterrupt):
                        print_error("\nInvalid input. Please try again.")
        else:
            # Not a wildcard pattern - return as-is (could be new or existing)
            return category_input
