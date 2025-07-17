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
- Delete files from both GoFile servers and local database
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
- [x] Remote deletion of files from GoFile servers
- [x] Sortable file listings
- [x] Pagination for large file listings
- [x] Category removal and management
- [ ] Automatic retry on failed uploads
- [ ] Send expiration date notifications

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

# Upload files to a specific category (folder) using glob patterns
python gofile-uploader.py -c Photos /path/to/photo*.jpg

# Upload files to a specific category (folder) using partial category name
python gofile-uploader.py -c P* /path/to/photo.jpg # This will try to automatically resolve the category name

# List all available categories and their folder links
python gofile-uploader.py -l

# Suppress summary output
python gofile-uploader.py -q /path/to/your/file.ext

# List all uploaded files (now with expiry date information)
python gofile-uploader.py -lf

# List files from a specific category
python gofile-uploader.py -lf Photos

# Control filename display width
python gofile-uploader.py -lf -mfn       # Limit filenames to 80 characters
python gofile-uploader.py -lf -mfn 50    # Limit filenames to 50 characters

# Pagination for large file listings
python gofile-uploader.py -lf -p 2       # View second page of results

# Upload directory contents recursively
python gofile-uploader.py -c MyFiles -r /path/to/directory  # Upload all files in directory and subdirectories

# Sort file listings by various criteria
python gofile-uploader.py -lf -s name     # Sort by on of name, size, date, expiry, category, link

# Change sort order (default is ascending)
python gofile-uploader.py -lf -s size -o desc  # Sort by size in descending order

# Select specific columns to display
python gofile-uploader.py -lf -col id,name,size      # Show only ID, filename and size

# Combine options
python gofile-uploader.py -lf -s date -o desc -p 2 -mfn 50  # Sort by date, page 2, 50-char filenames

# Delete a file from both GoFile server and local database
python gofile-uploader.py -df filename.ext   # Delete by filename
python gofile-uploader.py -df 1              # Delete by serial ID
python gofile-uploader.py -df abc123-456...  # Delete by file ID

# -rm, -dl, -pf and --clear can all use --force to skip remote deletion

# Remove a category (with confirmation and option to delete its files)
# This does not remove files from GoFile or the database, just the category entry
python gofile-uploader.py -rm some_category  # Supports wildcard matching (e.g. Test*)

# Delete all files for a category (even if category was already removed)
python gofile-uploader.py --purge-files some_category  # Supports wildcard matching (e.g. Test*)
python gofile-uploader.py --purge-files some_category --force  # Skip remote deletion

# Clean up all file entries for deleted categories
python gofile-uploader.py --clear
python gofile-uploader.py --clear --force  # Skip remote deletion
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

> **Be aware that if a folder is deleted from GoFile.io**, the category will still be in the database and you will not be able to upload to it again. It will return error 500 if you try to upload to it. You can remove the category from the database using the `-rm` option and clean up associated file entries with `--purge-files` or `--clear`.

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