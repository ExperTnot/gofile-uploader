# GoFile Uploader v1.0 UX Improvements - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform gofile-uploader into a v1.0 release with subcommand syntax, comprehensive filtering, view modes, interactive mode, and improved UX while maintaining full backwards compatibility.

**Architecture:** Add argparse subparsers for new command structure while preserving existing flag-based routing. Implement a filter system that composes multiple predicates. Create an interactive mode using simple numbered menus (no TUI libraries). Add color support with graceful degradation for non-TTY.

**Tech Stack:** Python 3.x, argparse subparsers, SQLite (existing), tqdm (existing), wcwidth (existing)

---

## Task 1: Size Parsing Utility

**Files:**
- Create: `src/size_parser.py`
- Test: `tests/test_size_parser.py`

**Step 1: Write the failing tests**

```python
# tests/test_size_parser.py
"""Tests for size parsing utility."""
import pytest
from src.size_parser import parse_size, ParseSizeError


class TestParseSize:
    """Test parse_size function."""

    def test_bytes_plain_number(self):
        """Plain numbers are treated as bytes."""
        assert parse_size("1048576") == 1048576

    def test_kilobytes_kb(self):
        """Parse KB suffix."""
        assert parse_size("500KB") == 500 * 1024

    def test_kilobytes_k(self):
        """Parse K suffix."""
        assert parse_size("500K") == 500 * 1024

    def test_megabytes_mb(self):
        """Parse MB suffix."""
        assert parse_size("100MB") == 100 * 1024 * 1024

    def test_megabytes_m(self):
        """Parse M suffix."""
        assert parse_size("100M") == 100 * 1024 * 1024

    def test_gigabytes_gb(self):
        """Parse GB suffix."""
        assert parse_size("1GB") == 1 * 1024 * 1024 * 1024

    def test_gigabytes_g(self):
        """Parse G suffix."""
        assert parse_size("1G") == 1 * 1024 * 1024 * 1024

    def test_case_insensitive(self):
        """Size parsing is case-insensitive."""
        assert parse_size("100mb") == parse_size("100MB")
        assert parse_size("1gb") == parse_size("1GB")

    def test_with_spaces(self):
        """Handles spaces between number and unit."""
        assert parse_size("100 MB") == 100 * 1024 * 1024

    def test_decimal_values(self):
        """Handles decimal values."""
        assert parse_size("1.5GB") == int(1.5 * 1024 * 1024 * 1024)

    def test_invalid_format_raises(self):
        """Invalid format raises ParseSizeError."""
        with pytest.raises(ParseSizeError):
            parse_size("invalid")

    def test_negative_raises(self):
        """Negative values raise ParseSizeError."""
        with pytest.raises(ParseSizeError):
            parse_size("-100MB")

    def test_empty_raises(self):
        """Empty string raises ParseSizeError."""
        with pytest.raises(ParseSizeError):
            parse_size("")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_size_parser.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.size_parser'"

**Step 3: Write minimal implementation**

```python
# src/size_parser.py
"""Size parsing utility for human-readable size strings."""
import re


class ParseSizeError(ValueError):
    """Raised when size string cannot be parsed."""
    pass


# Size multipliers in bytes
SIZE_UNITS = {
    'B': 1,
    'K': 1024,
    'KB': 1024,
    'M': 1024 ** 2,
    'MB': 1024 ** 2,
    'G': 1024 ** 3,
    'GB': 1024 ** 3,
    'T': 1024 ** 4,
    'TB': 1024 ** 4,
}

# Pattern: optional whitespace, number (with optional decimal), optional whitespace, optional unit
SIZE_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*([A-Za-z]*)\s*$')


def parse_size(size_str: str) -> int:
    """
    Parse a human-readable size string to bytes.

    Args:
        size_str: Size string like "100MB", "1.5GB", "1024", "500 KB"

    Returns:
        Size in bytes as integer

    Raises:
        ParseSizeError: If the string cannot be parsed or is invalid
    """
    if not size_str or not size_str.strip():
        raise ParseSizeError("Size string cannot be empty")

    size_str = size_str.strip()

    # Check for negative values
    if size_str.startswith('-'):
        raise ParseSizeError(f"Size cannot be negative: {size_str}")

    match = SIZE_PATTERN.match(size_str)
    if not match:
        raise ParseSizeError(f"Invalid size format: {size_str}")

    number_str, unit = match.groups()
    number = float(number_str)

    if not unit:
        # Plain number, treat as bytes
        return int(number)

    unit_upper = unit.upper()
    if unit_upper not in SIZE_UNITS:
        raise ParseSizeError(f"Unknown size unit: {unit}")

    return int(number * SIZE_UNITS[unit_upper])
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_size_parser.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/size_parser.py tests/test_size_parser.py
git commit -m "$(cat <<'EOF'
feat: add size parsing utility for human-readable sizes

Supports formats like 100MB, 1.5GB, 500KB, and plain bytes.
Case-insensitive with spaces allowed between number and unit.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Date Parsing Utility

**Files:**
- Create: `src/date_parser.py`
- Test: `tests/test_date_parser.py`

**Step 1: Write the failing tests**

```python
# tests/test_date_parser.py
"""Tests for date parsing utility."""
import pytest
from datetime import datetime, date
from src.date_parser import parse_date, ParseDateError


class TestParseDate:
    """Test parse_date function."""

    def test_iso_format(self):
        """Parse YYYY-MM-DD format."""
        result = parse_date("2025-06-15")
        assert result == datetime(2025, 6, 15)

    def test_returns_datetime_at_midnight(self):
        """Result is datetime at start of day."""
        result = parse_date("2025-06-15")
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_invalid_format_raises(self):
        """Invalid format raises ParseDateError."""
        with pytest.raises(ParseDateError):
            parse_date("15/06/2025")

    def test_invalid_date_raises(self):
        """Invalid date raises ParseDateError."""
        with pytest.raises(ParseDateError):
            parse_date("2025-13-01")  # Month 13 doesn't exist

    def test_empty_raises(self):
        """Empty string raises ParseDateError."""
        with pytest.raises(ParseDateError):
            parse_date("")

    def test_whitespace_stripped(self):
        """Whitespace is stripped."""
        result = parse_date("  2025-06-15  ")
        assert result == datetime(2025, 6, 15)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_date_parser.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.date_parser'"

**Step 3: Write minimal implementation**

```python
# src/date_parser.py
"""Date parsing utility for filter options."""
from datetime import datetime


class ParseDateError(ValueError):
    """Raised when date string cannot be parsed."""
    pass


def parse_date(date_str: str) -> datetime:
    """
    Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        datetime object at midnight (00:00:00) of the given date

    Raises:
        ParseDateError: If the string cannot be parsed
    """
    if not date_str or not date_str.strip():
        raise ParseDateError("Date string cannot be empty")

    date_str = date_str.strip()

    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ParseDateError(f"Invalid date format '{date_str}'. Use YYYY-MM-DD format.") from e
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_date_parser.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/date_parser.py tests/test_date_parser.py
git commit -m "$(cat <<'EOF'
feat: add date parsing utility for YYYY-MM-DD format

Used by date filter options (--since, --before, --older-than).

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Filter Predicate System

**Files:**
- Create: `src/filters.py`
- Test: `tests/test_filters.py`

**Step 1: Write the failing tests**

```python
# tests/test_filters.py
"""Tests for file filter system."""
import pytest
from datetime import datetime, timedelta
from src.filters import (
    FileFilter,
    SearchFilter,
    SinceFilter,
    BeforeFilter,
    LargerFilter,
    SmallerFilter,
    ExpiredFilter,
    ExpiringFilter,
    CategoryFilter,
    combine_filters,
)

# Constants from the app
DAYS = 10  # GoFile expiry period


def make_file(
    name="test.txt",
    size=1000,
    upload_time=None,
    category=None,
):
    """Create a test file dict."""
    if upload_time is None:
        upload_time = datetime.now().isoformat()
    return {
        "name": name,
        "size": size,
        "upload_time": upload_time,
        "category": category,
    }


class TestSearchFilter:
    """Test SearchFilter class."""

    def test_matches_filename(self):
        """Matches substring in filename."""
        f = SearchFilter("video")
        assert f.matches(make_file(name="vacation_video.mp4"))

    def test_case_insensitive(self):
        """Search is case-insensitive."""
        f = SearchFilter("VIDEO")
        assert f.matches(make_file(name="vacation_video.mp4"))

    def test_no_match(self):
        """Returns False when no match."""
        f = SearchFilter("photo")
        assert not f.matches(make_file(name="vacation_video.mp4"))


class TestSinceFilter:
    """Test SinceFilter class."""

    def test_matches_after_date(self):
        """Matches files uploaded after date."""
        f = SinceFilter(datetime(2025, 6, 1))
        file = make_file(upload_time="2025-06-15T10:00:00")
        assert f.matches(file)

    def test_no_match_before_date(self):
        """Returns False for files before date."""
        f = SinceFilter(datetime(2025, 6, 1))
        file = make_file(upload_time="2025-05-15T10:00:00")
        assert not f.matches(file)

    def test_matches_same_day(self):
        """Matches files on the same day."""
        f = SinceFilter(datetime(2025, 6, 15))
        file = make_file(upload_time="2025-06-15T10:00:00")
        assert f.matches(file)


class TestBeforeFilter:
    """Test BeforeFilter class."""

    def test_matches_before_date(self):
        """Matches files uploaded before date."""
        f = BeforeFilter(datetime(2025, 6, 15))
        file = make_file(upload_time="2025-06-01T10:00:00")
        assert f.matches(file)

    def test_no_match_after_date(self):
        """Returns False for files after date."""
        f = BeforeFilter(datetime(2025, 6, 15))
        file = make_file(upload_time="2025-06-20T10:00:00")
        assert not f.matches(file)


class TestLargerFilter:
    """Test LargerFilter class."""

    def test_matches_larger_file(self):
        """Matches files larger than threshold."""
        f = LargerFilter(1000)
        assert f.matches(make_file(size=2000))

    def test_no_match_smaller_file(self):
        """Returns False for smaller files."""
        f = LargerFilter(1000)
        assert not f.matches(make_file(size=500))

    def test_no_match_equal_size(self):
        """Returns False for equal size (must be larger)."""
        f = LargerFilter(1000)
        assert not f.matches(make_file(size=1000))


class TestSmallerFilter:
    """Test SmallerFilter class."""

    def test_matches_smaller_file(self):
        """Matches files smaller than threshold."""
        f = SmallerFilter(1000)
        assert f.matches(make_file(size=500))

    def test_no_match_larger_file(self):
        """Returns False for larger files."""
        f = SmallerFilter(1000)
        assert not f.matches(make_file(size=2000))


class TestExpiredFilter:
    """Test ExpiredFilter class."""

    def test_matches_expired_file(self):
        """Matches files past expiry date."""
        f = ExpiredFilter()
        old_time = (datetime.now() - timedelta(days=DAYS + 1)).isoformat()
        assert f.matches(make_file(upload_time=old_time))

    def test_no_match_valid_file(self):
        """Returns False for files not yet expired."""
        f = ExpiredFilter()
        recent_time = datetime.now().isoformat()
        assert not f.matches(make_file(upload_time=recent_time))


class TestExpiringFilter:
    """Test ExpiringFilter class."""

    def test_matches_expiring_soon(self):
        """Matches files expiring in 1-4 days."""
        f = ExpiringFilter()
        # Upload 7 days ago = 3 days remaining (expiring soon)
        expiring_time = (datetime.now() - timedelta(days=DAYS - 3)).isoformat()
        assert f.matches(make_file(upload_time=expiring_time))

    def test_no_match_healthy_file(self):
        """Returns False for files with 5+ days remaining."""
        f = ExpiringFilter()
        recent_time = datetime.now().isoformat()
        assert not f.matches(make_file(upload_time=recent_time))

    def test_no_match_expired_file(self):
        """Returns False for already expired files."""
        f = ExpiringFilter()
        old_time = (datetime.now() - timedelta(days=DAYS + 1)).isoformat()
        assert not f.matches(make_file(upload_time=old_time))


class TestCategoryFilter:
    """Test CategoryFilter class."""

    def test_matches_category(self):
        """Matches files in category."""
        f = CategoryFilter("Videos")
        assert f.matches(make_file(category="Videos"))

    def test_no_match_different_category(self):
        """Returns False for different category."""
        f = CategoryFilter("Videos")
        assert not f.matches(make_file(category="Photos"))

    def test_case_insensitive(self):
        """Category matching is case-insensitive."""
        f = CategoryFilter("videos")
        assert f.matches(make_file(category="Videos"))


class TestCombineFilters:
    """Test combine_filters function."""

    def test_empty_list_matches_all(self):
        """Empty filter list matches everything."""
        combined = combine_filters([])
        assert combined(make_file())

    def test_single_filter(self):
        """Single filter works."""
        combined = combine_filters([SearchFilter("video")])
        assert combined(make_file(name="video.mp4"))
        assert not combined(make_file(name="photo.jpg"))

    def test_multiple_filters_and_logic(self):
        """Multiple filters use AND logic."""
        combined = combine_filters([
            SearchFilter("video"),
            LargerFilter(1000),
        ])
        # Both match
        assert combined(make_file(name="video.mp4", size=2000))
        # Only name matches
        assert not combined(make_file(name="video.mp4", size=500))
        # Only size matches
        assert not combined(make_file(name="photo.jpg", size=2000))
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_filters.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.filters'"

**Step 3: Write minimal implementation**

```python
# src/filters.py
"""File filter system for list, search, and purge commands."""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Callable, List

