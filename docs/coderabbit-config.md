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

`coderabbit_trigger.yaml` fires on `synchronize` (every push to an open PR) and posts an
explicit review request, which CodeRabbit honours regardless of this file. Measured on
2026-08-30 across 71 PRs updated in the prior 7 days: 773 CodeRabbit events followed each
PR's opening review, 42 (5.4%) produced a new finding, and 538 (69.6%) were rate-limit notices.
The remedy for that waste is in the trigger workflow, not here.

## Validation

The file validates against CodeRabbit's published schema,
`https://coderabbit.ai/integrations/schema.v2.json`.
