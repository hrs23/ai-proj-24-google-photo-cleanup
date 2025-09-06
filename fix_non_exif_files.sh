#!/bin/bash

# EXIF非対応ファイル（GIF、PNG、AVI等）のタイムスタンプ処理スクリプト

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 [--dry-run] <directory>"
    echo "  --dry-run:  テストモード（変更を表示のみ）"
    echo "  directory:  処理対象ディレクトリ"
    exit 1
fi

# Parse options
DRY_RUN=false
DIR=""

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
            if [ -z "$DIR" ]; then
                DIR="$1"
            else
                echo "Error: Too many arguments"
                exit 1
            fi
            shift
            ;;
    esac
done

if [ -z "$DIR" ]; then
    echo "Error: Directory argument required"
    exit 1
fi

if [ ! -d "$DIR" ]; then
    echo "Error: Directory '$DIR' does not exist"
    exit 1
fi

if [ "$DRY_RUN" = true ]; then
    MODE="test"
else
    MODE="fix"
fi

echo "=== EXIF非対応ファイル処理 ==="
echo "Mode: $MODE"
echo "Directory: $DIR"
echo "========================================"

# CPU並列数を自動検出
PARALLEL_JOBS=$(nproc)
echo "並列処理: ${PARALLEL_JOBS}プロセス"
echo

# 日時を抽出してタイムスタンプ形式に変換
extract_datetime() {
    local filename="$1"
    local path="$2"
    local base_name=$(basename "$filename")
    local datetime=""
    local timestamp=""
    
    # Screenshot_YYYYMMDD-HHMMSS形式
    if [[ "$base_name" =~ Screenshot_([0-9]{8})-([0-9]{6}) ]]; then
        local date_part="${BASH_REMATCH[1]}"
        local time_part="${BASH_REMATCH[2]}"
        timestamp="${date_part:0:4}${date_part:4:2}${date_part:6:2}${time_part:0:2}${time_part:2:2}.${time_part:4:2}"
        datetime="${date_part:0:4}:${date_part:4:2}:${date_part:6:2} ${time_part:0:2}:${time_part:2:2}:${time_part:4:2}"
        
    # スクリーンショット YYYY-MM-DD HH.MM.SS形式
    elif [[ "$base_name" =~ スクリーンショット\ ([0-9]{4})-([0-9]{2})-([0-9]{2})\ ([0-9]{2})\.([0-9]{2})\.([0-9]{2}) ]]; then
        local year="${BASH_REMATCH[1]}"
        local month="${BASH_REMATCH[2]}"
        local day="${BASH_REMATCH[3]}"
        local hour="${BASH_REMATCH[4]}"
        local min="${BASH_REMATCH[5]}"
        local sec="${BASH_REMATCH[6]}"
        timestamp="${year}${month}${day}${hour}${min}.${sec}"
        datetime="${year}:${month}:${day} ${hour}:${min}:${sec}"
        
    # BURST形式
    elif [[ "$base_name" =~ BURST([0-9]{14}) ]]; then
        local ts="${BASH_REMATCH[1]}"
        timestamp="${ts:0:4}${ts:4:2}${ts:6:2}${ts:8:2}${ts:10:2}.${ts:12:2}"
        datetime="${ts:0:4}:${ts:4:2}:${ts:6:2} ${ts:8:2}:${ts:10:2}:${ts:12:2}"
        
    # 13桁UNIXタイムスタンプ（ミリ秒） - PNGファイルでよくある
    elif [[ "$base_name" =~ ^([0-9]{13})\. ]]; then
        local unix_ms="${BASH_REMATCH[1]}"
        local unix_s=$((unix_ms / 1000))
        datetime=$(date -d "@$unix_s" "+%Y:%m:%d %H:%M:%S" 2>/dev/null)
        timestamp=$(date -d "@$unix_s" "+%Y%m%d%H%M.%S" 2>/dev/null)
        
    # 10桁UNIXタイムスタンプ（秒）
    elif [[ "$base_name" =~ ^([0-9]{10})\. ]]; then
        local unix_s="${BASH_REMATCH[1]}"
        datetime=$(date -d "@$unix_s" "+%Y:%m:%d %H:%M:%S" 2>/dev/null)
        timestamp=$(date -d "@$unix_s" "+%Y%m%d%H%M.%S" 2>/dev/null)
        
    # YYYYMMDDHHMMSS形式（AVIファイル等）
    elif [[ "$base_name" =~ ^([0-9]{14}) ]]; then
        local ts="${BASH_REMATCH[1]}"
        timestamp="${ts:0:4}${ts:4:2}${ts:6:2}${ts:8:2}${ts:10:2}.${ts:12:2}"
        datetime="${ts:0:4}:${ts:4:2}:${ts:6:2} ${ts:8:2}:${ts:10:2}:${ts:12:2}"
        
    # Screen Shot形式: Screen Shot YYYY-MM-DD at H.MM.SS AM/PM
    elif [[ "$base_name" =~ Screen\ Shot\ ([0-9]{4})-([0-9]{2})-([0-9]{2})\ at\ ([0-9]{1,2})\.([0-9]{2})\.([0-9]{2})\ (AM|PM) ]]; then
        local year="${BASH_REMATCH[1]}"
        local month="${BASH_REMATCH[2]}"
        local day="${BASH_REMATCH[3]}"
        local hour="${BASH_REMATCH[4]}"
        local min="${BASH_REMATCH[5]}"
        local sec="${BASH_REMATCH[6]}"
        local ampm="${BASH_REMATCH[7]}"
        
        if [[ "$ampm" == "PM" && "$hour" != "12" ]]; then
            hour=$((hour + 12))
        elif [[ "$ampm" == "AM" && "$hour" == "12" ]]; then
            hour=0
        fi
        
        timestamp="${year}${month}${day}$(printf "%02d" $hour)${min}.${sec}"
        datetime="${year}:${month}:${day} $(printf "%02d" $hour):${min}:${sec}"
        
    # Screenshot from形式: Screenshot from YYYY-MM-DD HH-MM-SS
    elif [[ "$base_name" =~ Screenshot\ from\ ([0-9]{4})-([0-9]{2})-([0-9]{2})\ ([0-9]{2})-([0-9]{2})-([0-9]{2}) ]]; then
        local year="${BASH_REMATCH[1]}"
        local month="${BASH_REMATCH[2]}"
        local day="${BASH_REMATCH[3]}"
        local hour="${BASH_REMATCH[4]}"
        local min="${BASH_REMATCH[5]}"
        local sec="${BASH_REMATCH[6]}"
        timestamp="${year}${month}${day}${hour}${min}.${sec}"
        datetime="${year}:${month}:${day} ${hour}:${min}:${sec}"
        
    # フォルダ名から年を推測（最後の手段）
    elif [[ "$path" =~ Photos\ from\ ([0-9]{4}) ]]; then
        local year="${BASH_REMATCH[1]}"
        timestamp="${year}0101000000"
        datetime="${year}:01:01 00:00:00"
    fi
    
    echo "$timestamp|$datetime"
}

