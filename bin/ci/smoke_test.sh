#!/usr/bin/env bash
# Runs blueprintx new --dry-run for the given skeleton.
# Computes menu indices dynamically from skeleton.meta files,
# so the test remains correct regardless of directory ordering changes.

set -euo pipefail

SKELETON="${1:?skeleton name required}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TEMPLATES_DIR="$REPO_ROOT/templates"

# Resolve the language for this skeleton
target_lang=""
for meta in "$TEMPLATES_DIR"/*/skeleton.meta; do
    [ -f "$meta" ] || continue
    dir="$(basename "$(dirname "$meta")")"
    if [ "$dir" = "$SKELETON" ]; then
        target_lang="$(grep '^language=' "$meta" | cut -d= -f2-)"
        break
    fi
done

[ -n "$target_lang" ] || { echo "ERROR: skeleton '$SKELETON' not found" >&2; exit 1; }

# Build the language list (same glob order + dedup as blueprintx.sh)
lang_list=()
seen_langs=""
for meta in "$TEMPLATES_DIR"/*/skeleton.meta; do
    [ -f "$meta" ] || continue
    lang="$(grep '^language=' "$meta" | cut -d= -f2-)"
    [ -z "$lang" ] && continue
    case " $seen_langs " in
        *" $lang "*) ;;
        *) lang_list+=("$lang"); seen_langs="$seen_langs $lang" ;;
    esac
done

# Find 1-based index of target_lang
lang_idx=0
for i in "${!lang_list[@]}"; do
    [ "${lang_list[$i]}" = "$target_lang" ] && lang_idx=$((i + 1)) && break
done
[ "$lang_idx" -gt 0 ] || { echo "ERROR: language '$target_lang' not in list" >&2; exit 1; }

# Build skeleton list for this language (same glob order as blueprintx.sh)
skel_list=()
for meta in "$TEMPLATES_DIR"/*/skeleton.meta; do
    [ -f "$meta" ] || continue
    lang="$(grep '^language=' "$meta" | cut -d= -f2-)"
    [ "$lang" = "$target_lang" ] || continue
    skel_list+=("$(basename "$(dirname "$meta")")")
done

# Find 1-based index of SKELETON
skel_idx=0
for i in "${!skel_list[@]}"; do
    [ "${skel_list[$i]}" = "$SKELETON" ] && skel_idx=$((i + 1)) && break
done
[ "$skel_idx" -gt 0 ] || { echo "ERROR: skeleton '$SKELETON' not found for lang '$target_lang'" >&2; exit 1; }

echo "smoke_test: skeleton=$SKELETON lang=$target_lang lang_idx=$lang_idx skel_idx=$skel_idx"

# project_name / description (empty) / lang_idx / skel_idx / license (1=MIT)
printf "ci-smoke\n\n%s\n%s\n1\n" "$lang_idx" "$skel_idx" \
    | bash "$REPO_ROOT/bin/blueprintx.sh" new --dry-run
