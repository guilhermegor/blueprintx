# **Offline Wheelhouse**

How a scaffolded Python project installs its dependencies on a machine that cannot reach
PyPI at all — a corporate box behind a TLS-inspecting proxy that blocks the index outright,
not merely one that needs its CA trusted. Ships in every Python skeleton via
`templates/python-common/bin/build_wheelhouse.sh` (blueprintx#299, pieces 1-3 of #127).

> **See also:** [Troubleshooting](troubleshooting.md) for the corporate-CA half of this
> problem · [FAQ](faq.md).

---

## Why this exists

[`poe venv`](cli-reference.md) already fails **loudly** on a blocked index instead of
silently leaving an empty `.venv` behind (`verify_venv_imports.py`, blueprintx#127 piece 4).
Failing loudly names the problem; it does not fix it. When the index is genuinely
unreachable — not just untrusted — the only remedy is to bring the wheels with you.

Two probes that lie, worth repeating because both were the actual cause the first time this
was measured:

- **`curl` reaching pypi.org proves nothing about `pip`.** A reachable host and a usable
  package index are different questions.
- **A `pip install` that never needed `--upgrade` never queried the index.** A probe package
  already satisfied locally passes even when the network is fully blocked.

## Building the wheelhouse (on a machine WITH internet access)

```bash
poe wheelhouse
```

This writes a **sibling** payload — `../_wheels/<repo-name>/`, one level *outside* the
project — never inside it: code changes constantly, wheels almost never, and a payload
inside the repo would be a `git add` candidate and would not survive a re-clone. It is
per-repo because sibling projects pin different versions.

Three steps, run in order:

1. **Export** the locked, marker-annotated dependency set via `poe export_deps`'s own
   `poetry export` (reused, not reimplemented).
2. **Select** — evaluate each requirement's PEP 508 marker against a TARGET environment,
   not the build machine's own. `pip download --platform` does **not** do this: it evaluates
   markers against the CURRENT interpreter, so a Linux build downloading for a Windows
   target silently drops `pywin32` (declared with `markers = "sys_platform == 'win32'"`)
   with no error. This step also prunes whichever DB driver `DB_BACKEND` did not select —
   the native-DB tiers ship `pyodbc`/`oracledb`/`psycopg`/`mysql-connector-python`
   **unconditionally** (the backend is chosen at runtime from config, not at scaffold time),
   so shipping all four in the wheelhouse is pure waste (measured 65 MB → 45 MB).
3. **Pack** — zip the downloaded wheels, split into fixed-size parts, and write
   `manifest.json` recording every part's sha256 plus the whole archive's sha256. A truncated
   `cat` of 1-of-5 parts otherwise writes a zip whose only symptom is `End-of-central-directory
   signature not found` — a message naming nothing useful. The manifest is what lets the
   install side catch that *before* writing a broken archive.

### Targeting a different machine than the one you're building on

Unset, the wheelhouse targets the build machine's own Python version, platform and
architecture — the common case (build and target are the same OS, only the network
differs). Override any of these to build for a **different** target:

| Variable | Default | Meaning |
|---|---|---|
| `WHEELHOUSE_DIR` | `../_wheels/<repo-name>` | Where the payload is written |
| `WHEELHOUSE_TARGET_PYTHON_VERSION` | build machine's | Target `python_version` for marker evaluation |
| `WHEELHOUSE_TARGET_SYS_PLATFORM` | build machine's | Target `sys.platform` (`win32`/`linux`/`darwin`) |
| `WHEELHOUSE_TARGET_PLATFORM_MACHINE` | build machine's | Target `platform.machine()` (`x86_64`, `AMD64`, ...) |
| `WHEELHOUSE_TARGET_IMPLEMENTATION` | `cpython` | Target Python implementation |
| `WHEELHOUSE_PIP_PLATFORM` | unset | pip's own `--platform` tag (`win_amd64`, `manylinux2014_x86_64`, ...) — needed only for a genuinely cross-platform binary download; see below |
| `WHEELHOUSE_PIP_ABI` | unset | pip's own `--abi` tag, paired with `WHEELHOUSE_PIP_PLATFORM` |
| `WHEELHOUSE_PART_MB` | `45` | Split-part size |
| `DB_BACKEND` | unset | `postgresql`/`mysql`/`oracle`/`mssql` — prunes the other native-DB drivers |

`WHEELHOUSE_TARGET_*` only changes **which packages are selected** (the marker-evaluation
step). It does not by itself make pip fetch a binary wheel built for a different platform —
that needs `WHEELHOUSE_PIP_PLATFORM` too, using pip's own platform-tag vocabulary
(deliberately not re-derived here; see
[pip's own `--platform` docs](https://pip.pypa.io/en/stable/cli/pip_download/)). Most users
building and installing on the same OS never need to set it.

## Transferring the payload

Copy `../_wheels/<repo-name>/` (USB drive, internal file share, whatever the corporate
network policy allows) so it sits **beside** the offline clone of the project — the same
sibling relationship it was built in.

## Assembling and installing (on the OFFLINE target)

```bash
poe wheelhouse_assemble
pip install --no-index --find-links ../_wheels/<repo-name>/wheels -r requirements-lock.txt
```

`wheelhouse_assemble` accepts three payload shapes, tried in order, and **REFUSES** rather
than writing a broken result:

1. **Loose wheels** already sitting in the output directory — nothing to do.
2. **Manifest + split parts** (what `poe wheelhouse` produces) — every part's presence and
   sha256 is checked against `manifest.json` before concatenation, and the reassembled
   archive's own sha256 is checked again before extraction. A missing part, a part-count
   mismatch, or a single corrupted byte aborts with a named cause instead of silently
   producing a truncated `wheels/` directory.
3. **A bare `wheelhouse.zip`** with no manifest — accepted as-is (e.g. someone zipped the
   `wheels/` folder by hand for a quick transfer); there is nothing to verify it against, so
   this path is explicitly unverified.

## Should-fail witness

Verified against an actually blocked index, not merely an absent one — a reachable-but-empty
index still looks like success to a probe that never asked for the right thing:

```bash
PIP_INDEX_URL=http://127.0.0.1:1/simple poe wheelhouse_assemble
pip install --no-index --find-links <wheels-dir> -r requirements-lock.txt
```

The install must succeed with the network fully denied. A wheelhouse that is never exercised
this way is not verified — it is a directory.