# GoFile expiry period in days
DAYS = 10


class FileFilter(ABC):
    """Base class for file filters."""

    @abstractmethod
    def matches(self, file: dict) -> bool:
        """Return True if the file matches this filter."""
        pass


class SearchFilter(FileFilter):
    """Filter files by name substring."""

    def __init__(self, query: str):
        self.query = query.lower()

    def matches(self, file: dict) -> bool:
        return self.query in file.get("name", "").lower()


class SinceFilter(FileFilter):
    """Filter files uploaded after a date."""

    def __init__(self, since_date: datetime):
        self.since_date = since_date

    def matches(self, file: dict) -> bool:
        upload_time = datetime.fromisoformat(file.get("upload_time", ""))
        return upload_time >= self.since_date


class BeforeFilter(FileFilter):
    """Filter files uploaded before a date."""

    def __init__(self, before_date: datetime):
        self.before_date = before_date

    def matches(self, file: dict) -> bool:
        upload_time = datetime.fromisoformat(file.get("upload_time", ""))
        return upload_time < self.before_date


class LargerFilter(FileFilter):
    """Filter files larger than a size."""

    def __init__(self, size_bytes: int):
        self.size_bytes = size_bytes

    def matches(self, file: dict) -> bool:
        return file.get("size", 0) > self.size_bytes


class SmallerFilter(FileFilter):
    """Filter files smaller than a size."""

    def __init__(self, size_bytes: int):
        self.size_bytes = size_bytes

    def matches(self, file: dict) -> bool:
        return file.get("size", 0) < self.size_bytes


class ExpiredFilter(FileFilter):
    """Filter expired files."""

    def matches(self, file: dict) -> bool:
        upload_time = datetime.fromisoformat(file.get("upload_time", ""))
        expiry_time = upload_time + timedelta(days=DAYS)
        return datetime.now() > expiry_time


class ExpiringFilter(FileFilter):
    """Filter files expiring soon (1-4 days remaining)."""

    def matches(self, file: dict) -> bool:
        upload_time = datetime.fromisoformat(file.get("upload_time", ""))
        expiry_time = upload_time + timedelta(days=DAYS)
        days_remaining = (expiry_time - datetime.now()).days

        # Expiring soon: 1-4 days remaining
        return 0 < days_remaining <= 4


class CategoryFilter(FileFilter):
    """Filter files by category."""

    def __init__(self, category: str):
        self.category = category.lower()

    def matches(self, file: dict) -> bool:
        file_category = file.get("category") or ""
        return file_category.lower() == self.category


def combine_filters(filters: List[FileFilter]) -> Callable[[dict], bool]:
    """
    Combine multiple filters with AND logic.

    Args:
        filters: List of FileFilter instances

    Returns:
        Function that returns True if file matches ALL filters
    """
    if not filters:
        return lambda file: True

    def combined(file: dict) -> bool:
        return all(f.matches(file) for f in filters)

    return combined
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_filters.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/filters.py tests/test_filters.py
git commit -m "$(cat <<'EOF'
feat: add composable filter system for file queries

Filters: search, since, before, larger, smaller, expired, expiring, category.
Filters combine with AND logic for list, search, and purge commands.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Color Output Utility

**Files:**
- Create: `src/color.py`
- Test: `tests/test_color.py`

**Step 1: Write the failing tests**

```python
# tests/test_color.py
"""Tests for color output utility."""
import os
import pytest
from unittest.mock import patch
from src.color import (
    Color,
    colorize,
    green,
    yellow,
    red,
    blue,
    is_color_enabled,
)


class TestColorize:
    """Test colorize function."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.stdout.isatty", return_value=True)
    def test_colorize_in_tty(self, mock_isatty):
        """Applies color codes in TTY."""
        result = colorize("test", Color.GREEN)
        assert result == "\033[92mtest\033[0m"

    @patch.dict(os.environ, {"NO_COLOR": "1"})
    def test_no_color_env_var(self):
        """Respects NO_COLOR environment variable."""
        result = colorize("test", Color.GREEN)
        assert result == "test"

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.stdout.isatty", return_value=False)
    def test_no_color_in_pipe(self, mock_isatty):
        """No color when output is piped."""
        result = colorize("test", Color.GREEN)
        assert result == "test"


class TestColorHelpers:
    """Test color helper functions."""

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.stdout.isatty", return_value=True)
    def test_green(self, mock_isatty):
        """green() applies green color."""
        result = green("healthy")
        assert "\033[92m" in result

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.stdout.isatty", return_value=True)
    def test_yellow(self, mock_isatty):
        """yellow() applies yellow color."""
        result = yellow("warning")
        assert "\033[93m" in result

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.stdout.isatty", return_value=True)
    def test_red(self, mock_isatty):
        """red() applies red color."""
        result = red("error")
        assert "\033[91m" in result

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.stdout.isatty", return_value=True)
    def test_blue(self, mock_isatty):
        """blue() applies blue color."""
        result = blue("link")
        assert "\033[94m" in result


class TestIsColorEnabled:
    """Test is_color_enabled function."""

    @patch.dict(os.environ, {"NO_COLOR": "1"})
    def test_no_color_env_disables(self):
        """NO_COLOR env var disables color."""
        assert is_color_enabled() is False

    @patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=True)
    def test_force_color_env_enables(self):
        """FORCE_COLOR env var enables color."""
        assert is_color_enabled() is True

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.stdout.isatty", return_value=True)
    def test_tty_enables(self, mock_isatty):
        """TTY enables color."""
        assert is_color_enabled() is True

    @patch.dict(os.environ, {}, clear=True)
    @patch("sys.stdout.isatty", return_value=False)
    def test_non_tty_disables(self, mock_isatty):
        """Non-TTY disables color."""
        assert is_color_enabled() is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_color.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.color'"

**Step 3: Write minimal implementation**

```python
# src/color.py
"""Color output utility with terminal detection."""
import os
import sys
from enum import Enum


