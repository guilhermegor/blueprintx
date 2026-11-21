# README layout gate

`templates/common/bin/check_readme_structure.sh` (blueprintx#867) fails when a README leaves
the shared layout. BlueprintX runs it on its own `README.md` and on every template README
(`bin/ci/check_readme_structure.sh`, the pre-commit hook `readme-structure` and the
`readme-structure` CI job). Every generated project gets a copy at
`bin/check_readme_structure.sh` plus its parser `bin/lib/md_structure.sh`, and runs it on
`README.md` (pre-commit hook and `poe check_readme_structure` in Python projects, a
pre-commit hook in `bash-cli` and `etcher-chromeos`, `make lint` in `ventoy-usb`, `npm run
lint:readme` and lint-staged in the TypeScript skeletons).

## Why

Before the gate there were two unrelated README families: emoji headings with a logo inside the
H1 (the root, `python-common`, `react-spa-webpack`) and plain headings with their own section
list (`bash-cli`, `ts-lib`, `etcher-chromeos`, `ventoy-usb`). Nothing checked either, and the
Python template rendered `[LinkedIn](${LINKEDIN_URL})` with a variable no scaffold ever set.

## The contract

Sections are matched by a **slug marker**, never by heading text, so a translated heading
(`## Estrutura do projeto`) conforms without renaming. The marker is an HTML comment above the
heading (blank lines between are fine): `<!-- slug: install -->`.

| Slot | Slugs, in this order |
|---|---|
| Core, first | `overview`, optional `features`, `library` only: `documentation`, then `getting-started`, `install`, `usage`, `project-structure`, `development` |
| Archetype | `library`: `public-api`, `publishing`. `cli`: `releasing`. `spa`: `deployment`. `service`: `configuration`. `usb-tool`: `payload`. `toolkit`: `commands` |
| Core, last | `contributing`, `license`, `authors`, `useful-links` |

Outside `--strict`, other sections are allowed anywhere and only the slugged ones are ordered.

### Closed H2 vocabulary (`--strict`)

`--strict` closes the list. The gate passes it for `README.template.md`, every
`templates/*/README.md` and every generated README (`bin/ci/check_readme_structure.sh`); the
root `README.md` and a vendored copy in another repository run without it.

- Every H2 carries a slug from the table above, narrowed to the README's archetype: `overview`,
  `features`, `getting-started`, `project-structure`, `development`, `contributing`, `license`,
  `authors`, `useful-links`, the archetype's own slugs and, for `library`, `documentation`. An
  unslugged H2, or a slug outside that set (`releasing` in a `usb-tool`), fails.
- An extra section is an H3 under an existing slug: a Docker recipe is `### Docker` under
  `deployment`, a manifest reference is `### The manifest` under `usage`. A README that needs an
  H2 the vocabulary lacks adds the slug to the gate and to this page first.
- `features` is required in every archetype except `toolkit` (no user-facing surface).
- Template parity: a template-owned `README.md` keeps the H2 order of
  `templates/common/README.template.md` for its archetype, because the order check and the
  vocabulary check run on it too.

Further rules:

- The first line is `<!-- readme-archetype: NAME -->`, one of the archetypes above.
- No H1 to H6 contains an emoji, `<img>`, `![...]` or `<picture>`. The logo sits on its own
  line under the H1. Badges and images stay allowed in the body.
- `features` is optional without `--strict`: its position is checked only when the section is present.
  `documentation` is required for `library` and holds the docs site URL plus the local serve command: `bash bin/poe_exec.sh docs_serve`
  for Python libraries, `npm run docs:start` for TypeScript libraries.
- `install` in the `library` archetype has two `####` subparts, in both languages: "As a
  dependency" (`pip install` and `poetry add`, or `npm install` for ts-lib; pt-BR "Como
  dependência") and "For development" (clone plus `bin/venv.sh` and `poetry run poe init` for
  Python, clone plus `npm install` for ts-lib; pt-BR "Para desenvolver"). Service, CLI, SPA and
  USB-tool archetypes keep the single clone-and-bootstrap block, since that is their real
  install. The English Python subparts come from an `only: library` block in
  `templates/python-common/README.md`, which every Python tier renders; the pt-BR copy is written
  out in `templates/lib-minimal/README.pt-BR.md`, so edit both together. The package name is the
  project name, and the commands work once the first release is published. The gate reads `####`
  headings inside a slug section without complaint.
- The logo is centered on its own line under the H1 (`<p align="center"><img ... width="200"></p>`),
  never inside the heading.
