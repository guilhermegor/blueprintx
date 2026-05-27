# CLAUDE.md — bin/

Shell-script conventions for every `*.sh` in this directory.

## Shebang

- `#!/usr/bin/env bash` — user-facing scripts and any script that must be
  `$PATH`-portable (e.g. `venv.sh`, `run.sh`).
- `#!/bin/bash` — all other scripts (pre-commit hooks, CI helpers,
  internal utilities).

## Strict mode

```bash
set -euo pipefail
```

Use `set -e` (without `-u`/`-o pipefail`) only when the script sources
environment files that may contain unset variables (e.g. `db_setup_schema.sh`
which loads `.env` before the guard runs).

## Boilerplate (every script)

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Optional: cd "$SCRIPT_DIR/.." to run from the project root
source "$SCRIPT_DIR/lib/common.sh"
```

## Structure

All logic goes in named functions. A `main()` function wires them together
and is called at the bottom of the file:

```bash
main() {
    step_one
    step_two
}

main "$@"
```

## Status output

Use `print_status <level> <message>` (from `lib/common.sh`) for all
user-facing output. Never use bare `echo`/`printf` for status messages.

| Level     | Use for                        | Routing |
|-----------|--------------------------------|---------|
| `success` | completed action               | stdout  |
| `error`   | failure the user must see      | stderr  |
| `warning` | recoverable / skipped state    | stdout  |
| `info`    | progress narration             | stdout  |
| `config`  | a chosen setting being applied | stdout  |
| `debug`   | verbose diagnostics            | stdout  |
| `section` | banner separating major phases | stdout  |

Plain data the caller will capture (a path, a resolved value) may still go
to stdout via `echo`/`printf` — the rule is about *status*, not all output.

## Reading `.env` values

Use `_read_env_var VAR_NAME` (from `lib/common.sh`) to read a variable
from `.env` directly. This bypasses Make's `$` and `#` expansion, which
corrupts passwords containing those characters.

```bash
str_db_password
str_db_password=$(_read_env_var DB_PASSWORD)
```

## SC2155 — split `local x` from `x=$(…)`

`local x=$(cmd)` swallows `cmd`'s exit code. Declare then assign:

```bash
# ❌ exit code masked
local str_result=$(some_command)

# ✅ failures are visible
local str_result
str_result=$(some_command)
```

## Lint gate

CI runs the following before merging:

```bash
shellcheck --severity=warning --exclude=SC1091 bin/*.sh bin/lib/*.sh
bash -n bin/*.sh bin/lib/*.sh
```

`SC1091` (can't follow sourced file) is excluded globally because scripts
source siblings at runtime paths shellcheck cannot resolve. Any other
`# shellcheck disable=` must be line-scoped and carry a one-line reason comment.
