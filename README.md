# Google Photos Takeout Cleanup Scripts

A collection of shell scripts to process Google Photos Takeout data, extract timestamps, and organize files by EXIF capability.

## Quick Start

```bash
# Clone the repository
git clone git@github.com:hrs23/ai-proj-24-google-photo-cleanup.git
cd ai-proj-24-google-photo-cleanup

# Make scripts executable (if needed)
chmod +x *.sh

# Process your Google Photos Takeout data
./fix_exif_files.sh takeout
./move_with_exif.sh takeout out
./fix_non_exif_files.sh takeout
./move_without_exif.sh takeout out_nonexif
./remove_duplicates_fast.sh out remove
./remove_duplicates_fast.sh out_nonexif remove
```

## Prerequisites

- `bash` shell
- `exiftool` - Install with `apt install libimage-exiftool-perl` (Ubuntu/Debian) or `brew install exiftool` (macOS)
- Standard Unix utilities: `find`, `grep`, `date`, `file`

## Usage

### 1. JPEG Processing (EXIF-capable files)

```bash
# Fix EXIF data from multiple sources
./fix_exif_files.sh --dry-run takeout    # Preview changes first
./fix_exif_files.sh takeout              # Apply fixes

# Move processed JPEG files
./move_with_exif.sh --dry-run takeout out    # Preview moves
./move_with_exif.sh takeout out              # Move files
```

### 2. Non-EXIF Processing (GIF/PNG/AVI files)

```bash
# Set file timestamps from filename patterns
./fix_non_exif_files.sh --dry-run takeout    # Preview changes
./fix_non_exif_files.sh takeout              # Apply fixes

# Move non-EXIF files
./move_without_exif.sh --dry-run takeout out_nonexif    # Preview moves
./move_without_exif.sh takeout out_nonexif              # Move files
```

### 3. Remove Duplicates

```bash
./remove_duplicates_fast.sh out remove           # Clean EXIF folder
./remove_duplicates_fast.sh out_nonexif remove   # Clean non-EXIF folder
```

## What Each Script Does

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `fix_exif_files.sh` | Fix JPEG files: extension correction, JSON metadata extraction, filename pattern matching | `takeout/` | Files with corrected EXIF data |
| `fix_non_exif_files.sh` | Set timestamps for GIF/PNG/AVI files from filename patterns | `takeout/` | Files with corrected timestamps |
| `move_with_exif.sh` | Move EXIF-capable files to output directory | `takeout/` | `out/` (or custom) |
| `move_without_exif.sh` | Move non-EXIF files to output directory | `takeout/` | `out_nonexif/` (or custom) |
| `remove_duplicates_fast.sh` | Remove duplicate files using MD5 comparison | Any directory | Cleaned directory |

## Supported Patterns

### EXIF Processing (JPEG)
- Extension correction: `.PNG` → `.jpg` when file is actually JPEG
- JSON metadata: `photo.jpg.json` → EXIF DateTimeOriginal
- Filename patterns:
  - `Screenshot_YYYYMMDD-HHMMSS`
  - `BURST20181222131329`
  - Unix timestamps (10/13 digits)
  - `Screen Shot YYYY-MM-DD at H.MM.SS AM/PM`

### Non-EXIF Processing (GIF/PNG/AVI)
- Timestamp patterns:
  - `Screenshot_YYYYMMDD-HHMMSS`
  - `スクリーンショット YYYY-MM-DD HH.MM.SS`
  - `BURST20181222131329`
  - `YYYYMMDDHHMMSS.avi`
  - Unix timestamps
- Folder-based year inference: `Photos from 2019/` → 2019

## Safety Features

- **Dry-run mode**: Use `--dry-run` to preview changes before execution
- **Backup recommended**: Always backup your data before processing
- **Non-destructive**: Files are moved, not copied (preserves disk space)
- **Duplicate handling**: Automatic filename numbering for conflicts
- **Parallel processing**: Utilizes all CPU cores for faster processing

## Directory Structure

```
your-project/
├── takeout/              # Google Photos Takeout data
│   └── Photos from YYYY/ # Year-based folders
├── out/                  # EXIF-processed files (Amazon Photos recognizes dates)
├── out_nonexif/         # Non-EXIF files (sorted by modification time)
└── scripts...           # These processing scripts
```

## Troubleshooting

- **Permission denied**: Run `chmod +x *.sh`
- **exiftool not found**: Install with your package manager
- **No files processed**: Check input directory structure
- **Stuck processing**: Some files may have complex patterns - check logs

## Contributing

Feel free to submit issues and pull requests to improve pattern matching or add new file type support.

## License

This project is provided as-is for personal use. Please backup your data before use.