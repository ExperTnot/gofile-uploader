#!/usr/bin/env python3
"""
File Manager Module

Handles file listing, sorting, and deletion functions for the GoFile uploader.
"""

import unicodedata
from datetime import datetime, timedelta
import logging
from .utils import format_size

# Get logger
logger = logging.getLogger("gofile_uploader")


def confirm_and_delete_file(db_manager, file_to_delete, file_id=None, file_name=None, serial_id=None):
    """
    Display confirmation and handle file deletion from the database.
    
    Args:
        db_manager: The database manager instance
        file_to_delete: Dict containing file information
        file_id: Optional file ID to use for deletion
        file_name: Optional file name to display in messages
        serial_id: Optional serial ID to display
        
    Returns:
        bool: True if deletion was confirmed and succeeded, False otherwise
    """
    # Use provided values or extract from file_to_delete
    actual_id = file_id or file_to_delete["id"]
    name = file_name or file_to_delete["name"]
    
    # Print file info in a compact format
    info_str = f"Found: '{name}' (ID: {actual_id}"
    if serial_id:
        info_str += f", Serial: {serial_id}"
    info_str += ")"
    
    if "category" in file_to_delete and file_to_delete["category"]:
        info_str += f" in category '{file_to_delete['category']}'"
    print(info_str)
    
    # Simplified warning and confirmation
    confirmation = input("Delete database entry (does not remove file from GoFile)? (yes/no): ")
    if confirmation.lower() == "yes":
        if db_manager.delete_file(actual_id):
            print(f"Entry for '{name}' deleted from database.")
            return True
        else:
            print("Failed to delete entry from database.")
    else:
        print("Deletion cancelled.")
    return False


def handle_file_deletion(db_manager, file_id_or_name):
    """
    Handle file deletion based on ID or name.
    
    Args:
        db_manager: The database manager instance
        file_id_or_name: ID or name of file to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    # First, try to find by ID (which could be either the actual file ID or a serial ID)
    if file_id_or_name.isdigit():
        # Could be a serial ID, let's check all files
        serial_id = int(file_id_or_name)
        all_files = db_manager.get_all_files()
        
        # Add serial IDs
        for i, file in enumerate(all_files):
            file["serial_id"] = i + 1
            
        # Find by serial ID
        file_to_delete = None
        for file in all_files:
            if file["serial_id"] == serial_id:
                file_to_delete = file
                break
                
        if file_to_delete:
            return confirm_and_delete_file(db_manager, file_to_delete, serial_id=serial_id)
        else:
            # Try as a direct file ID
            file = db_manager.get_file_by_id(file_id_or_name)
            if file:
                return confirm_and_delete_file(db_manager, file, file_id=file_id_or_name)
            else:
                print(f"No file found with ID {file_id_or_name}.")
    else:
        # Try to find by exact filename
        all_files = db_manager.get_all_files()
        file_to_delete = None
        
        for file in all_files:
            if file["name"] == file_id_or_name:
                file_to_delete = file
                break
                
        if file_to_delete:
            return confirm_and_delete_file(db_manager, file_to_delete, file_name=file_id_or_name)
        else:
            print(f"No file found with name '{file_id_or_name}'.")
            
    return False


def print_dynamic_table(data, headers):
    """Print a dynamically sized table based on content length.

    Args:
        data: List of dictionaries containing the data to print
        headers: Dictionary mapping column keys to header names
    """
    # Calculate column widths based on the longest entry + spacing
    col_widths = {col: len(header) + 2 for col, header in headers.items()}

    # Find the maximum length of each column value
    for row in data:
        for col in headers.keys():
            value = str(row.get(col, ""))
            col_widths[col] = max(col_widths[col], len(value) + 2)

    # Create format string for each row
    format_str = " ".join([f"{{:{col_widths[col]}}}" for col in headers.keys()])

    # Calculate total table width
    total_width = (
        sum(col_widths.values()) + len(headers) - 1
    )  # -1 for one less space than columns

    # Print the table
    print(f"\n{'=' * total_width}")
    print(format_str.format(*[headers[col] for col in headers.keys()]))
    print(f"{'-' * total_width}")

    for row in data:
        print(
            format_str.format(
                *[str(row.get(col, "")) for col in headers.keys()]
            )
        )

    print(f"{'=' * total_width}\n")


def sort_by_name(file_entry):
    """Sort by name with unicode normalization for special characters."""
    return unicodedata.normalize('NFKD', file_entry["name"].lower())
    
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


def list_files(db_manager, category=None, sort_field=None, sort_order="asc"):
    """
    List files with optional sorting.
    
    Args:
        db_manager: Database manager instance
        category: Category to filter by, or None for all files
        sort_field: Field to sort by (name, size, date, category, expiry, link)
        sort_order: Sort order (asc or desc)
        
    Returns:
        bool: True if files were found and displayed, False otherwise
    """
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
        print(
            "No files found."
            + (f" for category '{category}'." if category else ".")
        )
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
                # Calculate expiry date (14 days from upload)
                expiry_dt = upload_dt + timedelta(days=14)
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
        expiry_time_original = expiry_dt.timestamp() if 'expiry_dt' in locals() and expiry_dt else 0
        
        # Create formatted entry with all needed fields
        formatted_files.append({
            "serial_id": str(file["serial_id"]),  # Convert to string for display
            "name": file.get("name", ""),
            "category": file.get("category", "") or "",
            "size": format_size(size_bytes),
            "size_bytes": size_original,  # For sorting
            "upload_time": upload_time_formatted,
            "upload_timestamp": upload_time_original,  # For sorting
            "expiry": file["expiry"],
            "expiry_timestamp": expiry_time_original,  # For sorting
            "download_link": file.get("download_link", "")
        })

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
            "link": sort_by_link
        }
        
        # Get the appropriate sort function
        sort_key = sort_functions.get(sort_field)
        
        # Apply the sort if we have a valid sort key
        if sort_key:
            formatted_files.sort(key=sort_key, reverse=reverse_order)
    
    # Define headers
    headers = {
        "serial_id": "ID",
        "name": "File Name",
        "category": "Category",
        "size": "Size",
        "upload_time": "Upload Date",
        "expiry": "Expires On",
        "download_link": "Download Link",
    }

    # Print the table
    print_dynamic_table(formatted_files, headers)
    return True
