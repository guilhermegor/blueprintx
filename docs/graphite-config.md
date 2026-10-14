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

Documented, not measured: the docs describe label filtering but no comment trigger, and do
not say whether adding a label fires a review or the label is only checked on the next push.
Settle that on a real PR once the App is installed.
