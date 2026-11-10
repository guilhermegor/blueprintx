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
`docs/` pages are meant to be written in — `en` (default) or `pt-BR`. The value reaches the scaffold as
`DOCS_LOCALE`, next to `LICENSE_CHOICE`, and every MkDocs-bearing Python skeleton renders it
into `theme.language` in the project's `mkdocs.yml`, so Material's search and UI strings
follow the pages. Running a `bin/scaffold/*.sh` script directly, without the menu, falls back
to `en`.

The locale is **checked**, not just recorded: the generated project's
`bin/check_docs_language.py` (pre-commit `check-docs-language`, the `tests.yml` step, and
`poe lint`) reads `theme.language` from `mkdocs.yml` and fails, naming the file and line, when a
prose paragraph of `README.md` or of a page under `docs_dir` is written in the other locale. The
page set comes from `mkdocs.yml` (`docs_dir`, `exclude_docs`), so a tree that config already
excludes is never read. Fenced code, YAML front matter, multi-line HTML comments, inline code, links and tables are
ignored, and a `docs-lang:ok` marker in a paragraph (outside inline code) skips it. A `theme.language` other than `en` or `pt-BR`
fails closed. Its Portuguese function words are the ones `check_comment_language.py` uses.

`lib-minimal` ships pt-BR pages: for `DOCS_LOCALE=pt-BR` the scaffold overwrites the English
`README.md`, every page it publishes (`index`, `usage`, `examples`, `faq`, `contributing`, `api/*`,
`changelog`, `releasing-1-0-0`) and the `mkdocs.yml` nav labels (`Início`, `Uso`, `Exemplos`,
`Referência da API`) with the translations kept under `templates/lib-minimal/docs/pt-BR/`,
`templates/python-common/docs/pt-BR/` and `templates/lib-minimal/README.pt-BR.md`. The README keeps
its `<!-- slug: -->` comments, so `check_readme_structure.sh` has no locale logic, and the docs
gate checks every translated page from the first commit. Nav labels live in
`templates/lib-minimal/docs/pt-BR/nav-labels.tsv`. codespell has no Portuguese dictionary, so the
generated project's `.codespellrc` skips `docs/` and `README.md` for `pt-BR`, and this repository's
skips the translations.

⚠️ The other Python skeletons still ship English pages. A project scaffolded as `pt-BR` from one of
them gets `<!-- docs-lang:untranslated -->` appended to every page that was not translated. The gate
skips a marked page and counts it in its summary line (`N skipped as docs-lang:untranslated`), so
the first lint is green and the untranslated pages stay visible. Delete the marker from a page once
it is translated; from then on the gate checks it.

A `--spec` file must carry `docs_locale` on an MkDocs skeleton. An omitted key used to become
`en` silently; it is now refused, naming the key, before anything is created. Skeletons that
ignore the locale (every one without an `mkdocs.yml`: `ts-lib`, `react-spa-webpack`,
`bash-cli`, `etcher-chromeos`, `ventoy-usb`) still default to `en`.

Two things the choice does **not** change:

- **Code stays English in every locale.** Comments and docstrings are English whether the
  docs are `en` or `pt-BR`; `bin/check_comment_language.py` enforces that and never reads
  `docs/`, which is why it needs no locale setting of its own.
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
| `--spec <file>` | Answer every prompt by name from a spec file instead of interactively — see [Named-key spec answers](spec-answers.md). |
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
