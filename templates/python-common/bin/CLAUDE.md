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

## Cross-platform env resolution (`lib/bootstrap.sh`)

`lib/bootstrap.sh` is a sourced lib (like `lib/common.sh`) holding the
cross-platform setup logic shared by `venv.sh`, `run.sh`, and
`corporate_ca.sh`. It runs no work on source — the caller invokes
`bootstrap_init` first, then the helpers it needs:

| Function | Purpose |
|----------|---------|
| `bootstrap_init` | Resolve + export `OS_TYPE`, `PYTHON`, `PROJECT_ROOT`, `BIN_DIR`, `CORPORATE_CA_PEM`, `PY_VERSION`. Call once before the rest. |
| `detect_os` | `linux` / `macos` / `windows` / `unknown` from `uname`. |
| `resolve_python` | First working of `python3` → `python` → `py`. |
| `resolve_poetry` / `run_poetry` | Populate the `POETRY_CMD` array (`poetry` or `python -m poetry`) and invoke it. |
| `ensure_poetry` | Resolve Poetry, installing the pinned version (`requirements.txt`) when absent. |
| `ensure_python_version` | **pyenv-preferred, system-Python fallback** — pin via pyenv when present, else use the system interpreter with a version-mismatch warning (for hosts where pyenv cannot be installed). |
| `wire_corporate_ca` | No-op unless `bin/corporate_ca.pem` exists; when it does, export `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE`/`CURL_CA_BUNDLE`/`PIP_TRUSTED_HOST`, append the CA to the certifi bundle, and point Poetry at it. |

Source both libs after `SCRIPT_DIR`, with a `source=` directive so shellcheck
can follow the second one:

```bash
source "$SCRIPT_DIR/lib/common.sh"
# shellcheck source=bin/lib/bootstrap.sh
source "$SCRIPT_DIR/lib/bootstrap.sh"
```

`corporate_ca.sh` is the **manual** generator for `bin/corporate_ca.pem` — it
disables TLS verification *on purpose* to capture a TLS-inspecting proxy's CA,
so run it only on such a network. The pem is git-ignored; its mere presence
opts a project into corporate-SSL mode on the next `make venv` / `make run`.

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
