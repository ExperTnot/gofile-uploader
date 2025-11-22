#!/usr/bin/env python3
"""
Utility functions for the GoFile uploader.
"""

import os
import time
import shutil
import subprocess
import wcwidth
from typing import Callable, Optional, List, Union
from tqdm import tqdm

DAYS = 10  # gofile default expiry
BLUE = "\033[94m"
END = "\033[0m"


def format_time(seconds: float) -> str:
    """
    Format seconds into a human-readable time string (HH:MM:SS).

    Args:
        seconds: Number of seconds

    Returns:
        Human-readable time string
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def format_size(size_bytes: int) -> str:
    """
    Format a size in bytes to a human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable string with appropriate unit (B, KB, MB, GB)
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_speed(bytes_per_second: float) -> str:
    """
    Format a speed in bytes/second to a human-readable string.

    Args:
        bytes_per_second: Speed in bytes per second

    Returns:
        Human-readable string with appropriate unit (B/s, KB/s, MB/s, GB/s)
    """
    if bytes_per_second < 1024:
        return f"{bytes_per_second:.2f} B/s"
    elif bytes_per_second < 1024 * 1024:
        return f"{bytes_per_second / 1024:.2f} KB/s"
    elif bytes_per_second < 1024 * 1024 * 1024:
        return f"{bytes_per_second / (1024 * 1024):.2f} MB/s"
    else:
        return f"{bytes_per_second / (1024 * 1024 * 1024):.2f} GB/s"


def is_mpegts_file(file_path: str) -> bool:
    """
    Check if a file is in MPEG-TS format using ffprobe.

    Args:
        file_path: Path to the file to check

    Returns:
        bool: True if the file is in MPEG-TS format, False otherwise or if ffprobe fails
    """
    try:
        # Run ffprobe command to get format information
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=format_name,format_long_name",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            # ffprobe failed, log error and assume it's not MPEG-TS
            return False

        # Check if output contains MPEG-TS indicators
        output = result.stdout.strip()
        return "mpegts" in output.lower() or "mpeg-ts" in output.lower()

    except Exception:
        # If ffprobe is not installed or other error occurs, assume it's not MPEG-TS
        return False


class ProgressFileReader:
    """
    A file reader that tracks progress and reports it to a callback function.
    """

    def __init__(self, file_obj, callback: Callable[[int], None]):
        """
        Initialize a progress file reader.

        Args:
            file_obj: The file object to read from
            callback: A callback function that takes the number of bytes read
        """
        self.file_obj = file_obj
        self.callback = callback
        self.bytes_read = 0

    def read(self, size=-1):
        """
        Read from the file and report progress.

        Args:
            size: Number of bytes to read

        Returns:
            The bytes read
        """
        chunk = self.file_obj.read(size)
        self.bytes_read += len(chunk)
        self.callback(len(chunk))
        return chunk


def create_progress_bar(file_path: str, desc: str = None) -> tqdm:
    """
    Create a progress bar for a file upload.

    Args:
        file_path: Path to the file
        desc: Description for the progress bar

    Returns:
        A tqdm progress bar
    """
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path) if desc is None else desc

    return tqdm(
        total=file_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=f"↑ {file_name}",
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
    )


