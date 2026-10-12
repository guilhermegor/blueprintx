# Lockfile sync gate

blueprintx#588, a regression of #464. `bin/ci/check_lockfile_sync.sh` fails when a
`templates/*/package.json` declares a dependency that its `package-lock.json` does not carry. That
drift is what makes `npm ci` refuse to install in a generated project.

## What it checks

- A pure JSON comparison done with `python3`, so it runs offline in pre-commit.
- A tier with no lockfile is skipped, not failed: not every tier ships one.
- An optional peer dependency need not be installed. It is declared in the lock root and has no
  `node_modules` entry, so the gate accepts that shape.
- Usage: `bash bin/ci/check_lockfile_sync.sh [--root <dir>]`, defaulting to the repo root.

## The regression test

`tests/test_check_lockfile_sync.sh` covers both directions. A dependency missing from the lock must
fail and name the package; a synced pair and a lockfile-less tier must pass. Each case takes a
description, the `package.json` deps, the lock root deps, the lock `node_modules` keys (space
separated, `-` for a tier without a lockfile), `pass` or `fail`, and the needle expected on failure.

## Dependabot for the ts-lib lockfile

`.github/dependabot.yml` watches `/templates/ts-lib` because every ts-lib scaffold copies that
lockfile (#735). Its `eslint` group comes first on purpose: the first matching group wins, and
`@eslint/js` moves in lockstep with `eslint`, majors included.
