#!/usr/bin/env bash
# Report-only scan for PR/issue bodies left in <repo>/.git/*.md that match no PR or issue
# on the forge (blueprintx#657). Local-only by design: .git/ is outside the worktree, so no
# CI job can see these files. Never deletes or moves anything.
#
# Matching is by CONTENT (whitespace-normalised text), never by filename: a body matches a
# forge PR/issue when either text contains the other. Fails closed: a body that cannot be
# decided (forge unreadable, too short to match, ambiguous) is UNKNOWN, never ORPHAN.
#
# Usage: bash bin/check_orphan_pr_bodies.sh [git-dir]
# Env:   BLUEPRINTX_REPO=owner/name  overrides the slug parsed from `origin`.
# Exit:  0 all MATCHED | 1 ORPHAN found | 2 could not decide (UNKNOWN or forge unreadable)

set -euo pipefail

INT_MIN_LEN=40  # ponytail: shorter normalised bodies match too loosely; report UNKNOWN instead

norm() { tr -s '[:space:]' ' ' | sed 's/^ //; s/ $//'; }

str_gitdir="${1:-$(git rev-parse --path-format=absolute --git-common-dir)}"
str_repo="${BLUEPRINTX_REPO:-$(git remote get-url origin 2>/dev/null | sed -E 's#^.*github\.com[:/]##; s#\.git$##')}"

str_forge="$(mktemp -d)"
trap 'rm -rf "$str_forge"' EXIT

# REST on purpose (GraphQL is rate-limited more tightly). /issues returns PRs too.
bool_forge_ok=1
if [ -z "$str_repo" ] || ! gh api --paginate "repos/$str_repo/issues?state=all&per_page=100" \
    --jq '.[] | "\(.number)\t\((.body // "") | gsub("\\s+"; " ") | sub("^ "; "") | sub(" $"; ""))"' \
    > "$str_forge/all.tsv" 2>"$str_forge/err"; then
    bool_forge_ok=0
    echo "UNKNOWN-FORGE: could not read issues/PRs of '${str_repo:-?}': $(head -c 200 "$str_forge/err" 2>/dev/null)" >&2
fi

int_orphans=0
int_unknown=0
[ "$bool_forge_ok" = 1 ] || int_unknown=1

shopt -s nullglob
for path_md in "$str_gitdir"/*.md; do
    int_size="$(stat -c %s "$path_md")"
    int_age_days=$(( ($(date +%s) - $(stat -c %Y "$path_md")) / 86400 ))
    str_body="$(norm < "$path_md")"
    str_verdict="UNKNOWN"

    if [ "$bool_forge_ok" = 1 ] && [ "${#str_body}" -ge "$INT_MIN_LEN" ]; then
        list_hits=()
        while IFS=$'\t' read -r str_num str_forge_body; do
            if [ "${#str_forge_body}" -ge "$INT_MIN_LEN" ] &&
                { [[ "$str_forge_body" == *"$str_body"* ]] || [[ "$str_body" == *"$str_forge_body"* ]]; }; then
                list_hits+=("#$str_num")
            fi
        done < "$str_forge/all.tsv"
        case "${#list_hits[@]}" in
            0) str_verdict="ORPHAN" ;;
            1) str_verdict="MATCHED ${list_hits[0]}" ;;
            *) str_verdict="UNKNOWN (ambiguous: ${list_hits[*]})" ;;
        esac
    fi

    case "$str_verdict" in
        ORPHAN) int_orphans=$((int_orphans + 1)) ;;
        UNKNOWN*) int_unknown=$((int_unknown + 1)) ;;
    esac
    printf '%s\t%sB\t%sd\t%s\n' "$path_md" "$int_size" "$int_age_days" "$str_verdict"
done

[ "$int_unknown" -eq 0 ] || exit 2
[ "$int_orphans" -eq 0 ] || exit 1
