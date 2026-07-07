# **Changelog**

Release history for BlueprintX. Entries are generated from
[Conventional Commit](https://www.conventionalcommits.org/) messages via
[commitizen](https://commitizen-tools.github.io/commitizen/), so the version headings below track
what actually shipped (each `vX.Y.Z` tag is cut from the **Release** GitHub Action).

**How it updates:** the sections below are generated from the git tags and commit history by
`cz changelog`. The published page is regenerated **fresh on every docs build** (the docs workflow
runs `cz changelog` before `mkdocs build`), so it always reflects the default branch — CI never
commits `CHANGELOG.md` back to the repo. You never edit it by hand. Regenerate or preview locally
any time with `make changelog` (or `bash tasks.sh changelog`).

For the authoritative per-version notes and downloadable artifacts, see the
**[Releases on GitHub »](https://github.com/guilhermegor/blueprintx/releases)**.

---

<!-- Single-sourced from the repo-root CHANGELOG.md — never edit the entries here by hand. -->
--8<-- "CHANGELOG.md"
