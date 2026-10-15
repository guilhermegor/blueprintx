#!/usr/bin/env bash
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
