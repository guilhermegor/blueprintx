# BlueprintX documentation

![BlueprintX logo](https://raw.githubusercontent.com/guilhermegor/blueprintx/main/public/logo.png)


Lightweight scaffolding tool (Make + bash) for creating ready-to-code projects. It is language-agnostic by design.

## Scaffolds covered
- Hex Service: hex/DDD-leaning service skeleton with per-feature modules and shared infrastructure. See [Hex Service](hex-service.md).
- Lib Minimal: lean library starter with packaging, tests, and CI ready. See [Lib Minimal](lib-minimal.md).

## View these docs locally (Poetry)
**Option A (direct)**
1. Install docs deps: `poetry install --with docs`
2. Serve with live reload: `poetry run mkdocs serve -a 0.0.0.0:8000 --livereload`
3. Build static site: `poetry run mkdocs build`

**Option B (Make recipes)**
1. `make mkdocs-serve` (installs docs deps, serves with live reload)
2. `make mkdocs-build` (builds static site)

## Scaffolder quick reference
- Interactive menu: `make init`
- Preview structures: `make preview`
- Temp sandbox: `make dev` or `make dev-clean`
- Structure-only preview: `make dry-run`

Each scaffold copies shared Python assets from `templates/python-common` (pyproject, pre-commit, VS Code, CI, README boilerplate) and then applies its template-specific layout.
