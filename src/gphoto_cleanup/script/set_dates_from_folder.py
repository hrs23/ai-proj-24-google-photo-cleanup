#!/usr/bin/env python3
"""
フォルダ名から日時を推定して各種メディアに設定するスクリプト

初回対応: フォルダ名（親ディレクトリ名など）から YYYY-MM-DD / YYYY_MM_DD / YYYYMMDD / YYYY-MM / YYYYMM を検出。
検出できた場合のみ、以下に書き込み（ドライランがデフォルト）:
- JPEG: EXIF DateTimeOriginal/Create/Modify
- PNG: EXIF DateTimeOriginal/Create/Modify + XMP DateCreated
- 動画(MP4/MOV): QuickTime Create/Modify/TrackCreate/MediaCreate + Keys:CreationDate
"""

import re
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

from gphoto_cleanup.lib.common_functions import (
    ScriptBase,
    has_exif_datetime, set_exif_datetime,
    has_png_datetime, set_png_datetime, set_png_xmp_date, set_png_creation_time, set_file_modify_date,
    has_quicktime_datetime, set_quicktime_datetime,
    has_avi_datetime, set_avi_datetime,
)


DATE_PATTERNS = [
    re.compile(r"(?P<y>\d{4})[._\-/](?P<m>\d{2})[._\-/](?P<d>\d{2})"),  # YYYY-MM-DD, YYYY_MM_DD, YYYY.MM.DD
    re.compile(r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})(?!\d)"),   # YYYYMMDD
    re.compile(r"(?P<y>\d{4})[._\-/](?P<m>\d{2})(?!\d)"),                 # YYYY-MM, YYYY_MM, YYYY.MM
    re.compile(r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?!\d)"),                 # YYYYMM
    re.compile(r"(?<!\d)(?P<y>\d{4})(?!\d)"),                              # YYYY (e.g., 'Photos from 2024')
]


class FolderDateInferenceProcessor(ScriptBase):
    def __init__(self):
        super().__init__("フォルダ名から日時を推定して設定（JPEG/PNG/MP4/MOV）", "single")

    def find_media_files(self, directory: str):
        dir_path = Path(directory)
        media_files = []
        for pattern in [
            '*.jpg', '*.jpeg', '*.JPG', '*.JPEG',
            '*.png', '*.PNG',
            '*.heic', '*.HEIC',
            '*.mp4', '*.MP4', '*.mov', '*.MOV', '*.3gp', '*.3GP',
            '*.avi', '*.AVI',
        ]:
            media_files.extend(dir_path.rglob(pattern))
        return [str(f) for f in media_files]

    def infer_date_from_path(self, file_path: Path) -> str:
        """Infer date from the folder names. Returns EXIF-style datetime or empty string.

        Strategy: Walk up parents; return first match with highest specificity (YMD > YM).
        Time portion is set to 00:00:00.
        """
        best = None  # (priority, y, m, d)
        for parent in [file_path.parent, *file_path.parents]:
            name = parent.name
            if not name:
                continue
            for idx, pat in enumerate(DATE_PATTERNS):
                m = pat.search(name)
                if not m:
                    continue
                gd = m.groupdict()
                y = int(gd.get('y'))
                mth = int(gd.get('m') or 1)
                day = int(gd.get('d') or 1)
                # Priority: prefer specificity (YMD > YM > Y)
                has_day = 1 if gd.get('d') else 0
                has_month = 1 if gd.get('m') else 0
                priority = (has_day, has_month, -idx)
                if best is None or priority > best[0]:
                    best = (priority, y, mth, day)
                # Early return on first YMD found
                if has_day:
                    break
            if best and best[0][0] == 1:  # already have YMD
                break
        if not best:
            return ""
        _, y, mth, day = best
        try:
            dt = datetime(y, mth, day, 0, 0, 0)
        except ValueError:
            return ""
        return dt.strftime("%Y:%m:%d %H:%M:%S")

    def process_file(self, media_file: str) -> None:
        p = Path(media_file)
        datetime_str = self.infer_date_from_path(p)
        if not datetime_str:
            return

        suffix = p.suffix.lower()
        if suffix in ('.jpg', '.jpeg', '.heic'):
            if has_exif_datetime(media_file):
                return
            if not self.dry_run:
                ok = set_exif_datetime(media_file, datetime_str)
                if ok:
                    print(f"推定日時を設定: {p.name} -> {datetime_str}")
                else:
                    print(f"推定日時 設定失敗: {p.name}")
            else:
                print(f"推定日時（確認）: {p.name} -> {datetime_str}")
        elif suffix == '.png':
            if has_png_datetime(media_file):
                return
            if not self.dry_run:
                ok = set_png_datetime(media_file, datetime_str)
                if ok:
                    print(f"推定日時を設定(PNG): {p.name} -> {datetime_str}")
                else:
                    # Fallback 1: XMP only
                    if set_png_xmp_date(media_file, datetime_str):
                        print(f"推定日時を設定(PNG XMPのみ): {p.name} -> {datetime_str}")
                    # Fallback 2: PNG:CreationTime (legacy)
                    elif set_png_creation_time(media_file, datetime_str):
                        print(f"推定日時を設定(PNG CreationTime): {p.name} -> {datetime_str}")
                    # Fallback 3: FileModifyDate for Amazon Photos ordering
                    elif set_file_modify_date(media_file, datetime_str):
                        print(f"推定日時をFileModifyDateに設定(PNG fallback): {p.name} -> {datetime_str}")
                    else:
                        print(f"推定日時 設定失敗(PNG): {p.name}")
            else:
                print(f"推定日時（確認 PNG）: {p.name} -> {datetime_str}")
        elif suffix in ('.mp4', '.mov', '.3gp'):
            if has_quicktime_datetime(media_file):
                return
            if not self.dry_run:
                ok = set_quicktime_datetime(media_file, datetime_str)
                if ok:
                    print(f"推定日時を設定(動画): {p.name} -> {datetime_str}")
                else:
                    print(f"推定日時 設定失敗(動画): {p.name}")
            else:
                print(f"推定日時（確認 動画）: {p.name} -> {datetime_str}")
        elif suffix == '.avi':
            if has_avi_datetime(media_file):
                return
            if not self.dry_run:
                ok = set_avi_datetime(media_file, datetime_str)
                if ok:
                    print(f"推定日時を設定(AVI): {p.name} -> {datetime_str}")
                else:
                    print(f"推定日時 設定失敗(AVI): {p.name}")
            else:
                print(f"推定日時（確認 AVI）: {p.name} -> {datetime_str}")

    def run(self):
        directory = self.parse_single_dir_args()
        self.validate_directory(directory)
        self.print_mode_info(directory=directory)
        self.setup_parallel_processing()

        files = self.find_media_files(directory)
        if not files:
            print("対象ファイルが見つかりませんでした。")
            return

        Executor = ThreadPoolExecutor if self.executor_type == 'thread' else ProcessPoolExecutor
        try:
            with Executor(max_workers=self.parallel_jobs) as ex:
                futures = [ex.submit(self.process_file, f) for f in files]
                for fut in as_completed(futures):
                    try:
                        fut.result()
                    except Exception as e:
                        print(f"Error processing file: {e}")
        except PermissionError:
            print("Permission error on process-based executor. Falling back to threads.")
            self.executor_type = 'thread'
            return self.run()


