#!/usr/bin/env python3
"""
Utility functions for the GoFile uploader.
"""

import os
import time
import mimetypes
import subprocess
from typing import Callable
from tqdm import tqdm

DAYS = 10 # gofile default expiry

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
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=format_name,format_long_name', 
               '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode != 0:
            # ffprobe failed, log error and assume it's not MPEG-TS
            return False
            
        # Check if output contains MPEG-TS indicators
        output = result.stdout.strip()
        return 'mpegts' in output.lower() or 'mpeg-ts' in output.lower()
        
    except Exception:
        # If ffprobe is not installed or other error occurs, assume it's not MPEG-TS
        return False


def get_mime_type(filename: str) -> str:
    """
    Determine the correct MIME type for a file, with special handling for media formats.
    
    Args:
        filename: The name of the file
        
    Returns:
        The appropriate MIME type string
    """
    # First try Python's built-in MIME type detection
    mime_type, _ = mimetypes.guess_type(filename)
    
    # Get file extension
    ext = os.path.splitext(filename)[1].lower()
    
    # Special case handling for common video and audio formats
    media_types = {
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.webm': 'video/webm',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.ts': 'video/mp2t',
        '.m4a': 'audio/mp4',
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.flac': 'audio/flac',
        '.ogg': 'audio/ogg'
    }
    
    # If it's a known media type and the detected MIME type is missing or generic,
    # use our explicit mapping
    if ext in media_types and (not mime_type or 'octet-stream' in mime_type):
        return media_types[ext]
    
    # If we have a valid MIME type from Python's detection, use that
    if mime_type:
        return mime_type
    
    # Fallback to our mapping or generic type
    return media_types.get(ext, 'application/octet-stream')


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
                    speed = bytes_read / elapsed  # bytes per second
                    pbar.set_postfix_str(format_speed(speed))

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
                result = upload_func(file_data, file_name, form_data, CHUNK_SIZE, update_progress)
                
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
        except Exception as e:
            # Log the specific exception
            import traceback
            pbar.write(f"\nError during upload: {str(e)}")
            pbar.write(traceback.format_exc())
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
