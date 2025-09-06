# GoogleフォトTakeout整理スクリプト

GoogleフォトのTakeoutデータから撮影日時を抽出してファイルを整理するスクリプト群。

## 🚀 使い方

```bash
# 1. JPEG処理（EXIF対応）
./fix_exif_files.sh --dry-run takeout      # 事前確認
./fix_exif_files.sh takeout                # 実際に実行
./move_with_exif.sh --dry-run takeout out  # 事前確認  
./move_with_exif.sh takeout out             # 実際に移動

# 2. GIF/PNG/AVI処理（EXIF非対応）
./fix_non_exif_files.sh --dry-run takeout        # 事前確認
./fix_non_exif_files.sh takeout                  # 実際に実行
./move_without_exif.sh --dry-run takeout out_nonexif  # 事前確認
./move_without_exif.sh takeout out_nonexif             # 実際に移動

# 3. 重複削除
./remove_duplicates_fast.sh out remove
./remove_duplicates_fast.sh out_nonexif remove
```

## ⚠️ 重要事項

- **事前にバックアップを取る**
- 初回は `--dry-run` オプションで確認してから実際に実行
- 出力フォルダは自由に指定可能

## 📁 スクリプト構成

- `fix_exif_files.sh` - JPEG修正（拡張子・JSON・パターン）
- `fix_non_exif_files.sh` - GIF/PNG/AVI修正（タイムスタンプ設定）  
- `move_with_exif.sh` - EXIF対応ファイル移動
- `move_without_exif.sh` - EXIF非対応ファイル移動
- `remove_duplicates_fast.sh` - 重複削除

## 📋 対応パターン

**EXIF対応（JPEG）**
- 拡張子修正、JSONメタデータ、ファイル名パターン（Screenshot_、BURST、UNIXタイムスタンプ等）

**EXIF非対応（GIF/PNG/AVI）**
- タイムスタンプ設定（各種スクリーンショットパターン、フォルダ名から年推測）