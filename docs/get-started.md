# 🚀 **Get Started**

## 1. Clone the repository

```bash
git clone https://github.com/guilhermegor/blueprintx.git
cd blueprintx
```

## 2. Run the interactive scaffolder

```bash
make init        # interactive scaffolder
make preview     # show skeleton structures
make dev         # scaffold into a temp dir (kept)
make dev-clean   # scaffold into temp dir and auto-delete on exit
make dry-run     # print structure; no files written
```

---

## Requirements

- `bash` ≥ 4
- For Python skeletons: `pyenv`/`poetry` (or your Python toolchain of choice) in the generated project

---

## ✨ Highlights

- **Interactive CLI** (`make init`) with skeleton choice
- **Ready-made skeletons** (currently Python): DDD service (hexagonal/ports-and-adapters) and lib-minimal
- **Common Python baseline**: templated `pyproject.toml`, pre-commit, VS Code settings, CI workflow, CODEOWNERS, PR template, and test folders
- **Dev/preview modes**: temp scaffolds, dry-run structure previews, optional auto-clean

---

📦 **GitHub Repository:** [github.com/guilhermegor/blueprintx](https://github.com/guilhermegor/blueprintx)
