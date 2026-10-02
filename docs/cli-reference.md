# **CLI Reference**

Every command BlueprintX exposes. The interactive scaffolder is driven through `make` targets
(or `bash tasks.sh <target>` where `make` is unavailable) and the `blueprintx` CLI flags.

> **See also:** [Get Started](get-started.md) for a first run · [FAQ](faq.md).

---

## Scaffolding

| Command | What it does |
|---------|--------------|
| `make new` | Interactive scaffolder — prompts for language, skeleton, project name, license, and documentation locale. |
| `make preview` | Show every skeleton's structure without creating anything. |
| `make dev` | Scaffold into a temp dir (preserved on exit). |
| `make dev_clean` | Scaffold into a temp dir, auto-deleted on exit. |
| `make dry_run` | Print the chosen skeleton structure; write no files. |

## Documentation locale

The last `make new` prompt asks which language the **generated project's** `README.md` and
`docs/` pages are written in — `en` (default) or `pt-BR`. The value reaches the scaffold as
`DOCS_LOCALE`, next to `LICENSE_CHOICE`, and every MkDocs-bearing Python skeleton renders it
into `theme.language` in the project's `mkdocs.yml`, so Material's search and UI strings
follow the pages. Running a `bin/scaffold/*.sh` script directly, without the menu, falls back
to `en`.

Two things the choice does **not** change:

- **Code stays English in every locale.** Comments and docstrings are English whether the
  docs are `en` or `pt-BR`; the generated project's `bin/check_comment_language.py` enforces
  that boundary and never reads `docs/`, which is why it needs no locale setting of its own.
- **BlueprintX's own prose.** This repository is en-US with no exceptions (blueprintx#194).
  The prompt describes the project being created, not the tool creating it.

Only MkDocs skeletons consume the value today; `ts-lib` (Docusaurus), `react-spa-webpack` and
`bash-cli` receive `DOCS_LOCALE` and ignore it.

## `blueprintx` flags

| Flag | Effect |
|------|--------|
| `blueprintx new` | Create a new project interactively. |
| `blueprintx preview` | Show available skeleton structures. |
| `--dev` | Scaffold into a temp directory (preserved). |
| `--dry-run` | Preview structure without creating files. |
| `--clean` | Delete the temp dir on exit (with `--dev`). |
| `-V`, `--version` | Print the version (from the git tag) and exit. |
| `-h`, `--help` | Show usage. |

## Docs and install

| Command | What it does |
|---------|--------------|
| `make mkdocs_serve` | Install docs deps and serve this site at http://0.0.0.0:8000. |
| `make install` | Install `bin/` + `templates/` under `/usr/share/blueprintx` (needs sudo). |

## Adding a skeleton

Create `templates/<name>/` with a `skeleton.meta`, write a scaffold script under
`bin/scaffold/`, and the menu updates automatically — no change to `blueprintx.sh`. See
[Contributing](contributing.md).
