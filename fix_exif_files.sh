#!/bin/bash

# EXIF対応ファイル（JPEG）の包括的処理スクリプト
# 拡張子修正 → JSON修正 → パターン修正

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

echo "=== EXIF対応ファイル（JPEG）処理 ==="
echo "Mode: $MODE"
echo "Directory: $DIR"
echo "========================================"

# CPU並列数を自動検出
PARALLEL_JOBS=$(nproc)
echo "並列処理: ${PARALLEL_JOBS}プロセス"
echo

# 一時ファイル管理
temp_results=$(mktemp)
temp_progress=$(mktemp)

cleanup() {
    [[ -n "$temp_results" && -f "$temp_results" ]] && rm -f "$temp_results"
    [[ -n "$temp_progress" && -f "$temp_progress" ]] && rm -f "$temp_progress"
}
trap cleanup EXIT

# フォルダ名から年を推測してEXIF設定
set_exif_from_folder() {
    local file="$1"
    
    if [[ "$file" =~ Photos\ from\ ([0-9]{4}) ]]; then
        year="${BASH_REMATCH[1]}"
        datetime="${year}:01:01 00:00:00"
        
        if ! exiftool -DateTimeOriginal "$file" 2>/dev/null | grep -q "Date/Time Original"; then
            if [ "$MODE" = "fix" ]; then
                exiftool -DateTimeOriginal="$datetime" \
                        -CreateDate="$datetime" \
                        -ModifyDate="$datetime" \
                        -overwrite_original "$file" >/dev/null 2>&1
                
                if [ $? -eq 0 ]; then
                    echo "  → Set EXIF date to: $datetime"
                else
                    echo "  → Failed to set EXIF date"
                fi
            else
                echo "  → Would set EXIF date to: $datetime"
            fi
        fi
    fi
}

# 1. 拡張子とファイル形式の不一致修正
echo "Phase 1: 拡張子とファイル形式の不一致修正..."

process_extension() {
    local file="$1"
    local mode="$2"
    local file_type=$(file -b "$file")
    local extension="${file##*.}"
    local basename="${file%.*}"
    local new_file=""
    
    # JPEG形式だが拡張子がPNG系の場合
    if echo "$file_type" | grep -q "JPEG" && [[ "$extension" =~ ^(PNG|png)$ ]]; then
        new_file="${basename}.jpg"
        echo "Found JPEG with .$extension extension: $file"
        
        if [ "$mode" = "fix" ]; then
            mv "$file" "$new_file"
            echo "  → Renamed to: $new_file"
            set_exif_from_folder "$new_file"
        else
            echo "  → Would rename to: $new_file"
        fi
    fi
}

export -f process_extension
export -f set_exif_from_folder
export MODE

find "$DIR" -type f \( -name "*.PNG" -o -name "*.png" \) -print0 | \
    xargs -0 -P "$PARALLEL_JOBS" -I {} bash -c 'process_extension "$@"' _ {} "$MODE"

echo "Phase 1 完了"
echo

# 2. JSONメタデータからEXIF修正
echo "Phase 2: JSONメタデータからEXIF修正..."

process_json_metadata() {
    local media_file="$1"
    local mode="$2"
    
    # 対応するJSONファイルを探す
    local json_file="${media_file}.supplemental-metadata.json"
    
    if [[ ! -f "$json_file" ]]; then
        return 0
    fi
    
    # JSONから日時を抽出
    local photo_taken_time=$(grep -o '"photoTakenTime"[^}]*"timestamp"[^}]*"[0-9]*"' "$json_file" 2>/dev/null | grep -o '[0-9]*' | tail -1)
    
    if [[ -z "$photo_taken_time" ]]; then
        return 0
    fi
    
    # UNIXタイムスタンプを日時に変換
    local datetime=$(date -d "@$photo_taken_time" "+%Y:%m:%d %H:%M:%S" 2>/dev/null)
    
    if [[ -z "$datetime" ]]; then
        return 0
    fi
    
    # 既存のDateTimeOriginalがない場合のみ設定
    if ! exiftool -DateTimeOriginal "$media_file" 2>/dev/null | grep -q "Date/Time Original"; then
        echo "JSON metadata found: $media_file"
        
        if [[ "$mode" == "fix" ]]; then
            exiftool -DateTimeOriginal="$datetime" \
                    -CreateDate="$datetime" \
                    -ModifyDate="$datetime" \
                    -overwrite_original "$media_file" >/dev/null 2>&1
            
            if [ $? -eq 0 ]; then
                echo "  → Set EXIF date to: $datetime (from JSON)"
            else
                echo "  → Failed to set EXIF date from JSON"
            fi
        else
            echo "  → Would set EXIF date to: $datetime (from JSON)"
        fi
    fi
}