def main():
    FolderDateInferenceProcessor().run()


if __name__ == "__main__":
    main()


# -------------------------
# Unit tests (co-located)
# -------------------------
import tempfile as _tempfile
import unittest as _unittest
from unittest.mock import patch as _patch


class TestFolderDateInferenceProcessor(_unittest.TestCase):
    def setUp(self):
        self.proc = FolderDateInferenceProcessor()
        self.tmp = Path(_tempfile.mkdtemp())

    def tearDown(self):
        import shutil as _shutil
        _shutil.rmtree(self.tmp, ignore_errors=True)

    def test_infer_date_from_path_patterns(self):
        for folder in ["2016-10-12", "2016_10_12", "20161012", "2016-10", "201610"]:
            p = self.tmp / folder / "a.jpg"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x")
            s = self.proc.infer_date_from_path(p)
            self.assertRegex(s, r"^2016:10:\d{2} 00:00:00$")

    def test_infer_year_only_and_phrases(self):
        # Pure year
        p1 = self.tmp / "2016" / "a.jpg"
        p1.parent.mkdir(parents=True, exist_ok=True)
        p1.write_bytes(b"x")
        s1 = self.proc.infer_date_from_path(p1)
        self.assertEqual(s1, "2016:01:01 00:00:00")

        # Phrase with year, e.g., 'Photos from 2024'
        p2 = self.tmp / "Photos from 2024" / "b.png"
        p2.parent.mkdir(parents=True, exist_ok=True)
        p2.write_bytes(b"x")
        s2 = self.proc.infer_date_from_path(p2)
        self.assertEqual(s2, "2024:01:01 00:00:00")

    @_patch('gphoto_cleanup.script.set_dates_from_folder.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_exif_datetime')
    def test_sets_for_jpeg_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        p = self.tmp / "2016-10-12" / "b.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        self.proc.dry_run = False
        self.proc.process_file(str(p))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_dates_from_folder.has_png_datetime')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_png_datetime')
    def test_sets_for_png_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        p = self.tmp / "2016_10" / "c.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        self.proc.dry_run = False
        self.proc.process_file(str(p))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_file_modify_date')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_png_creation_time')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_png_xmp_date')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_png_datetime')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.has_png_datetime')
    def test_png_fallback_chain(self, mock_has, mock_exif, mock_xmp, mock_ctime, mock_mtime):
        mock_has.return_value = False
        mock_exif.return_value = False
        mock_xmp.return_value = False
        mock_ctime.return_value = False
        mock_mtime.return_value = True
        p = self.tmp / "2016" / "g.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        self.proc.dry_run = False
        self.proc.process_file(str(p))
        self.assertTrue(mock_mtime.called)

    @_patch('gphoto_cleanup.script.set_dates_from_folder.has_quicktime_datetime')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_quicktime_datetime')
    def test_sets_for_video_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        p = self.tmp / "201610" / "d.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        self.proc.dry_run = False
        self.proc.process_file(str(p))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_dates_from_folder.has_quicktime_datetime')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_quicktime_datetime')
    def test_sets_for_3gp_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        p = self.tmp / "201610" / "e.3gp"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        self.proc.dry_run = False
        self.proc.process_file(str(p))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_dates_from_folder.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_dates_from_folder.set_exif_datetime')
    def test_sets_for_heic_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        p = self.tmp / "2016" / "f.heic"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        self.proc.dry_run = False
        self.proc.process_file(str(p))
        self.assertTrue(mock_set.called)