# ファイル処理関数
process_non_exif_file() {
    local file="$1"
    local mode="$2"
    
    # ファイル形式チェック
    local file_type=$(file -b "$file")
    local extension="${file##*.}"
    
    # EXIF対応ファイル（JPEG）はスキップ
    if echo "$file_type" | grep -q "JPEG"; then
        return 0
    fi
    
    # 実際にPNGかどうか確認（拡張子が.jpgでも実際はPNG）
    local is_actual_png=false
    if echo "$file_type" | grep -q "PNG"; then
        is_actual_png=true
    fi
    
    # GIF、AVI、実際のPNGファイルを対象
    if [[ "$extension" =~ ^(gif|GIF|avi|AVI|mkv|MKV|mp4|MP4|mov|MOV|webm|WEBM)$ ]] || [ "$is_actual_png" = true ]; then
        
        local result=$(extract_datetime "$file" "$(dirname "$file")")
        local timestamp=$(echo "$result" | cut -d'|' -f1)
        local datetime=$(echo "$result" | cut -d'|' -f2)
        
        if [[ -n "$timestamp" && -n "$datetime" ]]; then
            echo "Non-EXIF file with datetime: $file"
            echo "  → DateTime: $datetime"
            
            if [[ "$mode" == "fix" ]]; then
                # タイムスタンプ形式に変換してファイル日時を設定
                if [[ ${#timestamp} -eq 12 ]]; then
                    # YYYYMMDDHHMM形式
                    touch -t "$timestamp" "$file" 2>/dev/null
                elif [[ ${#timestamp} -eq 15 ]]; then
                    # YYYYMMDDHHMM.SS形式
                    touch -t "$timestamp" "$file" 2>/dev/null
                fi
                
                if [ $? -eq 0 ]; then
                    echo "  → File timestamp updated"
                else
                    echo "  → Failed to update timestamp"
                fi
            else
                echo "  → Would set file timestamp"
            fi
        else
            echo "No datetime pattern found: $file"
        fi
    fi
}

export -f extract_datetime
export -f process_non_exif_file
export MODE

echo "処理対象ファイルを検索中..."

# EXIF非対応ファイルを検索して処理
find "$DIR" -type f \( \
    -iname "*.gif" -o -iname "*.png" -o -iname "*.avi" -o -iname "*.mkv" \
    -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.webm" -o -iname "*.jpg" -o -iname "*.jpeg" \
\) -print0 | \
    xargs -0 -P "$PARALLEL_JOBS" -I {} bash -c 'process_non_exif_file "$@"' _ {} "$MODE"

echo
echo "=== 処理結果 ==="

# 統計表示
total_non_exif=$(find "$DIR" -type f \( -iname "*.gif" -o -iname "*.avi" -o -iname "*.mkv" -o -iname "*.mp4" -o -iname "*.mov" -o -iname "*.webm" \) 2>/dev/null | wc -l)
actual_png_count=0

# 実際のPNGファイルをカウント
while IFS= read -r -d '' file; do
    if file -b "$file" | grep -q "PNG"; then
        actual_png_count=$((actual_png_count + 1))
    fi
done < <(find "$DIR" -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) -print0 2>/dev/null)

total_processed=$((total_non_exif + actual_png_count))

echo "GIF/AVI/MP4等: $total_non_exif"
echo "実際のPNGファイル: $actual_png_count"
echo "処理対象総数: $total_processed"
echo "========================================"