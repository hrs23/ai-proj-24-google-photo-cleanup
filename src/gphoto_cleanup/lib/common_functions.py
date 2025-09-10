#!/usr/bin/env python3
"""
Common functions library for Google Photos cleanup scripts
Import this module in other scripts to use shared functionality
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from typing import Tuple, Optional


class ScriptBase:
    """Base class for Google Photos cleanup scripts"""
    
    def __init__(self, description: str, script_type: str = "single"):
        """
        Initialize script base
        
        Args:
            description: Description of the script functionality
            script_type: Either "single" (one directory) or "dual" (input/output directories)
        """
        self.description = description
        self.script_type = script_type
        self.dry_run = True
        self.parallel_jobs = os.cpu_count()
        self.executor_type = "thread"  # default to threads (good for I/O-bound exiftool)
        
    def parse_single_dir_args(self) -> str:
        """Parse command line arguments for single directory scripts"""
        parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="⚠️  デフォルトは安全のためdry-runモードです"
        )
        
        parser.add_argument(
            '--execute',
            action='store_true',
            help='実際に変更を実行（デフォルトはdry-runモード）'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Dry-run mode (now the default - use --execute to actually run)'
        )

        parser.add_argument(
            '--jobs', '-j', type=int, default=None,
            help='並列ジョブ数（デフォルト: CPUコア数）'
        )
        parser.add_argument(
            '--executor', choices=['thread', 'process'], default=None,
            help='並列実行方式（デフォルト: thread）'
        )
        
        parser.add_argument(
            'directory',
            help='処理対象ディレクトリ'
        )
        
        args = parser.parse_args()
        
        if args.dry_run:
            print("⚠️  --dry-run is now the default behavior. Use --execute to actually run.")

        self.dry_run = not args.execute
        if args.jobs:
            self.parallel_jobs = max(1, args.jobs)
        if args.executor:
            self.executor_type = args.executor
        return args.directory
    
    def parse_dual_dir_args(self) -> Tuple[str, str]:
        """Parse command line arguments for dual directory scripts"""
        parser = argparse.ArgumentParser(
            description=self.description,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="⚠️  デフォルトは安全のためdry-runモードです"
        )
        
        parser.add_argument(
            '--execute',
            action='store_true',
            help='実際に移動を実行（デフォルトはdry-runモード）'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Dry-run mode (now the default - use --execute to actually run)'
        )

        parser.add_argument(
            '--jobs', '-j', type=int, default=None,
            help='並列ジョブ数（デフォルト: CPUコア数）'
        )
        parser.add_argument(
            '--executor', choices=['thread', 'process'], default=None,
            help='並列実行方式（デフォルト: thread）'
        )
        
        parser.add_argument(
            'input_dir',
            help='検索対象ディレクトリ'
        )
        
        parser.add_argument(
            'output_dir',
            help='移動先ディレクトリ'
        )
        
        args = parser.parse_args()
        
        if args.dry_run:
            print("⚠️  --dry-run is now the default behavior. Use --execute to actually run.")

        self.dry_run = not args.execute
        if args.jobs:
            self.parallel_jobs = max(1, args.jobs)
        if args.executor:
            self.executor_type = args.executor
        return str(Path(args.input_dir).resolve()), str(Path(args.output_dir).resolve())
    
    def validate_directory(self, directory: str) -> None:
        """Validate that a directory exists"""
        if not Path(directory).is_dir():
            print(f"Error: Directory '{directory}' does not exist")
            sys.exit(1)
    
    def get_mode_string(self) -> str:
        """Get mode string for display"""
        return "test" if self.dry_run else "fix"
    
    def setup_parallel_processing(self) -> None:
        """Setup parallel processing and display info"""
        unit = 'workers'
        print(f"並列処理: {self.parallel_jobs}{unit} ({self.executor_type})")
        print()
    
    def print_mode_info(self, directory: Optional[str] = None, 
                       input_dir: Optional[str] = None, 
                       output_dir: Optional[str] = None) -> None:
        """Print mode and directory information"""
        mode = self.get_mode_string()
        
        print(f"=== {self.description} ===")
        print(f"Mode: {mode}")
        
        if directory:
            print(f"Directory: {directory}")
        elif input_dir and output_dir:
            print(f"Input: {input_dir}")
            print(f"Output: {output_dir}")
            
        print("=" * 40)
        print()


def calculate_jpeg_stats(directory: str) -> Tuple[int, int]:
    """Calculate JPEG statistics for a directory"""
    dir_path = Path(directory)
    
    # Find all JPEG files
    jpeg_files = []
    for pattern in ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG']:
        jpeg_files.extend(dir_path.rglob(pattern))
    
    total_jpg = len(jpeg_files)
    
    # Count files with EXIF DateTimeOriginal
    with_exif = 0
    for jpeg_file in jpeg_files:
        try:
            result = subprocess.run(
                ['exiftool', '-DateTimeOriginal', str(jpeg_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if 'Date/Time Original' in result.stdout:
                with_exif += 1
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            # Skip files that cause errors or if exiftool is not available
            continue
    
    return total_jpg, with_exif


def display_jpeg_stats(total_jpg: int, with_exif: int) -> None:
    """Display standard JPEG statistics"""
    print("=== 処理結果 ===")
    print(f"総JPEGファイル数: {total_jpg}")
    print(f"EXIF日時設定済み: {with_exif}")
    print(f"EXIF未設定: {total_jpg - with_exif}")
    print("=" * 40)


def has_exif_datetime(filepath: str) -> bool:
    """Check if a file has EXIF DateTimeOriginal"""
    try:
        result = subprocess.run(
            ['exiftool', '-DateTimeOriginal', filepath],
            capture_output=True,
            text=True,
            timeout=10
        )
        return 'Date/Time Original' in result.stdout
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def set_exif_datetime(filepath: str, datetime_str: str) -> bool:
    """Set EXIF datetime for a file"""
    try:
        result = subprocess.run([
            'exiftool',
            f'-DateTimeOriginal={datetime_str}',
            f'-CreateDate={datetime_str}',
            f'-ModifyDate={datetime_str}',
            '-overwrite_original',
            filepath
        ], capture_output=True, text=True, timeout=30)
        
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_file_type(filepath: str) -> str:
    """Get file type using file command"""
    try:
        result = subprocess.run(
            ['file', '-b', filepath],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return ""


def has_quicktime_datetime(filepath: str) -> bool:
    """Check if a video has any QuickTime date (CreateDate/TrackCreateDate/MediaCreateDate)."""
    try:
        result = subprocess.run(
            ['exiftool', filepath, '-CreateDate', '-TrackCreateDate', '-MediaCreateDate', '-s', '-s', '-s'],
            capture_output=True,
            text=True,
            timeout=10
        )
        for line in result.stdout.strip().split('\n'):
            if line and line[0].isdigit():
                return True
        return False
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def set_quicktime_datetime(filepath: str, datetime_str: str) -> bool:
    """Set QuickTime datetime fields for a video file.

    Writes common fields used by cloud services to sort videos.
    """
    try:
        result = subprocess.run([
            'exiftool',
            f'-CreateDate={datetime_str}',
            f'-ModifyDate={datetime_str}',
            f'-TrackCreateDate={datetime_str}',
            f'-MediaCreateDate={datetime_str}',
            f'-Keys:CreationDate={datetime_str}',
            '-overwrite_original',
            filepath
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def has_avi_datetime(filepath: str) -> bool:
    """Check if an AVI has any recognizable date (DateTimeOriginal/CreateDate)."""
    try:
        result = subprocess.run(
            ['exiftool', filepath, '-DateTimeOriginal', '-CreateDate', '-s', '-s', '-s'],
            capture_output=True,
            text=True,
            timeout=10
        )
        for line in result.stdout.strip().split('\n'):
            if line and line[0].isdigit():
                return True
        return False
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def set_avi_datetime(filepath: str, datetime_str: str) -> bool:
    """Set datetime for AVI (RIFF) containers using generic tags."""
    try:
        result = subprocess.run([
            'exiftool',
            f'-DateTimeOriginal={datetime_str}',
            f'-CreateDate={datetime_str}',
            f'-ModifyDate={datetime_str}',
            '-overwrite_original',
            filepath
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def set_file_modify_date(filepath: str, datetime_str: str) -> bool:
    """Set filesystem modify time via ExifTool (FileModifyDate).

    Many services (including Amazon Photos) fall back to mtime when metadata is missing.
    """
    try:
        result = subprocess.run([
            'exiftool',
            f'-FileModifyDate={datetime_str}',
            '-overwrite_original',
            filepath
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False

def has_png_datetime(filepath: str) -> bool:
    """Check if a PNG has any recognizable date in EXIF or XMP.

    Looks at EXIF:DateTimeOriginal / EXIF:CreateDate / XMP:DateCreated
    """
    try:
        result = subprocess.run(
            ['exiftool', filepath, '-DateTimeOriginal', '-CreateDate', '-XMP:DateCreated', '-s', '-s', '-s'],
            capture_output=True,
            text=True,
            timeout=10
        )
        for line in result.stdout.strip().split('\n'):
            if line and line[0].isdigit():
                return True
        return False
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def set_png_datetime(filepath: str, datetime_str: str) -> bool:
    """Set PNG datetime to both EXIF and XMP for better compatibility."""
    try:
        result = subprocess.run([
            'exiftool',
            f'-EXIF:DateTimeOriginal={datetime_str}',
            f'-EXIF:CreateDate={datetime_str}',
            f'-EXIF:ModifyDate={datetime_str}',
            f'-XMP:DateCreated={datetime_str}',
            '-overwrite_original',
            filepath
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def set_png_xmp_date(filepath: str, datetime_str: str) -> bool:
    """Set only XMP:DateCreated for PNG (some files reject EXIF eXIf chunk)."""
    try:
        result = subprocess.run([
            'exiftool',
            f'-XMP:DateCreated={datetime_str}',
            '-overwrite_original',
            filepath
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def set_png_creation_time(filepath: str, datetime_str: str) -> bool:
    """Set PNG:CreationTime (legacy text chunk)."""
    try:
        result = subprocess.run([
            'exiftool',
            f'-PNG:CreationTime={datetime_str}',
            '-overwrite_original',
            filepath
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False
