#!/usr/bin/env python3
"""
File Manager Module

Handles file listing, sorting, and deletion functions for the GoFile uploader.
"""

import logging
import unicodedata
from datetime import datetime, timedelta

from src.utils import print_dynamic_table, format_size, DAYS

# Get logger
logger = logging.getLogger("gofile_uploader")


def find_file(db_manager, file_id_or_name):
    """
    Find a file by ID, serial number, or name.

    Args:
        db_manager: The database manager instance
        file_id_or_name: ID, serial number, or name of file to find

    Returns:
        dict: A dictionary containing file info and supplementary properties:
            - file_data: The found file data dictionary
            - actual_id: The file's unique ID in the database
            - serial_id: The file's serial ID (if found by serial ID), or None
            - info_str: A formatted string with file information for display
        Returns None if no file is found or user cancels selection.
    """
    file_to_delete = None
    serial_id = None
    file_id = None
    all_files = db_manager.get_all_files()

    # Add serial IDs to all files
    for i, file in enumerate(all_files):
        file["serial_id"] = i + 1

    # First, try to find by direct ID match
    file_to_delete = db_manager.get_file_by_id(file_id_or_name)
    if file_to_delete:
        file_id = file_id_or_name
    elif file_id_or_name.isdigit():
        # No direct ID match, check if it's a numeric serial ID
        serial_id = int(file_id_or_name)

        # Find by serial ID
        for file in all_files:
            if file["serial_id"] == serial_id:
                file_to_delete = file
                break

        if not file_to_delete:
            print(f"No file found with ID or serial number {file_id_or_name}.")
            return None
    else:
        # Try to find by exact filename - collect all matches
        matching_files = []

        for file in all_files:
            if file["name"] == file_id_or_name:
                matching_files.append(file)

        if not matching_files:
            print(f"No file found with name '{file_id_or_name}'")
            return None

        # If there's only one match, use it
        if len(matching_files) == 1:
            file_to_delete = matching_files[0]
        else:
            # Multiple files with the same name - ask user to select
            print(
                f"Multiple files found with name '{file_id_or_name}'. Please select one:"
            )

            # Prepare data for table display with sequential numbers
            display_data = []
            for idx, file in enumerate(matching_files, 1):
                upload_date = file.get("upload_time", "Unknown")
                display_data.append(
                    {
                        "num": idx,
                        "category": file.get("category", "None"),
                        "upload_date": upload_date,
                        "name": file["name"],
                    }
                )
            headers = {
                "num": "#",
                "category": "Category",
                "upload_date": "Upload Date",
                "name": "Name",
            }
            print_dynamic_table(display_data, headers)
            while True:
                try:
                    choice = input(
                        "Enter the number of the file you want to select or 'q' to cancel: "
                    ).strip()
                    if choice.lower() == "q":
                        print("Selection cancelled.")
                        return None
                    if choice.isdigit() and 1 <= int(choice) <= len(matching_files):
                        file_to_delete = matching_files[int(choice) - 1]
                        break
                    else:
                        print(
                            f"Invalid selection. Please enter a number between 1 and {len(matching_files)}, or 'q' to cancel:"
                        )
                except KeyboardInterrupt:
                    print("\nSelection cancelled by user (Ctrl+C).")
                    return None

    # At this point, we have found the file
    # Get file details for display
    actual_id = file_id or file_to_delete["id"]
    name = file_to_delete["name"]

    # Prepare info string
    info_str = f"✖ '{name}' (ID: {actual_id}"
    if serial_id:
        info_str += f", Serial: {serial_id}"
    info_str += ")"

    if "category" in file_to_delete and file_to_delete["category"]:
        info_str += f" in category '{file_to_delete['category']}'"

    # Return all the information in a dictionary
    return {
        "file_data": file_to_delete,
        "actual_id": actual_id,
        "name": name,
        "serial_id": serial_id,
        "info_str": info_str,
    }


