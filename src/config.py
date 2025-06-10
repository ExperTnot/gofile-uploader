#!/usr/bin/env python3
"""
Configuration management for the GoFile uploader.
Handles loading and saving configuration settings using a singleton pattern.
"""

import os
import json
from typing import Dict, Any, Optional


class Config:
    _instance: Optional["Config"] = None
    _initialized = False

    # Calculate the project root directory (parent of src/)
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # Default configuration settings
    DEFAULT_CONFIG = {
        "log_folder": os.path.join(PROJECT_ROOT, "logs"),  # Logs directory
        "log_basename": "gofile",  # Base name for log files
        "database_path": os.path.join(
            PROJECT_ROOT, "db", "gofile.db"
        ),  # Path to database
        "max_log_size_mb": 5,
        "max_log_backups": 10,
    }

    # Configuration file path
    CONFIG_FILE = os.path.join(PROJECT_ROOT, "gofile_config.json")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._config = self._load_config()
            self._initialized = True

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from the config file, or create it with defaults if it doesn't exist.
        Also ensures that necessary directories exist.

        Returns:
            Dict: Configuration settings
        """
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    # Update with any missing defaults
                    for key, value in self.DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value

                    # Ensure directories exist
                    self._ensure_directories(config)
                    return config
            except (json.JSONDecodeError, IOError):
                # If there's an error reading the config, use defaults
                pass

        # No config file or error reading it, create with defaults
        self._save_config(self.DEFAULT_CONFIG)
        self._ensure_directories(self.DEFAULT_CONFIG)
        return self.DEFAULT_CONFIG.copy()

    def _ensure_directories(self, config: Dict[str, Any]) -> None:
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

    def _save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to the config file.

        Args:
            config: Configuration settings
        """
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
        except IOError as e:
            print(f"Warning: Could not save configuration to {self.CONFIG_FILE}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key doesn't exist

        Returns:
            The configuration value or default if not found
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any, save: bool = False) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
            save: Whether to save the configuration to disk
        """
        self._config[key] = value
        if save:
            self._save_config(self._config)

    def save(self) -> None:
        """Save the current configuration to disk."""
        self._save_config(self._config)

    def ensure_database_initialized(self) -> None:
        """
        Ensure the database file and its parent directory exist.
        The actual database schema initialization is handled by DatabaseManager.
        """
        db_path = self._config["database_path"]
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # Just ensure the file exists, DatabaseManager will handle schema
        if not os.path.exists(db_path):
            open(db_path, "a").close()


# Create a single instance of the Config class
config = Config()