export -f process_json_metadata

find "$DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) -print0 | \
    xargs -0 -P "$PARALLEL_JOBS" -I {} bash -c 'process_json_metadata "$@"' _ {} "$MODE"

echo "Phase 2 完了"
echo

# 3. ファイル名パターンからEXIF修正
echo "Phase 3: ファイル名パターンからEXIF修正..."

extract_datetime_from_pattern() {
    local filename="$1"
    local base_name=$(basename "$filename")
    local datetime=""
    
    # Screenshot_YYYYMMDD-HHMMSS形式
    if [[ "$base_name" =~ Screenshot_([0-9]{8})-([0-9]{6}) ]]; then
        local date_part="${BASH_REMATCH[1]}"
        local time_part="${BASH_REMATCH[2]}"
        datetime="${date_part:0:4}:${date_part:4:2}:${date_part:6:2} ${time_part:0:2}:${time_part:2:2}:${time_part:4:2}"
        
    # BURST形式: BURST20181222131329
    elif [[ "$base_name" =~ BURST([0-9]{14}) ]]; then
        local timestamp="${BASH_REMATCH[1]}"
        datetime="${timestamp:0:4}:${timestamp:4:2}:${timestamp:6:2} ${timestamp:8:2}:${timestamp:10:2}:${timestamp:12:2}"
        
    # 13桁UNIXタイムスタンプ（ミリ秒）
    elif [[ "$base_name" =~ ^([0-9]{13})\. ]]; then
        local unix_ms="${BASH_REMATCH[1]}"
        local unix_s=$((unix_ms / 1000))
        datetime=$(date -d "@$unix_s" "+%Y:%m:%d %H:%M:%S" 2>/dev/null)
        
    # 10桁UNIXタイムスタンプ（秒）
    elif [[ "$base_name" =~ ^([0-9]{10})\. ]]; then
        local unix_s="${BASH_REMATCH[1]}"
        datetime=$(date -d "@$unix_s" "+%Y:%m:%d %H:%M:%S" 2>/dev/null)
        
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
        
        datetime="${year}:${month}:${day} $(printf "%02d" $hour):${min}:${sec}"
    fi
    
    echo "$datetime"
}

process_pattern_file() {
    local file="$1"
    local mode="$2"
    
    # 既存のDateTimeOriginalがある場合はスキップ
    if exiftool -DateTimeOriginal "$file" 2>/dev/null | grep -q "Date/Time Original"; then
        return 0
    fi
    
    local datetime=$(extract_datetime_from_pattern "$file")
    
    if [[ -n "$datetime" ]]; then
        echo "Pattern match found: $file"
        
        if [[ "$mode" == "fix" ]]; then
            exiftool -DateTimeOriginal="$datetime" \
                    -CreateDate="$datetime" \
                    -ModifyDate="$datetime" \
                    -overwrite_original "$file" >/dev/null 2>&1
            
            if [ $? -eq 0 ]; then
                echo "  → Set EXIF date to: $datetime (from pattern)"
            else
                echo "  → Failed to set EXIF date from pattern"
            fi
        else
            echo "  → Would set EXIF date to: $datetime (from pattern)"
        fi
    fi
}

export -f extract_datetime_from_pattern
export -f process_pattern_file

find "$DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) -print0 | \
    xargs -0 -P "$PARALLEL_JOBS" -I {} bash -c 'process_pattern_file "$@"' _ {} "$MODE"

echo "Phase 3 完了"
echo

# 統計表示
echo "=== 処理結果 ==="
total_jpg=$(find "$DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) 2>/dev/null | wc -l)
with_exif=$(find "$DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" \) -exec exiftool -DateTimeOriginal {} \; 2>/dev/null | grep -c "Date/Time Original")

echo "総JPEGファイル数: $total_jpg"
echo "EXIF日時設定済み: $with_exif"
echo "EXIF未設定: $((total_jpg - with_exif))"
echo "========================================"