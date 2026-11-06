#!/usr/bin/env bash
set -euo pipefail

str_root="$(cd "$(dirname "$0")/../.." && pwd)"
[ "${1:-}" = "--root" ] && str_root="$(cd "$2" && pwd)"

int_failures=0
int_checked=0

while IFS= read -r str_file; do
    int_checked=$((int_checked + 1))
    str_base="$(basename "$str_file")"
    case "$str_file" in
        */templates/lib-minimal/.github/workflows/release-pypi.yaml | \
            */templates/lib-minimal/.github/workflows/release-test-pypi.yaml) continue ;;
    esac
    if ! [[ "$str_base" =~ ^[a-z0-9]+(-[a-z0-9]+)*\.yml$ ]]; then
        echo "ERROR: ${str_file#"$str_root"/}: template workflow names must be kebab-case with .yml" >&2
        int_failures=$((int_failures + 1))
    fi
done < <(find "$str_root/templates" -path '*/.github/workflows/*' -type f | sort)

if [ "$int_checked" -eq 0 ]; then
    echo "ERROR: no template workflows found under $str_root/templates; the gate checked nothing" >&2
    exit 1
fi

[ "$int_failures" -eq 0 ] || exit 1
echo "OK: $int_checked template workflow names conform"
