#!/usr/bin/env python3
"""
Configuration management for the GoFile uploader.
Handles loading and saving configuration settings.
"""

import os
import json
import sqlite3
from typing import Dict, Any

# Calculate the project root directory (parent of src/)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Default configuration settings
DEFAULT_CONFIG = {
    "log_folder": os.path.join(PROJECT_ROOT, "logs"),  # Logs directory
    "log_basename": "gofile",  # Base name for log files
    "database_path": os.path.join(PROJECT_ROOT, "db", "gofile.db"),  # Path to database
    "max_log_size_mb": 5,
    "max_log_backups": 10,
}

# Configuration file path
CONFIG_FILE = os.path.join(PROJECT_ROOT, "gofile_config.json")


def load_config() -> Dict[str, Any]:
    """
    Load configuration from the config file, or create it with defaults if it doesn't exist.
    Also ensures that necessary directories exist.

    Returns:
        Dict: Configuration settings
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Update with any missing defaults
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value

                # Ensure directories exist
                ensure_directories(config)
                return config
        except (json.JSONDecodeError, IOError):
            # If there's an error reading the config, use defaults
            pass

    # No config file or error reading it, create with defaults
    save_config(DEFAULT_CONFIG)
    ensure_directories(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()


def ensure_directories(config: Dict[str, Any]) -> None:
    """
    Ensure that directories for logs and database exist.
    Create them if they don't exist.

    Args:
        config: Configuration settings
    """
    # Ensure log directory exists
    log_folder = config["log_folder"]
    if log_folder and not os.path.exists(log_folder):
        os.makedirs(log_folder, exist_ok=True)

    # Ensure database directory exists
    db_path = config["database_path"]
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)


def save_config(config: Dict[str, Any]) -> None:
    """
    Save configuration to the config file.

    Args:
        config: Configuration settings
    """
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except IOError:
        print(f"Warning: Could not save configuration to {CONFIG_FILE}")


def migrate_legacy_db(config: Dict[str, Any]) -> None:
    """
    Check for and migrate data from legacy database files.
    The migration is handled by the DatabaseManager, this function
    just ensures the database file is properly set in the config.

    Args:
        config: Configuration settings
    """
    target_db = config["database_path"]

    # Check if target DB exists and is initialized
    if os.path.exists(target_db):
        # Check if this is an empty/new database
        try:
            conn = sqlite3.connect(target_db)
            cursor = conn.cursor()

            # Check if categories table exists and has data
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
            )
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM categories")
                if cursor.fetchone()[0] > 0:
                    # Target DB already has data, assume it's up to date
                    conn.close()
                    return

            conn.close()
        except sqlite3.Error:
            # If there's an error accessing the database, assume it needs initialization
            pass

    # No need to check for JSON migration as the DatabaseManager already handles that
    # Just ensure the target DB file is properly set in the config
