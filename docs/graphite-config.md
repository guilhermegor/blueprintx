# Graphite Configuration

Graphite has no repo-level config file (no `.graphite.yaml`). Everything below is either one
versioned file or a dashboard step the repository owner performs by hand.

## What the repository versions

- `.gitattributes` marks lockfiles, the coverage badge and the comment-budget baseline
  `linguist-generated=true`. Per Graphite's docs, marked files are collapsed in the Graphite
  and GitHub diff views, skipped by the AI review and excluded from its PR size check. They
  are collapsed for every reviewer and human too.
- The review rules are the existing `.greptile/rules.md`. There is no `.graphite/` copy.

## Dashboard steps (not versionable)

1. Install the Graphite GitHub App on the account (personal accounts: *Join team*), then
   sync the repository.
2. AI reviews, enable the repository.
3. Rules & exclusions, add a file-based rule with the glob `.greptile/rules.md`
   (globs are case-sensitive; large files are truncated).
4. Settings tab (org-admin rights required), PR filtering by **PR labels**: restrict AI
   reviews to PRs carrying `review:graphite`.

## Never auto-review

Graphite reviews every new PR by default. The label filter in step 4 is the opt-in: the
`/dev-loop` ladder adds `review:graphite` when it is Graphite's turn and removes it once the
review lands. A label left on lets every push trigger another review.

What the docs say: PR-level filtering by label applies to new and updated PRs. They describe
no "label added" event and no comment trigger.

Documented, not measured: whether adding the label alone fires a review. That stays unknown until Graphite
is installed on a repo and the behavior is tested on a real PR. Until then the ladder may
need to push a commit or post a comment after adding the label, and must not assume a
Graphite turn has started just because the label was added. If adding the label fires
nothing, a `/dev-loop` Graphite turn completes without a review.
