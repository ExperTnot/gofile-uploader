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
