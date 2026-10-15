# Retire classic protection on main (blueprintx#750)

Status: measurement and proposal done 2026-10-15; the PUT and the delete are the owner's.

- [x] Scaffold half: generated projects get the ruleset (PR #801, merged).
- [x] Measure which classic checks report on every PR (below).
- [x] Propose the ruleset's new list and the exact PUT payload (below).
- [ ] Owner: PUT the ruleset, verify with a throwaway PR, delete classic protection.

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

No name is conditional or absent: all 56 reported on 30 of 30. Both ruleset-only contexts also
reported on 30 of 30. That is a sample, not proof, so it is cross-checked structurally:
`python3 bin/ci/check_required_checks_sync.py` on `origin/main` returns `findings=0`, meaning
every required context is emitted by an unconditional PR job or is declared `external` in
`bin/ci/required_checks_policy.txt` (CodeQL, the four `Analyze` names, GitGuardian Security
Checks). Caveat: a path-filtered check can still show 30 of 30 if all 30 PRs touched its paths;
the gate result is what rules that out.

## Proposal

New `required_status_checks` list: the union of classic's 56 and the ruleset's 2 TypeScript
contexts, 58 names, all always-reporting, `strict_required_status_checks_policy: true` (equal to
classic's `strict`). Nothing is dropped. The three `optional` entries in the policy file stay
optional until they have a green record.

Every other rule is preserved byte for byte: `pull_request` (0 approvals, thread resolution
required), `code_scanning` (CodeQL), `copilot_code_review`, `non_fast_forward`, `deletion`.
A PUT replaces the whole rules array, so the payload below carries all six.

## Owner steps

1. Save the payload below as `payload.json` (or rebuild it: take `gh api repos/guilhermegor/blueprintx/rulesets/23741414`,
   keep `name`, `target`, `enforcement`, `conditions`, `bypass_actors` and `rules`, and replace the
   `required_status_checks` rule's list with classic's contexts plus the two TypeScript ones).
2. Apply: `gh api -X PUT repos/guilhermegor/blueprintx/rulesets/23741414 --input payload.json`.
3. Read it back: `gh api repos/guilhermegor/blueprintx/rulesets/23741414 --jq '.rules[]|select(.type=="required_status_checks")|.parameters.required_status_checks|length'` must print 58.
4. Verify with one throwaway PR (a one-line docs change): the merge button must stay blocked until
   all 58 report, and a red check must block it. Do this before step 5, while classic is still a net.
5. Delete classic: `gh api -X DELETE repos/guilhermegor/blueprintx/branches/main/protection`.
6. Run `python3 bin/ci/check_required_checks_sync.py --live` (admin token) and update
   `.github/required-checks.json` so `classic` is `[]` and `ruleset` has the 58 names. Then close #750.

Rollback: the old state is the same two calls reversed; keep the classic JSON from
`gh api repos/guilhermegor/blueprintx/branches/main/protection > classic.json` before step 5.

## Payload

```json
{
  "name": "pr-quality-gate",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "exclude": [],
      "include": [
        "~DEFAULT_BRANCH"
      ]
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
            "context": "--spec regression tests"
          },
          {
            "context": ".specs/ structure guard"
          },
          {
            "context": "Analyze (actions)"
          },
          {
            "context": "Analyze (javascript-typescript)"
          },
          {
            "context": "Analyze (python)"
          },
          {
            "context": "Analyze (ruby)"
          },
          {
            "context": "CodeQL"
          },
          {
            "context": "Comment budget — long runs + decorative banners (blueprintx#303)"
          },
          {
            "context": "Cyclomatic complexity — templates/python-common (tests 1, src 2, bin 8)"
          },
          {
            "context": "Cyclomatic complexity — tests 1, src 2, bin 8"
          },
          {
            "context": "Dist name vs import package"
          },
          {
            "context": "Docs code references — symbols + import paths (blueprintx#159)"
          },
          {
            "context": "Docs gap — published pages registered in nav and index"
          },
          {
            "context": "Dry-run smoke — bash-cli"
          },
          {
            "context": "Dry-run smoke — ddd-service-native-db"
          },
          {
            "context": "Dry-run smoke — ddd-service-orm-db"
          },
          {
            "context": "Dry-run smoke — lib-minimal"
          },
          {
            "context": "Dry-run smoke — mvc-service-native-db"
          },
          {
            "context": "Dry-run smoke — mvc-service-orm-db"
          },
          {
            "context": "Dry-run smoke — react-spa-webpack"
          },
          {
            "context": "Every skeleton ships the hosted-reviewer config"
          },
          {
            "context": "Function length — 60 lines, docstring excluded"
          },
          {
            "context": "Gate integrity — a PR must not weaken a check without saying why"
          },
          {
            "context": "GitGuardian Security Checks"
          },
          {
            "context": "GitGuardian — secret scan"
          },
          {
            "context": "Lockfile sync — templates/*/package.json vs package-lock.json"
          },
          {
            "context": "Makefile <-> tasks.sh <-> bin/help.sh pairing (blueprintx#241)"
          },
          {
            "context": "MkDocs build — strict mode"
          },
          {
            "context": "PR file-count ceiling — 90 files (blueprintx#551)"
          },
          {
            "context": "Pre-commit and CI run the same checks, both directions (blueprintx#384)"
          },
          {
            "context": "Review threads answered"
          },
          {
            "context": "Review-bot roster opt-out — \"no\" must omit .review-bots.yaml"
          },
          {
            "context": "Scaffold + lint + test (multi-intent) — mvc-service-native-db"
          },
          {
            "context": "Scaffold + lint + test (multi-intent) — mvc-service-orm-db"
          },
          {
            "context": "Scaffold + lint + test (storage opt-in) — api-service-native-db"
          },
          {
            "context": "Scaffold + lint + test (storage opt-in) — ddd-service-native-db"
          },
          {
            "context": "Scaffold + lint + test (storage opt-in) — ddd-service-orm-db"
          },
          {
            "context": "Scaffold + lint + test — ddd-service-native-db"
          },
          {
            "context": "Scaffold + lint + test — ddd-service-orm-db"
          },
          {
            "context": "Scaffold + lint + test — lib-minimal"
          },
          {
            "context": "Scaffold + lint + test — mvc-service-native-db"
          },
          {
            "context": "Scaffold + lint + test — mvc-service-orm-db"
          },
          {
            "context": "Scaffold origin verification — mismatched remote must fail"
          },
          {
            "context": "Shared test copy lists — scaffolds vs python-common"
          },
          {
            "context": "ShellCheck — bin/**/*.sh"
          },
          {
            "context": "Spell check — docs/ and templates/"
          },
          {
            "context": "TypeScript build + lint — react-spa-webpack template"
          },
          {
            "context": "TypeScript build + lint — ts-lib template"
          },
          {
            "context": "Validate skeleton.meta integrity"
          },
          {
            "context": "Version sync — pyproject vs CLI"
          },
          {
            "context": "actionlint — workflows (repo + templates)"
          },
          {
            "context": "docs/ boundary guard"
          },
          {
            "context": "gitleaks — repo history (root + templates)"
          },
          {
            "context": "markdownlint — measured rule set (blueprintx#383)"
          },
          {
            "context": "promote_offline_to_online.sh refusal-path tests"
          },
          {
            "context": "quality-rules.yaml validation (blueprintx#432)"
          },
          {
            "context": "scaffold kanban board and labels"
          },
          {
            "context": "sed portability — no bare sed -i (blueprintx#459)"
          }
        ]
      }
    }
  ]
}```
