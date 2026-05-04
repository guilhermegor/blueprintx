# **Home**
![BlueprintX logo](https://raw.githubusercontent.com/guilhermegor/blueprintx/main/assets/logo.png)


Lightweight scaffolding tool (Make + bash) for creating ready-to-code projects. It is language-agnostic by design.

📦 **GitHub Repository:** [github.com/guilhermegor/blueprintx](https://github.com/guilhermegor/blueprintx)

---

## 🚀 Get Started

New to BlueprintX? See the [Get Started guide](get-started.md) for installation and quick start instructions.

---

## Python scaffolds
- DDD Service (Native DB): Domain-Driven Design, hexagonal service skeleton with per-feature capabilities and shared chassis infrastructure. Uses native database libraries (psycopg2, sqlite3, cx_Oracle, etc.). See [DDD Service (Native DB)](py-ddd-service-native-db.md).
- DDD Service (ORM DB): Same DDD/hexagonal structure, but uses SQLAlchemy ORM for database operations. See [DDD Service (ORM DB)](py-ddd-service-orm-db.md).
- Lib Minimal: lean library starter with packaging, tests, and CI ready. See [Lib Minimal](py-lib-minimal.md).

## TypeScript scaffolds
- React SPA (Webpack): Single-page application using React 19, TypeScript 5, Webpack 5, Babel, ESLint (flat config), and Prettier. Src directories pre-created for components, pages, contexts, models, routers, utils, and more. See [React SPA (Webpack)](ts-react-spa-webpack.md).

## View these docs locally (Poetry)
**Option A (direct)**
1. Install docs deps: `poetry install --with docs`
2. Serve with live reload: `poetry run mkdocs serve -a 0.0.0.0:8000 --livereload`
3. Build static site: `poetry run mkdocs build`

**Option B (Make recipes)**
1. `make mkdocs_server` (installs docs deps, serves with live reload)
2. `make mkdocs-build` (builds static site)

## Scaffolder quick reference
- Interactive menu: `make new`
- Preview structures: `make preview`
- Temp sandbox: `make dev` or `make dev-clean`
- Structure-only preview: `make dry-run`

Each scaffold copies shared assets from a common template directory (`templates/python-common` for Python, `templates/ts-common` for TypeScript) and then applies its skeleton-specific layout. New skeletons are discovered automatically via `skeleton.meta` files — no changes to the menu code needed.
