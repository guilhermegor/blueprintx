# Backlog — backport the wwdates lesson wave into BlueprintX templates

Branch: `feat/backport-wwdates-lessons`. One PR, commits grouped by cluster (A → B → C → D).
Plan: `~/.claude/plans/synchronous-bubbling-walrus.md`. **18 lessons + 1 advisory + 2 new
refinement captures.** Tick each box as it lands; update blueprintx's `docs/blueprintx-lessons.md`
mirror + the global store as lessons apply. Delete this file once every box is `[x]`.

## Cluster A — Secret-free tag-driven release + publish/consume wiring (lib-minimal)

- [x] 1. `versioning-origin-dependent-tag-driven-online` — **DONE + verified**. Chose the *safer*
  direction (inverts the plan's default, same outcome): template pyproject ships **static** (default),
  and `apply_online_tag_versioning` in `python_lib_minimal.sh` converts to `0.0.0` stub +
  poetry-dynamic-versioning + strips `bump_version` (Makefile+tasks.sh) when a remote is connected;
  offline stays static + keeps `bump_version`. Additive online edit is lower-risk than an offline
  regex-removal, and `make dev` (offline) keeps the simple path. Verified: conversion + strip on real
  files (version→0.0.0, dynamic block, backend swap, 0 bump_version refs, `make help`/`install_dist_locally`
  resolve, tasks.sh parses, TOML valid). **TODO: still verify a full online scaffold end-to-end.**
- [x] 2. `pypi-oidc-trusted-publishing` — **DONE**: OIDC workflow jobs (`pypa/gh-action-pypi-publish`,
  no tokens/twine, `id-token: write`) + language-agnostic OIDC directive (per-registry table) in
  `templates/common/.github/CLAUDE.md` + global lesson `prefer-oidc-over-stored-tokens-publishing.md`
  (indexed).
- [x] 3. `release-gate-runs-tests-not-attestation` — **DONE**. `run_tests` job (`uses: tests.yaml`)
  that `setup_and_build` `needs`; deleted `tests_passed` input + `check_tests`/attestation jobs.
- [x] 4. `changelog-no-ci-push-to-protected-main` — **DONE**: `changelog` target (`cz changelog`) in
  `make/library.mk` + tasks.sh; commitizen block in lib pyproject; no per-push `changelog.yaml`
  shipped; the release-time sequence ("regenerated from tags at release/build time; CI never commits
  CHANGELOG.md back to protected main") is documented in `docs/contributing.md` (Releasing section).
- [x] 5. `install-dist-locally-wheel-smoke-test` — **DONE**. `install_dist_locally` in lib-only
  `make/library.mk` + tasks.sh (guarded); `python -m build`, runtime pkg-name resolution, prints built
  wheel filename. Lib `__init__.py` now defines `__version__` (scaffold). Targets resolve (verified).
- [x] 6. `mkdocs-version-badge-from-git-tag` — **DONE**. `templates/common/docs_version/mkdocs_hooks.py`
  ported from wwdates: `git describe --tags --always`, strip `v`, fallback git → pyproject → `?`;
  bandit S603/S607 line-scoped.
- [x] 7. `pypi-oidc-publisher-claims-must-match` — **DONE** (workflow side): per-index envs
  `release_pypi`/`release_test_pypi`. **TODO:** document project-name/env claim-matching + pending
  publisher in lib CLAUDE.md + contributing (Cluster B / docs pass).
- [x] 8. `scaffold-publish-target-selection` — **DONE + verified**. `prompt_publish_targets` in
  `python_lib_minimal.sh` asks Q1 (publish to PyPI?), Q2 (staging/sandbox Test PyPI?), Q3 (consume
  from a non-official source?), resolved for Python; defaults preserve prior behaviour for `--dev`.
  Only the selected release workflows are emitted (Q1/Q2 gate the copies). Q3
  (`apply_private_consumer_source`) appends a documented, commented explicit-priority
  `[[tool.poetry.source]]` block (dependency-confusion guard) — verified pyproject stays valid TOML.
  The publish-target / private-source guidance is documented in `docs/contributing.md`
  ("Choosing publish targets"). Verified: scaffold shellcheck clean, prompt + Q3 wired in main.
- [x] 8c. `scaffold-repo-website-pages-docs-url` *(NEW lesson — wwdates mirror line 304, not in
  global store)* — **DONE + verified**. Online path: `apply_online_docs_url` points pyproject
  `homepage`/`documentation`/`[tool.poetry.urls] Documentation` at `https://<owner>.github.io/<repo>/`;
  `prompt_git_remote_setup` sets the GitHub repo **Website** field via `gh repo create --homepage`
  (+ `gh repo edit --homepage`). Offline stays generic. TODO: promote to global store.
- [x] 8b. `release-build-bypass-never-local-tag` *(NEW lesson — wwdates mirror only, not yet in
  global store)* — `release_pypi.yaml` build step stamps via `POETRY_DYNAMIC_VERSIONING_BYPASS`,
  **no local `git tag`, no `fetch-depth: 0`** on `setup_and_build` (byte-identical to the Test PyPI
  build step); the `v<version>` tag is a release artifact created only by `github_release` after
  build. **Satisfied by the faithful port of the workflows.** TODO: promote to the global store
  (`release-build-bypass-never-local-tag.md`) + README index; it supersedes the "release workflow
  tags vX.Y.Z and builds" phrasing in `versioning-origin-dependent-tag-driven-online`.

## Cluster B — Docs tooling (mkdocs-bearing tiers)

- [x] 9. `mkdocs-exclude-docs-no-inline-comments` — **DONE (all 5 tiers)**: comments moved to own
  lines in lib + mvc×2 + ddd×2 mkdocs.yml; verified no inline-comment leak in any.
- [x] 10. `docs-gh-pages-deploy-workflow` — **DONE (all 5 tiers)**: lib
  `lib-minimal/.github/workflows/docs.yaml` (with `cz changelog` regen); services use shared
  `common/docs_version/docs.yaml` (no changelog step); all scaffolds copy it (GitHub-remote-only).
  Lib pyproject homepage/documentation → gh-pages via `apply_online_docs_url` (lesson 8c). NOTE:
  service pyproject homepage URL wiring not added (services aren't published packages) — acceptable.
- [x] 11. `mkdocs-version-badge-needs-css` — **DONE (all 5 tiers)**: shared
  `common/docs_version/version-badge.css`; all 5 scaffolds copy it to `docs/stylesheets/`; `extra_css`
  wired in all 5 mkdocs.yml (verified).
- [x] 12. `mkdocs-standard-nav-sections` — **DONE**: lib nav now Home · Usage · API Reference ·
  Contributing · Changelog; created `docs/contributing.md` (dev setup, tests, wheel verify, PR gate,
  **releasing: tag-driven + OIDC + trusted-publisher claim-matching table + publish-target notes** —
  closes the release/claim-matching/publish-target docs-prose item), `docs/changelog.md`
  (`--8<-- "CHANGELOG.md"` single-source), placeholder root `CHANGELOG.md`, `pymdownx.snippets`
  wired; scaffold copies all three. Verified mkdocs.yml + scaffold.
- [x] 13. `no-source-repo-name-in-shipped-artifacts` — **DONE**: (1) `CONTRIBUTING.md` issues URL
  fixed (`github.com/guilhermegor/stpstone/issues` → relative `../../issues`, all tiers); (2)
  `utils/logs.py` module docstring genericized ("self-contained in-repo logging seam" — dropped the
  "vendored from stpstone" shipped-provenance, which reached the lib on the logs opt-in). NOTE: the
  remaining `stpstone` refs (service pyproject dep, `utils/dates.py` wrapper, `mypy.ini` stub-list
  example) are **legitimate** — stpstone is a real upstream dependency of the service tiers here,
  not a dehydrated source repo (unlike wwdates); leaving them is correct.
- [x] 14. `branch-work-ledger-in-docs-backlog` — **DONE (all 5 tiers)**: expanded the `docs/backlog/`
  bullet in every tier's `docs/CLAUDE.md` with the timestamped per-branch work-ledger convention
  (what-done/what-remains, cross-session, distinct from lessons, delete when complete).

## Cluster C — python-common code

- [x] 15. `rich-default-log-emitter` — **DONE + verified**. Added
  `python-common/src/utils/logs_emitter.py` (`LogsEmitter(LogEmitter)` → `CreateLog`); **fixed the
  latent `logs.py` bug** (stack-walker now matches the module's last dotted component, not a
  `startswith` prefix; skip-set = `{pydantic,typing,inspect,logging,logs,logs_emitter,retry}`);
  wired `logs_emitter` into all 4 service `copy_shared_utils` lists + the lib `copy_internal_utils`
  opt-in (logs) branch; added `test_logs_emitter.py` (is-a-LogEmitter, emits at any level,
  last-component skip regression). No cache manager exists in the templates → that part N/A.
  Verified: ruff clean, 3 tests pass, LogsEmitter imports + emits with rich `{Class}` context.
- [x] 16. `tabular-read-requires-contract` — **already implemented in blueprintx (verified)**: the
  ruff `TID251` banned-api gate exists in `python-common/ruff.toml` banning all `pd.read_*` +
  `ExcelFile` + `FileContract` construction, with `tabular_reader.py`/`contracts`/tests/`_internal`
  variants exempted. Confirmed TID251 **fires on aliased `pd.read_csv`** against venv ruff 0.11.13
  (no pygrep fallback needed). `read_table` already has `list_columns` + headerless (`header=None`,
  `names=`) + `int_header_row`. The `enforce-tabular-contract-via-ruff-banned-api` capture is **moot**
  (already embodied). MINOR OPTIONAL gap: no `int_skip_rows` for the headerless-AND-banner combo.

## Cluster D — Conventions (CLAUDE.md only)

- [x] 17. `never-build-on-transitive-dependency` — **DONE**: direct-dep guardrail added to lib
  `CLAUDE.md` Conventions. (Universal rule; could also be propagated to service-tier CLAUDE.md — optional follow-up.)
- [x] 18. `no-redundant-package-name-subfolder` — **DONE**: flat-layout guidance in lib `CLAUDE.md`
  Architecture; promoted to global store (`no-redundant-package-name-subfolder.md` + README).
- [x] adv. `reuse-target-repo-implementation` — **DONE**: migration-reuse advisory in lib `CLAUDE.md`
  Architecture; promoted to global store (`reuse-target-repo-implementation.md` + README).

## NEW lesson landed mid-flight — `self-enabling-actions-pages-deploy` (user added to global store)

- [x] **`docs.yaml` rewritten to Actions-native Pages deploy** (lib + shared service): `actions/
  configure-pages@v5` (`enablement: true`) + `upload-pages-artifact@v3` + `deploy-pages@v4`,
  `permissions: pages: write / id-token: write`, `concurrency: pages`. **Supersedes** the
  `mkdocs gh-deploy` model (which can't self-enable Pages → first-publish 404). Verified both YAMLs.
- Scaffold Website-field wiring (`gh repo create/edit --homepage`) + pyproject URLs already satisfy
  the Website half of `scaffold-sets-repo-website-to-pages-docs-online-mode`; Pages enablement is now
  the workflow's job (configure-pages). No gap.

## Global-store lesson reconciliation (user edited the store concurrently)

- User added canonical `release-build-stamps-version-via-bypass-not-git-tag.md`,
  `scaffold-sets-repo-website-to-pages-docs-online-mode.md`, `self-enabling-actions-pages-deploy.md`.
- My two duplicates (`release-build-bypass-never-local-tag.md`, `scaffold-repo-website-pages-docs-url.md`)
  were **deleted** to avoid divergence.
- My 3 non-duplicate lessons kept + indexed: `prefer-oidc-over-stored-tokens-publishing.md`,
  `no-redundant-package-name-subfolder.md`, `reuse-target-repo-implementation.md`.
- Still TODO: `enforce-tabular-contract-via-ruff-banned-api.md` (with Cluster C).

## Verification / follow-ups

**Component-level verification DONE (static + unit):** all 5 scaffolds `bash -n` + shellcheck clean;
all template YAML parse (5 mkdocs + release ×2 + docs ×2); ruff clean on changed Python
(`logs.py`, `logs_emitter.py`, `mkdocs_hooks.py`, `test_logs_emitter.py`); lib pyproject valid TOML
(static default) + online-conversion transform verified (0.0.0 stub, dynamic block, bump_version
stripped) + offline path unchanged; `install_dist_locally`/`changelog`/`help` targets resolve;
TID251 confirmed firing on aliased `pd.read_csv`; `logs_emitter` regression test passes (3/3);
Q3 consumer-source append keeps pyproject valid.

**LIVE end-to-end verification still to run (needs a real scaffold + venv + remote + act):**
- [ ] `make dev` online **and** offline with a LONG package name; `make lint` clean (no drift).
- [ ] `act` on release workflows + `docs.yaml` before pushing (per the standing act rule).
- [ ] `mkdocs build --strict` in a generated tree; inspect `site/` for no leaked internal docs.
- [ ] `poetry run pytest tests/unit/` green in a generated tree.

**Housekeeping:**
- [ ] Update the repo mirror `docs/blueprintx-lessons.md` with this wave (global store already current).
- [ ] Commit + open PR (only on explicit user request).