def upload_with_progress(file_path: str, upload_func, desc: str = None):
    """
    Upload a file with progress tracking and frequent interrupt checks.

    Args:
        file_path: Path to the file to upload
        upload_func: A function that handles the actual upload with the signature:
                    upload_func(file_obj, file_name, form_data, chunk_size, interrupt_check_func)
        desc: Description for the progress bar

    Returns:
        The result of the upload function
    """

    start_time = time.time()
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    desc = desc or f"↑ {file_name}"

    # Create progress bar with known total size
    with tqdm(
        total=file_size,  # We know the total file size upfront
        initial=0,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=desc,
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]{postfix}",
    ) as pbar:
        # Store last read position to avoid progress bar jumps
        last_position = [0]

        # This callback is called during upload to update progress
        def progress_callback(current_bytes):
            # Get current bytes processed
            bytes_read = current_bytes

            # Ensure we never go backwards or beyond total
            if bytes_read > last_position[0] and bytes_read <= file_size:
                # Update progress bar by the difference
                pbar.update(bytes_read - last_position[0])
                last_position[0] = bytes_read

                # Update speed display
                elapsed = time.time() - start_time
                if elapsed > 0:
                    # Calculate current speed
                    speed = bytes_read / elapsed  # bytes per second

                    if not hasattr(pbar, "speed_history"):
                        pbar.speed_history = []

                    # Add current speed to history
                    timestamp = time.time()
                    pbar.speed_history.append((timestamp, speed))

                    # Keep only recent entries (last 2 seconds)
                    cutoff_time = timestamp - 2
                    pbar.speed_history = [
                        (t, s) for t, s in pbar.speed_history if t >= cutoff_time
                    ]

                    # Use slightly smoothed speed for display
                    if len(pbar.speed_history) > 1:
                        speed = sum(s for _, s in pbar.speed_history) / len(
                            pbar.speed_history
                        )

                    # Set speed display with just current speed
                    pbar.set_postfix_str(f"{format_speed(speed)}")

        # Ensure we close with the bar at 100%
        def ensure_completion():
            # Only update if not interrupted
            if pbar.n < file_size and not getattr(pbar, "_interrupted", False):
                pbar.update(file_size - pbar.n)

        # Implement a modified approach that allows more frequent interrupt checks
        # We'll set a small chunk size for reading the file to allow more frequent interrupt checks
        CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks

        try:
            # Function to check for interrupt periodically
            def check_for_interrupt():
                # This provides a hook point for keyboard interrupts to be processed
                time.sleep(0)  # Yield to the event loop briefly

            # Open the file and prepare for chunked upload
            with open(file_path, "rb") as file_data:
                # Create the initial request data
                form_data = {}

                # Create a wrapper for the progress callback
                def update_progress(bytes_read):
                    progress_callback(bytes_read)
                    # Check for interrupt after each progress update
                    check_for_interrupt()

                # Prepare the upload with progress tracking
                result = upload_func(
                    file_data, file_name, form_data, CHUNK_SIZE, update_progress
                )

                # Ensure progress bar completes to 100%
                ensure_completion()

        except KeyboardInterrupt:
            # Handle keyboard interrupt (Ctrl+C) gracefully
            # Mark as interrupted to avoid completion message
            setattr(pbar, "_interrupted", True)

            # Clear the progress bar line completely to prevent duplicate display
            pbar.clear()

            # Disable the progress bar to prevent further output
            pbar.disable = True

            # Close without additional messages
            pbar.close()

            # Re-raise the interrupt for the main handler
            raise
        except Exception:
            # Ensure progress bar is properly closed
            pbar.close()
            raise

    # Calculate and return final stats
    elapsed_time = time.time() - start_time
    speed = file_size / elapsed_time if elapsed_time > 0 else 0

    return {
        "result": result,
        "elapsed_time": elapsed_time,
        "file_size": file_size,
        "speed": speed,
        "file_size_formatted": format_size(file_size),
        "speed_formatted": format_speed(speed),
    }


def get_visual_width(text) -> int:
    """
    Calculate the visual width of text, considering emojis and other wide characters.

    Args:
        text: The string to calculate visual width for

    Returns:
        int: The visual width of the text
    """
    return wcwidth.wcswidth(str(text))


def pad_string(text, width, align="left") -> str:
    """
    Pad a string to the given visual width, taking into account wide characters like emojis.

    Args:
        text: The string to pad
        width: The desired visual width
        align: Alignment ('left', 'right', 'center')

    Returns:
        str: The padded string
    """
    text_str = str(text)
    visual_width = get_visual_width(text_str)
    padding_needed = max(0, width - visual_width)

    if align == "right":
        return " " * padding_needed + text_str
    elif align == "center":
        left_padding = padding_needed // 2
        right_padding = padding_needed - left_padding
        return " " * left_padding + text_str + " " * right_padding
    else:  # left align
        return text_str + " " * padding_needed


