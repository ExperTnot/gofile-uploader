#!/usr/bin/env python3
"""
Database manager for storing and retrieving folder information using SQLite3.
"""

import sqlite3
import sys
from datetime import datetime
from typing import Dict, Optional, List
from .logging_utils import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    SQLite-based database manager for storing GoFile folder mappings.
    """

    def __init__(self, db_file: str = "gofile.db"):
        """
        Initialize the database manager.

        Args:
            db_file: Path to the database file
        """
        # Check if sqlite3 is available
        if not self._check_sqlite_available():
            logger.error("SQLite3 is not available on this system. Cannot proceed.")
            sys.exit(1)

        self.db_file = db_file
        self.conn = self._initialize_db()

    def _check_sqlite_available(self) -> bool:
        """
        Check if SQLite3 is available on the system.

        Returns:
            bool: True if SQLite3 is available, False otherwise
        """
        try:
            # sqlite3 is already imported at the top, just verify it's available
            return sqlite3 is not None
        except NameError:
            return False

    def _initialize_db(self) -> sqlite3.Connection:
        """
        Initialize the database and create tables if they don't exist.

        Returns:
            sqlite3.Connection: Database connection
        """
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # Create categories table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    name TEXT PRIMARY KEY,
                    folder_id TEXT NOT NULL,
                    folder_code TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Create settings table for guest account if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Create files table to track uploaded files
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    mime_type TEXT,
                    upload_time TEXT NOT NULL,
                    download_link TEXT NOT NULL,
                    folder_id TEXT NOT NULL,
                    folder_code TEXT,
                    category TEXT,
                    account_id TEXT,
                    upload_speed REAL,
                    upload_duration REAL
                )
            """)

            conn.commit()
            return conn
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    def get_folder_by_category(self, category: str) -> Optional[Dict[str, str]]:
        """
        Get folder information for a specific category.

        Args:
            category: The category name

        Returns:
            Dict or None: Folder information if found, None otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT folder_id, folder_code, created_at FROM categories WHERE name = ?",
                (category,),
            )
            row = cursor.fetchone()

            if row:
                return {
                    "folder_id": row[0],
                    "folder_code": row[1],
                    "category": category,
                    "created_at": row[2],
                }
            return None
        except sqlite3.Error as e:
            logger.error(f"Error getting folder for category {category}: {str(e)}")
            return None

    def save_folder_for_category(
        self, category: str, folder_info: Dict[str, str]
    ) -> None:
        """
        Save folder information for a category.

        Args:
            category: The category name
            folder_info: Dictionary with folder information
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO categories (name, folder_id, folder_code, created_at) VALUES (?, ?, ?, ?)",
                (
                    category,
                    folder_info.get("folder_id", ""),
                    folder_info.get("folder_code", ""),
                    folder_info.get("created_at", datetime.now().isoformat()),
                ),
            )
            self.conn.commit()
            logger.debug(f"Saved folder information for category: {category}")
        except sqlite3.Error as e:
            logger.error(f"Error saving folder for category {category}: {str(e)}")

    def get_guest_account(self) -> Optional[str]:
        """
        Get the stored guest account ID, if any.

        Returns:
            str or None: The guest account ID if stored, None otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = 'guest_account'")
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Error getting guest account: {str(e)}")
            return None

    def save_guest_account(self, account_id: str) -> None:
        """
        Save a guest account ID.

        Args:
            account_id: The guest account ID
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("guest_account", account_id),
            )
            self.conn.commit()
            logger.debug(f"Saved guest account ID: {account_id}")
        except sqlite3.Error as e:
            logger.error(f"Error saving guest account: {str(e)}")

    def remove_category(self, category: str) -> bool:
        """
        Remove a category from the database.

        Args:
            category: The category name to remove

        Returns:
            bool: True if the category was removed, False if it didn't exist
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM categories WHERE name = ?", (category,))
            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"Removed category: {category}")
                return True
            return False
        except sqlite3.Error as e:
            logger.error(f"Error removing category {category}: {str(e)}")
            return False

    def list_categories(self) -> List[str]:
        """
        Get a list of all stored categories.

        Returns:
            List[str]: List of category names
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM categories ORDER BY name")
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error listing categories: {str(e)}")
            return []

    def save_file_info(self, file_info: Dict[str, any]) -> bool:
        """
        Save information about an uploaded file.

        Args:
            file_info: Dictionary containing file information

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO files (
                    id, name, size, mime_type, upload_time, download_link, 
                    folder_id, folder_code, category, account_id, upload_speed, upload_duration
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_info.get("id", ""),
                    file_info.get("name", ""),
                    file_info.get("size", 0),
                    file_info.get("mime_type", ""),
                    file_info.get("upload_time", datetime.now().isoformat()),
                    file_info.get("download_link", ""),
                    file_info.get("folder_id", ""),
                    file_info.get("folder_code", ""),
                    file_info.get("category", ""),
                    file_info.get("account_id", ""),
                    file_info.get("upload_speed", 0.0),
                    file_info.get("upload_duration", 0.0),
                ),
            )
            self.conn.commit()
            logger.debug(f"Saved file information for: {file_info.get('name')}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving file information: {str(e)}")
            return False

    def get_files_by_category(self, category: str) -> List[Dict[str, any]]:
        """
        Get all files uploaded to a specific category.

        Args:
            category: The category name

        Returns:
            List[Dict]: List of file information dictionaries
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, name, size, mime_type, upload_time, download_link, folder_id, folder_code, category, account_id, upload_speed, upload_duration FROM files WHERE category = ? ORDER BY upload_time DESC",
                (category,),
            )

            files = []
            for row in cursor.fetchall():
                files.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "size": row[2],
                        "mime_type": row[3],
                        "upload_time": row[4],
                        "download_link": row[5],
                        "folder_id": row[6],
                        "folder_code": row[7],
                        "category": row[8],
                        "account_id": row[9],
                        "upload_speed": row[10],
                        "upload_duration": row[11],
                    }
                )
            return files
        except sqlite3.Error as e:
            logger.error(f"Error getting files for category {category}: {str(e)}")
            return []

    def get_all_files(self) -> List[Dict[str, any]]:
        """
        Get all uploaded files.

        Returns:
            List[Dict]: List of file information dictionaries
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, name, size, mime_type, upload_time, download_link, folder_id, folder_code, category, account_id, upload_speed, upload_duration FROM files ORDER BY upload_time DESC"
            )

            files = []
            for row in cursor.fetchall():
                files.append(
                    {
                        "id": row[0],
                        "name": row[1],
                        "size": row[2],
                        "mime_type": row[3],
                        "upload_time": row[4],
                        "download_link": row[5],
                        "folder_id": row[6],
                        "folder_code": row[7],
                        "category": row[8],
                        "account_id": row[9],
                        "upload_speed": row[10],
                        "upload_duration": row[11],
                    }
                )
            return files
        except sqlite3.Error as e:
            logger.error(f"Error getting all files: {str(e)}")
            return []

    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, any]]:
        """
        Get a file by its ID.

        Args:
            file_id: The ID of the file to retrieve

        Returns:
            Dict or None: File information if found, None otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, name, size, mime_type, upload_time, download_link, folder_id, folder_code, category, account_id, upload_speed, upload_duration FROM files WHERE id = ?",
                (file_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row[0],
                "name": row[1],
                "size": row[2],
                "mime_type": row[3],
                "upload_time": row[4],
                "download_link": row[5],
                "folder_id": row[6],
                "folder_code": row[7],
                "category": row[8],
                "account_id": row[9],
                "upload_speed": row[10],
                "upload_duration": row[11],
            }
        except sqlite3.Error as e:
            logger.error(f"Error getting file with ID {file_id}: {str(e)}")
            return None

    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from the database by its ID.

        Args:
            file_id: The ID of the file to delete

        Returns:
            bool: True if the file was deleted, False if it didn't exist or an error occurred
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))

            if cursor.rowcount > 0:
                self.conn.commit()
                logger.info(f"Deleted file with ID: {file_id}")
                return True

            logger.warning(f"No file found with ID: {file_id}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Error deleting file with ID {file_id}: {str(e)}")
            return False

    def delete_files_by_category(self, category: str) -> int:
        """
        Delete all files associated with a specific category from the database.

        Args:
            category: The category name whose files should be deleted

        Returns:
            int: Number of files deleted
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM files WHERE category = ?", (category,))
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                self.conn.commit()
                logger.info(f"Deleted {deleted_count} files associated with category: {category}")
            
            return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Error deleting files for category {category}: {str(e)}")
            return 0
