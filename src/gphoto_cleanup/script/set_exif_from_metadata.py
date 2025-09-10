#!/usr/bin/env python3
"""
JSONメタデータから日時設定スクリプト（統合）
GoogleフォトのJSONメタデータから各種メディアの日時を設定

対応:
- JPEG: EXIF DateTimeOriginal/Create/Modify
- PNG: EXIF DateTimeOriginal/Create/Modify + XMP DateCreated
- 動画(MP4/MOV): QuickTime Create/Modify/TrackCreate/MediaCreate + Keys:CreationDate
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

from gphoto_cleanup.lib.common_functions import (
    ScriptBase,
    calculate_jpeg_stats, display_jpeg_stats,
    has_exif_datetime, set_exif_datetime,
    has_quicktime_datetime, set_quicktime_datetime,
    has_png_datetime, set_png_datetime,
    has_avi_datetime, set_avi_datetime, set_file_modify_date,
)


class JSONMetadataProcessor(ScriptBase):
    """JSON metadata to date processor (unified for JPEG/PNG/MP4/MOV)"""

    def __init__(self):
        super().__init__("GoogleフォトのJSONメタデータから日時を設定（JPEG/PNG/HEIC/MP4/MOV/3GP/AVI）", "single")

    def find_media_files(self, directory: str):
        """Find all supported media files in directory"""
        dir_path = Path(directory)
        media_files = []

        for pattern in ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG',
                        '*.png', '*.PNG',
                        '*.heic', '*.HEIC',
                        '*.mp4', '*.MP4', '*.mov', '*.MOV', '*.3gp', '*.3GP',
                        '*.avi', '*.AVI']:
            media_files.extend(dir_path.rglob(pattern))
        
        return [str(f) for f in media_files]

    def extract_timestamp_from_json(self, json_file_path: str) -> str:
        """Extract photoTakenTime timestamp from JSON metadata"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Navigate to photoTakenTime.timestamp
            if 'photoTakenTime' in data and 'timestamp' in data['photoTakenTime']:
                timestamp = data['photoTakenTime']['timestamp']
                
                # Convert Unix timestamp to EXIF format
                dt = datetime.fromtimestamp(int(timestamp))
                return dt.strftime("%Y:%m:%d %H:%M:%S")
            
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            # Silent failure for malformed JSON or missing keys
            pass
        
        return ""
    
    def _find_sidecar_for(self, media_path: Path) -> str:
        """Return sidecar JSON path if found, else empty string.

        Generalized detection:
        - <file>.supplemental*.json (includes parentheses, truncated variants)
        - <file>.supp*.json (broadened), but validated by JSON keys
        Validation: must contain 'photoTakenTime' or 'creationTime'.
        """
        candidates = []
        # Known common patterns
        for name in [
            f"{media_path.name}.supplemental-metadata.json",
            f"{media_path.name}.supplemental-m.json",
            f"{media_path.name}.supplemental.json",
            f"{media_path.name}.json",
            f"{media_path.stem}.json",
        ]:
            p = media_path.parent / name
            if p.exists():
                candidates.append(p)

        # Broad patterns (validated later by JSON content)
        candidates.extend(sorted(media_path.parent.glob(f"{media_path.name}.supplemental*json")))
        candidates.extend(sorted(media_path.parent.glob(f"{media_path.name}.supp*json")))

        seen = set()
        for cand in candidates:
            if cand in seen:
                continue
            seen.add(cand)
            try:
                with open(cand, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict) and (
                    'photoTakenTime' in data or 'creationTime' in data
                ):
                    return str(cand)
            except (OSError, json.JSONDecodeError):
                # skip invalid/unreadable
                continue
        return ""

    def process_json_metadata(self, media_file: str) -> None:
        """Process JSON metadata for a single media file (type-aware)"""
        media_path = Path(media_file)
        json_file_path = self._find_sidecar_for(media_path)

        if not json_file_path:
            return

        datetime_str = self.extract_timestamp_from_json(json_file_path)
        if not datetime_str:
            return

        suffix = media_path.suffix.lower()
        if suffix in ('.jpg', '.jpeg', '.heic'):
            if has_exif_datetime(media_file):
                print(f"JSON metadata found but EXIF already set: {media_file}")
                return
            print(f"JSON metadata found: {media_file}")
            if not self.dry_run:
                success = set_exif_datetime(media_file, datetime_str)
                if success:
                    print(f"  → Set EXIF date to: {datetime_str} (from JSON)")
                else:
                    print(f"  → Failed to set EXIF date from JSON")
            else:
                print(f"  → Would set EXIF date to: {datetime_str} (from JSON)")

        elif suffix == '.png':
            if has_png_datetime(media_file):
                print(f"JSON metadata found but PNG date already set: {media_file}")
                return
            print(f"JSON metadata found: {media_file}")
            if not self.dry_run:
                success = set_png_datetime(media_file, datetime_str)
                if success:
                    print(f"  → Set PNG EXIF/XMP date to: {datetime_str} (from JSON)")
                else:
                    print(f"  → Failed to set PNG date from JSON")
            else:
                print(f"  → Would set PNG EXIF/XMP date to: {datetime_str} (from JSON)")

        elif suffix in ('.mp4', '.mov', '.3gp'):
            if has_quicktime_datetime(media_file):
                print(f"JSON metadata found but QuickTime date already set: {media_file}")
                return
            print(f"JSON metadata found: {media_file}")
            if not self.dry_run:
                success = set_quicktime_datetime(media_file, datetime_str)
                if success:
                    print(f"  → Set QuickTime dates to: {datetime_str} (from JSON)")
                else:
                    print(f"  → Failed to set QuickTime dates from JSON")
            else:
                print(f"  → Would set QuickTime dates to: {datetime_str} (from JSON)")
        elif suffix == '.avi':
            if has_avi_datetime(media_file):
                print(f"JSON metadata found but AVI date already set: {media_file}")
                return
            print(f"JSON metadata found: {media_file}")
            if not self.dry_run:
                success = set_avi_datetime(media_file, datetime_str)
                if success:
                    print(f"  → Set AVI dates to: {datetime_str} (from JSON)")
                else:
                    # Fallback for Amazon Photos ordering when container tags unsupported
                    if set_file_modify_date(media_file, datetime_str):
                        print(f"  → Set FileModifyDate to: {datetime_str} (fallback for Amazon Photos)")
                    else:
                        print(f"  → Failed to set AVI dates from JSON (and fallback)")
            else:
                print(f"  → Would set AVI dates to: {datetime_str} (from JSON); fallback would set FileModifyDate if needed")
        else:
            # Unsupported extension: ignore silently
            return
    
    def count_json_files(self, directory: str) -> int:
        """Count JSON metadata files in directory"""
        dir_path = Path(directory)
        json_files = list(dir_path.rglob("*.supplemental-metadata.json"))
        return len(json_files)
    
    def run(self):
        """Main execution function"""
        # Parse arguments
        directory = self.parse_single_dir_args()
        
        # Validate directory
        self.validate_directory(directory)
        
        # Display script info
        self.print_mode_info(directory=directory)
        
        # Setup parallel processing
        self.setup_parallel_processing()
        
        # Find all supported media files
        media_files = self.find_media_files(directory)

        if media_files:
            Executor = ThreadPoolExecutor if self.executor_type == 'thread' else ProcessPoolExecutor
            try:
                with Executor(max_workers=self.parallel_jobs) as executor:
                    futures = [executor.submit(self.process_json_metadata, filepath) for filepath in media_files]
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            print(f"Error processing file: {e}")
            except PermissionError:
                print("Permission error on process-based executor. Falling back to threads.")
                self.executor_type = 'thread'
                return self.run()

        print("JSON処理完了")
        print()
        
        # Display simple statistics (keep JPEG stats for continuity)
        print("=== 処理結果 ===")
        total_jpg, with_exif = calculate_jpeg_stats(directory)
        print(f"総JPEGファイル数: {total_jpg}")
        print(f"EXIF日時設定済み: {with_exif}")
        print(f"EXIF未設定: {total_jpg - with_exif}")
        print("=" * 40)


