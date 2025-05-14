#!/usr/bin/env python3
"""
Logging utilities for the GoFile uploader.
Provides a rotating file logger with console output.
"""

import sys
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_folder='.', log_basename='gofile', max_bytes=5*1024*1024, backup_count=10, verbose=False):
    """
    Configure a rotating file logger with console output.
    
    Args:
        log_folder: Folder where log files will be stored (default: current directory)
        log_basename: Base name for log files (default: 'gofile')
        max_bytes: Maximum size of the log file before rotation in bytes (default: 5MB)
        backup_count: Number of backup files to keep (default: 10)
        verbose: Whether to show verbose output in the console
        
    Returns:
        The configured root logger
    """
    # Root logger configuration
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Clear existing handlers to avoid duplication
    logger.handlers = []
    
    # Rotating file handler - logs everything to file with rotation
    import os
    log_file = os.path.join(log_folder, f"{log_basename}_0.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # Console handler - logs only important info to console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO if verbose else logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    
    return logger

def get_logger(name):
    """
    Get a named logger.
    
    Args:
        name: The name for the logger
        
    Returns:
        A named logger
    """
    return logging.getLogger(name)
