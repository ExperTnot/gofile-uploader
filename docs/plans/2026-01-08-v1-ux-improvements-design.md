# GoFile Uploader v1.0 - UX Improvements Design

**Date:** 2026-01-08
**Focus:** Casual user experience improvements
**Status:** Approved

## Overview

Design for the first major version of gofile-uploader, focused on making the tool more approachable for casual users while maintaining backwards compatibility for power users.

**Primary audience:** Casual users who upload files occasionally and want simplicity. Power users already have pattern matching, recursive uploads, and scripting support - no extras needed for them.

---

## 1. Command Structure

### Subcommands

New subcommand syntax alongside existing flags (backwards compatible):

```
gofile-uploader upload <files> [-c category] [--dry-run]
gofile-uploader list [category] [filters] [view options]
gofile-uploader search <query> [filters]
gofile-uploader delete <id|name|pattern>
gofile-uploader purge [--expired | --older-than DATE | --larger SIZE]
gofile-uploader categories [list|remove|import|export]
gofile-uploader interactive
```

### Backwards Compatibility

Existing syntax continues to work:

```
gofile-uploader file.zip -c Photos       # Same as: upload file.zip -c Photos
gofile-uploader -lf                      # Same as: list
gofile-uploader -df file.zip             # Same as: delete file.zip
```

**Implementation:** Use argparse subparsers with fallback - if no subcommand is recognized and positional args look like files, treat as implicit `upload` command.

---

## 2. Filter Options

All filters can be combined (AND logic):

```
--search TEXT          Filter by filename
--since DATE           Uploaded after (YYYY-MM-DD)
--before DATE          Uploaded before (YYYY-MM-DD)
--larger SIZE          Larger than (e.g., 100MB, 1GB)
--smaller SIZE         Smaller than
--expired              Only expired files
--expiring             Only files expiring soon
--category NAME        Filter by category
```

### `search` Command vs `--search` Filter

- `gofile-uploader search "video"` - Dedicated search command, search is the primary action
- `gofile-uploader list --search "video"` - Filter within list command

Both support the same filters. The `search` command is shorthand for `list --search`.

### Size Format

Accepts human-readable sizes (case-insensitive):
- `100MB`, `100mb`, `100M` → 100 megabytes
- `1GB`, `1gb`, `1G` → 1 gigabyte
- `500KB`, `500kb`, `500K` → 500 kilobytes
- Plain numbers treated as bytes: `1048576` → 1 MB

### Examples

```bash
# Find large expired files in Photos
gofile-uploader list --category Photos --expired --larger 500MB

# Purge old small files
gofile-uploader purge --older-than 2025-06-01 --smaller 10MB

# Search within a date range
gofile-uploader search "video" --since 2025-01-01 --before 2025-06-01

# Combine multiple filters
gofile-uploader list --category Videos --since 2025-01-01 --larger 100MB --expiring
```

---

## 3. View Options

```
--view simple          Name, link, expiry only (default)
--view detailed        All columns
--view links           Just download URLs (for scripting)
--compact              Dense layout for narrow terminals
--columns COL1,COL2    Custom column selection
--sort FIELD           Sort by field
--order asc|desc       Sort direction
--page N               Page number (default: 1)
--per-page N           Items per page (default: 20)
```

### Available Columns

For `--columns` and `--sort`:

| Column | Description |
|--------|-------------|
| `#` | Row number |
| `name` | Filename |
| `size` | File size |
| `category` | Category name |
| `uploaded` | Upload date/time |
| `expiry` | Expiry date or status |
| `link` | Download URL |
| `mime` | MIME type |
| `speed` | Upload speed achieved |

### Compact Mode

`--compact` reduces spacing and truncates long filenames to fit narrow terminals:

```
NAME              SIZE    EXPIRY      LINK
vacation.mp4      1.2GB   2025-01-18  gofile.io/d/abc123
report.pdf        2.4MB   EXPIRING    gofile.io/d/def456
old_backup.zip    890MB   EXPIRED     gofile.io/d/ghi789
```

Combines with any view mode: `--view detailed --compact`

### Pagination

Results are paginated by default. Summary footer shows pagination info:

```
3 files (2.1 GB) · 1 expired · Page 1/3

Use --page N to navigate, or --per-page 0 for all results.
```

---

## 4. Purge Command

Bulk delete with filters:

```bash
gofile-uploader purge --expired                      # All expired files
gofile-uploader purge --older-than 2025-01-01        # Before date
gofile-uploader purge --larger 1GB                   # Large files
gofile-uploader purge --interactive                  # Select files to delete
gofile-uploader purge --category Photos --expired    # Combined filters
```

