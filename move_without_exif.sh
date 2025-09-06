#!/bin/bash

# EXIF非対応ファイル（GIF、PNG、AVI等）移動スクリプト

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 [--dry-run] <input_dir> <output_dir>"
    echo "  --dry-run:    テスト実行（実際の移動は行わない）"
    echo "  <input_dir>:  検索対象ディレクトリ"
    echo "  <output_dir>: 移動先ディレクトリ"
    exit 1
fi

# Parse options
DRY_RUN=false
INPUT_DIR=""
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -*)
            echo "Error: Unknown option $1"
            exit 1
            ;;
        *)
            if [ -z "$INPUT_DIR" ]; then
                INPUT_DIR="$(realpath "$1")"
            elif [ -z "$OUTPUT_DIR" ]; then
                OUTPUT_DIR="$(realpath "$1")"
            else
                echo "Error: Too many arguments"
                exit 1
            fi
            shift
            ;;
    esac
done

if [ -z "$INPUT_DIR" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Error: Both input and output directories required"
    exit 1
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Error: Input directory does not exist: $INPUT_DIR"
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    MODE="test"
else
    MODE="move"
fi

echo "=== EXIF非対応ファイル移動スクリプト ==="
echo "入力: $INPUT_DIR"
echo "出力: $OUTPUT_DIR"
echo "モード: $MODE"
echo

# 一時ファイルのクリーンアップ関数
cleanup() {
    [[ -n "$temp_file" && -f "$temp_file" ]] && rm -f "$temp_file"
}
trap cleanup EXIT

# EXIF非対応ファイルを検索
echo "EXIF非対応ファイルを検索中..."

temp_file=$(mktemp)

# CPU並列数を自動検出
PARALLEL_JOBS=$(nproc)

# ファイル判定関数
check_non_exif_file() {
    local file="$1"
    local file_type=$(file -b "$file")
    local extension="${file##*.}"
    
    # EXIF対応ファイル（JPEG）はスキップ
    if echo "$file_type" | grep -q "JPEG"; then
        return 0
    fi
    
    # 実際にPNGかどうか確認
    local is_actual_png=false
    if echo "$file_type" | grep -q "PNG"; then
        is_actual_png=true
    fi
    
    # GIF、AVI、実際のPNGファイル等を対象
    if [[ "$extension" =~ ^(gif|GIF|avi|AVI|mkv|MKV|mp4|MP4|mov|MOV|webm|WEBM)$ ]] || [ "$is_actual_png" = true ]; then
        # タイムスタンプが設定されているかチェック
        local current_time=$(date +%s)
        local file_time=$(stat -c %Y "$file" 2>/dev/null || echo 0)
        
        # ファイルタイムスタンプが現在時刻より古い場合は処理済みとみなす
        if [[ $file_time -lt $((current_time - 86400)) ]]; then  # 1日以上古い
            echo "$file"
        fi
    fi
}

export -f check_non_exif_file

echo "${PARALLEL_JOBS}並列でファイル種別チェック開始..."

# すべての候補ファイルを検索
find "$INPUT_DIR" -type f \( \
    -iname "*.gif" -o -iname "*.png" -o -iname "*.avi" -o -iname "*.mkv" \
    -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.webm" \
    -o -iname "*.jpg" -o -iname "*.jpeg" \
\) -not -path "$OUTPUT_DIR/*" -print0 | \
    xargs -0 -P "$PARALLEL_JOBS" -I {} bash -c 'check_non_exif_file "{}"' > "$temp_file"

# 結果確認
if [ -s "$temp_file" ]; then
    move_count=$(wc -l < "$temp_file")
else
    move_count=0
fi

echo
echo "移動対象ファイル数: $move_count"

if [[ $move_count -eq 0 ]]; then
    echo "移動対象ファイルが見つかりませんでした。"
    echo "先にfix_non_exif_files.shを実行してタイムスタンプを設定してください。"
    exit 0
fi

echo
echo "対象ファイルの内訳:"

# ファイル種別ごとの統計
echo "--- ファイル種別統計 ---"
while IFS= read -r file; do
    if [[ -n "$file" ]]; then
        extension="${file##*.}"
        echo "$extension"
    fi
done < "$temp_file" | sort | uniq -c | sort -nr

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
                
                # 元のタイムスタンプを保持
                touch -r "$file" "$dest" 2>/dev/null || true
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
    echo "  $0 $INPUT_DIR $OUTPUT_DIR"
fi

echo "========================================"