#!/usr/bin/env python3
"""Pytest configuration and shared fixtures."""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db_manager import DatabaseManager


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_db(temp_db_path):
    """Create a temporary database for testing."""
    db = DatabaseManager(temp_db_path)
    yield db
    db.close()


@pytest.fixture
def temp_file():
    """Create a temporary file for upload testing."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.write(fd, b"Test file content for upload testing")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def temp_large_file():
    """Create a larger temporary file for testing."""
    fd, path = tempfile.mkstemp(suffix=".bin")
    os.write(fd, b"x" * 1024 * 100)  # 100KB
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)