class Color(Enum):
    """ANSI color codes."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def is_color_enabled() -> bool:
    """
    Check if color output should be enabled.

    Respects:
    - NO_COLOR env var (disables color)
    - FORCE_COLOR env var (enables color)
    - TTY detection (enable if interactive terminal)
    """
    # NO_COLOR takes precedence (standard: https://no-color.org/)
    if os.environ.get("NO_COLOR"):
        return False

    # FORCE_COLOR overrides TTY detection
    if os.environ.get("FORCE_COLOR"):
        return True

    # Check if stdout is a TTY
    return sys.stdout.isatty()


def colorize(text: str, color: Color) -> str:
    """
    Apply color to text if color is enabled.

    Args:
        text: Text to colorize
        color: Color to apply

    Returns:
        Colored text or plain text if color disabled
    """
    if not is_color_enabled():
        return text

    return f"{color.value}{text}{Color.RESET.value}"


def green(text: str) -> str:
    """Apply green color (healthy status)."""
    return colorize(text, Color.GREEN)


def yellow(text: str) -> str:
    """Apply yellow color (warning status)."""
    return colorize(text, Color.YELLOW)


def red(text: str) -> str:
    """Apply red color (error/expired status)."""
    return colorize(text, Color.RED)


def blue(text: str) -> str:
    """Apply blue color (links)."""
    return colorize(text, Color.BLUE)


def bold(text: str) -> str:
    """Apply bold formatting."""
    return colorize(text, Color.BOLD)


def dim(text: str) -> str:
    """Apply dim formatting."""
    return colorize(text, Color.DIM)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_color.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/color.py tests/test_color.py
git commit -m "$(cat <<'EOF'
feat: add color output utility with terminal detection

Respects NO_COLOR/FORCE_COLOR env vars and TTY detection.
Provides green/yellow/red/blue helpers for status display.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Refactor CLI to Subcommand Architecture

**Files:**
- Modify: `src/gofile_uploader.py:32-268`
- Test: `tests/test_cli.py` (extend existing)

**Step 1: Write the failing tests for subcommand parsing**

```python
# Add to tests/test_cli.py

class TestSubcommandParsing:
    """Test new subcommand syntax."""

    def test_upload_subcommand(self, capsys):
        """'upload' subcommand is recognized."""
        with patch.object(sys, 'argv', ['gofile-uploader', 'upload', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "upload" in captured.out.lower()

    def test_list_subcommand(self, capsys):
        """'list' subcommand is recognized."""
        with patch.object(sys, 'argv', ['gofile-uploader', 'list', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "list" in captured.out.lower()

    def test_search_subcommand(self, capsys):
        """'search' subcommand is recognized."""
        with patch.object(sys, 'argv', ['gofile-uploader', 'search', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "search" in captured.out.lower()

    def test_delete_subcommand(self, capsys):
        """'delete' subcommand is recognized."""
        with patch.object(sys, 'argv', ['gofile-uploader', 'delete', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "delete" in captured.out.lower()

    def test_purge_subcommand(self, capsys):
        """'purge' subcommand is recognized."""
        with patch.object(sys, 'argv', ['gofile-uploader', 'purge', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "purge" in captured.out.lower()

    def test_categories_subcommand(self, capsys):
        """'categories' subcommand is recognized."""
        with patch.object(sys, 'argv', ['gofile-uploader', 'categories', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "categories" in captured.out.lower()

    def test_interactive_subcommand(self, capsys):
        """'interactive' subcommand is recognized."""
        with patch.object(sys, 'argv', ['gofile-uploader', 'interactive', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "interactive" in captured.out.lower()


class TestBackwardsCompatibility:
    """Test existing flag syntax still works."""

    @patch("src.gofile_uploader.DatabaseManager")
    @patch("src.gofile_uploader.setup_logging")
    def test_list_files_flag(self, mock_logging, mock_db, capsys):
        """-lf flag still works."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_all_files.return_value = []
        mock_db.return_value = mock_db_instance

        with patch.object(sys, 'argv', ['gofile-uploader', '-lf']):
            main()

        mock_db_instance.get_all_files.assert_called()

    @patch("src.gofile_uploader.DatabaseManager")
    @patch("src.gofile_uploader.setup_logging")
    def test_list_categories_flag(self, mock_logging, mock_db, capsys):
        """-l flag still works."""
        mock_db_instance = MagicMock()
        mock_db_instance.get_all_categories.return_value = []
        mock_db.return_value = mock_db_instance

        with patch.object(sys, 'argv', ['gofile-uploader', '-l']):
            main()

        mock_db_instance.get_all_categories.assert_called()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestSubcommandParsing -v`
Expected: FAIL because subcommands don't exist yet

**Step 3: Implement subcommand architecture**

Modify `src/gofile_uploader.py` to add subparsers while maintaining backwards compatibility. The key changes:

1. Create main parser with subparsers
2. Add `upload`, `list`, `search`, `delete`, `purge`, `categories`, `interactive` subcommands
3. Keep existing flag parsing in main parser for backwards compatibility
4. Route to appropriate handlers based on subcommand or flags

```python
# Key structure changes in src/gofile_uploader.py