---

## 5. Interactive Mode

Launch: `gofile-uploader interactive` or `gofile-uploader -i`

### Main Menu

```
GoFile Uploader - Interactive Mode

1) Upload files
2) List uploads
3) Search files
4) Delete file
5) Purge files
6) Manage categories
7) Settings
0) Exit

Choice:
```

### Upload Flow (Multi-file)

```
Enter file path(s) or folder: /path/to/videos/

Found 5 files (3.2 GB total):
  1. video1.mp4    (800 MB)
  2. video2.mp4    (1.2 GB)
  3. clip.mp4      (450 MB)
  4. intro.mp4     (120 MB)
  5. outro.mp4     (630 MB)

Category (or press Enter for none): Videos

Upload 5 files (3.2 GB) to 'Videos'? [y/N]: y

[1/5] video1.mp4    [████████████████████] 100%
[2/5] video2.mp4    [████████------] 58% 14.2 MB/s

✓ Uploaded 5 files to 'Videos'
  Folder link: https://gofile.io/d/xyz789
  Expires: 2025-01-18

What next?
1) Upload more  2) Copy folder link  3) List uploads  4) Main menu
```

Supports glob patterns: `/photos/*.jpg`

### List Flow

```
List uploads

Filter by category (or press Enter for all): Videos

NAME                SIZE      EXPIRY        LINK
vacation.mp4        1.2 GB    2025-01-18    gofile.io/d/abc123
clip.mp4            450 MB    2025-01-15    gofile.io/d/def456

2 files (1.6 GB) · Page 1/1

What next?
1) Filter/search  2) Change view  3) Delete file  4) Main menu
```

### Search Flow

```
Search files

Search term: video
Found 3 files matching "video":

NAME                SIZE      EXPIRY        LINK
vacation.mp4        1.2 GB    2025-01-18    gofile.io/d/abc123
video_edit.mp4      2.1 GB    2025-01-20    gofile.io/d/xyz789
home_video.avi      890 MB    EXPIRED       gofile.io/d/old123

What next?
1) New search  2) Delete file  3) Main menu
```

### Delete Flow

```
Delete file

Enter file ID, number, or name: vacation.mp4

Found: vacation.mp4 (1.2 GB) in 'Videos'
  Link: https://gofile.io/d/abc123

Delete this file? [y/N]: y

✓ Deleted vacation.mp4

What next?
1) Delete another  2) List files  3) Main menu
```

### Purge Flow

```
Purge files

1) Purge expired files
2) Purge by date
3) Purge by size
4) Select files to delete
0) Back

Choice: 1

Found 3 expired files (2.4 GB):
  old_backup.zip     890 MB    EXPIRED
  temp_file.dat      1.1 GB    EXPIRED
  draft.pdf          410 MB    EXPIRED

Delete all 3 expired files? [y/N]: y

✓ Deleted 3 files (2.4 GB)
```

### Categories Flow

```
Manage categories

1) List categories
2) Create category
3) Remove category
4) Import categories
5) Export categories
0) Back

Choice: 1

CATEGORY     FILES    SIZE      FOLDER LINK
Videos       12       8.4 GB    gofile.io/d/xyz789
Photos       45       2.1 GB    gofile.io/d/abc123
Work         3        156 MB    gofile.io/d/def456

3 categories (10.6 GB total)
```

---

## 6. Categories Subcommand

```bash
gofile-uploader categories                    # List all categories (default)
gofile-uploader categories list               # Same as above
gofile-uploader categories remove <pattern>   # Remove category (supports wildcards)
gofile-uploader categories import <file>      # Import from file
gofile-uploader categories export <file>      # Export to file
```

### Category List Output

```
CATEGORY     FILES    SIZE      FOLDER LINK
Videos       12       8.4 GB    gofile.io/d/xyz789
Photos       45       2.1 GB    gofile.io/d/abc123
Work         3        156 MB    gofile.io/d/def456

3 categories (10.6 GB total)
```

Shows file count and total size per category (new feature).

### Import/Export Format

Same as existing format for backwards compatibility:
```
name|folder_id|folder_code
Videos|abc123|xyz789
Photos|def456|uvw012
```

---

## 7. Help Text

Grouped options with quick-start section:

