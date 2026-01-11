# GoFile Uploader PyPI Release Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform gofile-uploader into a production-ready PyPI package installable via `pip install gofile-uploader`.

**Architecture:** Restructure to src-layout package with pyproject.toml, add proper versioning, LICENSE, and entry points. Improve test coverage for CLI. Keep existing functionality intact.

**Tech Stack:** Python 3.9+, setuptools/pyproject.toml, pytest

---

## Task 1: Add MIT License File

**Files:**
- Create: `LICENSE`

**Step 1: Create LICENSE file**

Create `LICENSE` with MIT license text:

```
MIT License

Copyright (c) 2025 GoFile Uploader Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Step 2: Commit**

```bash
git add LICENSE
git commit -m "chore: add MIT license"
```

---

## Task 2: Create pyproject.toml

**Files:**
- Create: `pyproject.toml`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "gofile-uploader"
version = "0.1.0"
description = "Upload files to GoFile.io with progress tracking, category management, and SQLite-based file tracking"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
authors = [
    {name = "GoFile Uploader Contributors"}
]
keywords = ["gofile", "upload", "file-sharing", "cli"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Internet",
    "Topic :: Utilities",
]
dependencies = [
    "requests>=2.28.1",
    "tqdm>=4.64.1",
    "requests-toolbelt>=1.0.0",
    "wcwidth>=0.2.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
]

[project.scripts]
gofile-uploader = "src.gofile_uploader:main"

[project.urls]
Homepage = "https://github.com/YOUR_USERNAME/gofile-uploader"
Repository = "https://github.com/YOUR_USERNAME/gofile-uploader"
Issues = "https://github.com/YOUR_USERNAME/gofile-uploader/issues"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
filterwarnings = ["ignore::DeprecationWarning"]
```

**Step 2: Verify package builds**

```bash
source .venv/bin/activate && pip install build && python -m build --sdist
```

Expected: Creates `dist/gofile_uploader-0.1.0.tar.gz`

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add pyproject.toml for PyPI packaging"
```

---

## Task 3: Centralize Version String

**Files:**
- Modify: `src/gofile_uploader.py:43` (remove `__version__`)
- Modify: `src/__init__.py` (add `__version__`)
- Modify: `pyproject.toml` (use dynamic versioning)

**Step 1: Update src/__init__.py**

Replace empty `src/__init__.py` with:

```python
"""GoFile Uploader - Upload files to GoFile.io with progress tracking."""

__version__ = "0.1.0"
```

**Step 2: Update src/gofile_uploader.py**

At line 43, change:
```python
__version__ = "0.1.0"
```
to:
```python
from src import __version__
```

**Step 3: Update pyproject.toml for dynamic version**

Change in pyproject.toml:
```toml
version = "0.1.0"
```
to:
```toml
dynamic = ["version"]
```

And add:
```toml
[tool.setuptools.dynamic]
version = {attr = "src.__version__"}
```

**Step 4: Run tests to verify nothing broke**

```bash
source .venv/bin/activate && python -m pytest --tb=short
```

Expected: All 171 tests pass

**Step 5: Commit**

```bash
git add src/__init__.py src/gofile_uploader.py pyproject.toml
git commit -m "refactor: centralize version string in src/__init__.py"
```

---

## Task 4: Add __main__.py for Module Execution

**Files:**
- Create: `src/__main__.py`

**Step 1: Create src/__main__.py**

```python
"""Allow running as: python -m src"""

from src.gofile_uploader import main

if __name__ == "__main__":
    main()
```

**Step 2: Test module execution**

```bash
source .venv/bin/activate && python -m src --version
```

Expected: Prints version number

**Step 3: Commit**

```bash
git add src/__main__.py
git commit -m "feat: add __main__.py for python -m src execution"
```

---

## Task 5: Add pytest to dev dependencies in requirements

**Files:**
- Modify: `requirements.txt`

**Step 1: Update requirements.txt**

Add at the end:
```
# Development dependencies
pytest>=7.0.0
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pytest to requirements.txt"
```

---

## Task 6: Create CHANGELOG.md

**Files:**
- Create: `CHANGELOG.md`

**Step 1: Create CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-08

### Added
- Initial PyPI release
- Upload files to GoFile.io with progress tracking
- Category-based folder organization
- SQLite database for persistent file tracking
- File expiry tracking (10-day minimum)
- Delete files from GoFile servers and local database
- Dry-run mode for previewing uploads
- Automatic retry on transient failures
- Rotating log files
- Sortable and paginated file listings

### Features
- `gofile-uploader` CLI command
- Category management with wildcard matching
- Batch file operations
- Recursive directory uploads
```

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add CHANGELOG.md"
```

---

## Task 7: Update README for PyPI

**Files:**
- Modify: `README.md`

**Step 1: Update installation section**

Replace lines 52-59 (the Installation section) with:

```markdown
## Installation

### From PyPI (recommended)

```bash
pip install gofile-uploader
```

### From source

```bash
git clone https://github.com/YOUR_USERNAME/gofile-uploader.git
cd gofile-uploader
pip install -e .
```
```

**Step 2: Update usage examples**

Replace `python gofile-uploader.py` with `gofile-uploader` in all examples (lines 63-141).

For example, change:
```bash
python gofile-uploader.py /path/to/your/file.ext
```
to:
```bash
gofile-uploader /path/to/your/file.ext
```

**Step 3: Update License section at bottom**

Replace lines 244-246:
```markdown
## License

