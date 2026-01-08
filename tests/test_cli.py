#!/usr/bin/env python3
"""Tests for CLI argument parsing and main entry points."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gofile_uploader import main
from src import __version__


class TestVersionFlag:
    """Tests for --version flag."""

    def test_version_flag(self, capsys):
        """Should print version and exit."""
        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, 'argv', ['gofile-uploader', '--version']):
                main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert __version__ in captured.out


class TestHelpFlag:
    """Tests for --help flag."""

    def test_help_flag(self, capsys):
        """Should print help and exit."""
        with pytest.raises(SystemExit) as exc_info:
            with patch.object(sys, 'argv', ['gofile-uploader', '--help']):
                main()
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert 'usage:' in captured.out.lower()


class TestListCategories:
    """Tests for -l flag."""

    @patch('src.gofile_uploader.DatabaseManager')
    @patch('src.gofile_uploader.setup_logging')
    def test_list_categories_with_data(self, mock_logging, mock_db_class, capsys):
        """Should list categories when data exists."""
        mock_db = MagicMock()
        mock_db.get_categories_info.return_value = [{'name': 'TestCategory', 'folder_code': 'abc123'}]
        mock_db_class.return_value = mock_db

        with patch.object(sys, 'argv', ['gofile-uploader', '-l']):
            result = main()

        # Function returns None on success for list operation
        assert result is None or result == 0
        captured = capsys.readouterr()
        assert 'TestCategory' in captured.out


class TestNoArguments:
    """Tests for running without arguments."""

    def test_no_arguments_shows_help(self, capsys):
        """Should show usage when no arguments provided."""
        with patch.object(sys, 'argv', ['gofile-uploader']):
            result = main()

        captured = capsys.readouterr()
        # Either shows help or returns error
        assert result != 0 or 'usage' in captured.out.lower() or 'usage' in captured.err.lower()
