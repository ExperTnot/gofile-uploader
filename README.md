# GoFile Uploader

A Python program that uploads files to GoFile.io with progress tracking, logging, and category-based folder management. **This tool is designed specifically for temporary GoFile accounts only.**

## Features

- Upload files to GoFile.io
- Display real-time progress bar with human-readable upload speed (GB/s, MB/s, KB/s)
- Human-readable file sizes (GB, MB, KB)
- Estimate remaining time for upload completion
- Log file uploads with timestamps and download links
- Support for multiple file uploads
- Modular code structure for better maintainability
- Category-based folder management for organizing uploads
- Persistent storage of categories, folders, and guest account information in SQLite database
- File tracking system with detailed upload history
- Rotating log files with size management

> **Important Note**  
> This tool works exclusively with temporary GoFile accounts which expire after a period of inactivity. Files uploaded using this tool will not be permanently stored and may become inaccessible after the temporary account expires. This tool is not intended for long-term file storage.

## TODOs

- [x] Basic file upload functionality
- [x] Progress tracking with tqdm
- [x] SQLite database integration
- [x] Category-based folder management
- [x] File tracking system
- [x] File expiry tracking (hardcoded 10 days from upload which his minimum expiration time)
- [x] Database entry deletion functionality
- [x] Sortable file listings
- [ ] Automatic retry on failed uploads
- [ ] Send expiration date notifications
- [ ] Pagination for large file listings

## Requirements

- Python 3.9+
- SQLite3 (included in Python's standard library)
- Required packages (install using `pip install -r requirements.txt`):
  - requests
  - tqdm
  - requests-toolbelt

## Installation

1. Clone or download this repository
2. Install the required packages:

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Upload a single file
python gofile-uploader.py /path/to/your/file.ext

# Upload multiple files
python gofile-uploader.py /path/to/file1.ext /path/to/file2.ext

# Upload files to a specific category (folder)
python gofile-uploader.py -c Photos /path/to/photo1.jpg /path/to/photo2.jpg

# List all available categories
python gofile-uploader.py -l

# Upload more files to an existing category
python gofile-uploader.py -c Photos /path/to/more_photos/*.jpg

# Suppress summary output
python gofile-uploader.py -q /path/to/your/file.ext

# Show verbose output
python gofile-uploader.py -v /path/to/your/file.ext

# List all uploaded files (now with expiry date information)
python gofile-uploader.py -lf

# List files from a specific category
python gofile-uploader.py -lf Photos

# Sort file listings by various criteria
python gofile-uploader.py -lf -s name     # Sort by filename
python gofile-uploader.py -lf -s size     # Sort by file size
python gofile-uploader.py -lf -s date     # Sort by upload date
python gofile-uploader.py -lf -s expiry   # Sort by expiry date
python gofile-uploader.py -lf -s category # Sort by category
python gofile-uploader.py -lf -s link     # Sort by download link

# Change sort order (default is ascending)
python gofile-uploader.py -lf -s size -o desc  # Sort by size in descending order

# Delete a file entry from the database
python gofile-uploader.py -df filename.ext   # Delete by filename
python gofile-uploader.py -df 1              # Delete by serial ID
python gofile-uploader.py -df abc123-456     # Delete by file ID

# Remove a category (with confirmation) . Does not remove files from GoFile or the database jsut the category
python gofile-uploader.py -rm Photos
```

## Configuration

The program uses a configuration file (`gofile_config.json`) to store settings such as:

1. Database file location (`database_path`)
2. Log folder path (`log_folder`)
3. Log file base name (`log_basename`)
4. Maximum log file size in MB (`max_log_size_mb`)
5. Number of backup log files to keep (`max_log_backups`)

This allows for permanent changes to these settings without needing to specify them on the command line each time.

### Default Configuration

By default, the program uses the following directory structure:

```
gofile-auto/
├── db/                  # Database directory
│   └── gofile.db        # SQLite database file
├── logs/                # Log files directory
│   ├── gofile_0.log     # Current log file
│   ├── gofile_1.log     # Backup log file 1
│   └── gofile_2.log     # Backup log file 2
├── src/                 # Source code directory
│   ├── main.py          # Core application logic
│   ├── gofile_client.py # API client implementation
│   ├── db_manager.py    # Database manager
│   ├── utils.py         # Utility functions
│   ├── logging_utils.py # Logging utilities
│   └── config.py        # Configuration management
├── gofile_config.json   # Configuration file
└── gofile.py            # Main launcher script
```

The program will automatically create these directories if they don't exist.

## Log Format

The uploader creates rotating log files (default: `logs/gofile_*.log`), with a configurable maximum size and number of backup files. The logs contain:

1. Standard log messages with timestamps
2. JSON-formatted entries for each upload containing:
   - Timestamp
   - Filename
   - File size (both bytes and human-readable format)
   - Upload speed (human-readable format)
   - Download link
   - File ID
   - Folder ID
   - Category (if specified)

## Category and File Management

The program maintains a SQLite database file (default: `db/gofile.db`) to store:

1. Category-to-folder mappings
2. Guest account information
3. Detailed file tracking information

This allows you to organize your uploads by categories, with each category corresponding to a folder on GoFile.io. When you upload files with the same category name, they'll be stored in the same folder, even across different sessions.

## File Expiry Tracking

GoFile uploads expire after a minimum of 10 days. This tool helps you keep track of your files' minimum expiry status:

1. **Expiry Status Display**: When listing files with `-lf`, each file shows one of these status indicators:
   - "EXPIRED" for files past their expiration date
   - "EXPIRES SOON (X days)" for files that will expire within 3 days
   - An exact expiry date (YYYY-MM-DD) for other files

2. **Sorted Expiry View**: Use `-lf -s expiry` to sort files by their expiration date

3. **Safe File Management**: Files are only added to the database when fully uploaded. Interrupted uploads (via Ctrl+C or errors) are not tracked.

4. **Database Cleanup**: Use the `-df` option to delete expired file entries from your local database

### How It Works

1. The first time you use a category, a new folder is created on GoFile.io
2. The folder ID is saved to the SQLite database with the category name
3. Future uploads using the same category will go to the same folder
4. Your guest account information is also saved, so all uploads use the same account
5. All uploaded files are tracked in the database with detailed information
6. You can list all previously uploaded files or filter by category

### File Tracking

For each uploaded file, the following information is stored in the database:

- File ID and name
- File size and MIME type
- Upload time, speed, and duration
- Download link
- Associated folder and category
- Guest account ID

This tracking allows you to maintain a complete history of all uploads and easily retrieve file information later.

## License

This project is open-source and free to use.
