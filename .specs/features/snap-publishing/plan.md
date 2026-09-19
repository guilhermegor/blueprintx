# Snap Store Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish BlueprintX to the Snap Store so users can install it with `sudo snap install blueprintx --classic`.

**Architecture:** Follows the existing two-tier release orchestrator pattern — a new `release_snap.yml` sub-workflow is called from `release.yml` after the tag job. The workflow checks out `main`, patches the version in `snap/snapcraft.yaml`, downloads the release tarball, copies the snap manifest into the extracted source, builds the snap with `snapcraft --destructive-mode`, publishes to the Store via `SNAPCRAFT_STORE_CREDENTIALS`, then commits the bumped manifest back to `main`.

**Tech Stack:** snapcraft CLI (classic snap), `plugin: dump` (no build step), `confinement: classic`, `base: core24`, GitHub Actions `workflow_call`.

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `snap/snapcraft.yaml` | Snap manifest — name, confinement, app command, parts |
| Create | `.github/workflows/release_snap.yml` | Sub-workflow: build + publish to Store + commit version bump |
| Modify | `.github/workflows/release.yml` | Add `snap` job that calls the sub-workflow |
| Modify | `README.md` | Add Snap install/uninstall section |

---

### Task 1: Create `snap/snapcraft.yaml`

**Files:**
- Create: `snap/snapcraft.yaml`

- [ ] **Step 1: Create the snap directory and manifest**

```bash
mkdir -p snap
```

Create `snap/snapcraft.yaml` with this exact content:

```yaml
name: blueprintx
base: core24
version: '0.1.6'
summary: Make + bash scaffolding for opinionated Python project skeletons
description: |
  BlueprintX provides an interactive CLI to scaffold Python projects with DDD
  architecture, pre-commit hooks, CI/CD workflows, and test structure.
  Run `blueprintx` to start the interactive menu.
grade: stable
confinement: classic

apps:
  blueprintx:
    command: bin/blueprintx.sh

parts:
  blueprintx:
    plugin: dump
    source: .
    stage:
      - bin/
      - templates/
```

- [ ] **Step 2: Verify the manifest is valid YAML**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('snap/snapcraft.yaml'))" && echo "OK"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add snap/snapcraft.yaml
git commit -m "feat(snap): add snapcraft manifest"
```

---

### Task 2: Create `.github/workflows/release_snap.yml`

**Files:**
- Create: `.github/workflows/release_snap.yml`

- [ ] **Step 1: Create the sub-workflow**

Create `.github/workflows/release_snap.yml` with this exact content:

```yaml
name: Release — Snap

on:
  workflow_call:
    inputs:
      version:
        description: "Version being released (e.g. 0.2.0)"
        type: string
        required: true
    secrets:
      SNAPCRAFT_STORE_CREDENTIALS:
        required: true

permissions:
  contents: write

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          ref: main

      - name: Update snap/snapcraft.yaml version
        env:
          VERSION: ${{ inputs.version }}
        run: |
          sed -i "s/^version: '.*'/version: '${VERSION}'/" snap/snapcraft.yaml

      - name: Download and extract release tarball
        env:
          VERSION: ${{ inputs.version }}
        run: |
          URL="https://github.com/guilhermegor/blueprintx/archive/refs/tags/v${VERSION}.tar.gz"
          sleep 5
          curl -sL "$URL" -o blueprintx.tar.gz
          mkdir -p /tmp/bpx-src
          tar -xzf blueprintx.tar.gz --strip-components=1 -C /tmp/bpx-src

      - name: Copy snap manifest into build directory
        run: cp -r snap /tmp/bpx-src/snap

      - name: Install snapcraft
        run: sudo snap install snapcraft --classic

      - name: Build snap
        run: |
          cd /tmp/bpx-src
          snapcraft --destructive-mode

      - name: Publish to Snap Store
        env:
          SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.SNAPCRAFT_STORE_CREDENTIALS }}
        run: |
          SNAP_FILE=$(ls /tmp/bpx-src/blueprintx_*.snap)
          snapcraft upload --release=stable "$SNAP_FILE"

      - name: Commit updated snap/snapcraft.yaml
        env:
          VERSION: ${{ inputs.version }}
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add snap/snapcraft.yaml
          git diff --cached --quiet && exit 0
          git commit -m "chore(snap): bump snapcraft to v${VERSION}"
          for attempt in 1 2 3 4 5; do
            git pull --rebase && git push && break
            echo "Push attempt $attempt failed — retrying in 5s"
            sleep 5
          done
