# **Troubleshooting**

What broke while wiring this site's brand assets and reader routing (issue #250), the cause,
and the change that closed it. Kept as a record — see [Contributing](contributing.md) if a
future change needs to add to it.

> **See also:** [FAQ](faq.md) · [Get Started](get-started.md).

---

## The home page fetched its own logo over the network (fixed)

**Symptom:** `docs/index.md` embedded the logo as
`https://raw.githubusercontent.com/guilhermegor/blueprintx/main/assets/logo.png` instead of a
local path.

**Cause:** the asset lived at `assets/logo.png`, outside `docs_dir`. MkDocs only serves what is
under `docs/`, so there was no local path to point at, and the remote URL was substituted
instead.

**Why it mattered:** `bin/ci/check_docs_build.sh` (`mkdocs build --strict`) does not fetch
images, so a build behind a network-restricted or TLS-inspecting proxy — or fully offline —
still passed with a broken image. The remote URL also pinned every published version of the
site to the `main` branch of a public repo: renaming, moving, or privatising the repo would
have broken the logo retroactively in every past build.

**Fix:** copied the asset to `docs/assets/logo.png` and referenced it with a relative path.
`assets/logo.png` at the repo root is left in place — `README.md` still points at it directly,
and GitHub renders that path relative to the repo root regardless of `docs_dir`.

## No `theme.logo` / `theme.favicon` (fixed)

**Symptom:** the header showed Material's default book glyph instead of the project mark.

**Cause:** `mkdocs.yml` set `theme.name: material` and a `palette`, nothing else. Material only
swaps in a logo/favicon when `theme.logo` / `theme.favicon` are set.

**Fix:** added both, pointing at `assets/logo.png` (path is resolved relative to `docs_dir`).

## The hero image had no width control (fixed)

**Symptom:** the logo on the home page rendered at full content width — there was no
`extra_css` entry in `mkdocs.yml` for a width rule to live in.

**Fix:** added `docs/stylesheets/extra.css` (registered via `extra_css:`) with a `.hero-logo`
rule, and switched the home-page image from a bare markdown `![]()` to an `<img class="hero-logo">`
tag — the markdown extensions enabled here do not include `attr_list`, so a class cannot be
attached to a markdown image; the raw HTML form can carry one.

## The home page had no reader routing (fixed)

**Symptom:** `docs/index.md` was a flat feature list — a first-time reader had no
task-oriented way to find the page they needed.

**Fix:** added a "Where to start" table ("If you want to… / Read…") and a `!!! info` admonition
naming the intended audience, ahead of the feature list.

## The logo file's bytes do not match its extension (recorded, not changed)

**Found while wiring the above:** `assets/logo.png` (and its `docs/assets/` copy) is JPEG-encoded
data (`file` reports `JPEG image data, JFIF standard 1.01`) despite the `.png` extension.
Browsers sniff image content rather than trusting the extension, so this renders correctly in
every path exercised here (hero image, `theme.logo`, `theme.favicon`, GitHub's README render).
Left unchanged: re-encoding risks a visible quality/color shift in a brand asset, which is a
design decision, not a docs-wiring one. Recorded here so the next person debugging an
image-related build oddity does not waste time on it.

---

## Decisions — what belongs in the scaffolded templates

Issue #250 asked which of the fixes above should also apply to `templates/*/mkdocs.yml`, since
every "yes" reaches every generated project. Recorded here (this page's edits stop at
BlueprintX's own site — none of these were implemented in `templates/`):

| Item | Decision | Why |
|---|---|---|
| `theme.logo` / `theme.favicon` wired to the shipped `templates/python-common/assets/logo_lorem_ipsum.png` | **Yes** | Same one-line config addition, and the placeholder asset already ships in every Python skeleton. Needs a template-side change — out of this issue's surface, tracked separately. |
| Remote-asset defect (logo fetched over the network) | **No action needed** | Audited every `templates/**/docs/*.md` for `raw.githubusercontent.com`: no matches. The defect was BlueprintX-only. |
| `extra_css` + role-based nav highlighting | **No, for now** | A generated project ships a single skeleton, not BlueprintX's multi-skeleton menu — there is no equivalent "reader role" split to highlight. Revisit only if a skeleton grows internal audience splits (e.g. operator vs. developer pages). |
| Home-page "Where to start" routing table | **No** | Same reasoning: a generated project's `index.md` already describes one skeleton, so there is nothing to route between. |
| Troubleshooting / "what broke" page | **Deferred to #240** | #240 already owns scaffolding an incident-record page into generated projects; this page is BlueprintX-only and should not fork that work. |
