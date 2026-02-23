<!-- markdownlint-disable MD013 -->
# BlueprintX <img src="public/logo.png" align="right" width="180" style="border-radius: 12px;" alt="BlueprintX logo">

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Bash](https://img.shields.io/badge/bash-%3E%3D4-4EAA25?logo=gnubash&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Open Issues](https://img.shields.io/github/issues/guilhermegor/BlueprintX)
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

**BlueprintX** is a lightweight scaffolding tool (Make + bash) for creating ready-to-code projects. It is language-agnostic by design.

## ✨ Highlights
- Interactive CLI (`make init`) with skeleton choice
- Ready-made skeletons (currently Python): **DDD service** (Domain-Driven Design, hexagonal/ports-and-adapters; template folder `templates/ddd-service`) and **lib-minimal**
- Common Python baseline: templated `pyproject.toml`, pre-commit, VS Code settings, CI workflow, CODEOWNERS, PR template, and test folders (unit/integration/performance)
- Dev/preview modes: temp scaffolds, dry-run structure previews, optional auto-clean

## 🚀 Quick start

```bash
make init        # interactive scaffolder
make preview     # show skeleton structures
make dev         # scaffold into a temp dir (kept)
make dev-clean   # scaffold into temp dir and auto-delete on exit
make dry-run     # print structure; no files written
```

Requirements: `bash` ≥ 4. For the current Python skeletons, use `pyenv`/`poetry` (or your Python toolchain of choice) in the generated project.

## 🏗️ Supported skeletons

### DDD service (templates/ddd-service)
Domain-Driven Design service skeleton with hexagonal/ports-and-adapters structure. `core` stays minimal (shared utilities/infra); `modules/<feature>` hosts the feature’s domain, application layer, and adapters.

```
project/
    src/
        core/
            domain/            # shared-only if truly cross-cutting
            infrastructure/    # shared infra building blocks
            application/       # shared application services (optional)
        modules/
            example_feature/   # rename per bounded context/feature
                domain/          # entities, value objects, domain services, ports
                application/     # use-cases orchestrating domain + ports
                infrastructure/  # adapters implementing ports (DB, APIs, queues)
        utils/
        config/
        main.py              # entrypoint; selects DB backend via .env
    tests/{unit,integration,performance}/
    container/
    scripts/
    public/
    docs/
    .github/
    .vscode/
    .env
    pyproject.toml
    requirements.txt
    README.md
```

Per-feature example (in template): `modules/example_feature/` with `Note` entity, ports, in-memory repo, and use-cases. Banking balance alert remains a docs-only illustration.

### lib-minimal
Lean library starter: package under `src/<project_name>/`, tests, CI, VS Code config, and pre-commit ready to go.

```
project/
    src/<project_name>/
    tests/{unit,integration,performance}/
    docs/
    container/
    scripts/
    .github/
    .vscode/
    .env
    pyproject.toml
    README.md
```

## 🧭 Folder attribution (ddd-service intent)
- `core/`: cross-cutting pieces only (shared infra, shared types). Keep lean to avoid a “god domain.”
- `modules/<feature>/domain`: feature/bounded-context domain (entities, value objects, domain services, ports).
- `modules/<feature>/application`: application/use-case layer orchestrating domain + ports; no framework code.
- `modules/<feature>/infrastructure`: adapters implementing ports (DB handlers, HTTP clients, brokers, files).
- `utils/`: generic helpers not tied to a feature.
- `config/`: configuration loading, settings.

## 📂 Repo layout (this tool)

```
BlueprintX/
├── Makefile                 # entry targets: init, preview, dev, dev-clean, dry-run
├── run.sh                   # same targets for non-make usage
├── scripts/
│   ├── blueprintx.sh        # interactive menu + modes
│   ├── preview.sh           # skeleton previews
│   ├── help.sh              # usage tips and targets
│   ├── init_venv.sh         # convenience venv bootstrap
│   └── scaffold/            # per-skeleton scaffolders
│       ├── python_ddd_service.sh
│       └── python_lib_minimal.sh
├── templates/               # skeleton contents
│   ├── ddd-service/         # DDD/hexagonal template with per-feature modules
│   ├── lib-minimal/         # minimal library template
│   └── python-common/       # shared assets copied to all Python projects (scripts, pyproject, CI, VS Code)
├── docs/                    # mkdocs sources
├── mkdocs.yml               # mkdocs config
└── public/logo.png          # logo used in this README
```

## 👨‍💻 Authors

**Guilherme Rodrigues**  
[![GitHub](https://img.shields.io/badge/GitHub-guilhermegor-181717?style=flat&logo=github)](https://github.com/guilhermegor)  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Guilherme_Rodrigues-0077B5?style=flat&logo=linkedin)](https://www.linkedin.com/in/guilhermegor/)

## 🔗 Useful Links

* [GitHub Repository](https://github.com/guilhermegor/BlueprintX)

* [Issue Tracker](https://github.com/guilhermegor/BlueprintX/issues)

## 🤝 Contributing
Issues and PRs are welcome. Please keep templates minimal, opinionated, and consistent across skeletons.

## 📜 License
MIT. See [LICENSE](LICENSE).