```

- [ ] **Step 2: Verify YAML syntax**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/release_snap.yml'))" && echo "OK"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release_snap.yml
git commit -m "feat(snap): add snap release sub-workflow"
```

---

### Task 3: Update `release.yml` — add snap job

**Files:**
- Modify: `.github/workflows/release.yml`

- [ ] **Step 1: Add the snap job**

Open `.github/workflows/release.yml`. After the `apt:` job block (which ends before the closing of the `jobs:` section), add this block at the end of `jobs:`:

```yaml
  snap:
    needs: tag
    uses: ./.github/workflows/release_snap.yml
    permissions:
      contents: write
    with:
      version: ${{ github.event.inputs.version }}
    secrets:
      SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.SNAPCRAFT_STORE_CREDENTIALS }}
```

After the edit the full `jobs:` section should look like:

```yaml
jobs:
  tag:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Create and push tag
        env:
          VERSION: ${{ github.event.inputs.version }}
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git tag -a "v${VERSION}" -m "release: v${VERSION}"
          git push origin "v${VERSION}"

  homebrew:
    needs: tag
    uses: ./.github/workflows/release_homebrew.yml
    permissions:
      contents: write
    with:
      version: ${{ github.event.inputs.version }}

  chocolatey:
    needs: tag
    uses: ./.github/workflows/release_chocolatey.yml
    permissions:
      contents: write
    with:
      version: ${{ github.event.inputs.version }}

  apt:
    needs: tag
    uses: ./.github/workflows/release_apt.yml
    permissions:
      contents: write
    with:
      version: ${{ github.event.inputs.version }}
    secrets:
      APT_GPG_PRIVATE_KEY: ${{ secrets.APT_GPG_PRIVATE_KEY }}
      APT_GPG_KEY_ID: ${{ secrets.APT_GPG_KEY_ID }}
      APT_GPG_PASSPHRASE: ${{ secrets.APT_GPG_PASSPHRASE }}

  snap:
    needs: tag
    uses: ./.github/workflows/release_snap.yml
    permissions:
      contents: write
    with:
      version: ${{ github.event.inputs.version }}
    secrets:
      SNAPCRAFT_STORE_CREDENTIALS: ${{ secrets.SNAPCRAFT_STORE_CREDENTIALS }}
```

- [ ] **Step 2: Verify YAML syntax**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/release.yml'))" && echo "OK"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "feat(snap): wire snap job into release orchestrator"
```

---

### Task 4: Update `README.md` — add Snap section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the Snap `<details>` block**

In `README.md`, find the closing `</details>` of the `apt` section. Immediately after it, insert this block (before the `<details>` for Git clone):

```markdown
<details>
<summary><strong>Snap</strong> (Linux)</summary>

```bash
sudo snap install blueprintx --classic
```

To uninstall:

```bash
sudo snap remove blueprintx
```

</details>
```

- [ ] **Step 2: Verify the section renders correctly**

```bash
grep -A 12 "Snap" README.md
```

Expected: the `<details>` block with `snap install` and `snap remove` commands appears.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(snap): add snap install instructions to README"
```

---

## Manual Prerequisites (outside CI — do these before the first release)

These steps cannot be automated and must be done by the repository owner before triggering a release:

1. **Register the snap name** — go to [snapcraft.io/snaps/blueprintx](https://snapcraft.io) and register `blueprintx`. Requires a Ubuntu One account.

2. **Request classic confinement** — after registration, file a forum request at [forum.snapcraft.io](https://forum.snapcraft.io) in the "store-requests" category. Classic confinement is manually reviewed; approval typically takes 1–3 business days. Reference: the snap is a developer tool (scaffolding CLI) that writes project files in arbitrary directories chosen by the user.

3. **Export store credentials** — on a machine with snapcraft installed and logged in:
   ```bash
   snapcraft export-login credentials.txt
   cat credentials.txt
   ```
   Copy the full output and add it as a GitHub Actions repository secret named `SNAPCRAFT_STORE_CREDENTIALS` (Settings → Secrets → Actions → New repository secret).

4. **First publish** — the very first `snapcraft upload` call registers the snap in the Store. Subsequent calls update it.
