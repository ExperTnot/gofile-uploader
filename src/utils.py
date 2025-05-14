#!/usr/bin/env python3
"""
Utility functions for the GoFile uploader.
"""

import os
import time
from typing import Callable
from tqdm import tqdm


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
        desc=f"Uploading {file_name}",
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
    )


def upload_with_progress(file_path: str, upload_func, desc: str = None):
    """
    Upload a file with progress tracking using requests-toolbelt for network upload progress.

    Args:
        file_path: Path to the file to upload
        upload_func: A function that takes a function to monitor upload progress
        desc: Description for the progress bar

    Returns:
        The result of the upload function
    """
    from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

    start_time = time.time()
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    desc = desc or f"Uploading {file_name}"

    # Create progress bar with known total size
    with tqdm(
        total=file_size,  # We know the total file size upfront
        initial=0,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=desc,
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
    ) as pbar:
        # Store last read position to avoid progress bar jumps
        last_position = 0

        # This callback is called during upload to update progress
        def progress_callback(monitor):
            nonlocal last_position
            # Get current bytes sent over the network
            bytes_read = monitor.bytes_read

            # Ensure we never go backwards or beyond total
            if bytes_read > last_position and bytes_read <= file_size:
                # Update progress bar by the difference
                pbar.update(bytes_read - last_position)
                last_position = bytes_read

                # Update speed display
                elapsed = time.time() - start_time
                if elapsed > 0:
                    speed = bytes_read / elapsed  # bytes per second
                    pbar.set_postfix_str(format_speed(speed))

        # Ensure we close with the bar at 100%
        def ensure_completion():
            if pbar.n < file_size:
                pbar.update(file_size - pbar.n)

        # Create a MultipartEncoder for the file upload
        with open(file_path, "rb") as file_data:
            # Create encoder
            encoder = MultipartEncoder(
                {"file": (file_name, file_data, "application/octet-stream")}
            )

            # Create a monitor for the encoder that will call our progress callback
            monitor = MultipartEncoderMonitor(encoder, progress_callback)

            # Let the upload function handle the actual POST request using our monitor
            try:
                result = upload_func(monitor, encoder.content_type)
                # Ensure progress bar completes to 100%
                ensure_completion()
            except Exception:
                # Ensure progress bar completes even if there's an error
                ensure_completion()
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