def print_dynamic_table(data, headers, max_filename_length=None) -> None:
    """
    Print a dynamically sized table based on content length.
    Handles wide characters like emojis correctly for proper alignment.

    Args:
        data: List of dictionaries containing the data to print
        headers: Dictionary mapping column keys to header names
        max_filename_length: Maximum length for filename column (None for no limit)
    """
    # Make a copy of data to avoid modifying the original
    display_data = data.copy()

    # Truncate filenames if max length is specified
    if max_filename_length is not None and "name" in headers:
        for row in display_data:
            if (
                "name" in row
                and get_visual_width(str(row["name"])) > max_filename_length
            ):
                # Truncate by visual width, not character count
                name = str(row["name"])
                truncated = ""
                for char in name:
                    if (
                        get_visual_width(truncated + char + "...")
                        <= max_filename_length
                    ):
                        truncated += char
                    else:
                        break
                row["name"] = truncated + "..."

    # Calculate column widths based on the longest entry + spacing
    col_widths = {col: get_visual_width(header) + 2 for col, header in headers.items()}

    # Find the maximum visual width of each column value
    for row in display_data:
        for col in headers.keys():
            value = str(row.get(col, ""))
            col_widths[col] = max(col_widths[col], get_visual_width(value) + 2)

    # Calculate total table width
    total_width = sum(col_widths.values()) + len(headers) - 1

    # Print the table
    print(f"\n{'=' * total_width}")

    # Print headers with proper padding
    header_cells = []
    for col in headers.keys():
        header_cells.append(pad_string(headers[col], col_widths[col]))
    print(" ".join(header_cells))

    print(f"{'-' * total_width}")

    # Print each row with proper padding for wide characters
    for row in display_data:
        row_cells = []
        for col in headers.keys():
            value = str(row.get(col, ""))
            row_cells.append(pad_string(value, col_widths[col]))
        print(" ".join(row_cells))

    print(f"{'=' * total_width}\n")


def print_info(message: str, prefix: str = "INFO") -> None:
    """
    Print an informational message with consistent formatting.

    Args:
        message: The message to display
        prefix: Optional prefix for the message
    """
    print(f"[{prefix}] {message}")


def print_warning(message: str) -> None:
    """
    Print a warning message with consistent formatting.

    Args:
        message: The warning message to display
    """
    print(f"[WARNING] {message}")


def print_error(message: str) -> None:
    """
    Print an error message with consistent formatting.

    Args:
        message: The error message to display
    """
    print(f"[ERROR] {message}")


def print_success(message: str) -> None:
    """
    Print a success message with consistent formatting.

    Args:
        message: The success message to display
    """
    print(f"[SUCCESS] {message}")


def print_separator(char: str = "=", width: int = 50) -> None:
    """
    Print a separator line.

    Args:
        char: Character to use for the separator
        width: Width of the separator line
    """
    print(char * width)


def confirm_action(message: str, require_yes: bool = True) -> bool:
    """
    Get user confirmation for an action with consistent formatting.

    Args:
        message: The confirmation message to display
        require_yes: If True, require exact 'yes' response; if False, accept 'y' or 'yes'

    Returns:
        bool: True if user confirmed, False otherwise
    """
    try:
        response = input(f"{message} ").strip().lower()
        if require_yes:
            return response == "yes"
        else:
            return response in ["y", "yes"]
    except (KeyboardInterrupt, EOFError):
        print("\nOperation cancelled.")
        return False


def print_file_count_summary(
    deleted: int, failed: int, operation: str = "processed"
) -> None:
    """
    Print a standardized summary of file operation results.

    Args:
        deleted: Number of files successfully processed
        failed: Number of files that failed
        operation: Description of the operation performed
    """
    total = deleted + failed
    print(f"\nOperation completed: {deleted}/{total} files {operation} successfully")
    if failed > 0:
        print(f"  - {failed} files failed")


