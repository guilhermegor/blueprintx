# **CLI Reference**

Every command BlueprintX exposes. The interactive scaffolder is driven through `make` targets
(or `bash tasks.sh <target>` where `make` is unavailable) and the `blueprintx` CLI flags.

> **See also:** [Get Started](get-started.md) for a first run · [FAQ](faq.md).

---

## Scaffolding

| Command | What it does |
|---------|--------------|
| `make new` | Interactive scaffolder — prompts for language, skeleton, and project name. |
| `make preview` | Show every skeleton's structure without creating anything. |
| `make dev` | Scaffold into a temp dir (preserved on exit). |
| `make dev-clean` | Scaffold into a temp dir, auto-deleted on exit. |
| `make dry-run` | Print the chosen skeleton structure; write no files. |

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
| `make mkdocs_server` | Install docs deps and serve this site at http://0.0.0.0:8000. |
| `make install` | Install `bin/` + `templates/` under `/usr/share/blueprintx` (needs sudo). |

## Adding a skeleton

Create `templates/<name>/` with a `skeleton.meta`, write a scaffold script under
`bin/scaffold/`, and the menu updates automatically — no change to `blueprintx.sh`. See
[Contributing](contributing.md).
