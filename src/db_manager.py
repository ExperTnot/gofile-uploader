#!/usr/bin/env python3
"""
Database manager for storing and retrieving folder information using SQLite3.
"""

import sqlite3
import sys
from datetime import datetime
from typing import Dict, Optional, List, Union
from src.logging_utils import get_logger

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
    ) -> bool:
        """
        Save folder information for a category.

        Args:
            category: The category name
            folder_info: Dictionary with folder information

        Returns:
            bool: True if successful, False otherwise
        """
        if not category or not isinstance(category, str):
            logger.error("Invalid category name provided")
            return False

        if not folder_info or not isinstance(folder_info, dict):
            logger.error("Invalid folder_info provided")
            return False

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
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving folder for category {category}: {str(e)}")
            return False

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

    def save_guest_account(self, account_id: str) -> bool:
        """
        Save a guest account ID.

        Args:
            account_id: The guest account ID

        Returns:
            bool: True if successful, False otherwise
        """
        if not account_id or not isinstance(account_id, str):
            logger.error("Invalid account_id provided")
            return False

        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("guest_account", account_id),
            )
            self.conn.commit()
            logger.debug(f"Saved guest account ID: {account_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving guest account: {str(e)}")
            return False

    def clear_guest_account(self) -> bool:
        """
        Clear the stored guest account token.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM settings WHERE key = 'guest_account'")
            self.conn.commit()
            if cursor.rowcount > 0:
                logger.info("Cleared guest account token")
                return True
            logger.debug("No guest account token was stored")
            return False
        except sqlite3.Error as e:
            logger.error(f"Error clearing guest account: {str(e)}")
            return False

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
                return True
            return False
        except sqlite3.Error as e:
            logger.error(f"Error removing category {category}: {str(e)}")
            return False

    def list_categories(self) -> List[str]:
        """
        Get a list of all stored category names.

        Returns:
            List[str]: List of category names, empty list if error or no categories
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM categories ORDER BY name")
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Error listing categories: {str(e)}")
            return []

    def get_categories_info(self) -> List[Dict[str, str]]:
        """
        Get detailed information about all stored categories.

        Returns:
            List[Dict]: List of category info dictionaries with keys:
                       'name', 'folder_id', 'folder_code', 'created_at'
                       Empty list if error or no categories
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT name, folder_id, folder_code, created_at FROM categories ORDER BY name"
            )
            return [
                {
                    "name": row[0],
                    "folder_id": row[1],
                    "folder_code": row[2],
                    "created_at": row[3],
                }
                for row in cursor.fetchall()
            ]
        except sqlite3.Error as e:
            logger.error(f"Error getting categories info: {str(e)}")
            return []

    def save_file_info(
        self, file_info: Dict[str, Union[str, int, float, None]]
    ) -> bool:
        """
        Save information about an uploaded file.

        Args:
            file_info: Dictionary containing file information

        Returns:
            bool: True if successful, False otherwise
        """
        if not file_info or not isinstance(file_info, dict):
            logger.error("Invalid file_info provided")
            return False

        # Validate required fields
        required_fields = ["id", "name", "download_link"]
        for field in required_fields:
            if not file_info.get(field):
                logger.error(f"Missing required field '{field}' in file_info")
                return False

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

    def get_files_by_category(
        self, category: str
    ) -> List[Dict[str, Union[str, int, float, None]]]:
        """
        Get all files uploaded to a specific category.

        Args:
            category: The category name

        Returns:
            List[Dict]: List of file information dictionaries, empty list if error or no files
        """
        if not category or not isinstance(category, str):
            logger.error("Invalid category provided")
            return []

        return self._get_files_with_filter("category = ?", (category,))

    def get_all_files(self) -> List[Dict[str, Union[str, int, float, None]]]:
        """
        Get all uploaded files.

        Returns:
            List[Dict]: List of file information dictionaries, empty list if error or no files
        """
        return self._get_files_with_filter()

    def get_file_by_id(
        self, file_id: str
    ) -> Optional[Dict[str, Union[str, int, float, None]]]:
        """
        Get a file by its ID.

        Args:
            file_id: The ID of the file to retrieve

        Returns:
            Dict or None: File information if found, None otherwise
        """
        if not file_id or not isinstance(file_id, str):
            logger.error("Invalid file_id provided")
            return None

        files = self._get_files_with_filter("id = ?", (file_id,))
        return files[0] if files else None

    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from the database by its ID.

        Args:
            file_id: The ID of the file to delete

        Returns:
            bool: True if the file was deleted, False if it didn't exist or an error occurred
        """
        if not file_id or not isinstance(file_id, str):
            logger.error("Invalid file_id provided")
            return False

        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))

            if cursor.rowcount > 0:
                self.conn.commit()
                logger.debug(f"Deleted file with ID: {file_id}")
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
            int: Number of files deleted, 0 if error or no files found
        """
        if not category or not isinstance(category, str):
            logger.error("Invalid category provided")
            return 0

        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM files WHERE category = ?", (category,))
            deleted_count = cursor.rowcount

            if deleted_count > 0:
                self.conn.commit()
                logger.info(
                    f"Deleted {deleted_count} files associated with category: {category}"
                )

            return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Error deleting files for category {category}: {str(e)}")
            return 0

    def _get_files_with_filter(
        self, where_clause: Optional[str] = None, params: Optional[tuple] = None
    ) -> List[Dict[str, Union[str, int, float, None]]]:
        """
        Internal method to get files with optional filtering.

        Args:
            where_clause: Optional WHERE clause (without the WHERE keyword)
            params: Parameters for the WHERE clause

        Returns:
            List[Dict]: List of file information dictionaries
        """
        try:
            cursor = self.conn.cursor()
            base_query = """
                SELECT id, name, size, mime_type, upload_time, download_link, 
                       folder_id, folder_code, category, account_id, upload_speed, upload_duration 
                FROM files
            """

            if where_clause:
                query = f"{base_query} WHERE {where_clause} ORDER BY upload_time DESC"
                cursor.execute(query, params or ())
            else:
                query = f"{base_query} ORDER BY upload_time DESC"
                cursor.execute(query)

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
            logger.error(f"Error getting files: {str(e)}")
            return []

    def get_file_count(self, category: Optional[str] = None) -> int:
        """
        Get the count of files, optionally filtered by category.

        Args:
            category: Optional category to filter by

        Returns:
            int: Number of files, 0 if error
        """
        try:
            cursor = self.conn.cursor()
            if category:
                if not isinstance(category, str):
                    logger.error("Invalid category provided")
                    return 0
                cursor.execute(
                    "SELECT COUNT(*) FROM files WHERE category = ?", (category,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM files")

            result = cursor.fetchone()
            return result[0] if result else 0
        except sqlite3.Error as e:
            logger.error(f"Error getting file count: {str(e)}")
            return 0

    def get_category_count(self) -> int:
        """
        Get the count of categories.

        Returns:
            int: Number of categories, 0 if error
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM categories")
            result = cursor.fetchone()
            return result[0] if result else 0
        except sqlite3.Error as e:
            logger.error(f"Error getting category count: {str(e)}")
            return 0

    def close(self) -> None:
        """
        Close the database connection.
        """
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