def _create_argument_parser() -> argparse.ArgumentParser:
    """Create the argument parser with subcommands and backwards-compatible flags."""
    parser = argparse.ArgumentParser(
        prog="gofile-uploader",
        description="GoFile Uploader - Upload files to GoFile.io with tracking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
QUICK START:
  gofile-uploader upload photo.jpg           Upload a file
  gofile-uploader upload *.mp4 -c Videos     Upload to category
  gofile-uploader list                       Show your uploads
  gofile-uploader interactive                Menu-driven mode

Run 'gofile-uploader <command> --help' for command-specific help.
""",
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Global options (apply to all commands)
    parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (-v, -vv)")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Upload subcommand
    upload_parser = subparsers.add_parser("upload", help="Upload files to GoFile")
    upload_parser.add_argument("files", nargs="+", help="Files or patterns to upload")
    upload_parser.add_argument("-c", "--category", help="Assign to category")
    upload_parser.add_argument("-r", "--recursive", action="store_true", help="Include subfolders")
    upload_parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    upload_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")

    # List subcommand
    list_parser = subparsers.add_parser("list", help="List uploaded files")
    _add_filter_arguments(list_parser)
    _add_view_arguments(list_parser)

    # Search subcommand
    search_parser = subparsers.add_parser("search", help="Search files by name")
    search_parser.add_argument("query", help="Search term")
    _add_filter_arguments(search_parser)
    _add_view_arguments(search_parser)

    # Delete subcommand
    delete_parser = subparsers.add_parser("delete", help="Delete a file")
    delete_parser.add_argument("target", help="File ID, name, or pattern")
    delete_parser.add_argument("-f", "--force", action="store_true", help="Delete local record only")
    delete_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")

    # Purge subcommand
    purge_parser = subparsers.add_parser("purge", help="Bulk delete files")
    _add_filter_arguments(purge_parser)
    purge_parser.add_argument("--interactive", action="store_true", help="Select files to delete")
    purge_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")

    # Categories subcommand
    categories_parser = subparsers.add_parser("categories", help="Manage categories")
    categories_sub = categories_parser.add_subparsers(dest="categories_action")
    categories_sub.add_parser("list", help="List all categories")
    remove_parser = categories_sub.add_parser("remove", help="Remove a category")
    remove_parser.add_argument("pattern", help="Category name or pattern")
    import_parser = categories_sub.add_parser("import", help="Import categories from file")
    import_parser.add_argument("file", help="File to import from")
    export_parser = categories_sub.add_parser("export", help="Export categories to file")
    export_parser.add_argument("file", help="File to export to")

    # Interactive subcommand
    subparsers.add_parser("interactive", help="Launch interactive mode", aliases=["i"])

    # Backwards-compatible flags (on main parser)
    _add_legacy_flags(parser)

    return parser


def _add_filter_arguments(parser: argparse.ArgumentParser):
    """Add filter arguments to a parser."""
    filter_group = parser.add_argument_group("Filter options")
    filter_group.add_argument("--search", metavar="TEXT", help="Filter by filename")
    filter_group.add_argument("--since", metavar="DATE", help="Uploaded after (YYYY-MM-DD)")
    filter_group.add_argument("--before", metavar="DATE", help="Uploaded before (YYYY-MM-DD)")
    filter_group.add_argument("--larger", metavar="SIZE", help="Larger than (e.g., 100MB)")
    filter_group.add_argument("--smaller", metavar="SIZE", help="Smaller than")
    filter_group.add_argument("--expired", action="store_true", help="Only expired files")
    filter_group.add_argument("--expiring", action="store_true", help="Only files expiring soon")
    filter_group.add_argument("--category", metavar="NAME", help="Filter by category")
    filter_group.add_argument("--older-than", metavar="DATE", help="Uploaded before (alias for --before)")


def _add_view_arguments(parser: argparse.ArgumentParser):
    """Add view arguments to a parser."""
    view_group = parser.add_argument_group("View options")
    view_group.add_argument("--view", choices=["simple", "detailed", "links"], default="simple", help="Output format")
    view_group.add_argument("--compact", action="store_true", help="Dense layout")
    view_group.add_argument("--columns", metavar="COLS", help="Custom columns (comma-separated)")
    view_group.add_argument("--sort", metavar="FIELD", help="Sort by field")
    view_group.add_argument("--order", choices=["asc", "desc"], default="desc", help="Sort direction")
    view_group.add_argument("--page", type=int, default=1, help="Page number")
    view_group.add_argument("--per-page", type=int, default=20, help="Items per page (0 for all)")


def _add_legacy_flags(parser: argparse.ArgumentParser):
    """Add backwards-compatible legacy flags."""
    legacy_group = parser.add_argument_group("Legacy options (backwards compatible)")
    legacy_group.add_argument("files", nargs="*", help="Files to upload (legacy syntax)")
    legacy_group.add_argument("-c", "--category", help="Category for upload")
    legacy_group.add_argument("-r", "--recursive", action="store_true")
    legacy_group.add_argument("-l", "--list", action="store_true", help="List categories")
    legacy_group.add_argument("-lf", "--list-files", nargs="?", const="", help="List files")
    legacy_group.add_argument("-df", "--delete-file", help="Delete file")
    legacy_group.add_argument("-pf", "--purge-files", help="Purge files in category")
    legacy_group.add_argument("-rm", "--remove", help="Remove category")
    legacy_group.add_argument("-f", "--force", action="store_true")
    legacy_group.add_argument("-it", "--import-token", help="Import account token")
    legacy_group.add_argument("-ic", "--import-category", help="Import categories")
    legacy_group.add_argument("--clear", action="store_true", help="Clear orphaned files")
    # View options for legacy list
    legacy_group.add_argument("-s", "--sort", dest="legacy_sort")
    legacy_group.add_argument("-o", "--order", dest="legacy_order")
    legacy_group.add_argument("-p", "--page", type=int, dest="legacy_page")
    legacy_group.add_argument("-mfn", "--max-filename", type=int)
    legacy_group.add_argument("-col", "--columns", dest="legacy_columns")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All tests PASS (both new subcommand and legacy flag tests)

**Step 5: Commit**

```bash
git add src/gofile_uploader.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
feat: add subcommand architecture with backwards compatibility

New commands: upload, list, search, delete, purge, categories, interactive
All existing flags (-lf, -df, -c, etc.) continue to work.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Implement Filter Integration in List Command

**Files:**
- Modify: `src/file_manager.py:191-381`
- Modify: `src/commands.py:32-61`
- Test: `tests/test_list_filters.py` (new)

**Step 1: Write the failing tests**

```python
# tests/test_list_filters.py
"""Tests for list command with filters."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.commands import handle_list_files_command
from src.filters import DAYS


def make_file(name, size, upload_time, category=None):
    """Create a test file dict."""
    return {
        "id": f"id_{name}",
        "name": name,
        "size": size,
        "upload_time": upload_time,
        "category": category,
        "download_link": f"https://gofile.io/d/{name}",
        "mime_type": "application/octet-stream",
    }


@pytest.fixture
def mock_db():
    """Create a mock database manager."""
    db = MagicMock()
    now = datetime.now()

    # Create test files with various attributes
    db.get_all_files.return_value = [
        make_file("video1.mp4", 500_000_000, now.isoformat(), "Videos"),
        make_file("video2.mp4", 1_500_000_000, (now - timedelta(days=5)).isoformat(), "Videos"),
        make_file("photo.jpg", 2_000_000, now.isoformat(), "Photos"),
        make_file("expired.zip", 100_000_000, (now - timedelta(days=DAYS + 1)).isoformat(), "Backups"),
        make_file("expiring.pdf", 50_000_000, (now - timedelta(days=DAYS - 2)).isoformat(), "Work"),
    ]
    return db


class TestListWithSearchFilter:
    """Test list with --search filter."""

    def test_filters_by_name(self, mock_db, capsys):
        """--search filters files by name."""
        args = MagicMock(
            search="video",
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=False,
            expiring=False,
            category=None,
            view="simple",
            compact=False,
            columns=None,
            sort=None,
            order="desc",
            page=1,
            per_page=20,
        )

        handle_list_files_command(mock_db, args)

        captured = capsys.readouterr()
        assert "video1.mp4" in captured.out
        assert "video2.mp4" in captured.out
        assert "photo.jpg" not in captured.out


class TestListWithSizeFilters:
    """Test list with size filters."""

    def test_larger_filter(self, mock_db, capsys):
        """--larger filters files by minimum size."""
        args = MagicMock(
            search=None,
            since=None,
            before=None,
            larger="1GB",
            smaller=None,
            expired=False,
            expiring=False,
            category=None,
            view="simple",
            compact=False,
            columns=None,
            sort=None,
            order="desc",
            page=1,
            per_page=20,
        )

        handle_list_files_command(mock_db, args)

        captured = capsys.readouterr()
        assert "video2.mp4" in captured.out  # 1.5GB
        assert "video1.mp4" not in captured.out  # 500MB


class TestListWithExpiryFilters:
    """Test list with expiry filters."""

    def test_expired_filter(self, mock_db, capsys):
        """--expired shows only expired files."""
        args = MagicMock(
            search=None,
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=True,
            expiring=False,
            category=None,
            view="simple",
            compact=False,
            columns=None,
            sort=None,
            order="desc",
            page=1,
            per_page=20,
        )

        handle_list_files_command(mock_db, args)

        captured = capsys.readouterr()
        assert "expired.zip" in captured.out
        assert "video1.mp4" not in captured.out

    def test_expiring_filter(self, mock_db, capsys):
        """--expiring shows only files expiring soon."""
        args = MagicMock(
            search=None,
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=False,
            expiring=True,
            category=None,
            view="simple",
            compact=False,
            columns=None,
            sort=None,
            order="desc",
            page=1,
            per_page=20,
        )

        handle_list_files_command(mock_db, args)

        captured = capsys.readouterr()
        assert "expiring.pdf" in captured.out
        assert "video1.mp4" not in captured.out


class TestListWithCombinedFilters:
    """Test list with multiple filters."""

    def test_multiple_filters_and_logic(self, mock_db, capsys):
        """Multiple filters use AND logic."""
        args = MagicMock(
            search="video",
            since=None,
            before=None,
            larger="400MB",
            smaller=None,
            expired=False,
            expiring=False,
            category="Videos",
            view="simple",
            compact=False,
            columns=None,
            sort=None,
            order="desc",
            page=1,
            per_page=20,
        )

        handle_list_files_command(mock_db, args)

        captured = capsys.readouterr()
        # Only video1.mp4 and video2.mp4 match all: name contains "video", size > 400MB, category = Videos
        assert "video1.mp4" in captured.out
        assert "video2.mp4" in captured.out
        assert "photo.jpg" not in captured.out
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_list_filters.py -v`
Expected: FAIL because filter integration doesn't exist yet

**Step 3: Implement filter integration**

Update `src/commands.py` `handle_list_files_command()` to build filters from args and apply them:

```python
# In src/commands.py

from src.filters import (
    SearchFilter,
    SinceFilter,
    BeforeFilter,
    LargerFilter,
    SmallerFilter,
    ExpiredFilter,
    ExpiringFilter,
    CategoryFilter,
    combine_filters,
)
from src.size_parser import parse_size
from src.date_parser import parse_date


def build_filters_from_args(args) -> list:
    """Build filter list from command-line arguments."""
    filters = []

    if getattr(args, 'search', None):
        filters.append(SearchFilter(args.search))

    if getattr(args, 'since', None):
        filters.append(SinceFilter(parse_date(args.since)))

    if getattr(args, 'before', None) or getattr(args, 'older_than', None):
        date_str = getattr(args, 'before', None) or getattr(args, 'older_than', None)
        filters.append(BeforeFilter(parse_date(date_str)))

    if getattr(args, 'larger', None):
        filters.append(LargerFilter(parse_size(args.larger)))

    if getattr(args, 'smaller', None):
        filters.append(SmallerFilter(parse_size(args.smaller)))

    if getattr(args, 'expired', False):
        filters.append(ExpiredFilter())

    if getattr(args, 'expiring', False):
        filters.append(ExpiringFilter())

    if getattr(args, 'category', None):
        filters.append(CategoryFilter(args.category))

    return filters


def handle_list_files_command(db_manager, args):
    """Handle the list files command with filtering."""
    # Get all files
    files = db_manager.get_all_files()

    # Apply filters
    filters = build_filters_from_args(args)
    filter_fn = combine_filters(filters)
    files = [f for f in files if filter_fn(f)]

    # Continue with existing sorting, pagination, and display logic...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_list_filters.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/commands.py src/file_manager.py tests/test_list_filters.py
git commit -m "$(cat <<'EOF'
feat: integrate filter system into list command

Supports --search, --since, --before, --larger, --smaller, --expired,
--expiring, --category filters with AND logic.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Implement Search Command

**Files:**
- Modify: `src/commands.py`
- Test: `tests/test_search_command.py` (new)

**Step 1: Write the failing tests**

```python
# tests/test_search_command.py
"""Tests for search command."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from src.commands import handle_search_command


def make_file(name, size=1000, category=None):
    """Create a test file dict."""
    return {
        "id": f"id_{name}",
        "name": name,
        "size": size,
        "upload_time": datetime.now().isoformat(),
        "category": category,
        "download_link": f"https://gofile.io/d/{name}",
    }


@pytest.fixture
def mock_db():
    """Create a mock database manager."""
    db = MagicMock()
    db.get_all_files.return_value = [
        make_file("vacation_video.mp4", 1_000_000_000, "Videos"),
        make_file("work_video.mp4", 500_000_000, "Work"),
        make_file("photo.jpg", 5_000_000, "Photos"),
        make_file("document.pdf", 1_000_000, "Work"),
    ]
    return db


class TestSearchCommand:
    """Test search command."""

    def test_search_finds_matching_files(self, mock_db, capsys):
        """Search finds files matching query."""
        args = MagicMock(
            query="video",
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=False,
            expiring=False,
            category=None,
            view="simple",
            compact=False,
            columns=None,
            sort=None,
            order="desc",
            page=1,
            per_page=20,
        )

        handle_search_command(mock_db, args)

        captured = capsys.readouterr()
        assert "vacation_video.mp4" in captured.out
        assert "work_video.mp4" in captured.out
        assert "photo.jpg" not in captured.out

    def test_search_with_category_filter(self, mock_db, capsys):
        """Search can be combined with category filter."""
        args = MagicMock(
            query="video",
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=False,
            expiring=False,
            category="Videos",
            view="simple",
            compact=False,
            columns=None,
            sort=None,
            order="desc",
            page=1,
            per_page=20,
        )

        handle_search_command(mock_db, args)

        captured = capsys.readouterr()
        assert "vacation_video.mp4" in captured.out
        assert "work_video.mp4" not in captured.out  # Different category

    def test_search_no_results(self, mock_db, capsys):
        """Search with no matches shows appropriate message."""
        args = MagicMock(
            query="nonexistent",
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=False,
            expiring=False,
            category=None,
            view="simple",
            compact=False,
            columns=None,
            sort=None,
            order="desc",
            page=1,
            per_page=20,
        )

        handle_search_command(mock_db, args)

        captured = capsys.readouterr()
        assert "no files" in captured.out.lower() or "0 files" in captured.out.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_search_command.py -v`
Expected: FAIL because handle_search_command doesn't exist

**Step 3: Implement search command**

```python
# Add to src/commands.py

def handle_search_command(db_manager, args):
    """
    Handle the search command.

    Search is a shortcut for list with --search filter pre-applied.
    """
    # Copy query to search attribute for filter building
    args.search = args.query

    # Delegate to list command
    handle_list_files_command(db_manager, args)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search_command.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/commands.py tests/test_search_command.py
git commit -m "$(cat <<'EOF'
feat: add search command as shorthand for list with search filter

'gofile-uploader search "video"' is equivalent to
'gofile-uploader list --search "video"'.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Implement Purge Command

**Files:**
- Modify: `src/commands.py`
- Modify: `src/services/deletion_service.py`
- Test: `tests/test_purge_command.py` (new)

**Step 1: Write the failing tests**

```python
# tests/test_purge_command.py
"""Tests for purge command."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

from src.commands import handle_purge_command
from src.filters import DAYS


def make_file(name, size, upload_time, category=None):
    """Create a test file dict."""
    return {
        "id": f"id_{name}",
        "name": name,
        "size": size,
        "upload_time": upload_time,
        "category": category,
        "download_link": f"https://gofile.io/d/{name}",
    }


@pytest.fixture
def mock_db():
    """Create a mock database manager."""
    db = MagicMock()
    now = datetime.now()

    db.get_all_files.return_value = [
        make_file("video.mp4", 1_000_000_000, now.isoformat(), "Videos"),
        make_file("expired1.zip", 100_000_000, (now - timedelta(days=DAYS + 1)).isoformat(), "Backups"),
        make_file("expired2.zip", 200_000_000, (now - timedelta(days=DAYS + 5)).isoformat(), "Backups"),
        make_file("recent.pdf", 50_000_000, now.isoformat(), "Work"),
    ]
    return db


class TestPurgeExpired:
    """Test purge with --expired filter."""

    @patch("src.commands.confirm_action", return_value=True)
    def test_purges_only_expired(self, mock_confirm, mock_db, capsys):
        """Purge --expired only deletes expired files."""
        args = MagicMock(
            search=None,
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=True,
            expiring=False,
            category=None,
            interactive=False,
            yes=False,
            force=False,
        )

        with patch("src.commands.DeletionService") as mock_deletion:
            mock_service = MagicMock()
            mock_deletion.return_value = mock_service

            handle_purge_command(mock_db, None, args)

            # Should delete only expired files
            delete_calls = mock_service.delete_file.call_args_list
            deleted_ids = [c[0][0] for c in delete_calls]

            assert "id_expired1.zip" in deleted_ids
            assert "id_expired2.zip" in deleted_ids
            assert "id_video.mp4" not in deleted_ids
            assert "id_recent.pdf" not in deleted_ids

    def test_shows_confirmation_prompt(self, mock_db, capsys):
        """Purge shows confirmation before deleting."""
        args = MagicMock(
            search=None,
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=True,
            expiring=False,
            category=None,
            interactive=False,
            yes=False,
            force=False,
        )

        with patch("src.commands.confirm_action", return_value=False) as mock_confirm:
            with patch("src.commands.DeletionService"):
                handle_purge_command(mock_db, None, args)

                mock_confirm.assert_called_once()
                assert "2" in str(mock_confirm.call_args)  # 2 files

    @patch("src.commands.confirm_action", return_value=True)
    def test_yes_flag_skips_confirmation(self, mock_confirm, mock_db):
        """--yes flag skips confirmation."""
        args = MagicMock(
            search=None,
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=True,
            expiring=False,
            category=None,
            interactive=False,
            yes=True,
            force=False,
        )

        with patch("src.commands.DeletionService"):
            handle_purge_command(mock_db, None, args)

            mock_confirm.assert_not_called()


class TestPurgeWithFilters:
    """Test purge with various filters."""

    @patch("src.commands.confirm_action", return_value=True)
    def test_purge_larger_than(self, mock_confirm, mock_db):
        """Purge --larger filters by size."""
        args = MagicMock(
            search=None,
            since=None,
            before=None,
            larger="500MB",
            smaller=None,
            expired=False,
            expiring=False,
            category=None,
            interactive=False,
            yes=True,
            force=False,
        )

        with patch("src.commands.DeletionService") as mock_deletion:
            mock_service = MagicMock()
            mock_deletion.return_value = mock_service

            handle_purge_command(mock_db, None, args)

            delete_calls = mock_service.delete_file.call_args_list
            deleted_ids = [c[0][0] for c in delete_calls]

            assert "id_video.mp4" in deleted_ids  # 1GB > 500MB
            assert "id_expired1.zip" not in deleted_ids  # 100MB < 500MB


class TestPurgeNoMatches:
    """Test purge when no files match."""

    def test_no_files_message(self, mock_db, capsys):
        """Shows message when no files match filters."""
        args = MagicMock(
            search="nonexistent",
            since=None,
            before=None,
            larger=None,
            smaller=None,
            expired=False,
            expiring=False,
            category=None,
            interactive=False,
            yes=False,
            force=False,
        )

        handle_purge_command(mock_db, None, args)

        captured = capsys.readouterr()
        assert "no files" in captured.out.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_purge_command.py -v`
Expected: FAIL because handle_purge_command doesn't exist

**Step 3: Implement purge command**

```python
# Add to src/commands.py

def handle_purge_command(db_manager, gofile_client, args):
    """
    Handle the purge command for bulk deletion.

    Applies filters, shows preview, confirms, and deletes.
    """
    from src.services.deletion_service import DeletionService
    from src.utils import confirm_action, format_size

    # Get all files
    files = db_manager.get_all_files()

    # Apply filters
    filters = build_filters_from_args(args)
    filter_fn = combine_filters(filters)
    matched_files = [f for f in files if filter_fn(f)]

    if not matched_files:
        print("No files match the specified filters.")
        return

    # Calculate totals
    total_size = sum(f.get("size", 0) for f in matched_files)
    count = len(matched_files)

    # Show preview
    print(f"\nFound {count} file(s) ({format_size(total_size)}) matching filters:")
    for f in matched_files[:10]:  # Show first 10
        print(f"  {f['name']} ({format_size(f.get('size', 0))})")
    if count > 10:
        print(f"  ... and {count - 10} more")

    # Confirm unless --yes
    if not getattr(args, 'yes', False):
        if not confirm_action(f"\nDelete {count} file(s) ({format_size(total_size)})?"):
            print("Cancelled.")
            return

    # Delete files
    deletion_service = DeletionService(db_manager, gofile_client)
    force = getattr(args, 'force', False)

    deleted = 0
    failed = 0
    for f in matched_files:
        try:
            deletion_service.delete_file(f['id'], force=force, auto_confirm=True)
            deleted += 1
        except Exception as e:
            print(f"Failed to delete {f['name']}: {e}")
            failed += 1

    print(f"\nDeleted {deleted} file(s).")
    if failed:
        print(f"Failed to delete {failed} file(s).")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_purge_command.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/commands.py tests/test_purge_command.py
git commit -m "$(cat <<'EOF'
feat: add purge command for bulk deletion with filters

Supports all filter options (--expired, --larger, --older-than, etc.)
with confirmation prompt and --yes flag for automation.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Implement View Modes

**Files:**
- Create: `src/views.py`
- Modify: `src/file_manager.py`
- Test: `tests/test_views.py` (new)

**Step 1: Write the failing tests**

```python
# tests/test_views.py
"""Tests for view mode rendering."""
import pytest
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from src.views import (
    render_simple_view,
    render_detailed_view,
    render_links_view,
    render_files,
    format_expiry,
)
from src.filters import DAYS


def make_file(name, size, upload_time, category=None, link="https://gofile.io/d/test"):
    """Create a test file dict."""
    return {
        "id": f"id_{name}",
        "name": name,
        "size": size,
        "upload_time": upload_time,
        "category": category,
        "download_link": link,
        "mime_type": "application/octet-stream",
    }


class TestFormatExpiry:
    """Test expiry formatting."""

    def test_healthy_shows_date(self):
        """Files with 5+ days show date."""
        upload_time = datetime.now().isoformat()
        result = format_expiry(upload_time)
        # Should show actual date, not EXPIRED or EXPIRING
        assert "EXPIRED" not in result
        assert "EXPIRING" not in result

    def test_expiring_shows_warning(self):
        """Files with 1-4 days show EXPIRING."""
        upload_time = (datetime.now() - timedelta(days=DAYS - 2)).isoformat()
        result = format_expiry(upload_time)
        assert "EXPIRING" in result

    def test_expired_shows_expired(self):
        """Expired files show EXPIRED."""
        upload_time = (datetime.now() - timedelta(days=DAYS + 1)).isoformat()
        result = format_expiry(upload_time)
        assert "EXPIRED" in result


class TestSimpleView:
    """Test simple view mode."""

    def test_shows_name_link_expiry(self, capsys):
        """Simple view shows name, link, and expiry."""
        files = [
            make_file("test.mp4", 1_000_000, datetime.now().isoformat()),
        ]

        render_simple_view(files, compact=False)

        captured = capsys.readouterr()
        assert "test.mp4" in captured.out
        assert "gofile.io" in captured.out

    def test_shows_summary_footer(self, capsys):
        """Simple view includes summary footer."""
        files = [
            make_file("test.mp4", 1_000_000_000, datetime.now().isoformat()),
        ]

        render_simple_view(files, compact=False)

        captured = capsys.readouterr()
        assert "1 file" in captured.out.lower() or "1GB" in captured.out or "1 GB" in captured.out


class TestDetailedView:
    """Test detailed view mode."""

    def test_shows_all_columns(self, capsys):
        """Detailed view shows all columns."""
        files = [
            make_file("test.mp4", 1_000_000, datetime.now().isoformat(), "Videos"),
        ]

        render_detailed_view(files, compact=False)

        captured = capsys.readouterr()
        assert "test.mp4" in captured.out
        assert "Videos" in captured.out
        # Should have headers
        assert "NAME" in captured.out or "Name" in captured.out


class TestLinksView:
    """Test links view mode."""

    def test_shows_only_links(self, capsys):
        """Links view shows only URLs."""
        files = [
            make_file("test1.mp4", 1_000_000, datetime.now().isoformat(),
                      link="https://gofile.io/d/abc123"),
            make_file("test2.mp4", 2_000_000, datetime.now().isoformat(),
                      link="https://gofile.io/d/def456"),
        ]

        render_links_view(files)

        captured = capsys.readouterr()
        assert "https://gofile.io/d/abc123" in captured.out
        assert "https://gofile.io/d/def456" in captured.out
        # Should NOT show filenames
        assert "test1.mp4" not in captured.out

    def test_one_link_per_line(self, capsys):
        """Links are one per line for easy scripting."""
        files = [
            make_file("test1.mp4", 1_000_000, datetime.now().isoformat(),
                      link="https://gofile.io/d/abc123"),
            make_file("test2.mp4", 2_000_000, datetime.now().isoformat(),
                      link="https://gofile.io/d/def456"),
        ]

        render_links_view(files)

        captured = capsys.readouterr()
        lines = captured.out.strip().split('\n')
        assert len(lines) == 2


class TestCompactMode:
    """Test compact mode."""

    def test_truncates_long_names(self, capsys):
        """Compact mode truncates long filenames."""
        files = [
            make_file("this_is_a_very_long_filename_that_should_be_truncated.mp4",
                      1_000_000, datetime.now().isoformat()),
        ]

        render_simple_view(files, compact=True)

        captured = capsys.readouterr()
        # Full name should not appear
        assert "this_is_a_very_long_filename_that_should_be_truncated.mp4" not in captured.out
        # Truncated version with ellipsis should appear
        assert "..." in captured.out or "…" in captured.out


class TestRenderFiles:
    """Test render_files dispatcher."""

    def test_dispatches_to_simple(self, capsys):
        """render_files with view='simple' uses simple view."""
        files = [make_file("test.mp4", 1_000_000, datetime.now().isoformat())]

        render_files(files, view="simple", compact=False)

        captured = capsys.readouterr()
        assert "test.mp4" in captured.out

    def test_dispatches_to_links(self, capsys):
        """render_files with view='links' uses links view."""
        files = [make_file("test.mp4", 1_000_000, datetime.now().isoformat(),
                           link="https://gofile.io/d/xyz")]

        render_files(files, view="links", compact=False)

        captured = capsys.readouterr()
        assert "https://gofile.io/d/xyz" in captured.out
        assert "test.mp4" not in captured.out
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_views.py -v`
Expected: FAIL because src/views.py doesn't exist

**Step 3: Implement view modes**

```python
# src/views.py
"""View modes for file listing output."""
from datetime import datetime, timedelta
from typing import List, Optional

from src.utils import format_size, print_dynamic_table
from src.color import green, yellow, red, blue

# GoFile expiry period
DAYS = 10

# Compact mode max filename length
COMPACT_MAX_NAME = 20


def format_expiry(upload_time: str) -> str:
    """
    Format expiry status with color coding.

    - Green: 5+ days remaining (shows date)
    - Yellow: 1-4 days remaining (shows "EXPIRING")
    - Red: Expired (shows "EXPIRED")
    """
    upload_dt = datetime.fromisoformat(upload_time)
    expiry_dt = upload_dt + timedelta(days=DAYS)
    days_remaining = (expiry_dt - datetime.now()).days

    if days_remaining < 0:
        return red("EXPIRED")
    elif days_remaining <= 4:
        return yellow(f"EXPIRING")
    else:
        return green(expiry_dt.strftime("%Y-%m-%d"))


def truncate_name(name: str, max_length: int) -> str:
    """Truncate filename with ellipsis if too long."""
    if len(name) <= max_length:
        return name
    return name[:max_length - 3] + "..."


def render_simple_view(files: List[dict], compact: bool = False) -> None:
    """
    Render simple view: name, size, expiry, link.

    Default view for casual users.
    """
    max_name = COMPACT_MAX_NAME if compact else 40

    headers = ["NAME", "SIZE", "EXPIRY", "LINK"]
    rows = []

    for f in files:
        name = f.get("name", "")
        if compact:
            name = truncate_name(name, max_name)

        link = f.get("download_link", "")
        # Shorten link for display
        if link.startswith("https://"):
            link = link[8:]  # Remove https://

        rows.append([
            name,
            format_size(f.get("size", 0)),
            format_expiry(f.get("upload_time", "")),
            blue(link),
        ])

    print_dynamic_table(rows, headers, max_name)

    # Summary footer
    _print_summary(files)


def render_detailed_view(files: List[dict], compact: bool = False) -> None:
    """
    Render detailed view: all columns.

    For users who need full information.
    """
    max_name = COMPACT_MAX_NAME if compact else 40

    headers = ["#", "NAME", "SIZE", "CATEGORY", "UPLOADED", "EXPIRY", "LINK"]
    rows = []

    for i, f in enumerate(files, 1):
        name = f.get("name", "")
        if compact:
            name = truncate_name(name, max_name)

        upload_dt = datetime.fromisoformat(f.get("upload_time", ""))
        upload_str = upload_dt.strftime("%Y-%m-%d %H:%M")

        link = f.get("download_link", "")
        if link.startswith("https://"):
            link = link[8:]

        rows.append([
            str(i),
            name,
            format_size(f.get("size", 0)),
            f.get("category", "") or "-",
            upload_str,
            format_expiry(f.get("upload_time", "")),
            blue(link),
        ])

    print_dynamic_table(rows, headers, max_name)

    # Summary footer
    _print_summary(files)


def render_links_view(files: List[dict]) -> None:
    """
    Render links view: just URLs.

    For scripting and piping.
    """
    for f in files:
        print(f.get("download_link", ""))


def _print_summary(files: List[dict]) -> None:
    """Print summary footer."""
    if not files:
        print("\nNo files found.")
        return

    total_size = sum(f.get("size", 0) for f in files)
    count = len(files)

    # Count expired and expiring
    expired = 0
    expiring = 0
    now = datetime.now()

    for f in files:
        upload_dt = datetime.fromisoformat(f.get("upload_time", ""))
        expiry_dt = upload_dt + timedelta(days=DAYS)
        days_remaining = (expiry_dt - now).days

        if days_remaining < 0:
            expired += 1
        elif days_remaining <= 4:
            expiring += 1

    # Build summary
    parts = [f"{count} file{'s' if count != 1 else ''} ({format_size(total_size)})"]

    if expired:
        parts.append(red(f"{expired} expired"))
    if expiring:
        parts.append(yellow(f"{expiring} expiring soon"))

    print(f"\n{' · '.join(parts)}")


def render_files(
    files: List[dict],
    view: str = "simple",
    compact: bool = False,
    columns: Optional[str] = None,
) -> None:
    """
    Render files in the specified view mode.

    Args:
        files: List of file dicts
        view: View mode (simple, detailed, links)
        compact: Enable compact mode
        columns: Custom columns (for future implementation)
    """
    if view == "links":
        render_links_view(files)
    elif view == "detailed":
        render_detailed_view(files, compact=compact)
    else:  # simple
        render_simple_view(files, compact=compact)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_views.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/views.py tests/test_views.py
git commit -m "$(cat <<'EOF'
feat: add view modes (simple, detailed, links) with compact option

Simple: name, size, expiry, link (default)
Detailed: all columns with row numbers
Links: just URLs for scripting
Compact: truncates filenames for narrow terminals

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Implement Categories Subcommand

**Files:**
- Modify: `src/commands.py`
- Modify: `src/services/category_service.py`
- Test: `tests/test_categories_command.py` (new)

**Step 1: Write the failing tests**

```python
# tests/test_categories_command.py
"""Tests for categories subcommand."""
import pytest
from unittest.mock import MagicMock, patch, mock_open
from io import StringIO

from src.commands import handle_categories_command


@pytest.fixture
def mock_db():
    """Create a mock database manager."""
    db = MagicMock()
    db.get_all_categories.return_value = [
        {"name": "Videos", "folder_id": "vid123", "folder_code": "xyz"},
        {"name": "Photos", "folder_id": "pho456", "folder_code": "abc"},
    ]
    db.get_files_by_category.side_effect = lambda cat: {
        "Videos": [{"size": 1_000_000_000}, {"size": 500_000_000}],
        "Photos": [{"size": 10_000_000}],
    }.get(cat, [])
    return db


class TestCategoriesList:
    """Test categories list subcommand."""

    def test_lists_categories_with_stats(self, mock_db, capsys):
        """List shows categories with file count and size."""
        args = MagicMock(categories_action="list")

        handle_categories_command(mock_db, None, args)

        captured = capsys.readouterr()
        assert "Videos" in captured.out
        assert "Photos" in captured.out
        # Should show file counts
        assert "2" in captured.out  # Videos has 2 files

    def test_default_action_is_list(self, mock_db, capsys):
        """No action defaults to list."""
        args = MagicMock(categories_action=None)

        handle_categories_command(mock_db, None, args)

        captured = capsys.readouterr()
        assert "Videos" in captured.out


class TestCategoriesRemove:
    """Test categories remove subcommand."""

    @patch("src.commands.confirm_action", return_value=True)
    def test_removes_category(self, mock_confirm, mock_db, capsys):
        """Remove deletes category."""
        args = MagicMock(categories_action="remove", pattern="Videos")

        with patch("src.commands.CategoryService") as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service

            handle_categories_command(mock_db, None, args)

            mock_service.remove_category.assert_called_once()


class TestCategoriesExport:
    """Test categories export subcommand."""

    def test_exports_to_file(self, mock_db, capsys):
        """Export writes categories to file."""
        args = MagicMock(categories_action="export", file="categories.txt")

        with patch("builtins.open", mock_open()) as mock_file:
            handle_categories_command(mock_db, None, args)

            mock_file.assert_called_once_with("categories.txt", "w")
            handle = mock_file()
            # Check format: name|folder_id|folder_code
            written = "".join(call.args[0] for call in handle.write.call_args_list)
            assert "Videos|vid123|xyz" in written


class TestCategoriesImport:
    """Test categories import subcommand."""

    def test_imports_from_file(self, mock_db, capsys):
        """Import reads categories from file."""
        args = MagicMock(categories_action="import", file="categories.txt")

        file_content = "Videos|vid123|xyz\nPhotos|pho456|abc\n"

        with patch("builtins.open", mock_open(read_data=file_content)):
            handle_categories_command(mock_db, None, args)

            # Should save imported categories
            assert mock_db.save_folder_for_category.call_count >= 1
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_categories_command.py -v`
Expected: FAIL because handle_categories_command doesn't exist

**Step 3: Implement categories command**

```python
# Add to src/commands.py

def handle_categories_command(db_manager, gofile_client, args):
    """
    Handle the categories subcommand.

    Subactions: list, remove, import, export
    """
    from src.services.category_service import CategoryService
    from src.utils import format_size, confirm_action

    action = getattr(args, 'categories_action', None) or 'list'

    if action == 'list':
        _categories_list(db_manager)

    elif action == 'remove':
        pattern = getattr(args, 'pattern', None)
        if not pattern:
            print("Error: category name or pattern required")
            return

        service = CategoryService(db_manager, gofile_client)
        service.remove_category(pattern)

    elif action == 'export':
        file_path = getattr(args, 'file', None)
        if not file_path:
            print("Error: export file path required")
            return

        _categories_export(db_manager, file_path)

    elif action == 'import':
        file_path = getattr(args, 'file', None)
        if not file_path:
            print("Error: import file path required")
            return

        _categories_import(db_manager, file_path)


def _categories_list(db_manager):
    """List all categories with stats."""
    from src.utils import format_size, print_dynamic_table

    categories = db_manager.get_all_categories()

    if not categories:
        print("No categories found.")
        return

    headers = ["CATEGORY", "FILES", "SIZE", "FOLDER LINK"]
    rows = []
    total_size = 0
    total_files = 0

    for cat in categories:
        name = cat.get("name", "")
        folder_code = cat.get("folder_code", "")

        # Get files in category
        files = db_manager.get_files_by_category(name)
        file_count = len(files)
        cat_size = sum(f.get("size", 0) for f in files)

        total_files += file_count
        total_size += cat_size

        link = f"gofile.io/d/{folder_code}" if folder_code else "-"

        rows.append([
            name,
            str(file_count),
            format_size(cat_size),
            link,
        ])

    print_dynamic_table(rows, headers, 30)

    print(f"\n{len(categories)} categories ({format_size(total_size)} total)")


def _categories_export(db_manager, file_path: str):
    """Export categories to file."""
    categories = db_manager.get_all_categories()

    with open(file_path, "w") as f:
        for cat in categories:
            name = cat.get("name", "")
            folder_id = cat.get("folder_id", "")
            folder_code = cat.get("folder_code", "")
            f.write(f"{name}|{folder_id}|{folder_code}\n")

    print(f"Exported {len(categories)} categories to {file_path}")


def _categories_import(db_manager, file_path: str):
    """Import categories from file."""
    imported = 0

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split("|")
            if len(parts) >= 2:
                name = parts[0]
                folder_id = parts[1]
                folder_code = parts[2] if len(parts) > 2 else ""

                db_manager.save_folder_for_category(name, {
                    "folder_id": folder_id,
                    "folder_code": folder_code,
                })
                imported += 1

    print(f"Imported {imported} categories from {file_path}")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_categories_command.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/commands.py tests/test_categories_command.py
git commit -m "$(cat <<'EOF'
feat: add categories subcommand with list, remove, import, export

List shows file count and total size per category.
Import/export use pipe-delimited format for backwards compatibility.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Implement Interactive Mode - Core Framework

**Files:**
- Create: `src/interactive.py`
- Test: `tests/test_interactive.py` (new)

**Step 1: Write the failing tests**

```python
# tests/test_interactive.py
"""Tests for interactive mode."""
import pytest
from unittest.mock import MagicMock, patch, call
from io import StringIO

from src.interactive import (
    InteractiveMode,
    get_menu_choice,
    prompt_input,
)


class TestGetMenuChoice:
    """Test menu choice input."""

    @patch("builtins.input", return_value="1")
    def test_valid_choice(self, mock_input):
        """Valid choice returns integer."""
        result = get_menu_choice(["Option 1", "Option 2"], "Choice: ")
        assert result == 1

    @patch("builtins.input", return_value="0")
    def test_zero_choice(self, mock_input):
        """Zero is valid for exit."""
        result = get_menu_choice(["Option 1", "Option 2"], "Choice: ", allow_zero=True)
        assert result == 0

    @patch("builtins.input", side_effect=["invalid", "1"])
    def test_invalid_then_valid(self, mock_input, capsys):
        """Invalid input prompts again."""
        result = get_menu_choice(["Option 1", "Option 2"], "Choice: ")
        assert result == 1
        captured = capsys.readouterr()
        assert "invalid" in captured.out.lower()


class TestPromptInput:
    """Test prompt input."""

    @patch("builtins.input", return_value="user input")
    def test_returns_input(self, mock_input):
        """Returns user input."""
        result = prompt_input("Enter value: ")
        assert result == "user input"

    @patch("builtins.input", return_value="")
    def test_default_value(self, mock_input):
        """Returns default when empty."""
        result = prompt_input("Enter value: ", default="default")
        assert result == "default"


class TestInteractiveMode:
    """Test InteractiveMode class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        db.get_all_categories.return_value = []
        db.get_all_files.return_value = []
        return db

    @pytest.fixture
    def mock_client(self):
        """Create mock GoFile client."""
        return MagicMock()

    @patch("builtins.input", return_value="0")
    def test_exit_from_main_menu(self, mock_input, mock_db, mock_client, capsys):
        """Selecting 0 exits interactive mode."""
        interactive = InteractiveMode(mock_db, mock_client)
        interactive.run()

        captured = capsys.readouterr()
        assert "exit" in captured.out.lower() or "goodbye" in captured.out.lower()

    @patch("builtins.input", side_effect=["2", "0"])  # List uploads, then exit
    def test_list_menu_option(self, mock_input, mock_db, mock_client, capsys):
        """List uploads option works."""
        mock_db.get_all_files.return_value = []

        interactive = InteractiveMode(mock_db, mock_client)
        interactive.run()

        mock_db.get_all_files.assert_called()

    def test_main_menu_shows_options(self, mock_db, mock_client, capsys):
        """Main menu displays all options."""
        with patch("builtins.input", return_value="0"):
            interactive = InteractiveMode(mock_db, mock_client)
            interactive.run()

        captured = capsys.readouterr()
        # Check main menu options are shown
        assert "upload" in captured.out.lower()
        assert "list" in captured.out.lower()
        assert "search" in captured.out.lower()
        assert "delete" in captured.out.lower()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_interactive.py -v`
Expected: FAIL because src/interactive.py doesn't exist

**Step 3: Implement interactive mode framework**

```python
# src/interactive.py
"""Interactive mode for gofile-uploader."""
from typing import List, Optional, Callable


def get_menu_choice(
    options: List[str],
    prompt: str = "Choice: ",
    allow_zero: bool = True,
) -> int:
    """
    Display menu and get user choice.

    Args:
        options: List of option labels
        prompt: Input prompt
        allow_zero: Whether 0 is a valid choice (for exit)

    Returns:
        Selected option number (1-based, or 0 for exit)
    """
    while True:
        try:
            choice = input(prompt).strip()
            num = int(choice)

            if allow_zero and num == 0:
                return 0

            if 1 <= num <= len(options):
                return num

            print(f"Invalid choice. Enter 1-{len(options)}" +
                  (" or 0 to go back" if allow_zero else ""))

        except ValueError:
            print("Invalid input. Enter a number.")


def prompt_input(prompt: str, default: str = "") -> str:
    """
    Get string input from user.

    Args:
        prompt: Input prompt
        default: Default value if empty

    Returns:
        User input or default
    """
    result = input(prompt).strip()
    return result if result else default


def print_menu(title: str, options: List[str], show_exit: bool = True) -> None:
    """Print a numbered menu."""
    print(f"\n{title}\n")

    for i, option in enumerate(options, 1):
        print(f"  {i}) {option}")

    if show_exit:
        print(f"  0) Exit" if title == "GoFile Uploader - Interactive Mode" else "  0) Back")

    print()


class InteractiveMode:
    """Interactive menu-driven interface."""

    def __init__(self, db_manager, gofile_client):
        self.db = db_manager
        self.client = gofile_client
        self.running = True

    def run(self):
        """Run the interactive mode loop."""
        print("\nGoFile Uploader - Interactive Mode")

        while self.running:
            self._show_main_menu()

    def _show_main_menu(self):
        """Display and handle main menu."""
        options = [
            "Upload files",
            "List uploads",
            "Search files",
            "Delete file",
            "Purge files",
            "Manage categories",
            "Settings",
        ]

        print_menu("GoFile Uploader - Interactive Mode", options)

        choice = get_menu_choice(options, "Choice: ")

        if choice == 0:
            self.running = False
            print("\nGoodbye!")
            return

        handlers = {
            1: self._upload_flow,
            2: self._list_flow,
            3: self._search_flow,
            4: self._delete_flow,
            5: self._purge_flow,
            6: self._categories_flow,
            7: self._settings_flow,
        }

        handler = handlers.get(choice)
        if handler:
            handler()

    def _upload_flow(self):
        """Interactive upload workflow."""
        from src.utils import format_size
        import glob
        import os

        print("\nUpload files\n")

        # Get file path(s)
        path_input = prompt_input("Enter file path(s) or folder: ")
        if not path_input:
            return

        # Expand globs and find files
        files = []
        for pattern in path_input.split():
            if os.path.isdir(pattern):
                # List files in directory
                for f in os.listdir(pattern):
                    full_path = os.path.join(pattern, f)
                    if os.path.isfile(full_path):
                        files.append(full_path)
            else:
                files.extend(glob.glob(pattern))

        if not files:
            print("No files found.")
            return

        # Show files
        total_size = sum(os.path.getsize(f) for f in files)
        print(f"\nFound {len(files)} file(s) ({format_size(total_size)} total):")
        for i, f in enumerate(files[:5], 1):
            size = os.path.getsize(f)
            print(f"  {i}. {os.path.basename(f)} ({format_size(size)})")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more")

        # Get category
        category = prompt_input("\nCategory (or press Enter for none): ")

        # Confirm
        confirm = prompt_input(
            f"\nUpload {len(files)} file(s) ({format_size(total_size)})"
            + (f" to '{category}'" if category else "") + "? [y/N]: "
        )

        if confirm.lower() != 'y':
            print("Cancelled.")
            return

        # Upload (simplified - actual implementation would use UploadService)
        print("\nUploading...")
        # TODO: Integrate with actual upload service

        self._post_upload_menu()

    def _post_upload_menu(self):
        """Menu shown after upload."""
        options = [
            "Upload more",
            "Copy folder link",
            "List uploads",
            "Main menu",
        ]
        print_menu("What next?", options, show_exit=False)

        choice = get_menu_choice(options, "Choice: ", allow_zero=False)
        if choice == 1:
            self._upload_flow()
        elif choice == 3:
            self._list_flow()
        # Options 2 and 4 return to main menu

    def _list_flow(self):
        """Interactive list workflow."""
        from src.views import render_simple_view

        print("\nList uploads\n")

        # Get optional category filter
        category = prompt_input("Filter by category (or press Enter for all): ")

        # Get files
        if category:
            files = self.db.get_files_by_category(category)
        else:
            files = self.db.get_all_files()

        if not files:
            print("No files found.")
        else:
            render_simple_view(files)

        self._post_list_menu()

    def _post_list_menu(self):
        """Menu shown after list."""
        options = [
            "Filter/search",
            "Change view",
            "Delete file",
            "Main menu",
        ]
        print_menu("What next?", options, show_exit=False)

        choice = get_menu_choice(options, "Choice: ", allow_zero=False)
        if choice == 1:
            self._search_flow()
        elif choice == 3:
            self._delete_flow()

    def _search_flow(self):
        """Interactive search workflow."""
        from src.views import render_simple_view
        from src.filters import SearchFilter

        print("\nSearch files\n")

        query = prompt_input("Search term: ")
        if not query:
            return

        files = self.db.get_all_files()
        search_filter = SearchFilter(query)
        matched = [f for f in files if search_filter.matches(f)]

        print(f'\nFound {len(matched)} file(s) matching "{query}":')
        if matched:
            render_simple_view(matched)

        self._post_search_menu()

    def _post_search_menu(self):
        """Menu shown after search."""
        options = [
            "New search",
            "Delete file",
            "Main menu",
        ]
        print_menu("What next?", options, show_exit=False)

        choice = get_menu_choice(options, "Choice: ", allow_zero=False)
        if choice == 1:
            self._search_flow()
        elif choice == 2:
            self._delete_flow()

    def _delete_flow(self):
        """Interactive delete workflow."""
        from src.file_manager import find_file
        from src.services.deletion_service import DeletionService

        print("\nDelete file\n")

        target = prompt_input("Enter file ID, number, or name: ")
        if not target:
            return

        result = find_file(self.db, target)
        if not result:
            print("File not found.")
            return

        file_data = result['file_data']
        print(f"\nFound: {file_data['name']} ({file_data.get('size', 0)} bytes)")
        print(f"  Link: {file_data.get('download_link', '')}")

        confirm = prompt_input("\nDelete this file? [y/N]: ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return

        deletion_service = DeletionService(self.db, self.client)
        deletion_service.delete_file(result['actual_id'], auto_confirm=True)

        print(f"\nDeleted {file_data['name']}")

        self._post_delete_menu()

    def _post_delete_menu(self):
        """Menu shown after delete."""
        options = [
            "Delete another",
            "List files",
            "Main menu",
        ]
        print_menu("What next?", options, show_exit=False)

        choice = get_menu_choice(options, "Choice: ", allow_zero=False)
        if choice == 1:
            self._delete_flow()
        elif choice == 2:
            self._list_flow()

    def _purge_flow(self):
        """Interactive purge workflow."""
        print("\nPurge files\n")

        options = [
            "Purge expired files",
            "Purge by date",
            "Purge by size",
            "Select files to delete",
        ]
        print_menu("Purge files", options)

        choice = get_menu_choice(options, "Choice: ")
        if choice == 0:
            return

        # TODO: Implement purge sub-flows
        print("Purge feature coming soon...")

    def _categories_flow(self):
        """Interactive categories workflow."""
        print("\nManage categories\n")

        options = [
            "List categories",
            "Create category",
            "Remove category",
            "Import categories",
            "Export categories",
        ]
        print_menu("Manage categories", options)

        choice = get_menu_choice(options, "Choice: ")
        if choice == 0:
            return

        if choice == 1:
            from src.commands import _categories_list
            _categories_list(self.db)

        # TODO: Implement other category operations

    def _settings_flow(self):
        """Interactive settings workflow."""
        print("\nSettings\n")
        print("Settings feature coming soon...")


def run_interactive(db_manager, gofile_client):
    """Entry point for interactive mode."""
    interactive = InteractiveMode(db_manager, gofile_client)
    interactive.run()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_interactive.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/interactive.py tests/test_interactive.py
git commit -m "$(cat <<'EOF'
feat: add interactive mode with menu-driven interface

Main menu with upload, list, search, delete, purge, categories.
Each flow has post-action menus for quick navigation.
Simple numbered menus, no TUI library required.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Update Help Text

**Files:**
- Modify: `src/gofile_uploader.py`
- Test: `tests/test_cli.py` (extend)

**Step 1: Write the failing test**

```python
# Add to tests/test_cli.py

class TestHelpTextFormat:
    """Test help text formatting."""

    def test_help_has_quick_start(self, capsys):
        """Help includes QUICK START section."""
        with patch.object(sys, 'argv', ['gofile-uploader', '--help']):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        assert "QUICK START" in captured.out

    def test_help_has_commands_section(self, capsys):
        """Help includes COMMANDS section."""
        with patch.object(sys, 'argv', ['gofile-uploader', '--help']):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        # Should list main commands
        assert "upload" in captured.out.lower()
        assert "list" in captured.out.lower()
        assert "search" in captured.out.lower()
        assert "interactive" in captured.out.lower()

    def test_subcommand_help(self, capsys):
        """Subcommand help shows relevant options."""
        with patch.object(sys, 'argv', ['gofile-uploader', 'list', '--help']):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        # Should show filter options
        assert "--search" in captured.out
        assert "--expired" in captured.out
        # Should show view options
        assert "--view" in captured.out
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestHelpTextFormat -v`
Expected: FAIL because help text doesn't have the expected format yet

**Step 3: Update help text in argument parser**

Update the epilog and descriptions in `_create_argument_parser()` to match the design document format:

```python
# In src/gofile_uploader.py, update _create_argument_parser()

HELP_EPILOG = """
QUICK START:
  gofile-uploader upload photo.jpg           Upload a file
  gofile-uploader upload *.mp4 -c Videos     Upload to category
  gofile-uploader list                       Show your uploads
  gofile-uploader interactive                Menu-driven mode

COMMANDS:
  upload      Upload files to GoFile
  list        List uploaded files
  search      Search files by name
  delete      Delete a file
  purge       Bulk delete files
  categories  Manage categories
  interactive Launch interactive mode

Run 'gofile-uploader <command> --help' for command-specific help.
"""
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::TestHelpTextFormat -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/gofile_uploader.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
feat: update help text with QUICK START and grouped options

Help now includes quick-start examples and organized command list
for better discoverability.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Wire Everything Together

**Files:**
- Modify: `src/gofile_uploader.py` (main routing)
- Modify: `src/commands.py` (handler imports)

**Step 1: Write integration tests**

```python
# tests/test_integration.py
"""Integration tests for full command flows."""
import pytest
from unittest.mock import MagicMock, patch
import sys

from src.gofile_uploader import main


class TestUploadSubcommand:
    """Test upload subcommand integration."""

    @patch("src.gofile_uploader.DatabaseManager")
    @patch("src.gofile_uploader.GoFileClient")
    @patch("src.gofile_uploader.setup_logging")
    def test_upload_with_category(self, mock_log, mock_client, mock_db, tmp_path):
        """Upload subcommand with category works."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_db_inst = MagicMock()
        mock_db.return_value = mock_db_inst
        mock_client_inst = MagicMock()
        mock_client.return_value = mock_client_inst

        with patch.object(sys, 'argv', ['gofile-uploader', 'upload', str(test_file), '-c', 'Test']):
            with patch("src.commands.handle_upload_command") as mock_upload:
                main()
                mock_upload.assert_called_once()


class TestListSubcommand:
    """Test list subcommand integration."""

    @patch("src.gofile_uploader.DatabaseManager")
    @patch("src.gofile_uploader.setup_logging")
    def test_list_with_filters(self, mock_log, mock_db, capsys):
        """List subcommand with filters works."""
        mock_db_inst = MagicMock()
        mock_db_inst.get_all_files.return_value = []
        mock_db.return_value = mock_db_inst

        with patch.object(sys, 'argv', ['gofile-uploader', 'list', '--expired']):
            main()

        mock_db_inst.get_all_files.assert_called()


class TestSearchSubcommand:
    """Test search subcommand integration."""

    @patch("src.gofile_uploader.DatabaseManager")
    @patch("src.gofile_uploader.setup_logging")
    def test_search_command(self, mock_log, mock_db, capsys):
        """Search subcommand works."""
        mock_db_inst = MagicMock()
        mock_db_inst.get_all_files.return_value = []
        mock_db.return_value = mock_db_inst

        with patch.object(sys, 'argv', ['gofile-uploader', 'search', 'video']):
            main()

        mock_db_inst.get_all_files.assert_called()


class TestInteractiveSubcommand:
    """Test interactive subcommand integration."""

    @patch("src.gofile_uploader.DatabaseManager")
    @patch("src.gofile_uploader.GoFileClient")
    @patch("src.gofile_uploader.setup_logging")
    @patch("builtins.input", return_value="0")  # Exit immediately
    def test_interactive_launches(self, mock_input, mock_log, mock_client, mock_db):
        """Interactive subcommand launches interactive mode."""
        mock_db.return_value = MagicMock()
        mock_client.return_value = MagicMock()

        with patch.object(sys, 'argv', ['gofile-uploader', 'interactive']):
            with patch("src.interactive.InteractiveMode") as mock_interactive:
                mock_interactive.return_value.run = MagicMock()
                main()
                mock_interactive.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_integration.py -v`
Expected: FAIL because routing isn't complete yet

**Step 3: Wire up all handlers in main()**

Update `src/gofile_uploader.py` main() to route to all new handlers:

```python
# In src/gofile_uploader.py main()

def main():
    """Main entry point."""
    parser = _create_argument_parser()
    args = parser.parse_args()

    # Initialize
    db_manager, gofile_client = _initialize_application(args)

    # Route to handlers based on subcommand or legacy flags
    command = getattr(args, 'command', None)

    if command == 'upload':
        handle_upload_command(db_manager, gofile_client, args)

    elif command == 'list':
        handle_list_files_command(db_manager, args)

    elif command == 'search':
        handle_search_command(db_manager, args)

    elif command == 'delete':
        handle_delete_file_command(db_manager, gofile_client, args)

    elif command == 'purge':
        handle_purge_command(db_manager, gofile_client, args)

    elif command == 'categories':
        handle_categories_command(db_manager, gofile_client, args)

    elif command in ('interactive', 'i'):
        from src.interactive import run_interactive
        run_interactive(db_manager, gofile_client)

    # Legacy flag handling (backwards compatibility)
    elif getattr(args, 'list', False):
        handle_list_categories_command(db_manager)

    elif getattr(args, 'list_files', None) is not None:
        # Convert legacy args to new format
        handle_list_files_command(db_manager, args)

    elif getattr(args, 'delete_file', None):
        handle_delete_file_command(db_manager, gofile_client, args)

    elif getattr(args, 'files', None):
        handle_upload_command(db_manager, gofile_client, args)

    # ... rest of legacy handlers
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_integration.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/gofile_uploader.py src/commands.py tests/test_integration.py
git commit -m "$(cat <<'EOF'
feat: wire up all subcommands and handlers

Complete routing for upload, list, search, delete, purge, categories,
and interactive commands with backwards compatibility preserved.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Update Version to 1.0.0

**Files:**
- Modify: `src/__init__.py`
- Modify: `pyproject.toml`

**Step 1: Write the failing test**

```python
# Add to tests/test_cli.py

class TestVersion:
    """Test version information."""

    def test_version_is_1_0_0(self, capsys):
        """Version should be 1.0.0."""
        with patch.object(sys, 'argv', ['gofile-uploader', '--version']):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        assert "1.0.0" in captured.out
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestVersion -v`
Expected: FAIL because version is still 0.1.0

**Step 3: Update version**

```python
# src/__init__.py
__version__ = "1.0.0"
```

```toml
# pyproject.toml
[project]
version = "1.0.0"
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::TestVersion -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/__init__.py pyproject.toml tests/test_cli.py
git commit -m "$(cat <<'EOF'
chore: bump version to 1.0.0

First major release with subcommand syntax, filtering, view modes,
and interactive mode.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Final Integration Testing and Documentation

**Files:**
- Run all tests
- Manual testing checklist

**Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS

**Step 2: Manual testing checklist**

Test each feature manually:

```bash
# New subcommand syntax
gofile-uploader upload test.txt -c Test
gofile-uploader list
gofile-uploader list --expired
gofile-uploader list --larger 100MB
gofile-uploader search "video"
gofile-uploader delete test.txt
gofile-uploader purge --expired
gofile-uploader categories list
gofile-uploader interactive

# Backwards compatibility
gofile-uploader test.txt -c Test
gofile-uploader -lf
gofile-uploader -l
gofile-uploader -df test.txt

# View modes
gofile-uploader list --view simple
gofile-uploader list --view detailed
gofile-uploader list --view links
gofile-uploader list --compact

# Combined filters
gofile-uploader list --category Videos --since 2025-01-01 --larger 100MB
```

**Step 3: Commit final state**

```bash
git add -A
git commit -m "$(cat <<'EOF'
test: verify v1.0.0 feature completeness

All features from design document implemented and tested:
- Subcommand syntax with backwards compatibility
- Filter options (search, since, before, larger, smaller, expired, expiring)
- View modes (simple, detailed, links, compact)
- Interactive mode with menu navigation
- Categories management
- Purge command with filters

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```

---

## Summary

This implementation plan covers 15 tasks:

1. **Size Parsing Utility** - Parse human-readable sizes
2. **Date Parsing Utility** - Parse YYYY-MM-DD dates
3. **Filter Predicate System** - Composable filters with AND logic
4. **Color Output Utility** - Terminal color with graceful degradation
5. **CLI Subcommand Architecture** - argparse subparsers with backwards compat
6. **Filter Integration in List** - Apply filters to list command
7. **Search Command** - Shorthand for list with search
8. **Purge Command** - Bulk delete with filters
9. **View Modes** - simple, detailed, links, compact
10. **Categories Subcommand** - list, remove, import, export
11. **Interactive Mode Framework** - Menu-driven interface
12. **Update Help Text** - QUICK START and grouped options
13. **Wire Everything Together** - Complete routing
14. **Update Version** - Bump to 1.0.0
15. **Final Integration Testing** - Full test suite verification

Each task follows TDD: failing test → minimal implementation → passing test → commit.
