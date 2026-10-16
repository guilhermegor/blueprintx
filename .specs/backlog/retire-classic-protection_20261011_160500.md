# Retire classic protection on main (blueprintx#750)

Status: measured and proposed 2026-10-15 (the date differs from the filename, which keeps its creation timestamp); the PUT and the delete are the owner's.

- [x] Scaffold half: generated projects get the ruleset (PR #801, merged).
- [x] Measure which classic checks report on every PR (below).
- [x] Propose the ruleset's new list and the exact PUT payload (below).
- [x] Owner-approved 2026-10-16, applied: PUT the ruleset, verify `rules/branches/main`, delete classic protection, red-check proof, sync `.github/required-checks.json`.

## Applied (2026-10-16)

Completed. Kept as a record.

The payload was rebuilt from the **live** state, not the stored copy below, because two things had changed since the proposal:

- **59 checks, not 58.** #821 added `Dry-run smoke — etcher-chromeos` to the classic policy file. It is an unconditional matrix job, reported by app 15368 on PR heads, so it was added. Every entry is pinned to the `app_id` classic used.
- **Two classic protections were missing from the proposal and were added to the ruleset before the delete:** `required_linear_history` (classic `required_linear_history: true`), and `dismiss_stale_reviews_on_push: true` (classic `dismiss_stale_reviews: true`). Deleting classic without them would have silently weakened `main`. Both were already in effect through classic, so the effective rules did not change.

Sequence:
1. Backed up `rulesets/23741414` and `branches/main/protection`.
2. PUT the ruleset.
3. Verified `rules/branches/main`: ruleset 23741414 with 59 checks, 0 unpinned, plus `required_linear_history`.
4. `DELETE branches/main/protection` returned 204, and a follow-up read returned "Branch not protected".
5. Red-check proof: no throwaway PR was needed. With classic gone, #822 and #823 (both failing `Review threads answered`) read `blocked` from the ruleset alone, while #819 (all green) read `clean` and merged.
6. `.github/required-checks.json`: `classic` is now `[]` and `ruleset` holds the 59 names. `check_required_checks_sync.py` returns `findings=0` both statically and with `--live`.

## Measurement

Read-only REST. Method: the last 30 merged PRs into `main` at 2026-10-15 (#745 to #803);
for each, the check-runs and commit statuses on the PR's final head SHA; a name counts as
reporting when it appears in either. Classic protection (`branches/main/protection`) requires
56 contexts, strict. Ruleset 23741414 requires 3: `Review threads answered`, which classic also
requires, and the two `TypeScript build + lint` contexts, which classic does not.

Three things in the issue body no longer hold. Classic has 56 unique names and no duplicates
(CodeQL and GitGuardian appear once each). 55 of the 56 are not in the ruleset, not 35. And
`Analyze (ruby)` has a producer: CodeQL default setup (`code-scanning/default-setup` lists ruby
among its languages) emits it through the `github-actions` app, with `Analyze (actions)`,
`Analyze (python)` and `Analyze (javascript-typescript)`.

| Check (classic) | Reported on final head | Verdict |
|---|---|---|
| --spec regression tests | 30/30 | always |
| .specs/ structure guard | 30/30 | always |
| Analyze (actions) | 30/30 | always |
| Analyze (javascript-typescript) | 30/30 | always |
| Analyze (python) | 30/30 | always |
| Analyze (ruby) | 30/30 | always |
| CodeQL | 30/30 | always |
| Comment budget — long runs + decorative banners (blueprintx#303) | 30/30 | always |
| Cyclomatic complexity — templates/python-common (tests 1, src 2, bin 8) | 30/30 | always |
| Cyclomatic complexity — tests 1, src 2, bin 8 | 30/30 | always |
| Dist name vs import package | 30/30 | always |
| Docs code references — symbols + import paths (blueprintx#159) | 30/30 | always |
| Docs gap — published pages registered in nav and index | 30/30 | always |
| Dry-run smoke — bash-cli | 30/30 | always |
| Dry-run smoke — ddd-service-native-db | 30/30 | always |
| Dry-run smoke — ddd-service-orm-db | 30/30 | always |
| Dry-run smoke — lib-minimal | 30/30 | always |
| Dry-run smoke — mvc-service-native-db | 30/30 | always |
| Dry-run smoke — mvc-service-orm-db | 30/30 | always |
| Dry-run smoke — react-spa-webpack | 30/30 | always |
| Every skeleton ships the hosted-reviewer config | 30/30 | always |
| Function length — 60 lines, docstring excluded | 30/30 | always |
| Gate integrity — a PR must not weaken a check without saying why | 30/30 | always |
| GitGuardian Security Checks | 30/30 | always |
| GitGuardian — secret scan | 30/30 | always |
| Lockfile sync — templates/*/package.json vs package-lock.json | 30/30 | always |
| Makefile <-> tasks.sh <-> bin/help.sh pairing (blueprintx#241) | 30/30 | always |
| MkDocs build — strict mode | 30/30 | always |
| PR file-count ceiling — 90 files (blueprintx#551) | 30/30 | always |
| Pre-commit and CI run the same checks, both directions (blueprintx#384) | 30/30 | always |
| Review threads answered | 30/30 | always |
| Review-bot roster opt-out — "no" must omit .review-bots.yaml | 30/30 | always |
| Scaffold + lint + test (multi-intent) — mvc-service-native-db | 30/30 | always |
| Scaffold + lint + test (multi-intent) — mvc-service-orm-db | 30/30 | always |
| Scaffold + lint + test (storage opt-in) — api-service-native-db | 30/30 | always |
| Scaffold + lint + test (storage opt-in) — ddd-service-native-db | 30/30 | always |
| Scaffold + lint + test (storage opt-in) — ddd-service-orm-db | 30/30 | always |
| Scaffold + lint + test — ddd-service-native-db | 30/30 | always |
| Scaffold + lint + test — ddd-service-orm-db | 30/30 | always |
| Scaffold + lint + test — lib-minimal | 30/30 | always |
| Scaffold + lint + test — mvc-service-native-db | 30/30 | always |
| Scaffold + lint + test — mvc-service-orm-db | 30/30 | always |
| Scaffold origin verification — mismatched remote must fail | 30/30 | always |
| Shared test copy lists — scaffolds vs python-common | 30/30 | always |
| ShellCheck — bin/**/*.sh | 30/30 | always |
| Spell check — docs/ and templates/ | 30/30 | always |
| Validate skeleton.meta integrity | 30/30 | always |
| Version sync — pyproject vs CLI | 30/30 | always |
| actionlint — workflows (repo + templates) | 30/30 | always |
| docs/ boundary guard | 30/30 | always |
| gitleaks — repo history (root + templates) | 30/30 | always |
| markdownlint — measured rule set (blueprintx#383) | 30/30 | always |
| promote_offline_to_online.sh refusal-path tests | 30/30 | always |
| quality-rules.yaml validation (blueprintx#432) | 30/30 | always |
| scaffold kanban board and labels | 30/30 | always |
| sed portability — no bare sed -i (blueprintx#459) | 30/30 | always |

All 56 reported on 30 of 30, but that count proves little: classic is strict with `enforce_admins`,
so a merged PR must already have had every one of its 56 names green. The real evidence is the
structural check, plus the two ruleset-only TypeScript contexts (30 of 30, and not previously
enforced by classic):
`python3 bin/ci/check_required_checks_sync.py` on `origin/main` returns `findings=0`, meaning
every required context is emitted by an unconditional PR job or is declared `external` in
`bin/ci/required_checks_policy.txt` (CodeQL, the four `Analyze` names, GitGuardian Security
Checks). Caveat: a path-filtered check can still show 30 of 30 if all 30 PRs touched its paths;
the gate result is what rules that out.

## Proposal

New `required_status_checks` list: classic's 56 names plus the ruleset's 2 TypeScript contexts,
58 entries, `strict_required_status_checks_policy: true` (equal to classic's `strict`). Nothing is
dropped. The seven `optional` entries in `bin/ci/required_checks_policy.txt` stay optional:
`PR files within declared issue scope`, `Required checks sync — expected contexts vs PR jobs
(blueprintx#535)`, `.env.example matches docs/configuration.md (blueprintx#304)`, and the four
`Scaffold + lint + test (otel opt-in)` jobs (api-service-native-db, ddd-service-orm-db,
lib-minimal, mvc-service-orm-db).

Each entry is pinned to the app that reports it (`integration_id`), as classic does: 54 to
15368 (GitHub Actions), `CodeQL` to 57789, `GitGuardian Security Checks` to 46505. The two
TypeScript contexts are reported by app 15368 on a recent PR. A bare `context` would let any
reporter satisfy `Gate integrity` or `Review threads answered`.

`conditions.ref_name.include` gains `refs/heads/main` beside `~DEFAULT_BRANCH`, so the ruleset
still guards `main` if the default branch is ever switched (it was, briefly, on 2026-10-14).

Every other rule is preserved byte for byte: `pull_request` (0 approvals, thread resolution
required), `code_scanning`, `copilot_code_review`, `non_fast_forward`, `deletion`. A PUT replaces
the whole rules array, so the payload carries all six.

## Owner steps

1. Back up both layers. For the ruleset, which is valid PUT input after trimming:
   `gh api repos/guilhermegor/blueprintx/rulesets/23741414 > ruleset.before.json`. Classic:
   `gh api repos/guilhermegor/blueprintx/branches/main/protection > classic.before.json`. Note that
   `GET branches/main/protection` output is **not** valid PUT input (it nests `{enabled, url}`
   objects and uses `contexts` plus `checks`); rebuilding classic needs reshaping, which is why
   the ruleset backup is the one to rely on.
2. Apply: `gh api -X PUT repos/guilhermegor/blueprintx/rulesets/23741414 --input payload.json`.
3. Verify the rules in effect: `gh api repos/guilhermegor/blueprintx/rules/branches/main` must
   list a `required_status_checks` rule with `ruleset_id` 23741414 and 58 entries, each with an
   `integration_id`.
4. Delete classic: `gh api -X DELETE repos/guilhermegor/blueprintx/branches/main/protection`.
5. Only now run the red-check proof: a throwaway PR with a deliberately failing check must show
   the merge blocked by the ruleset alone.
6. Update `.github/required-checks.json` (`classic` to `[]`, `ruleset` to the 58 names) in a PR
   right after the delete. `check_required_checks_sync.py --live` treats an unprotected branch as
   an empty classic set, so it keeps working after step 4. Then close #750.

Rollback: restore the ruleset with
`jq '{name,target,enforcement,conditions,bypass_actors,rules}' ruleset.before.json | gh api -X PUT repos/guilhermegor/blueprintx/rulesets/23741414 --input -`.
Classic is not restored by replaying `classic.before.json`; re-create it from the Settings UI or a
hand-built PUT body, which is why step 3 must pass before step 4.

## Payload

```json
{
  "name": "pr-quality-gate",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": [
        "~DEFAULT_BRANCH",
        "refs/heads/main"
      ],
      "exclude": []
    }
  },
  "bypass_actors": [],
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "required_reviewers": [],
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "require_extra_approval_for_unattributed_changes": true,
        "allowed_merge_methods": [
          "merge",
          "squash",
          "rebase"
        ]
      }
    },
    {
      "type": "code_scanning",
      "parameters": {
        "code_scanning_tools": [
          {
            "tool": "CodeQL",
            "security_alerts_threshold": "high_or_higher",
            "alerts_threshold": "errors"
          }
        ]
      }
    },
    {
      "type": "copilot_code_review",
      "parameters": {
        "review_on_push": true,
        "review_draft_pull_requests": false
      }
    },
    {
      "type": "non_fast_forward"
    },
    {
      "type": "deletion"
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": [
          {
            "context": "--spec regression tests",
            "integration_id": 15368
          },
          {
            "context": ".specs/ structure guard",
            "integration_id": 15368
          },
          {
            "context": "Analyze (actions)",
            "integration_id": 15368
          },
          {
            "context": "Analyze (javascript-typescript)",
            "integration_id": 15368
          },
          {
            "context": "Analyze (python)",
            "integration_id": 15368
          },
          {
            "context": "Analyze (ruby)",
            "integration_id": 15368
          },
          {
            "context": "CodeQL",
            "integration_id": 57789
          },
          {
            "context": "Comment budget — long runs + decorative banners (blueprintx#303)",
            "integration_id": 15368
          },
          {
            "context": "Cyclomatic complexity — templates/python-common (tests 1, src 2, bin 8)",
            "integration_id": 15368
          },
          {
            "context": "Cyclomatic complexity — tests 1, src 2, bin 8",
            "integration_id": 15368
          },
          {
            "context": "Dist name vs import package",
            "integration_id": 15368
          },
          {
            "context": "Docs code references — symbols + import paths (blueprintx#159)",
            "integration_id": 15368
          },
          {
            "context": "Docs gap — published pages registered in nav and index",
            "integration_id": 15368
          },
          {
            "context": "Dry-run smoke — bash-cli",
            "integration_id": 15368
          },
          {
            "context": "Dry-run smoke — ddd-service-native-db",
            "integration_id": 15368
          },
          {
            "context": "Dry-run smoke — ddd-service-orm-db",
            "integration_id": 15368
          },
          {
            "context": "Dry-run smoke — lib-minimal",
            "integration_id": 15368
          },
          {
            "context": "Dry-run smoke — mvc-service-native-db",
            "integration_id": 15368
          },
          {
            "context": "Dry-run smoke — mvc-service-orm-db",
            "integration_id": 15368
          },
          {
            "context": "Dry-run smoke — react-spa-webpack",
            "integration_id": 15368
          },
          {
            "context": "Every skeleton ships the hosted-reviewer config",
            "integration_id": 15368
          },
          {
            "context": "Function length — 60 lines, docstring excluded",
            "integration_id": 15368
          },
          {
            "context": "Gate integrity — a PR must not weaken a check without saying why",
            "integration_id": 15368
          },
          {
            "context": "GitGuardian Security Checks",
            "integration_id": 46505
          },
          {
            "context": "GitGuardian — secret scan",
            "integration_id": 15368
          },
          {
            "context": "Lockfile sync — templates/*/package.json vs package-lock.json",
            "integration_id": 15368
          },
          {
            "context": "Makefile <-> tasks.sh <-> bin/help.sh pairing (blueprintx#241)",
            "integration_id": 15368
          },
          {
            "context": "MkDocs build — strict mode",
            "integration_id": 15368
          },
          {
            "context": "PR file-count ceiling — 90 files (blueprintx#551)",
            "integration_id": 15368
          },
          {
            "context": "Pre-commit and CI run the same checks, both directions (blueprintx#384)",
            "integration_id": 15368
          },
          {
            "context": "Review threads answered",
            "integration_id": 15368
          },
          {
            "context": "Review-bot roster opt-out — \"no\" must omit .review-bots.yaml",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test (multi-intent) — mvc-service-native-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test (multi-intent) — mvc-service-orm-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test (storage opt-in) — api-service-native-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test (storage opt-in) — ddd-service-native-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test (storage opt-in) — ddd-service-orm-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test — ddd-service-native-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test — ddd-service-orm-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test — lib-minimal",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test — mvc-service-native-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold + lint + test — mvc-service-orm-db",
            "integration_id": 15368
          },
          {
            "context": "Scaffold origin verification — mismatched remote must fail",
            "integration_id": 15368
          },
          {
            "context": "Shared test copy lists — scaffolds vs python-common",
            "integration_id": 15368
          },
          {
            "context": "ShellCheck — bin/**/*.sh",
            "integration_id": 15368
          },
          {
            "context": "Spell check — docs/ and templates/",
            "integration_id": 15368
          },
          {
            "context": "TypeScript build + lint — react-spa-webpack template",
            "integration_id": 15368
          },
          {
            "context": "TypeScript build + lint — ts-lib template",
            "integration_id": 15368
          },
          {
            "context": "Validate skeleton.meta integrity",
            "integration_id": 15368
          },
          {
            "context": "Version sync — pyproject vs CLI",
            "integration_id": 15368
          },
          {
            "context": "actionlint — workflows (repo + templates)",
            "integration_id": 15368
          },
          {
            "context": "docs/ boundary guard",
            "integration_id": 15368
          },
          {
            "context": "gitleaks — repo history (root + templates)",
            "integration_id": 15368
          },
          {
            "context": "markdownlint — measured rule set (blueprintx#383)",
            "integration_id": 15368
          },
          {
            "context": "promote_offline_to_online.sh refusal-path tests",
            "integration_id": 15368
          },
          {
            "context": "quality-rules.yaml validation (blueprintx#432)",
            "integration_id": 15368
          },
          {
            "context": "scaffold kanban board and labels",
            "integration_id": 15368
          },
          {
            "context": "sed portability — no bare sed -i (blueprintx#459)",
            "integration_id": 15368
          }
        ]
      }
    }
  ]
}
```
