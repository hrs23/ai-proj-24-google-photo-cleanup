#!/bin/bash

# EXIF日時付きファイル（主にJPEG）移動スクリプト

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 [test|move] <input_dir> <output_dir>"
    echo "  test|move:    テスト実行 または 実際に移動を実行"
    echo "  <input_dir>:  検索対象ディレクトリ"
    echo "  <output_dir>: 移動先ディレクトリ"
    exit 1
fi

MODE="$1"
INPUT_DIR="$(realpath "$2")"
OUTPUT_DIR="$(realpath "$3")"

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Input directory does not exist: $2"
    exit 1
fi

if [ "$MODE" != "test" ] && [ "$MODE" != "move" ]; then
    echo "Error: First argument must be 'test' or 'move'"
    exit 1
fi

echo "=== EXIF対応ファイル移動スクリプト ==="
echo "入力: $INPUT_DIR"
echo "出力: $OUTPUT_DIR"
echo "モード: $MODE"
echo

# 一時ファイルのクリーンアップ関数
cleanup() {
    [[ -n "$temp_file" && -f "$temp_file" ]] && rm -f "$temp_file"
}
trap cleanup EXIT

# EXIF対応ファイル（主にJPEG）を検索
echo "EXIF対応ファイルを検索中..."
all_files=$(find "$INPUT_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.tiff" -o -iname "*.tif" \) -not -path "$OUTPUT_DIR/*" 2>/dev/null)

total_count=$(echo "$all_files" | grep -c .)
echo "候補ファイル総数: $total_count"
echo

if [[ $total_count -eq 0 ]]; then
    echo "移動対象ファイルが見つかりませんでした。"
    exit 0
fi

# 移動対象ファイルを検索（EXIF日時があるもの）
temp_file=$(mktemp)

# CPU並列数を自動検出
PARALLEL_JOBS=$(nproc)
echo "${PARALLEL_JOBS}並列でEXIF日時チェック開始..."

# 並列処理用の関数を定義
check_exif() {
    local file="$1"
    # EXIF日時情報をチェック
    if exiftool "$file" -DateTimeOriginal -CreateDate -s -s -s 2>/dev/null | grep -q "^[0-9]"; then
        echo "$file"
    fi
}

export -f check_exif

# xargsで並列実行
echo "$all_files" | xargs -P "$PARALLEL_JOBS" -I {} bash -c 'check_exif "{}"' > "$temp_file" &
XARGS_PID=$!

# 進捗監視
echo "進捗監視開始..."
start_time=$(date +%s)

while kill -0 $XARGS_PID 2>/dev/null; do
    current_count=$(wc -l < "$temp_file" 2>/dev/null || echo 0)
    elapsed=$(($(date +%s) - start_time))
    
    if [[ $elapsed -gt 0 ]]; then
        rate=$((current_count / elapsed))
        echo "進捗: $current_count/$total_count (${rate} files/sec, ${elapsed}s経過)"
    fi
    
    sleep 2
done

wait $XARGS_PID

# 結果確認
move_count=$(wc -l < "$temp_file")
echo
echo "EXIF日時付きファイル数: $move_count"

if [[ $move_count -eq 0 ]]; then
    echo "EXIF日時が設定されたファイルが見つかりませんでした。"
    echo "先にfix_exif_files.shを実行してください。"
    exit 0
fi

# 重複チェック
echo
echo "移動先での重複をチェック中..."

duplicate_count=0
while IFS= read -r file; do
    if [[ -n "$file" ]]; then
        filename=$(basename "$file")
        if [[ -f "$OUTPUT_DIR/$filename" ]]; then
            duplicate_count=$((duplicate_count + 1))
            echo "重複: $filename"
        fi
    fi
done < "$temp_file"

echo "重複ファイル数: $duplicate_count"

if [[ $duplicate_count -gt 0 && "$MODE" == "move" ]]; then
    echo
    echo "重複ファイルが存在します。移動時に自動的に連番が付与されます。"
    echo "続行しますか？ (y/N)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "操作をキャンセルしました。"
        exit 1
    fi
fi

# 移動処理
if [[ "$MODE" == "move" ]]; then
    echo
    echo "ファイル移動を開始..."
    
    # 出力ディレクトリを作成
    mkdir -p "$OUTPUT_DIR"
    
    moved=0
    failed=0
    
    while IFS= read -r file; do
        if [[ -n "$file" ]]; then
            filename=$(basename "$file")
            dest="$OUTPUT_DIR/$filename"
            
            # 重複する場合は連番を付与
            counter=1
            base_name="${filename%.*}"
            extension="${filename##*.}"
            
            while [[ -f "$dest" ]]; do
                dest="$OUTPUT_DIR/${base_name}_${counter}.${extension}"
                counter=$((counter + 1))
            done
            
            # ファイル移動
            if mv "$file" "$dest" 2>/dev/null; then
                moved=$((moved + 1))
                echo "移動: $(basename "$file") → $(basename "$dest")"
            else
                failed=$((failed + 1))
                echo "エラー: 移動失敗 $file"
            fi
        fi
    done < "$temp_file"
    
    echo
    echo "=== 移動結果 ==="
    echo "成功: $moved ファイル"
    echo "失敗: $failed ファイル"
    
else
    echo
    echo "=== テスト結果 ==="
    echo "移動対象: $move_count ファイル"
    echo "重複: $duplicate_count ファイル"
    echo
    echo "実際に移動するには以下を実行:"
    echo "  $0 $INPUT_DIR move"
    echo "または:"
    echo "  echo \"y\" | $0 $INPUT_DIR move"
fi

echo "========================================"