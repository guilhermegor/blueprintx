#!/usr/bin/env bash
# Fail when a templates/*/package.json declares a dependency its package-lock.json does not
# carry, the drift that makes `npm ci` refuse to install (blueprintx#588, regression of #464).
# Pure JSON comparison (python3), so it runs offline in pre-commit. A tier with no lockfile is
# skipped, not failed: not every tier ships one.
#
# Usage: bash bin/ci/check_lockfile_sync.sh [--root <dir>]   (default: repo root)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
[ "${1:-}" = "--root" ] && ROOT="$(cd "$2" && pwd)"

python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
sections = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
errors, checked = [], 0

for path_pkg in sorted(root.glob("templates/*/package.json")):
    path_lock = path_pkg.with_name("package-lock.json")
    if not path_lock.exists():
        continue
    checked += 1
    tier = path_pkg.parent.name
    pkg = json.loads(path_pkg.read_text())
    packages = json.loads(path_lock.read_text()).get("packages", {})
    top = packages.get("", {})
    optional_peers = {n for n, m in pkg.get("peerDependenciesMeta", {}).items() if m.get("optional")}
    for section in sections:
        declared, locked = pkg.get(section, {}), top.get(section, {})
        for name in sorted(set(locked) - set(declared)):
            errors.append(f"{tier}: {section} '{name}' is in package-lock.json but not package.json")
        for name, spec in declared.items():
            if locked.get(name) != spec:
                errors.append(f"{tier}: {section} '{name}' ({spec}) is not in package-lock.json")
            elif f"node_modules/{name}" not in packages and name not in optional_peers:
                errors.append(f"{tier}: '{name}' has no resolved entry in package-lock.json")

if errors:
    print("\n".join(errors), file=sys.stderr)
    print("Regenerate: npm install --package-lock-only (in a rendered copy of the tier)"
          " and commit the lockfile with the package.json change.", file=sys.stderr)
    sys.exit(1)
print(f"package.json and package-lock.json in sync ({checked} tier(s) with a lockfile).")
PY