```
GoFile Uploader - Upload files to GoFile.io with tracking

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

UPLOAD OPTIONS:
  -c, --category NAME    Assign to category (creates folder)
  -r, --recursive        Include subfolders
  --dry-run              Preview without uploading

FILTER OPTIONS:
  --search TEXT          Filter by filename
  --since DATE           Uploaded after (YYYY-MM-DD)
  --before DATE          Uploaded before (YYYY-MM-DD)
  --larger SIZE          Larger than (e.g., 100MB)
  --smaller SIZE         Smaller than
  --expired              Only expired files
  --expiring             Expiring soon

VIEW OPTIONS:
  --view MODE            simple | detailed | links
  --compact              Dense layout
  --columns COLS         Custom columns
  --sort FIELD           Sort by field
  --order asc|desc       Sort direction

OUTPUT:
  -q, --quiet            Minimal output
  -v, --verbose          More detail
  -vv                    Debug output

Run 'gofile-uploader <command> --help' for command-specific help.
```

---

## 8. Table Display

### Default View (simple)

```
NAME                SIZE      EXPIRY        LINK
vacation.mp4        1.2 GB    2025-01-18    gofile.io/d/abc123
report.pdf          2.4 MB    EXPIRING      gofile.io/d/def456
old_backup.zip      890 MB    EXPIRED       gofile.io/d/ghi789

3 files (2.1 GB) · 1 expired · 1 expiring soon
```

### Detailed View

```
#   NAME            SIZE      CATEGORY   UPLOADED          EXPIRY        LINK
1   vacation.mp4    1.2 GB    Videos     2025-01-05 14:23  2025-01-18    gofile.io/d/abc123
2   report.pdf      2.4 MB    Work       2025-01-07 09:15  EXPIRING      gofile.io/d/def456
3   old_backup.zip  890 MB    Backups    2024-12-28 11:00  EXPIRED       gofile.io/d/ghi789
```

### Links View

```
https://gofile.io/d/abc123
https://gofile.io/d/def456
https://gofile.io/d/ghi789
```

### Color Coding

- **Green:** Date shown (5+ days remaining)
- **Yellow:** `EXPIRING` replaces date (1-4 days remaining)
- **Red:** `EXPIRED` replaces date

### Summary Footer

Every list output includes a summary footer with:

```
3 files (2.1 GB) · 1 expired · 1 expiring soon · Page 1/2
```

Components:
- Total file count and size
- Expired file count (if any)
- Expiring soon count (if any)
- Page info (if paginated)

Suppressed with `-q` / `--quiet`.

### Date Format

All dates use `YYYY-MM-DD` format for clarity.

---

## 9. Verbosity Levels

### `-q` / `--quiet`

Minimal output:

```
gofile-uploader upload video.mp4 -q
https://gofile.io/d/abc123
```

### Default

Current behavior:

```
gofile-uploader upload video.mp4
Uploading video.mp4... [████████████████████] 100% 15.2 MB/s
✓ Uploaded: video.mp4
  Link: https://gofile.io/d/abc123
  Expires: 2025-01-18
```

### `-v` / `--verbose`

More detail:

```
gofile-uploader upload video.mp4 -v
Creating folder 'Unsorted' on GoFile...
  Folder ID: xyz789
Uploading video.mp4 (1.2 GB)...
  Server: store4.gofile.io
  [████████████████████] 100% 15.2 MB/s (1m 23s)
✓ Uploaded: video.mp4
  Link: https://gofile.io/d/abc123
  Category: Unsorted
  Expires: 2025-01-18
```

### `-vv`

Debug output - full request/response details, timing, API calls.

---

## 10. Error Handling

### Approach

- Replace technical stack traces with plain English
- Include actionable suggestions where possible
- Show retry progress visibly

### Retry Feedback

```
Uploading video.mp4...
  ⟳ Retrying (1/3)...
  ⟳ Retrying (2/3)...
  ✓ Uploaded successfully
```

### Implementation

Review actual errors from GoFile API and current exception handling, then write appropriate friendly messages for each real case.

---

## 11. Confirmation Prompts

Before uploads:

```
Upload 12 files (4.7 GB) to 'Videos'? [y/N]:
```

Skip with `--yes` or `-y` flag for scripting.

---

## Implementation Notes

### Backwards Compatibility

- All existing flags (`-lf`, `-df`, `-c`, `-rm`, etc.) must continue to work
- New subcommands are additions, not replacements
- Existing scripts should not break

### Terminal & Output

- Date format is `YYYY-MM-DD` everywhere
- Color output should detect terminal capability (`NO_COLOR` env var, `--no-color` flag)
- Degrade gracefully on non-TTY (pipes, redirects)
- Interactive mode uses simple numbered menus, no TUI libraries required

### Dependencies

- No new required dependencies for core features
- Color support via existing terminal capabilities or lightweight library if needed

### Testing

- Each new subcommand needs CLI argument parsing tests
- Interactive mode needs input/output mocking for tests
- Filter combinations need test coverage

### Version

This design targets version 1.0.0 release.
