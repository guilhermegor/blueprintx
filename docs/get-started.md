# 🚀 **Get Started**

## 1. Clone the repository

```bash
git clone https://github.com/guilhermegor/blueprintx.git
cd blueprintx
```

## 2. Run the interactive scaffolder

```bash
make new         # interactive scaffolder
make preview     # show skeleton structures
make dev         # scaffold into a temp dir (kept)
make dev-clean   # scaffold into temp dir and auto-delete on exit
make dry-run     # print structure; no files written
```

---

## Requirements

- `bash` ≥ 4
- For **Python skeletons**: `pyenv` + `poetry` (or your Python toolchain of choice) in the generated project
- For **TypeScript skeletons**: Node.js ≥ 20; run `npm install` after scaffolding

---

## ✨ Highlights

- **Interactive CLI** (`make new`) with auto-discovered language and skeleton menus
- **Python skeletons**: DDD service (hexagonal/ports-and-adapters, native DB or SQLAlchemy ORM) and lib-minimal
- **TypeScript skeletons**: React SPA with Webpack 5, Babel, ESLint, and Prettier
- **Common Python baseline**: templated `pyproject.toml`, pre-commit, VS Code settings, CI workflow, CODEOWNERS, PR template, and test folders
- **Common TypeScript baseline**: `package.json` with pinned deps, `.gitignore`, VS Code settings, `CONTRIBUTING.md`
- **Dev/preview modes**: temp scaffolds, dry-run structure previews, optional auto-clean
- **Extensible**: add a `skeleton.meta` to any `templates/` directory and it appears in the menu automatically

---

📦 **GitHub Repository:** [github.com/guilhermegor/blueprintx](https://github.com/guilhermegor/blueprintx)
