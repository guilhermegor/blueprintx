---
name: Cut 1.0.0
about: The blocked path to the first stable release
title: "Cut 1.0.0"
labels: ["state:blocked"]
---

<!--
issue-template-guard: require "**Blocked by:**" if-label state:blocked
-->

**Blocked by:** decision: every other open issue is implemented or labelled `post-1.0`; re-read the open list before starting

## What / Why

1.0.0 is the moment this library promises its public API. The version policy changes from
0.x rules (breaking is a MINOR, feat and fix are a PATCH) to full semver. The release
workflow refuses a 0.x to 1.0.0 jump while an open issue lacks the `post-1.0` label; see
`docs/releasing-1-0-0.md`.

## Checklist

- [ ] **Queue empty:** every remaining issue is implemented, or labelled `post-1.0` by the owner, never silently dropped
- [ ] **Example boilerplate removed:** the scaffold's placeholder module, its test, its re-export and every doc, example or smoke check that still shows it are deleted or replaced with real usage (the placeholder files are named in `AGENTS.md`)
- [ ] **Docs audit against the code:** README, CONTRIBUTING, SECURITY, CHANGELOG, everything under `docs/` (minus historical ledgers), every `CLAUDE.md` and `AGENTS.md`, issue and PR templates, the docs-site nav and the public-API docstrings. Every count, path, import example and status mark is re-measured from the code, never incremented by hand
- [ ] **Runnable examples:** each README and usage example runs, or is covered by a doctest or a test
- [ ] **SECURITY.md** gains a supported-versions table for 1.x
- [ ] **Python projects, Development Status:** the classifier is flipped to `Development Status :: 5 - Production/Stable`
- [ ] **Python projects, metadata:** `requires-python` (Poetry's `python` constraint) and one `Programming Language :: Python :: 3.X` classifier per version in the `tests.yml` matrix agree with each other
- [ ] **Public API frozen:** audit the exported names (Python: `__all__`; TypeScript: the package entry point exports) and remove deprecated or experimental names now; removing anything after 1.0 is a 2.0
- [ ] **Python projects, typed marker:** `py.typed` is present in the built wheel (`unzip -l dist/*.whl | grep py.typed`)
- [ ] **API guarantee 1.0.0:** the 1.x API guarantee is stated in the 1.0.0 GitHub Release notes and the README, not in `CHANGELOG.md`, which `cz changelog` regenerates from the commit history on every docs build
- [ ] **No open PRs at cut time:** each open PR is merged, closed, or explicitly deferred past 1.0 by the owner (the release gate counts issues only, see `docs/releasing-1-0-0.md`)
- [ ] **Release:** rehearsal, then publish, then install-verify (Test PyPI then PyPI; npm `--dry-run` then publish), with the tag present and the release not a draft
- [ ] **Post-release:** switch the documented version policy from 0.x rules to full semver
- [ ] **Projects using mike for docs, alias:** the mike `latest` alias of the docs site points at 1.0