def main():
    """Main entry point"""
    processor = JSONMetadataProcessor()
    processor.run()


if __name__ == "__main__":
    main()
    
    
# -------------------------
# Unit tests (co-located)
# -------------------------
import json as _json
import tempfile as _tempfile
import unittest as _unittest
from unittest.mock import patch as _patch


class TestJSONMetadataProcessor(_unittest.TestCase):
    def setUp(self):
        self.proc = JSONMetadataProcessor()
        self.temp_dir = Path(_tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_media_with_json(self, name: str, ts: int) -> Path:
        media = self.temp_dir / name
        media.write_bytes(b"dummy")
        meta = self.temp_dir / f"{name}.supplemental-metadata.json"
        meta.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": str(ts)}
        }), encoding='utf-8')
        return media

    def test_extract_timestamp_from_json_success(self):
        meta = self.temp_dir / "a.jpg.supplemental-metadata.json"
        meta.write_text(_json.dumps({"photoTakenTime": {"timestamp": "1700000000"}}))

        ts = self.proc.extract_timestamp_from_json(str(meta))
        self.assertRegex(ts, r"^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$")

    def test_extract_timestamp_from_json_malformed(self):
        meta = self.temp_dir / "b.jpg.supplemental-metadata.json"
        meta.write_text("{not: json}")

        ts = self.proc.extract_timestamp_from_json(str(meta))
        self.assertEqual(ts, "")

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_exif_datetime')
    def test_process_json_metadata_sets_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True

        media = self.create_media_with_json("img.jpg", 1700000000)
        self.proc.dry_run = False

        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_exif_datetime')
    def test_process_json_metadata_skips_when_existing(self, mock_set, mock_has):
        mock_has.return_value = True
        media = self.create_media_with_json("img2.jpg", 1700000000)

        self.proc.process_json_metadata(str(media))
        self.assertFalse(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_exif_datetime')
    def test_supports_supplemental_m_json_naming(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True

        # Create a JPEG with sidecar named .supplemental-m.json
        media = self.temp_dir / "aviary-image-1475859169506.jpeg"
        media.write_bytes(b"dummy")
        sidecar = self.temp_dir / "aviary-image-1475859169506.jpeg.supplemental-m.json"
        sidecar.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": "1475859169"}
        }), encoding='utf-8')

        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_exif_datetime')
    def test_supports_plain_json_sidecar(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True

        media = self.temp_dir / "0-02-06-0b21a076c351127f0eb7c1d8bbde0bc7ea2f486.jpg"
        media.write_bytes(b"dummy")
        sidecar = self.temp_dir / "0-02-06-0b21a076c351127f0eb7c1d8bbde0bc7ea2f486.jpg.json"
        sidecar.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": "1486339200"}
        }), encoding='utf-8')

        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_exif_datetime')
    def test_supports_stem_json_sidecar(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True

        media = self.temp_dir / "0-02-06-abc.jpg"
        media.write_bytes(b"dummy")
        # sidecar without extension segment: <stem>.json
        sidecar = self.temp_dir / "0-02-06-abc.json"
        sidecar.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": "1486339200"}
        }), encoding='utf-8')

        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_exif_datetime')
    def test_supports_supplemental_dash_json_naming(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True

        media = self.temp_dir / "yauction_2016-10-12_22.40.06.jpg"
        media.write_bytes(b"dummy")
        sidecar = self.temp_dir / "yauction_2016-10-12_22.40.06.jpg.supplemental-.json"
        sidecar.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": "1476292806"}
        }), encoding='utf-8')

        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_png_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_png_datetime')
    def test_supports_supp_json_naming_with_validation(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True

        media = self.temp_dir / "Screen Shot 2016-09-30 at 11.47.01 AM.png"
        media.write_bytes(b"dummy")
        # This should be detected via the broad pattern and validated by keys
        sidecar = self.temp_dir / "Screen Shot 2016-09-30 at 11.47.01 AM.png.supp.json"
        sidecar.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": "1475226421"}
        }), encoding='utf-8')

        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)


