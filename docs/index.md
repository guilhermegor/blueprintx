# blueprintx documentation

Lightweight scaffolding (Make + bash) with ready-to-code Python skeletons. Use these pages to understand what each scaffold gives you and how to extend it with the intended layering.

## Scaffolds covered
- Hex Service: hex/DDD-leaning service skeleton with per-feature modules and shared infrastructure. See [Hex Service](hex-service.md).
- Lib Minimal: lean library starter with packaging, tests, and CI ready. See [Lib Minimal](lib-minimal.md).

## View these docs locally (Poetry)
1. Add mkdocs to the docs group: `poetry add --group docs mkdocs`
2. Serve locally: `poetry run mkdocs serve -a 0.0.0.0:8000`
3. Build static site: `poetry run mkdocs build`

## Scaffolder quick reference
- Interactive menu: `make init`
- Preview structures: `make preview`
- Temp sandbox: `make dev` or `make dev-clean`
- Structure-only preview: `make dry-run`

Each scaffold copies shared Python assets from `templates/python-common` (pyproject, pre-commit, VS Code, CI, README boilerplate) and then applies its template-specific layout.
