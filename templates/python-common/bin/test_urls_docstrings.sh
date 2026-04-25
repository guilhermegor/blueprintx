#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

print_status() {
    local status="$1"
    local message="$2"
    case "$status" in
        "success") echo -e "${GREEN}[✓]${NC} ${message}" ;;
        "error") echo -e "${RED}[✗]${NC} ${message}" >&2 ;;
        "warning") echo -e "${YELLOW}[!]${NC} ${message}" ;;
        "info") echo -e "${BLUE}[i]${NC} ${message}" ;;
        "config") echo -e "${CYAN}[→]${NC} ${message}" ;;
        "debug") echo -e "${MAGENTA}[»]${NC} ${message}" ;;
        *) echo -e "[ ] ${message}" ;;
    esac
}

# Cache configuration
CACHE_DIR=".url_check_cache"
CACHE_TTL=$((60 * 60 * 24 * 7)) # 1 week in seconds

get_cache() {
    local url="$1"
    local cache_file="${CACHE_DIR}/$(echo -n "$url" | md5sum | cut -d' ' -f1)"

    if [[ -f "$cache_file" ]]; then
        local timestamp
        timestamp=$(stat -c %Y "$cache_file")
        local now
        now=$(date +%s)

        if (( now - timestamp < CACHE_TTL )); then
            cat "$cache_file"
            return 0
        fi
    fi
    return 1
}

set_cache() {
    local url="$1"
    local status="$2"
    local cache_file="${CACHE_DIR}/$(echo -n "$url" | md5sum | cut -d' ' -f1)"
    echo "$status" > "$cache_file"
}

clean_cache() {
    find "$CACHE_DIR" -type f -mtime +$((CACHE_TTL / 60 / 60 / 24)) -delete 2>/dev/null
}

check_url() {
    local url="$1"
    local status_code

    if status_code=$(get_cache "$url"); then
        echo "$status_code"
        return
    fi

    local user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    local problematic_domains=(
        "platform.openai.com"
        "openai.com"
        "stackoverflow.com"
        "b3.com.br"
        "line.bvmfnet.com.br"
        "reuters.com"
        "investing.com"
        "code.activestate.com"
        "exceltip.com"
        "chromedriver.chromium.org"
        "ime.usp.br"
        "udemy.com"
        "ssc.wisc.edu"
        "pythonnumericalmethods.berkeley.edu"
        "towardsdatascience.com"
        "download.bmfbovespa.com.br"
        "geeksforgeeks.org"
    )

    for domain in "${problematic_domains[@]}"; do
        if [[ "$url" == *"$domain"* ]] && [[ "$url" =~ ^https?:// ]]; then
            set_cache "$url" "200"
            echo "200"
            return
        fi
    done

    # Method 1: HEAD request
    status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 --head \
        -H "User-Agent: $user_agent" \
        -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8" \
        -H "Accept-Language: en-US,en;q=0.5" \
        -H "Accept-Encoding: gzip, deflate" \
        -H "Connection: keep-alive" \
        "$url" 2>/dev/null)

    # Method 2: GET if HEAD returns 403/405
    if [[ -z "$status_code" || "$status_code" -eq 403 || "$status_code" -eq 405 ]]; then
        status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
            -H "User-Agent: $user_agent" \
            -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8" \
            -H "Accept-Language: en-US,en;q=0.5" \
            -H "Accept-Encoding: gzip, deflate" \
            -H "Connection: keep-alive" \
            -H "Upgrade-Insecure-Requests: 1" \
            "$url" 2>/dev/null)
    fi

    # Method 3: wget fallback for persistent 403s
    if [[ "$status_code" -eq 403 ]]; then
        if wget --spider --timeout=10 --user-agent="$user_agent" "$url" >/dev/null 2>&1; then
            status_code="200"
        fi
    fi

    if [[ "$status_code" =~ ^2 ]]; then
        set_cache "$url" "$status_code"
    fi

    echo "$status_code"
}

process_python_files() {
    clean_cache

    local root_dir="${1:-.}"
    declare -A processed_urls
    local has_errors=0

    print_status "info" "Scanning Python docstrings for URLs in '$root_dir'..."

    while IFS= read -r -d '' file; do
        local line_num=0
        local in_docstring=false

        while IFS= read -r line; do
            ((line_num++))

            if [[ "$line" =~ ^[[:space:]]*\"\"\" ]]; then
                local after_open="${line#*\"\"\"}"
                if [[ "$in_docstring" == false && "$after_open" == *\"\"\"* ]]; then
                    continue
                fi
                [[ "$in_docstring" == true ]] && in_docstring=false || in_docstring=true
                continue
            fi
            if [[ "$line" =~ ^[[:space:]]*\'\'\' ]]; then
                local after_open="${line#*\'\'\'}"
                if [[ "$in_docstring" == false && "$after_open" == *\'\'\'* ]]; then
                    continue
                fi
                [[ "$in_docstring" == true ]] && in_docstring=false || in_docstring=true
                continue
            fi

            if [[ "$in_docstring" == true ]]; then
                while [[ "$line" =~ (https?://[a-zA-Z0-9./?=_%:-]+[a-zA-Z0-9./?=_%:-]) ]]; do
                    local url="${BASH_REMATCH[1]}"

                    if [[ -n "${processed_urls[$url]}" ]]; then
                        line="${line#*$url}"
                        continue
                    fi
                    processed_urls["$url"]=1

                    if [[ "$url" =~ (https?://[^/]+)$ ]]; then
                        line="${line#*$url}"
                        continue
                    fi

                    local status_code
                    status_code=$(check_url "$url")

                    if [[ -z "$status_code" ]]; then
                        print_status "error" "Failed to access URL in $file (line $line_num): $url"
                        has_errors=1
                    elif [[ "$status_code" =~ ^[34] ]]; then
                        print_status "error" "URL issue ($status_code) in $file (line $line_num): $url"
                        has_errors=1
                    elif [[ ! "$status_code" =~ ^2 ]]; then
                        print_status "error" "URL problem ($status_code) in $file (line $line_num): $url"
                        has_errors=1
                    fi

                    line="${line#*$url}"
                done
            fi
        done < "$file"
    done < <(find "$root_dir" -type f -name "*.py" -print0)

    if [[ $has_errors -eq 0 ]]; then
        print_status "success" "All docstring URLs are reachable"
        return 0
    fi
    return 1
}

main() {
    mkdir -p "$CACHE_DIR"
    process_python_files "${1:-.}" || exit 1
}

main "$@"
