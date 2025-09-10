# Google Photos Takeout Cleanup (Simplified)

Process Google Photos Takeout data with safe commands.

## 🎯 Capabilities
- 📝 Fill dates from Google metadata (JPEG/PNG/HEIC/MP4/MOV/3GP/AVI)
- 🧭 Infer dates from folder names (JPEG/PNG/HEIC/MP4/MOV/3GP/AVI)
- 📁 Move files that already have EXIF/QuickTime/XMP timestamps (photos/TIFF/PNG/HEIC/videos incl. 3GP/AVI)

## ⚙️ Environment
- Requires `python3` and `exiftool`
- Run from project root with `PYTHONPATH=src` (or add `src` to `PYTHONPATH` in your shell profile)

```bash
# Example: make src importable for module execution
export PYTHONPATH=src
```

## 🚀 Common Workflows

- Recommended (Set then Move):
  - Set dates (JPEG/PNG/HEIC/MP4/MOV/3GP/AVI): `PYTHONPATH=src python3 -m gphoto_cleanup.script.set_exif_from_metadata <input_dir>`
  - If some files still lack dates, infer from folder names: `PYTHONPATH=src python3 -m gphoto_cleanup.script.set_dates_from_folder <input_dir>`
  - Move (photos/TIFF/PNG/videos): `PYTHONPATH=src python3 -m gphoto_cleanup.script.move_with_exif <input_dir> <output_dir>`

- Preview Move first (dry-run default):
  - `PYTHONPATH=src python3 -m gphoto_cleanup.script.move_with_exif "Photos from 2012" "checked 2012"`
  - Review the count and duplicates summary, then actually move with `--execute` if OK:
    - `PYTHONPATH=src python3 -m gphoto_cleanup.script.move_with_exif --execute "Photos from 2012" "checked 2012"`
  - If some files lack EXIF timestamps, fill from metadata afterwards:
    - `PYTHONPATH=src python3 -m gphoto_cleanup.script.set_exif_from_metadata "Photos from 2012" --execute`
  - Dry-run output shows: 移動対象 (movable), 重複 (duplicates), 未移動 (not moved)

All commands default to dry-run. Add `--execute` to actually write/move.

## 🛡️ Safety
- Dry-run by default; explicit `--execute` required
- Parallel capable (may fall back to serial in constrained environments)
- Always work on a backup

## 📦 対応フォーマットと更新フィールド

現行コマンドが扱うフォーマットと、読み書きするメタデータ項目の一覧です。

| コマンド | 目的 | 対象フォーマット | 参照/更新フィールド | 値の由来 | 備考 |
|---|---|---|---|---|---|
| `set_exif_from_metadata` | JSONから日時をまとめて書き込み | JPEG/PNG/HEIC/MP4/MOV/3GP/AVI | 書き込み: JPEG/HEIC→`EXIF:DateTimeOriginal/Create/Modify`、PNG→`EXIF:DateTimeOriginal/Create/Modify`+`XMP:DateCreated`、MP4/MOV/3GP→`QuickTime:Create/Modify/TrackCreate/MediaCreate`+`Keys:CreationDate`、AVI→`DateTimeOriginal/Create/Modify`（不可の場合は `FileModifyDate` にフォールバック） | Google Takeout の `<元ファイル>.json` / `<元ファイルのstem>.json` および `<元ファイル>.supp* .json`（例: .json, stem.json, supplemental-metadata.json, supplemental.json, supplemental-m.json, supplemental-.json など）内 `photoTakenTime.timestamp` | デフォルトはドライラン |
| `set_dates_from_folder` | フォルダ名から日時を推定して書き込み | JPEG/PNG/HEIC/MP4/MOV/3GP/AVI | 書き込み: JPEG/HEIC→`EXIF:DateTimeOriginal/Create/Modify`、PNG→`EXIF:DateTimeOriginal/Create/Modify`+`XMP:DateCreated`、MP4/MOV/3GP→`QuickTime:Create/Modify/TrackCreate/MediaCreate`+`Keys:CreationDate`、AVI→`DateTimeOriginal/Create/Modify` | フォルダ名（例: `YYYY-MM-DD`, `YYYY_MM_DD`, `YYYYMMDD`, `YYYY-MM`, `YYYYMM`, `YYYY`, `Photos from 2024` など）を解析 | 将来的にファイル名タイムスタンプにも対応予定 |
| `move_with_exif` | EXIF/QuickTime/XMP日時があるファイルのみを移動 | JPEG/TIFF/PNG/HEIC/MP4/MOV/3GP/AVI | 判定: `EXIF:DateTimeOriginal` / `EXIF:CreateDate` / `XMP:DateCreated`（PNG/AVI は `FileModifyDate` も可） | — | 判定に使うだけで書き込みはしない |

注意:
- まず `set_exif_from_metadata` でJSONから日時を付与し、不足分は `set_dates_from_folder` で補完してから `move_with_exif` を実行してください。
