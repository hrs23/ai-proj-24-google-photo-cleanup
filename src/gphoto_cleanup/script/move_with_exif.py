#!/usr/bin/env python3
"""
EXIF日時付きファイル（主にJPEG）移動スクリプト
EXIF DateTimeOriginalまたはCreateDateが設定されているファイルを移動
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Set

from gphoto_cleanup.lib.common_functions import ScriptBase


class ExifFileMover(ScriptBase):
    def __init__(self):
        super().__init__("EXIF日時付きファイル（主にJPEG）移動スクリプト", "dual")
    
    def has_exif_date(self, filepath: str) -> bool:
        try:
            suffix = Path(filepath).suffix.lower()
            args = ['exiftool', filepath, '-DateTimeOriginal', '-CreateDate', '-XMP:DateCreated']
            # Allow FileModifyDate as a fallback signal for some types
            if suffix in ('.avi', '.png'):
                args.append('-FileModifyDate')
            args.extend(['-s', '-s', '-s'])
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
            for line in result.stdout.strip().split('\n'):
                if line and line[0].isdigit():
                    return True
            return False
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def find_exif_candidate_files(self, input_dir: str, output_dir: str) -> List[str]:
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        candidate_files = []
        extensions = [
            '*.jpg', '*.jpeg', '*.tiff', '*.tif',
            '*.JPG', '*.JPEG', '*.TIFF', '*.TIF',
            '*.mp4', '*.MP4', '*.mov', '*.MOV',
            '*.png', '*.PNG',
            '*.heic', '*.HEIC',
            '*.3gp', '*.3GP',
            '*.avi', '*.AVI',
        ]
        for ext in extensions:
            for file_path in input_path.rglob(ext):
                try:
                    if not file_path.is_relative_to(output_path):
                        candidate_files.append(str(file_path))
                except ValueError:
                    candidate_files.append(str(file_path))
        return candidate_files
    
    def check_exif_parallel(self, candidate_files: List[str]) -> List[str]:
        print(f"{self.parallel_jobs}並列でEXIF日時チェック開始... ({self.executor_type})")
        valid_files = []
        start_time = time.time()
        Executor = ThreadPoolExecutor if self.executor_type == 'thread' else ProcessPoolExecutor
        try:
            with Executor(max_workers=self.parallel_jobs) as executor:
                future_to_file = {executor.submit(self.has_exif_date, filepath): filepath for filepath in candidate_files}
                processed = 0
                total = len(candidate_files)
                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    processed += 1
                    try:
                        if future.result():
                            valid_files.append(filepath)
                    except Exception as e:
                        print(f"Error checking {filepath}: {e}")
                    if processed % 100 == 0 or processed == total:
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            rate = processed / elapsed
                            print(f"進捗: {len(valid_files)}/{processed} valid files found (" f"{rate:.1f} files/sec, {elapsed:.0f}s経過)")
        except PermissionError:
            print("Permission error on process-based executor. Falling back to threads.")
            self.executor_type = 'thread'
            return self.check_exif_parallel(candidate_files)
        return valid_files
    
    def check_duplicates(self, files_to_move: List[str], output_dir: str) -> Set[str]:
        print("移動先での重複をチェック中...")
        output_path = Path(output_dir)
        duplicates = set()
        for filepath in files_to_move:
            filename = Path(filepath).name
            dest_path = output_path / filename
            if dest_path.exists():
                duplicates.add(filename)
                print(f"重複: {filename}")
        return duplicates
    
    def get_unique_filename(self, output_dir: str, filename: str) -> str:
        output_path = Path(output_dir)
        dest_path = output_path / filename
        if not dest_path.exists():
            return filename
        name = Path(filename).stem
        extension = Path(filename).suffix
        counter = 1
        while dest_path.exists():
            new_filename = f"{name}_{counter}{extension}"
            dest_path = output_path / new_filename
            counter += 1
        return dest_path.name
    
    def move_files(self, files_to_move: List[str], output_dir: str) -> tuple:
        print("ファイル移動を開始...")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        moved = 0
        failed = 0
        for filepath in files_to_move:
            try:
                source_path = Path(filepath)
                original_filename = source_path.name
                unique_filename = self.get_unique_filename(output_dir, original_filename)
                dest_path = output_path / unique_filename
                shutil.move(str(source_path), str(dest_path))
                moved += 1
                if unique_filename != original_filename:
                    print(f"移動: {original_filename} → {unique_filename}")
                else:
                    print(f"移動: {original_filename}")
            except OSError as e:
                failed += 1
                print(f"エラー: 移動失敗 {filepath} - {e}")
        return moved, failed
    
    def run(self):
        input_dir, output_dir = self.parse_dual_dir_args()
        self.validate_directory(input_dir)
        self.print_mode_info(input_dir=input_dir, output_dir=output_dir)
        print("EXIF対応ファイルを検索中...")
        candidate_files = self.find_exif_candidate_files(input_dir, output_dir)
        total_count = len(candidate_files)
        print(f"候補ファイル総数: {total_count}\n")
        if total_count == 0:
            print("移動対象ファイルが見つかりませんでした。")
            return
        files_with_exif = self.check_exif_parallel(candidate_files)
        move_count = len(files_with_exif)
        not_moved_count = total_count - move_count
        print(f"\nEXIF日時付きファイル数: {move_count}")
        if move_count == 0:
            print("EXIF日時が設定されたファイルが見つかりませんでした。")
            print("先にメタデータからEXIFを設定してください:")
            print("  python -m gphoto_cleanup.script.set_exif_from_metadata <input_dir>")
            return
        duplicates = self.check_duplicates(files_with_exif, output_dir)
        duplicate_count = len(duplicates)
        print(f"重複ファイル数: {duplicate_count}")
        if duplicate_count > 0 and not self.dry_run:
            print("\n重複ファイルが存在します。移動時に自動的に連番が付与されます。")
            response = input("続行しますか？ (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("操作をキャンセルしました。")
                return
        if not self.dry_run:
            moved, failed = self.move_files(files_with_exif, output_dir)
            print("\n=== 移動結果 ===")
            print(f"成功: {moved} ファイル")
            print(f"失敗: {failed} ファイル")
            print(f"未移動: {not_moved_count + failed - failed} ファイル")
        else:
            print("\n=== テスト結果 ===")
            print(f"移動対象: {move_count} ファイル")
            print(f"重複: {duplicate_count} ファイル")
            print(f"未移動: {not_moved_count} ファイル")
            print("\n実際に移動するには --execute オプションを追加:")
            print(f"  {sys.argv[0]} --execute {input_dir} {output_dir}")
        print("=" * 40)


def main():
    mover = ExifFileMover()
    mover.run()


if __name__ == "__main__":
    main()


# -------------------------
# Unit tests (co-located)
# -------------------------
import tempfile as _tempfile
import unittest as _unittest
from unittest.mock import patch as _patch


class TestExifFileMover(_unittest.TestCase):
    def setUp(self):
        self.mover = ExifFileMover()
        self.temp_in = Path(_tempfile.mkdtemp())
        self.temp_out = Path(_tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_in, ignore_errors=True)
        shutil.rmtree(self.temp_out, ignore_errors=True)

    def test_get_unique_filename(self):
        existing = self.temp_out / 'photo.jpg'
        existing.write_bytes(b'data')

        unique = self.mover.get_unique_filename(str(self.temp_out), 'photo.jpg')
        _unittest.TestCase().assertNotEqual(unique, 'photo.jpg')
        _unittest.TestCase().assertRegex(unique, r'^photo_\d+\.jpg$')

    def test_check_duplicates(self):
        (self.temp_out / 'dup.jpg').write_bytes(b'x')
        files = [str(self.temp_in / 'a.jpg'), str(self.temp_in / 'dup.jpg')]
        dups = self.mover.check_duplicates(files, str(self.temp_out))
        _unittest.TestCase().assertIn('dup.jpg', dups)

    def test_find_exif_candidate_files_includes_videos(self):
        # Create sample files
        (self.temp_in / 'a.jpg').write_bytes(b'x')
        (self.temp_in / 'b.mp4').write_bytes(b'x')
        (self.temp_in / 'c.MOV').write_bytes(b'x')
        (self.temp_in / 'e.avi').write_bytes(b'x')
        (self.temp_in / 'f.3gp').write_bytes(b'x')
        (self.temp_in / 'g.heic').write_bytes(b'x')

        candidates = self.mover.find_exif_candidate_files(str(self.temp_in), str(self.temp_out))
        names = {Path(p).name for p in candidates}

        _unittest.TestCase().assertIn('a.jpg', names)
        _unittest.TestCase().assertIn('b.mp4', names)
        _unittest.TestCase().assertIn('c.MOV', names)
        _unittest.TestCase().assertIn('e.avi', names)
        _unittest.TestCase().assertIn('f.3gp', names)
        _unittest.TestCase().assertIn('g.heic', names)

    @_patch('subprocess.run')
    def test_has_exif_date_detects_avi_filemodify(self, mock_run):
        class R:
            def __init__(self):
                self.stdout = '2017:12:31 13:43:29\n'
                self.returncode = 0
        mock_run.return_value = R()
        self.assertTrue(self.mover.has_exif_date(str(self.temp_in / 'z.avi')))

    @_patch('subprocess.run')
    def test_has_exif_date_detects_png_filemodify(self, mock_run):
        class R:
            def __init__(self):
                self.stdout = '2020:01:01 00:00:00\n'
                self.returncode = 0
        mock_run.return_value = R()
        self.assertTrue(self.mover.has_exif_date(str(self.temp_in / 'k.png')))

    @_patch('subprocess.run')
    def test_has_exif_date_detects_xmp_date(self, mock_run):
        class R:
            def __init__(self):
                self.stdout = '2020:01:02 03:04:05\n'
                self.returncode = 0
        mock_run.return_value = R()

        self.assertTrue(self.mover.has_exif_date(str(self.temp_in / 'x.png')))

    @_patch('gphoto_cleanup.script.move_with_exif.ExifFileMover.check_duplicates')
    @_patch('gphoto_cleanup.script.move_with_exif.ExifFileMover.check_exif_parallel')
    @_patch('gphoto_cleanup.script.move_with_exif.ExifFileMover.find_exif_candidate_files')
    def test_run_dry_flow(self, mock_find, mock_check_exif, mock_check_dups):
        mock_find.return_value = [str(self.temp_in / 'a.jpg'), str(self.temp_in / 'b.jpg')]
        mock_check_exif.return_value = [str(self.temp_in / 'a.jpg')]
        mock_check_dups.return_value = set()

        self.mover.dry_run = True

        with _patch('sys.argv', ['script.py', str(self.temp_in), str(self.temp_out)]):
            with _patch('builtins.print') as mock_print:
                self.mover.run()
        
        _unittest.TestCase().assertTrue(mock_find.called)
        _unittest.TestCase().assertTrue(mock_check_exif.called)
        _unittest.TestCase().assertTrue(mock_check_dups.called)

        # Verify "未移動: 1 ファイル" was printed (2 candidates - 1 movable)
        printed = "\n".join(" ".join(map(str, c.args)) for c in mock_print.call_args_list)
        self.assertIn("未移動: 1 ファイル", printed)
