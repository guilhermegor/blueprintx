#!/usr/bin/env bash
# patch_package_json — add "scripts"/"dependencies" entries to a generated
# project's package.json. Shared by every ts-* scaffold (#397).
#
# ⚠️ The path travels through argv and is NEVER interpolated into the Python source. Four
# copies of this block wrote open('$project_path/package.json') inside a double-quoted
# `python3 -c`, so a project path holding an apostrophe (…/Joao's app/) ended the Python
# string literal — and with a newline it injected statements. The break is not exotic: an
# apostrophe in a directory name is enough (fixed for ts_react_app.sh by #396).
#
# Extracted here rather than left copy-pasted into ts_lib.sh (#397): both scaffolds already
# source bin/lib/ for common.sh and scaffold_git_remote.sh, and ts_lib.sh's own git-diff
# offline-mode block wants the exact same three-script patch ts_react_app.sh's does — the
# one-implementation rule (CLAUDE.md) applies as much here as it did to the git remote flow.
#
# This is a sourced lib: define-only, no work on source.
patch_package_json() {
    local pkg_path="$1" section="$2"
    shift 2

    python3 - "$pkg_path" "$section" "$@" <<'PYEOF'
import json
import sys

path_pkg, str_section = sys.argv[1], sys.argv[2]
with open(path_pkg) as cls_file:
	dict_pkg = json.load(cls_file)
dict_section = dict_pkg.setdefault(str_section, {})
for str_pair in sys.argv[3:]:
	str_key, _, str_value = str_pair.partition("=")
	dict_section[str_key] = str_value
with open(path_pkg, "w") as cls_file:
	json.dump(dict_pkg, cls_file, indent=2)
	cls_file.write("\n")
PYEOF
}
