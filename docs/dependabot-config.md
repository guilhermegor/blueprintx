# Dependabot configuration

Every skeleton ships a `.github/dependabot.yml` when a GitHub remote is connected (the
offline mode removes `.github/`, so it ships none there). The root repository's own
`.github/dependabot.yml` follows the same rules.

| Family | Source | Ecosystems |
|--------|--------|------------|
| Python (six skeletons) | `templates/python-common/.github/dependabot.yml` | `pip` (lockfile-only), `github-actions` |
| TypeScript (`react-spa-webpack`, `ts-lib`) | `templates/ts-common/dependabot.yml` | `npm`, `github-actions` |
| Bash (`bash-cli`, `etcher-chromeos`, `ventoy-usb`) | `templates/common/.github/dependabot.yml` | `github-actions` |

## Cooldown

A release is aged before Dependabot proposes it. Security updates ignore the cooldown.

- `pip` and `npm`: `semver-patch-days: 3`, `semver-minor-days: 7`, `semver-major-days: 90`
  (90 is the schema maximum, range 1-90).
- `github-actions`: `default-days: 7`; it does not support the `semver-*` keys.

## Assignee

Every ecosystem block carries a block-style `assignees:` list whose single item is
`"${GITHUB_USERNAME}"`, so dependency PRs have an owner
(the `assignee` PR-policy check skips bot PRs, so this is for triage, not for the gate). The
scaffold scripts and `promote_offline_to_online.sh` substitute the resolved username right after
copying the file. `resolve_github_username` always yields a value (it falls back to
`DEFAULT_GITHUB_USERNAME`), so the output stays valid YAML; offline projects ship no `.github/`
and so no `dependabot.yml`.

## Lint stack

`eslint`, `@eslint/js`, `typescript-eslint` and `eslint-plugin-jest` share one `eslint` group in
every npm block, so the lint stack moves as a unit. A lone `@eslint/js` major once broke
`npm ci` with ERESOLVE. The templates are on eslint 10 (#839), so no major is ignored.

## Gate

`bin/ci/check_dependabot_shipped.sh --static` (pre-commit hook `dependabot-shipped`, CI job
`dependabot-shipped`) fails when a skeleton script stops copying `dependabot.yml`, copies a
file that does not exist, any block of the copied file lacks a `cooldown` or the
`"${GITHUB_USERNAME}"` assignee item, or the script does not render it with
`GITHUB_USERNAME="$GITHUB_USERNAME" envsubst '${GITHUB_USERNAME}'`. The inline prefix is
required because several scripts never export `GITHUB_USERNAME`, and `envsubst` sees only
exported variables. `promote_offline_to_online.sh` is checked more loosely: it must export
`GITHUB_USERNAME` and pipe every `dependabot.yml` it writes through `envsubst`. The copy line
is matched as a single-line text pattern in exactly that spelling, so a reformatted
equivalent (a `\` continuation, an `env` prefix, a double-quoted `envsubst` argument) is
reported as "never copies"; rewrite it in the canonical form. There is no `--generated`
mode: the default scaffold answers take the offline path, which removes `.github/`, so a
generated tree would never contain the file.
