# .github/CLAUDE.md

Guidance for Claude Code when working with GitHub Actions workflows in this repo.

## Release workflow architecture

Releases follow a **two-tier orchestrator pattern**:

```
release.yml                  ← single entry point (workflow_dispatch, manual button)
  └─ job: tag                ← creates and pushes the git tag once
  └─ job: <package-manager>  ← needs: tag; calls release_<name>.yml (runs in parallel)
```

### Orchestrator — `release.yml`

- Only workflow with `workflow_dispatch`. This is the one users click in the GitHub Actions UI.
- Responsible for **one thing only**: creating and pushing the annotated git tag.
- Calls each `release_*.yml` via `uses: ./.github/workflows/release_<name>.yml` with `needs: tag` so all package-manager jobs run in parallel after the tag exists.
- Passes `version` (the user-supplied input) to every sub-workflow via `with:`.

### Sub-workflows — `release_*.yml`

- Triggered only via `workflow_call` — never manually.
- Each owns the full update cycle for **one package manager only**: compute checksum, update manifest, commit.
- Declare `permissions: contents: write` explicitly (do not rely on inherited defaults).
- All `${{ inputs.* }}` expressions must go through `env:` blocks before use in `run:` steps — never inline in shell commands.

### Adding a new package manager

1. Create `.github/workflows/release_<name>.yml` with `on: workflow_call` and `inputs.version`.
2. Add a job to `release.yml`:
   ```yaml
   <name>:
     needs: tag
     uses: ./.github/workflows/release_<name>.yml
     permissions:
       contents: write
     with:
       version: ${{ github.event.inputs.version }}
   ```
3. Add the new installation method to `README.md` — every supported package manager must have a documented install command there.
4. No other files change.

### Current sub-workflows

| File | Package manager | What it updates |
|------|----------------|-----------------|
| `release_homebrew.yml` | Homebrew (macOS / Linux) | `Formula/blueprintx.rb` — `url`, `sha256`, `version` fields |
| `release_chocolatey.yml` | Chocolatey (Windows) | `choco/blueprintx.nuspec` — `version` field; `choco/tools/chocolateyInstall.ps1` — `$version`, `$sha256`, tarball URL |

## Security rule for all workflow files

Never interpolate `${{ … }}` directly inside a `run:` block. Always extract to `env:` first:

```yaml
# Wrong
run: echo "${{ github.event.inputs.version }}"

# Correct
env:
  VERSION: ${{ github.event.inputs.version }}
run: echo "$VERSION"
```

This applies to all trigger types — including `workflow_dispatch` and `workflow_call` inputs.
