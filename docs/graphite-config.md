<!-- Single-sourced from templates/common/.greptile/graphite.md, which every scaffold ships. -->
--8<-- "templates/common/.greptile/graphite.md"

## In BlueprintX itself

The BlueprintX root has no `.greptile/rules.md` (each skeleton ships its own, under
`templates/<skeleton>/.greptile/`). The file-based rule for this repository points at
`CLAUDE.md` instead. The ship check for the shared page is
`bin/ci/check_review_config_shipped.sh`, which lists it in
`templates/common/review-config.manifest`.
