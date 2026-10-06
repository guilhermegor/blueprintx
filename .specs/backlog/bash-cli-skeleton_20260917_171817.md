# Bash CLI skeleton (#518)

Tracking the `bash-cli` skeleton (greenfield#26's `publishprobe` will scaffold from
this) — a BlueprintX skeleton mirroring how BlueprintX itself releases (git-tag
version, `make install` stamping, a `Release` workflow, package-manager channels).

## Done (this PR)

- [x] `templates/bash-cli/` skeleton: `bin/cli.sh` entrypoint (`--version`/`--help`),
      `Makefile` (`lint`/`test`/`install`), `tests/cli.bats`,
      `.pre-commit-config.yaml`, `.github/workflows/{ci,release}.yml`, `README.md`,
      `CLAUDE.md`, `.gitignore`, `skeleton.meta`.
- [x] `bin/scaffold/bash_cli.sh` — scaffolds it (validate → resolve GitHub user →
      copy + envsubst-render → common templates → git remote prompt → offline
      fallback), mirroring `ts_lib.sh`.
- [x] `docs/skeletons/bash-cli.md` — skeleton doc + the CLAUDE.md follow-up note.
- [x] `dry-run-smoke` matrix entry in `.github/workflows/scaffold_checks.yml` (no
      `bin/blueprintx.sh` change needed — discovery is automatic via
      `templates/*/skeleton.meta`).
- [x] Release workflow ships ONE channel: GitHub Release (tag + version-stamped
      tarball), same orchestrator shape as BlueprintX's own `release.yml`.

## Deferred to a follow-up PR

- [ ] `release_homebrew.yml`-equivalent sub-workflow (Formula stamping).
- [ ] `release_apt.yml`-equivalent (gh-pages apt repo).
- [ ] `release_snap.yml`-equivalent.
- [ ] `release_chocolatey.yml`-equivalent (optional per the issue).
- [ ] Wire a `bash-cli` case into `bin/ci/scaffold_lint_test.sh` (owned by #481 —
      that script is Poetry/pytest-specific today; a bash tier needs its own
      lint+test verification path, not a hunk of that one) or a standalone
      `scaffold-lint-test-bash` CI job that does `scaffold → make lint → make test`.
- [x] Add `bash-cli` to the root `CLAUDE.md` "Repo architecture" tree and skeleton
      count — done: `CLAUDE.md` names `bash-cli` in both places, so
      `bin/ci/validate_meta.sh`'s required mention resolves and `validate-meta` is
      no longer red on this branch.

## Completed — kept as a record

First PR (#518) landed the skeleton itself: scaffolds, lints, and tests green
locally; dry-run-smoke covers it in CI. The channels above are intentionally out
of scope for v1 per the issue's own "start small" guidance.