class TestQuickTimeMetadataProcessor(_unittest.TestCase):
    def setUp(self):
        self.proc = JSONMetadataProcessor()
        self.temp_dir = Path(_tempfile.mkdtemp())

    def tearDown(self):
        import shutil as _shutil
        _shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_media_with_json(self, name: str, ts: int) -> Path:
        media = self.temp_dir / name
        media.write_bytes(b"dummy")
        meta = self.temp_dir / f"{name}.supplemental-metadata.json"
        meta.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": str(ts)}
        }), encoding='utf-8')
        return media

    def test_extract_timestamp_from_json_success(self):
        meta = self.temp_dir / "v.mp4.supplemental-metadata.json"
        meta.write_text(_json.dumps({"photoTakenTime": {"timestamp": "1700000000"}}))
        ts = self.proc.extract_timestamp_from_json(str(meta))
        self.assertRegex(ts, r"^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$")

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_quicktime_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_quicktime_datetime')
    def test_process_json_metadata_sets_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True

        media = self.create_media_with_json("clip.mp4", 1700000000)
        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_quicktime_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_quicktime_datetime')
    def test_process_json_metadata_skips_when_existing(self, mock_set, mock_has):
        mock_has.return_value = True
        media = self.create_media_with_json("clip2.mov", 1700000000)
        self.proc.process_json_metadata(str(media))
        self.assertFalse(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_quicktime_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_quicktime_datetime')
    def test_process_json_metadata_sets_for_3gp(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        media = self.create_media_with_json("clip.3gp", 1700000000)
        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)


class TestAVIMetadataProcessor(_unittest.TestCase):
    def setUp(self):
        self.proc = JSONMetadataProcessor()
        self.temp_dir = Path(_tempfile.mkdtemp())

    def tearDown(self):
        import shutil as _shutil
        _shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_media_with_json(self, name: str, ts: int) -> Path:
        media = self.temp_dir / name
        media.write_bytes(b"dummy")
        meta = self.temp_dir / f"{name}.supplemental-metadata.json"
        meta.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": str(ts)}
        }), encoding='utf-8')
        return media

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_avi_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_avi_datetime')
    def test_process_json_metadata_sets_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True

        media = self.create_media_with_json("sample.avi", 1700000000)
        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_avi_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_avi_datetime')
    def test_process_json_metadata_skips_when_existing(self, mock_set, mock_has):
        mock_has.return_value = True
        media = self.create_media_with_json("sample2.avi", 1700000000)
        self.proc.process_json_metadata(str(media))
        self.assertFalse(mock_set.called)

    def test_find_media_files_includes_avi(self):
        avi = self.temp_dir / "x.avi"
        avi.write_bytes(b"dummy")
        files = self.proc.find_media_files(str(self.temp_dir))
        self.assertIn(str(avi), files)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_file_modify_date')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_avi_datetime')
    def test_avi_fallback_sets_file_mtime(self, mock_set_avi, mock_set_mtime):
        mock_set_avi.return_value = False
        mock_set_mtime.return_value = True
        media = self.create_media_with_json("fail.avi", 1700000000)
        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set_mtime.called)

