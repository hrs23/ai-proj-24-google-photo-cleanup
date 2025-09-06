#!/bin/bash

# 大量ファイル対応の重複削除スクリプト

TARGET_DIR="${1:-out}"
MODE="${2:-check}"  # check または remove

echo "=== 高速重複ファイル削除スクリプト ==="
echo "対象: $TARGET_DIR"
echo "モード: $MODE"
echo

# エラーログファイル
ERROR_LOG="/tmp/duplicate_removal_errors_$$.log"
REMOVED_LOG="/tmp/removed_files_$$.log"

# 一時ファイル
TEMP_HASH="/tmp/file_hashes_$$.txt"

# ファイル数確認
TOTAL=$(find "$TARGET_DIR" -type f | wc -l)
echo "総ファイル数: $TOTAL"
echo

# 並列処理でMD5計算（CPUコア数に応じて）
CORES=$(nproc)
echo "MD5ハッシュ計算中... (並列度: $CORES)"

# MD5計算でエラーをキャッチ
find "$TARGET_DIR" -type f -print0 | \
    xargs -0 -P "$CORES" -I {} sh -c '
        if ! md5sum "{}" 2>>"'"$ERROR_LOG"'"; then
            echo "MD5計算エラー: {}" >&2
        fi
    ' | sort > "$TEMP_HASH"

# MD5計算エラーの確認
if [ -s "$ERROR_LOG" ]; then
    echo "警告: MD5計算でエラーが発生したファイルがあります:"
    cat "$ERROR_LOG"
fi

# 重複検出と削除
echo "重複検出中..."
REMOVED=0

# 重複ハッシュのリストを作成
DUPLICATE_HASHES=$(awk '{print $1}' "$TEMP_HASH" | sort | uniq -d)

if [ -z "$DUPLICATE_HASHES" ]; then
    echo "重複ファイルは見つかりませんでした。"
else
    # カウンタ問題を解決するため、削除ファイルをログに記録
    > "$REMOVED_LOG"
    
    echo "$DUPLICATE_HASHES" | while read hash; do
        # 同じハッシュのファイルを取得
        files=$(grep "^$hash " "$TEMP_HASH" | cut -c35-)  # より確実な切り出し
        
        # 最初のファイルを残し、残りを削除対象に
        first=1
        echo "$files" | while IFS= read -r file; do
            if [ $first -eq 1 ]; then
                echo "保持: $file"
                first=0
            else
                echo "  重複: $file"
                if [[ "$MODE" == "remove" ]]; then
                    if rm -v "$file" 2>>"$ERROR_LOG"; then
                        echo "$file" >> "$REMOVED_LOG"
                    else
                        echo "削除エラー: $file" >&2
                    fi
                fi
            fi
        done
    done
    
    # 削除数を正確にカウント
    if [[ "$MODE" == "remove" ]] && [ -f "$REMOVED_LOG" ]; then
        REMOVED=$(wc -l < "$REMOVED_LOG" 2>/dev/null || echo 0)
    fi
fi

# エラーログの確認
if [ -s "$ERROR_LOG" ]; then
    echo
    echo "=== エラーログ ==="
    cat "$ERROR_LOG"
fi

# クリーンアップ
rm -f "$TEMP_HASH" "$ERROR_LOG" "$REMOVED_LOG"

echo
echo "=== 完了 ==="
if [[ "$MODE" == "check" ]]; then
    echo "実際に削除するには: $0 $TARGET_DIR remove"
else
    echo "削除ファイル数: $REMOVED"
fi