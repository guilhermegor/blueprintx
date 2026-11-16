## Gate parity — every gate in BOTH the git hooks and CI

Husky runs the commit gates (`.husky/pre-commit`, `.husky/pre-push`) and CI runs its gates as
**explicit steps** in `.github/workflows/`, so wiring a gate into one does **not** cover the
other. A `--no-verify` commit or an uninstalled hook skips husky, and branch-protection CI runs
the workflows, not local hooks. Wire every lint/static/test gate into **both**, in the same
change. The gate set that must stay mirrored: `npm run lint` (ESLint), `npm run lint:css`
(stylelint), `npm run type-check`, `bin/check_doc_commands.sh` (every documented `npm run`
exists), the assertion-weakening gate (`src/**/assertion-weakening.cjs`), the `AGENTS.md`
pairing gate, the comment budget, and `npm test`. `npm run build` runs in CI only.

- **A gate file that goes missing must fail loudly.** The hook and `lint.yml` locate
  `assertion-weakening.cjs` with `find src` and exit non-zero when it is absent; keep that
  shape for any new gate script, so a dropped file is a red check, not a silent skip.
- **Version-floor consistency.** `engines.node` in `package.json` and `.nvmrc` must agree, and
  CI reads the version from `.nvmrc` through `setup-node` (`node-version-file`) — never write a
  literal `node-version:` in a workflow.
