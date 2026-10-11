# CodeRabbit Configuration

Every generated project, online or offline, ships a `.coderabbit.yaml` at its root. The single
source is `templates/common/.coderabbit.yaml`, and BlueprintX's own root copy is byte-identical.
The file carries keys only; this page holds the explanation.

## The one active key

`reviews.auto_review.auto_incremental_review: false` stops CodeRabbit from re-reviewing the
changes added since the last review on every push. It does not re-review the whole PR when `true`.

## It may be a no-op

`reviews.auto_review.*` governs the automatic review path. CodeRabbit declines automatic
reviews on a repository with fewer than 10 stars, and that threshold is not configurable from
`.coderabbit.yaml`. Until a repository crosses it, the key has no effect.

## It is not the quota driver

Online Python projects ship `coderabbit_trigger.yaml`, which posts an explicit review request
on `opened`, `reopened`, and `ready_for_review`, regardless of this file. It no longer fires on
`synchronize`; another review is requested deliberately with `@coderabbitai full review`.

Before `synchronize` was removed, measurements on 2026-08-30 across 71 PRs updated in the prior
7 days found 773 CodeRabbit events after each PR's opening review. Of those, 42 (5.4%) produced
a new finding and 538 (69.6%) were rate-limit notices. Removing the push trigger addressed that
waste; this configuration does not control explicit review requests.

## Validation

The file validates against CodeRabbit's published schema,
`https://coderabbit.ai/integrations/schema.v2.json`.
