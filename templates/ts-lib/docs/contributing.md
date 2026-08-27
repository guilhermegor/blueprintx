# Contributing

Everything you need to develop, test, and release this library.

> **See also:** [Usage](usage.md) · the repository's root `CONTRIBUTING.md` holds the
> authoritative branch/PR and commit-message policy.

## Setting up for development

```bash
npm ci
npm run build
npm test
```

## Tests, lint, and the packaging gates

```bash
npm test              # jest
npm run lint           # eslint
npm run type-check     # tsc --noEmit
npm run pack:smoke     # npm pack -> install tarball -> require()/import() it (every PR)
```

`pack:smoke` and the Verdaccio rehearsal job (`.github/workflows/pack-smoke.yml`) both
run on every pull request — they catch a broken `exports` map, a missing `files` entry,
or an unpublished dependency before either reaches the real npm registry.

## Releasing (npm OIDC trusted publishing)

Releases publish through **OIDC trusted publishing** — no long-lived `NPM_TOKEN` is
stored. `.github/workflows/release-npm.yml` runs on `workflow_dispatch` with the
version to release: it runs the test suite, checks the version is not already
published, then runs `npm stage publish` (npm's staged-publish flow), which holds the
package on the registry until a maintainer approves it with 2FA. A GitHub release with
the named `npm pack` tarball is created once staging succeeds.

### One-time bootstrap (before the first automated release)

npm has no "pending publisher" concept like PyPI — the package must already exist
before a trusted publisher can be configured for it:

1. Publish an initial `0.0.1` manually with a granular access token:
   ```bash
   npm publish --access public
   ```
2. On [npmjs.com](https://www.npmjs.com), open the package's settings and add a
   **trusted publisher** for this repository and the `release-npm.yml` workflow.
   Configure it **stage-only** (allow `npm stage publish`, not `npm publish`) — the
   safer posture, since it forces every release through the manual 2FA approval gate.
3. Revoke the bootstrap token and enable "disallow tokens" on the package.

### Pitfalls worth knowing before you touch the workflow

- npm CLI **≥ 11.5.1** and Node **≥ 22.14.0** are required for trusted publishing and
  `npm stage publish` — pinned in `.nvmrc` and the workflow's `setup-node` step.
- The release workflow never caches (`cache: false` in `setup-node`) — caching in a
  release build risks publishing from a stale `node_modules`.
- `package.json`'s `repository.url` must match the GitHub repository **exactly**, or
  the publish fails.
- The workflow filename is case-sensitive and part of the trusted-publisher
  configuration on npmjs.com — renaming `release-npm.yml` breaks publishing silently
  (npm does not validate the config at save time, only at publish time).
- Provenance is generated automatically by OIDC trusted publishing — do not pass
  `--provenance` explicitly.
- Only GitHub-hosted runners are supported (no self-hosted runners), and npm allows
  exactly one trusted publisher per package.

## Publishing the documentation

`docs/` is a [Docusaurus](https://docusaurus.io) site with native version support — the
npm-ecosystem analogue of `mike` on the Python skeletons.

| Workflow | Trigger | What it does |
|---|---|---|
| `pack-smoke.yml` | every push + PR | `npm run pack:smoke` + Verdaccio publish/install rehearsal |
| `docs-deploy.yml` | GitHub release published, non-prerelease | `npm run docs:build`, deploys `docs-build/` to GitHub Pages |

To cut a versioned docs snapshot before/after a release, run locally and commit the
result:

```bash
npm run docs:version -- <X.Y.Z>
```

This creates `versioned_docs/<X.Y.Z>/`, `versioned_sidebars/`, and updates
`versions.json` — Docusaurus's version dropdown reads from these at build time.

## Pull requests

1. Branch off the default branch following the prefix policy (`feat/…`, `fix/…`, …).
2. Fill out the PR template completely.
3. Ensure CI (build, lint, test, type-check, pack:smoke) passes — it is the merge gate.
