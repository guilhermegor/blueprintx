#!/usr/bin/env bash
# Report-only scan for PR/issue bodies left in <repo>/.git/*.md that match no PR or issue
# on the forge (blueprintx#657). Local-only by design: .git/ is outside the worktree, so no
# CI job can see these files. Never deletes or moves anything. Needs python3.
#
# Matching is by CONTENT, never by filename, through ONE normaliser applied to both sides
# (NFKC, case-folded, all Unicode whitespace collapsed, `[x]` read as `[ ]` because ticking a
# box on GitHub rewrites the stored body). MATCHED = the local body is contained in exactly one
# forge body. Containment runs one way only: a forge body that is just the unfilled PR template
# must not match every local body built from it. A body edited on the forge since is UNKNOWN
# (near a PR), never ORPHAN: ORPHAN needs no forge body even close.
#
# Fails closed: anything undecidable (forge unreadable, no origin, body under 40 characters,
# ambiguous or near match) is UNKNOWN, never ORPHAN, and never a silent skip.
#
# Usage: bash bin/check_orphan_pr_bodies.sh [git-dir]   (origin is read from that git-dir)
# Env:   BLUEPRINTX_REPO=owner/name  overrides the slug parsed from `origin`.
# Exit:  0 all MATCHED | 1 ORPHAN found | 2 could not decide (UNKNOWN, forge or input unreadable)

set -uo pipefail

str_gitdir="${1:-}"
if [ -z "$str_gitdir" ]; then
	str_gitdir="$(git rev-parse --git-common-dir 2>/dev/null)" || {
		echo "UNKNOWN: not inside a git repository and no git-dir argument given" >&2
		exit 2
	}
	str_gitdir="$(cd "$str_gitdir" && pwd)"
fi
[ -d "$str_gitdir" ] || {
	echo "UNKNOWN: no such directory: $str_gitdir" >&2
	exit 2
}

str_repo="${BLUEPRINTX_REPO:-}"
if [ -z "$str_repo" ]; then
	str_url="$(git --git-dir="$str_gitdir" remote get-url origin 2>/dev/null || true)"
	str_repo="$(printf '%s' "$str_url" | sed -E 's#^.*github\.com[:/]##; s#\.git$##')"
fi

str_forge="$(mktemp -d)"
trap 'rm -rf "$str_forge"' EXIT

# REST on purpose (GraphQL is rate-limited more tightly). /issues returns PRs too.
bool_forge_ok=1
if [ -z "$str_repo" ]; then
	bool_forge_ok=0
	echo "UNKNOWN-FORGE: no BLUEPRINTX_REPO and no readable 'origin' remote" >&2
elif ! gh api --paginate "repos/$str_repo/issues?state=all&per_page=100" \
	>"$str_forge/all.json" 2>"$str_forge/err"; then
	bool_forge_ok=0
	echo "UNKNOWN-FORGE: could not read issues/PRs of '$str_repo': $(head -c 200 "$str_forge/err")" >&2
fi

FORGE_OK="$bool_forge_ok" python3 - "$str_gitdir" "$str_forge/all.json" <<'PY'
import json
import os
import pathlib
import re
import sys
import time
import unicodedata

INT_MIN_LEN = 40  # shorter normalised bodies match too loosely
FLOAT_NEAR = 0.8  # share of the local body's words found in one forge body: edited, not orphan


def norm(str_text: str) -> str:
    str_text = unicodedata.normalize("NFKC", str_text).casefold()
    str_text = re.sub(r"\[[x ]\]", "[ ]", str_text)
    return " ".join(str_text.split())


def forge_items(path_json: str) -> list:
    """Parse the concatenated JSON arrays `gh api --paginate` prints, one per page."""
    str_raw = pathlib.Path(path_json).read_text(encoding="utf-8")
    cls_dec = json.JSONDecoder()
    list_out, int_pos = [], 0
    while int_pos < len(str_raw):
        if str_raw[int_pos].isspace():
            int_pos += 1
            continue
        list_page, int_pos = cls_dec.raw_decode(str_raw, int_pos)
        list_out += [(str(d["number"]), norm(d.get("body") or "")) for d in list_page]
    return list_out


def verdict(str_body: str, list_forge: list) -> str:
    if len(str_body) < INT_MIN_LEN:
        return "UNKNOWN (too short to match)"
    list_hits = [f"#{n}" for n, b in list_forge if str_body in b]
    if len(list_hits) == 1:
        return f"MATCHED {list_hits[0]}"
    if list_hits:
        return f"UNKNOWN (ambiguous: {' '.join(list_hits)})"
    set_words = set(str_body.split())
    float_best, str_best = max(
        ((len(set_words & set(b.split())) / len(set_words), n) for n, b in list_forge),
        default=(0.0, ""),
    )
    if float_best >= FLOAT_NEAR:
        return f"UNKNOWN (near #{str_best}, {float_best:.0%} of words; edited since?)"
    return "ORPHAN"


bool_ok = os.environ["FORGE_OK"] == "1"
list_forge = []
if bool_ok:
    try:
        list_forge = forge_items(sys.argv[2])
    except (ValueError, KeyError, OSError) as cls_err:
        bool_ok = False
        print(f"UNKNOWN-FORGE: unparsable forge response: {cls_err}", file=sys.stderr)

int_orphans, int_unknown = 0, 0 if bool_ok else 1
list_files = sorted(pathlib.Path(sys.argv[1]).glob("*.md"))
if not list_files:
    print(f"no *.md bodies in {sys.argv[1]}")
for path_md in list_files:
    str_verdict, int_size, int_age = "UNKNOWN (unreadable body)", 0, 0
    try:
        cls_stat = path_md.stat()
        int_size, int_age = cls_stat.st_size, int((time.time() - cls_stat.st_mtime) // 86400)
        str_text = path_md.read_text(encoding="utf-8")
        str_verdict = verdict(norm(str_text), list_forge) if bool_ok else "UNKNOWN"
    except (OSError, UnicodeDecodeError):
        pass  # dangling symlink, permissions or non-UTF-8 bytes: undecidable, never ORPHAN
    int_orphans += str_verdict == "ORPHAN"
    int_unknown += str_verdict.startswith("UNKNOWN")
    print(f"{path_md}\t{int_size}B\t{int_age}d\t{str_verdict}")
sys.exit(2 if int_unknown else 1 if int_orphans else 0)
PY