def print_operation_header(operation: str, count: int, target: str = "files") -> None:
    """
    Print a standardized header for batch operations.

    Args:
        operation: Description of the operation (e.g., "Deleting", "Processing")
        count: Number of items being processed
        target: Type of items being processed (e.g., "files", "categories")
    """
    print(f"\n{operation} {count} {target}...")


def print_multi_column_list(
    items: List[Union[str, tuple]], headers: List[str] = None, term_width: int = None
) -> None:
    """
    Print a list of items in multiple columns with consistent formatting.
    Handles wide characters like emojis correctly for proper alignment.

    Args:
        items: List of items to display (strings or tuples for multi-column)
        headers: Optional headers for columns
        term_width: Terminal width (auto-detected if None)
    """
    if not items:
        print("No items to display.")
        return

    try:
        if term_width is None:
            term_width = shutil.get_terminal_size().columns
    except (AttributeError, ImportError, OSError):
        term_width = 90

    # Handle single column items
    if all(isinstance(item, str) for item in items):
        items = [(item,) for item in items]

    # Calculate column width based on the longest item
    max_width = 0
    for item_tuple in items:
        for item in item_tuple:
            # Handle colored text by removing ANSI codes for width calculation
            clean_item = (
                str(item).replace(BLUE, "").replace(END, "")
                if isinstance(item, str)
                else str(item)
            )
            max_width = max(max_width, get_visual_width(clean_item))

    max_width += 4  # Add padding
    num_cols = max(1, term_width // max_width)
    num_rows = (len(items) + num_cols - 1) // num_cols

    # Print headers if provided
    if headers:
        header_cells = [pad_string(header, max_width) for header in headers[:num_cols]]
        print("\n" + " ".join(header_cells))
        print("-" * (max_width * min(num_cols, len(headers))))

    # Print items in columns
    for row in range(num_rows):
        row_cells = []

        for col in range(num_cols):
            idx = col * num_rows + row
            if idx < len(items):
                item = items[idx][0]  # Get first column for this item
                row_cells.append(pad_string(str(item), max_width))

        print("".join(row_cells))

    print()  # Add spacing after the list


def print_file_list_summary(
    files: list, category: str = None, show_sample: bool = True, max_sample: int = 5
) -> None:
    """
    Print a summary of files with optional sampling for large lists.

    Args:
        files: List of file dictionaries
        category: Optional category name to include in the summary
        show_sample: Whether to show a sample of files
        max_sample: Maximum number of files to show in sample
    """
    if not files:
        category_text = f" for category '{category}'" if category else ""
        print(f"No files found{category_text}.")
        return

    count = len(files)
    category_text = f" for category '{category}'" if category else ""
    print(f"Found {count} file{'s' if count != 1 else ''}{category_text}:")

    if show_sample and files:
        for i, file in enumerate(files[:max_sample]):
            name = file.get("name", "Unknown")
            category_info = (
                f" (Category: '{file.get('category', 'Unknown')}')"
                if not category
                else ""
            )
            print(f"  - {name}{category_info}")

        if len(files) > max_sample:
            print(f"  ... and {len(files) - max_sample} more")

    print()  # Add spacing


def print_confirmation_message(
    action: str, count: int, target: str, force: bool = False, irreversible: bool = True
) -> str:
    """
    Generate a standardized confirmation message for destructive operations.

    Args:
        action: Description of the action (e.g., "delete", "remove")
        count: Number of items affected
        target: Description of what's being affected
        force: Whether this is a force operation (local only)
        irreversible: Whether to include irreversible warning

    Returns:
        str: Formatted confirmation message
    """
    if force:
        message = f"This will {action} {count} {target} from the LOCAL DATABASE ONLY.\n"
        message += "Files will remain on the GoFile server and cannot be deleted remotely after this action.\n"
    else:
        message = (
            f"This will attempt to {action} {count} {target} from GoFile servers.\n"
        )
        message += "Files will be removed from the local database ONLY IF they are successfully deleted from the GoFile server.\n"

    if irreversible:
        message += "This action is IRREVERSIBLE. "

    message += "Continue? (yes/no): "
    return message
