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
| Core, first | `overview`, `getting-started`, `install`, `usage`, `project-structure`, `development` |
| Archetype | `library`: `public-api`, `publishing`. `cli`: `releasing`. `spa`: `deployment`. `service`: `configuration`. `usb-tool`: `payload`. `toolkit`: `commands` |
| Core, last | `contributing`, `license`, `authors`, `useful-links` |

Other sections are allowed anywhere; only the slugged ones are ordered.

Further rules:

- The first line is `<!-- readme-archetype: NAME -->`, one of the archetypes above.
- No H1 to H6 contains an emoji, `<img>`, `![...]` or `<picture>`. The logo sits on its own
  line under the H1. Badges and images stay allowed in the body.
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
