# Required status checks per scaffolded tier

Answers blueprintx#164: *`REQUIRED_CHECKS` seeds one entry — does a generated
project deserve more?*

`templates/python-common/bin/enable_repo_rules.sh` seeds

```bash
REQUIRED_CHECKS=("Review threads answered")
```

and provisions the `pr-quality-gate` ruleset from it. A name in that array that
no job ever emits is worse than an empty array: branch protection then blocks
every PR forever, waiting for a status that never arrives. So the question is
not "which checks matter?" but "which check names are *emitted on every open
PR* in every tier the script ships to?"

## The qualification rule

A name belongs in `REQUIRED_CHECKS` only if all four hold:

1. It is the literal `jobs.<id>.name:` (or, absent a `name:`, the job id) of a
   workflow **this template ships**. Not a guess, not a reviewer's own status.
2. Its workflow triggers on `pull_request` with **no `types:` filter that
   excludes `opened`** and **no `branches:`/`paths:` filter** — otherwise the
   check is simply absent on some PRs, which reads as permanently pending.
3. No job-level `if:` can skip it on an otherwise ordinary PR.
4. It is copied **unconditionally** by every scaffold script that also ships
   `enable_repo_rules.sh` — a shared script cannot require a name that only one
   tier has.

Rule 2 is the one that bites: GitHub cannot distinguish "this check has not
reported yet" from "this check will never report."

## Measured inventory

Measured 2026-09-20 by reading `jobs.*.name` and `on:` in every
`templates/*/.github/workflows/*.y*ml`. Re-measure before trusting it.

### Python tiers — `ddd-service-native-db`, `ddd-service-orm-db`, `mvc-service-native-db`, `mvc-service-orm-db`, `lib-minimal`, `api-service`

| Emitted check name | Workflow | Trigger | Qualifies? |
|---|---|---|---|
| `Review threads answered` | `review_threads.yaml` | `pull_request` (+ `_review`, `_review_comment`), no filter | **yes** — seeded today |
| `Classify and gate this PR` | `pr-gate.yaml` | `pull_request: types: [opened, synchronize, reopened, labeled, unlabeled]` | **yes** — not seeded |
| `Run Automated Tests (<os>, py<version>)` ×15 | `tests.yaml` | `pull_request:` with a `branches:` filter | no — rule 2 (branch filter) and the names embed matrix values that drift |
| `Ask CodeRabbit for a review` | `coderabbit_trigger.yaml` | `pull_request`, job `if: draft == false` | no — rule 3, never reports on a draft PR |
| `Close linked issues of merged PRs` | `pr-reconcile.yaml` | `pull_request: types: [closed]` | no — rule 2, *never* reports on an open PR |
| `GitGuardian — secret scan` | `secret_scan.yaml` | `pull_request` | no — rule 4, copied only when `GITGUARDIAN_API_KEY` was exported at scaffold time |
| `Re-ask a rate-limited reviewer` | `review_retry.yaml` | `schedule`, `workflow_dispatch` | no — rule 2, not a PR event |
| `Contract drift check` | `contract_drift.yaml` | `schedule`, `workflow_dispatch` | no — rule 2, not a PR event |
| `build` | `docs.yaml` (`lib-minimal` only) | `push`, `pull_request` | no — rule 4, one tier out of six |

### TypeScript tiers — `react-spa-webpack`, `ts-lib`

| Emitted check name | Workflow | Trigger | Qualifies? |
|---|---|---|---|
| `Review threads answered` | `review-threads.yml` | `pull_request` (+ `_review`, `_review_comment`) | yes |
| `webpack` | `build.yml` | `push`, `pull_request` | yes |
| `eslint`, `stylelint` | `lint.yml` | `push`, `pull_request` | yes |
| `jest` | `test.yml` | `push`, `pull_request` | yes |
| `type-check` | `type-check.yml` | `push`, `pull_request` | yes |
| `build` | `docs.yml` (`ts-lib` only) | `push`, `pull_request` | yes, `ts-lib` only |
| `pack-smoke`, `verdaccio-rehearsal` | `pack-smoke.yml` (`ts-lib` only) | `push`, `pull_request` | yes, `ts-lib` only |

### Bash tier — `bash-cli`

| Emitted check name | Workflow | Trigger | Qualifies? |
|---|---|---|---|
| `Lint — shellcheck + shfmt` | `ci.yml` | `push`, `pull_request` | yes |
| `Test — bats` | `ci.yml` | `push`, `pull_request` | yes |

`bash-cli` ships **no** review-threads workflow, so the one name every other
tier has in common does not exist there.

## The answer

Three findings, in descending order of cost:

1. **`enable_repo_rules.sh` exists only at `templates/python-common/bin/`.** The
   three non-Python tiers get no branch-protection provisioning at all — for
   them `REQUIRED_CHECKS` is not one entry, it is zero, and the six-to-nine
   qualifying names above are required by nothing. `templates/ts-common/.github/.review-bots.yaml`
   already notes in passing that the script is "for the Python tiers"; the gap
   was documented as a property, never as a defect. Tracked as a follow-up.
2. **Python deserves exactly one more entry: `Classify and gate this PR`.** It
   passes all four rules — literal job name, `pull_request` with `opened` in
   `types:`, a job-level `if:` that is true for every `pull_request` event, and
   copied by all six Python scaffold scripts. Without it the gate that exists to
   block a PR cannot block it. Tracked as a follow-up, because adding the name
   turns an advisory classifier into a merge blocker — a policy change, not a
   wiring fix.
3. **Nothing else qualifies, and four candidates fail for a reason worth
   naming.** `Close linked issues of merged PRs` is the trap in its purest form:
   it is a real job, in a shipped workflow, on the `pull_request` event, and
   requiring it would deadlock every PR in every generated project, because it
   only runs on `types: [closed]`.

The earlier pass on blueprintx#164 (`docs/backlog/repo_rules_self_audit_164_20260904_062813.md`)
reached "keep one entry" for the Python tiers by reasoning about
`tests.yaml` alone. That conclusion survives for `tests.yaml` — with a second,
stronger disqualifier it did not have (the `branches:` filter, not just matrix
drift) — but it did not look at `pr-gate.yaml`, and it did not look outside
Python at all.