- Badge order: status, python, pypi, downloads, docs, linting, mypy, coverage, license, issues,
  contributions. `pypi` and `downloads` are `library` only; no Snyk License advisor badge. The
  downloads badge is `img.shields.io/pepy/dt/<name>` for Python and `img.shields.io/npm/d18m/<name>`
  for ts-lib: shields.io always answers HTTP 200 and prints "not found" for an unpublished package,
  so it is safe before the first publish (measured 2026-11-07 on both endpoints). They count
  different windows: `pepy/dt` is all-time, `npm/d18m` the last 18 months, because npm's API
  serves no all-time total. `static.pepy.tech` stays banned (404 until indexed,
  blueprintx#948) and so does `pypi/dm` (wrong figure). The order is a review convention, not a gate.
- README images use absolute `raw.githubusercontent.com` URLs (logo, coverage badge), because
  `readme = "README.md"` ships to PyPI where relative paths break. `scaffold_render_readme` fills
  them from `GITHUB_USERNAME` and `PROJECT_NAME`.
- A footer closes every README, template-owned or rendered: a rule, then `<sub>` text, no heading (so no
  slug), reading "Generated from the <tier> template via
  [BlueprintX](https://github.com/guilhermegor/blueprintx)" (`README_TIER`) followed by
  any project disclaimer. The link is absolute, like the images, because the README ships to
  PyPI where relative links break, and the structure gate reports a footer without it.
  A missing footer passes by default, so a repository that vendors the gate is not forced to
  add one; pass `--require-footer` to fail a README with no `<sub>Generated from` line or whose
  footer has no `---` rule above it. `bin/ci/check_readme_structure.sh` passes it for
  `README.template.md`, every `templates/*/README.md` and every generated project.
  Disclaimers **and** credits or attributions go here, not in the body. A disclaimer:
  "Unofficial, community library. Not affiliated with or endorsed by the BCB." A credit:
  "Logo photo by Jane Doe on Pexels." The gate reports a link to `pexels.com`, `unsplash.com`
  or `pixabay.com` above the footer; disclaimer wording is locale-dependent, so it is not
  gated. The footer line may be localized ("Gerado a partir do template ..."). On the docs
  site the same slot is `copyright:` in `mkdocs.yml` (Material renders it in the page
  footer), shipped holding the "Generated from ... via BlueprintX" line.
- Every list item under `authors` carries a `github.com/<user>` link and a
  `linkedin.com/in/<handle>` link, and none uses the placeholder
  `linkedin.com/in/your-linkedin-handle`.
- Outside `--template`, an unrendered `${VAR}` is a finding.

Fenced code and HTML comments are ignored, so a heading inside a fence does not count. The
heading-tree parser is `templates/common/bin/lib/md_structure.sh`, shared with
`bin/ci/check_pr_template.sh`: one parser, so the two gates cannot drift.

## The canonical template and the archetype

`templates/common/README.template.md` is the reference shape. Each skeleton declares its
archetype in `skeleton.meta` as `readme_archetype=` (optional; `bin/ci/validate_meta.sh`
rejects a value outside the list the gate itself prints with `--list-archetypes`).

The Python skeletons share one README. `bin/lib/scaffold_readme.sh` renders it per skeleton: a
block between `<!-- only: service -->` and `<!-- /only -->` is kept only when the skeleton's
archetype is listed, so a service gets `Configuration` and a library gets `Public API` and
`Publishing`. `--template` mode accepts `${...}` placeholders, so the template READMEs are
checked unrendered; the archetype slugs are only enforced on the rendered README.

## `LINKEDIN_URL`

The scaffold resolves it once, in `resolve_linkedin_url`:

1. the `LINKEDIN_URL` environment variable;
2. otherwise, on a real terminal (`[ -t 0 ]`), a prompt for a profile URL or handle;
3. otherwise the placeholder `https://www.linkedin.com/in/your-linkedin-handle`, with a
   warning. The gate flags it, so the link cannot stay empty or fake unnoticed.

The prompt checks the terminal itself instead of using `BLUEPRINTX_STDIN_ANSWERS`: spec-driven
scaffolds feed answers by position, and one more prompt would shift every stored answer. Set
`LINKEDIN_URL` in that case.

## Required check

The `readme-structure` job is listed in `.github/required-checks.json`; the repository owner
adds `README structure gate — plain headings, slug sections, Authors links` to the `main`
ruleset (`docs/required-status-checks.md`).