def delete_file_from_db(db_manager, file_id):
    """
    Delete a file from the local database only.

    Args:
        db_manager: The database manager instance
        file_id: ID of the file to delete

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    return db_manager.delete_file(file_id)


def sort_by_name(file_entry):
    """Sort by name with unicode normalization for special characters."""
    return unicodedata.normalize("NFKD", file_entry["name"].lower())


def sort_by_size(file_entry):
    """Sort by file size in bytes."""
    return file_entry["size_bytes"]


def sort_by_date(file_entry):
    """Sort by upload timestamp."""
    return file_entry["upload_timestamp"]


def sort_by_category(file_entry):
    """Sort by category name, case insensitive."""
    return file_entry["category"].lower()


def sort_by_expiry(file_entry):
    """Sort by expiry timestamp."""
    return file_entry["expiry_timestamp"]


def sort_by_link(file_entry):
    """Sort by download link to group by domain/folder."""
    return file_entry["download_link"]


def list_files(
    db_manager,
    category=None,
    sort_field=None,
    sort_order="asc",
    page=1,
    max_filename_length=None,
    columns=None,
):
    """
    List files with optional sorting, pagination, filename truncation, and column selection.

    Args:
        db_manager: Database manager instance
        category: Category to filter by, or None for all files
        sort_field: Field to sort by (name, size, date, category, expiry, link)
        sort_order: Sort order (asc or desc)
        page: Page number for pagination (1-based)
        max_filename_length: Maximum length for filename (None for no limit)
        columns: List of column names to display (None for all columns)

    Returns:
        bool: True if files were found and displayed, False otherwise
    """
    # Validate page number
    if page < 1:
        page = 1
    if category and not db_manager.get_folder_by_category(category):
        print(f"Error: Category '{category}' does not exist.")
        return False

    # Get files from database
    files = (
        db_manager.get_files_by_category(category)
        if category
        else db_manager.get_all_files()
    )

    if not files:
        print("No files found." + (f" for category '{category}'." if category else "."))
        return False

    # Add serial IDs to files for easier reference
    for i, file in enumerate(files):
        file["serial_id"] = i + 1

    # Format files for display
    formatted_files = []
    for i, file in enumerate(files):
        # Add the serial ID to each file
        file["serial_id"] = i + 1

        # Handle file expiry date
        upload_time = file.get("upload_time", "")
        upload_dt = None
        if upload_time:
            try:
                upload_dt = datetime.fromisoformat(upload_time)
                expiry_dt = upload_dt + timedelta(days=DAYS)
                now = datetime.now()

                # Calculate days left
                days_left = (expiry_dt - now).days
                if days_left < 0:
                    file["expiry"] = "EXPIRED"
                elif days_left <= 3:
                    file["expiry"] = f"EXPIRES SOON ({days_left} days)"
                else:
                    file["expiry"] = expiry_dt.strftime("%Y-%m-%d")
            except Exception as e:
                logger.debug(f"Error calculating expiry date: {e}")
                file["expiry"] = "Unknown"
        else:
            file["expiry"] = "Unknown"

        # Format size and date for display
        size_bytes = file.get("size", 0)
        upload_time_formatted = ""

        if upload_dt:
            upload_time_formatted = upload_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Store values for sorting before creating the dictionary
        size_original = size_bytes
        upload_time_original = upload_dt.timestamp() if upload_dt else 0
        expiry_time_original = (
            expiry_dt.timestamp() if "expiry_dt" in locals() and expiry_dt else 0
        )

        # Create formatted entry with all needed fields
        formatted_files.append(
            {
                "serial_id": str(file["serial_id"]),  # Convert to string for display
                "name": file.get("name", ""),
                "category": file.get("category", "") or "",
                "size": format_size(size_bytes),
                "size_bytes": size_original,  # For sorting
                "upload_time": upload_time_formatted,
                "upload_timestamp": upload_time_original,  # For sorting
                "expiry": file["expiry"],
                "expiry_timestamp": expiry_time_original,  # For sorting
                "download_link": file.get("download_link", ""),
            }
        )

    # Sort the files based on command-line arguments
    if sort_field:
        reverse_order = sort_order == "desc"

        # Map the sort argument to the appropriate sort function
        sort_functions = {
            "name": sort_by_name,
            "size": sort_by_size,
            "date": sort_by_date,
            "category": sort_by_category,
            "expiry": sort_by_expiry,
            "link": sort_by_link,
        }

        # Get the appropriate sort function
        sort_key = sort_functions.get(sort_field)

        # Apply the sort if we have a valid sort key
        if sort_key:
            formatted_files.sort(key=sort_key, reverse=reverse_order)

    # Define all available headers
    all_headers = {
        "serial_id": "ID",
        "name": "File Name",
        "category": "Category",
        "size": "Size",
        "upload_time": "Upload Date",
        "expiry": "Expires On",
        "download_link": "Download Link",
    }

    # Map user-friendly column names to actual column keys
    column_aliases = {
        "id": "serial_id",
        "name": "name",
        "category": "category",
        "size": "size",
        "date": "upload_time",
        "expiry": "expiry",
        "link": "download_link",
    }

    # Filter headers based on user column selection
    if columns:
        # Convert user column names to actual column keys
        selected_columns = []
        for col in columns:
            if col in column_aliases:
                selected_columns.append(column_aliases[col])
            elif col in all_headers:
                selected_columns.append(col)

        # Always include serial_id as the first column if not explicitly selected
        if "serial_id" not in selected_columns:
            selected_columns.insert(0, "serial_id")

        # Create filtered headers dictionary
        headers = {
            col: all_headers[col] for col in selected_columns if col in all_headers
        }
    else:
        # Use all headers if no columns specified
        headers = all_headers.copy()

    # Implement pagination
    page_size = 20  # Number of items per page
    total_pages = (len(formatted_files) + page_size - 1) // page_size

    # Ensure page is within valid range
    page = min(max(1, page), total_pages) if total_pages > 0 else 1

    # Get the current page of data
    current_page_data = formatted_files[(page - 1) * page_size : page * page_size]

    # Print the table
    print_dynamic_table(current_page_data, headers, max_filename_length)

    # Print pagination info below the table
    print(
        f"Page {page} of {total_pages} (showing {len(current_page_data)} of {len(formatted_files)} files)"
    )
    if total_pages > 1:
        print(f"Use '-p N' or '--page N' to view page N of {total_pages}")

    return True