class TestPNGMetadataProcessor(_unittest.TestCase):
    def setUp(self):
        self.proc = JSONMetadataProcessor()
        self.temp_dir = Path(_tempfile.mkdtemp())

    def tearDown(self):
        import shutil as _shutil
        _shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_media_with_json(self, name: str, ts: int) -> Path:
        media = self.temp_dir / name
        media.write_bytes(b"dummy")
        meta = self.temp_dir / f"{name}.supplemental-metadata.json"
        meta.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": str(ts)}
        }), encoding='utf-8')
        return media

    def test_extract_timestamp_from_json_success(self):
        meta = self.temp_dir / "p.png.supplemental-metadata.json"
        meta.write_text(_json.dumps({"photoTakenTime": {"timestamp": "1700000000"}}))
        ts = self.proc.extract_timestamp_from_json(str(meta))
        self.assertRegex(ts, r"^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$")

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_png_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_png_datetime')
    def test_process_json_metadata_sets_when_missing(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        media = self.create_media_with_json("img.png", 1700000000)
        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_png_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_png_datetime')
    def test_process_json_metadata_skips_when_existing(self, mock_set, mock_has):
        mock_has.return_value = True
        media = self.create_media_with_json("img2.png", 1700000000)
        self.proc.process_json_metadata(str(media))
        self.assertFalse(mock_set.called)


class TestHEICMetadataProcessor(_unittest.TestCase):
    def setUp(self):
        self.proc = JSONMetadataProcessor()
        self.temp_dir = Path(_tempfile.mkdtemp())

    def tearDown(self):
        import shutil as _shutil
        _shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_media_with_json(self, name: str, ts: int) -> Path:
        media = self.temp_dir / name
        media.write_bytes(b"dummy")
        meta = self.temp_dir / f"{name}.supplemental-metadata.json"
        meta.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": str(ts)}
        }), encoding='utf-8')
        return media

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_exif_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_exif_datetime')
    def test_sets_for_heic(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        media = self.create_media_with_json("img.heic", 1700000000)
        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)

    @_patch('gphoto_cleanup.script.set_exif_from_metadata.has_png_datetime')
    @_patch('gphoto_cleanup.script.set_exif_from_metadata.set_png_datetime')
    def test_supports_supplemental_json_naming(self, mock_set, mock_has):
        mock_has.return_value = False
        mock_set.return_value = True
        media = self.temp_dir / "caps.png"
        media.write_bytes(b"dummy")
        sidecar = self.temp_dir / "caps.png.supplemental.json"
        sidecar.write_text(_json.dumps({
            "photoTakenTime": {"timestamp": "1700000000"}
        }), encoding='utf-8')
        self.proc.dry_run = False
        self.proc.process_json_metadata(str(media))
        self.assertTrue(mock_set.called)