This project is open-source and free to use.
```
with:
```markdown
## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
```

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README for PyPI installation"
```

---

## Task 8: Add CLI Tests

**Files:**
- Create: `tests/test_cli.py`

**Step 1: Write CLI argument parsing tests**

Create `tests/test_cli.py`:

```python
#!/usr/bin/env python3
"""Tests for CLI argument parsing and main entry points."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

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
    def test_list_categories_empty(self, mock_logging, mock_db_class, capsys):
        """Should handle empty category list."""
        mock_db = MagicMock()
        mock_db.list_categories.return_value = []
        mock_db.get_categories_info.return_value = []
        mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(sys, 'argv', ['gofile-uploader', '-l']):
            result = main()

        assert result == 0


class TestListFiles:
    """Tests for -lf flag."""

    @patch('src.gofile_uploader.DatabaseManager')
    @patch('src.gofile_uploader.setup_logging')
    @patch('src.gofile_uploader.list_files')
    def test_list_files(self, mock_list_files, mock_logging, mock_db_class):
        """Should call list_files function."""
        mock_db = MagicMock()
        mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(sys, 'argv', ['gofile-uploader', '-lf']):
            main()

        mock_list_files.assert_called_once()


class TestDryRun:
    """Tests for --dry-run flag."""

    @patch('src.gofile_uploader.DatabaseManager')
    @patch('src.gofile_uploader.setup_logging')
    def test_dry_run_no_files(self, mock_logging, mock_db_class, capsys, tmp_path):
        """Should handle dry run with no matching files."""
        mock_db = MagicMock()
        mock_db_class.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_class.return_value.__exit__ = MagicMock(return_value=False)

        nonexistent = str(tmp_path / "nonexistent*.txt")
        with patch.object(sys, 'argv', ['gofile-uploader', '--dry-run', nonexistent]):
            result = main()

        # Should exit with error when no files found
        assert result != 0 or "No files" in capsys.readouterr().out


class TestNoArguments:
    """Tests for running without arguments."""

    def test_no_arguments_shows_help(self, capsys):
        """Should show usage when no arguments provided."""
        with patch.object(sys, 'argv', ['gofile-uploader']):
            result = main()

        captured = capsys.readouterr()
        # Either shows help or returns error
        assert result != 0 or 'usage' in captured.out.lower() or 'usage' in captured.err.lower()
```

**Step 2: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_cli.py -v
```

Expected: All tests pass

**Step 3: Run full test suite**

```bash
source .venv/bin/activate && python -m pytest --tb=short
```

Expected: 171+ tests pass

**Step 4: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: add CLI argument parsing tests"
```

---

## Task 9: Add .gitignore entries for build artifacts

**Files:**
- Modify: `.gitignore`

**Step 1: Add build artifact patterns**

Append to `.gitignore`:

```
# Build artifacts
dist/
build/
*.egg-info/
*.egg
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add build artifacts to .gitignore"
```

---

## Task 10: Test Full Package Build and Install

**Files:** None (verification only)

**Step 1: Build the package**

```bash
source .venv/bin/activate
pip install build
python -m build
```

Expected: Creates files in `dist/`:
- `gofile_uploader-0.1.0.tar.gz`
- `gofile_uploader-0.1.0-py3-none-any.whl`

**Step 2: Test installation in fresh venv**

```bash
python3 -m venv /tmp/test-gofile-venv
source /tmp/test-gofile-venv/bin/activate
pip install dist/gofile_uploader-0.1.0-py3-none-any.whl
gofile-uploader --version
gofile-uploader --help
deactivate
rm -rf /tmp/test-gofile-venv
```

Expected:
- `--version` prints `0.1.0`
- `--help` shows usage information

**Step 3: Clean up build artifacts**

```bash
rm -rf dist/ build/ *.egg-info/
```

---

## Task 11: Remove old entry point file

**Files:**
- Delete: `gofile-uploader.py`

**Step 1: Remove the file**

```bash
rm gofile-uploader.py
```

**Step 2: Commit**

```bash
git add -A
git commit -m "chore: remove old entry point, now using package entry point"
```

---

## Task 12: Final Verification

**Step 1: Run all tests**

```bash
source .venv/bin/activate && python -m pytest --tb=short
```

Expected: All tests pass

**Step 2: Verify editable install works**

```bash
pip install -e .
gofile-uploader --version
gofile-uploader -l
```

Expected: Commands work correctly

**Step 3: Create final release commit**

```bash
git add -A
git status
```

If there are uncommitted changes:
```bash
git commit -m "chore: prepare v0.1.0 release"
```

---

## Post-Implementation: PyPI Publishing (Manual Steps)

These steps are done manually when ready to publish:

1. **Create PyPI account** at https://pypi.org/account/register/

2. **Create API token** at https://pypi.org/manage/account/token/

3. **Install twine**:
   ```bash
   pip install twine
   ```

4. **Build final package**:
   ```bash
   python -m build
   ```

5. **Upload to TestPyPI first** (optional but recommended):
   ```bash
   twine upload --repository testpypi dist/*
   pip install --index-url https://test.pypi.org/simple/ gofile-uploader
   ```

6. **Upload to PyPI**:
   ```bash
   twine upload dist/*
   ```

7. **Verify installation**:
   ```bash
   pip install gofile-uploader
   gofile-uploader --version
   ```

8. **Tag release**:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   ```
