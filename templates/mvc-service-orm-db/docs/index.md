# **${PROJECT_DISPLAY_NAME}**

<img src="assets/logo.png" alt="Project logo" class="hero-logo">

A layered MVC service (Model–View–Controller) using the SQLAlchemy ORM. The controller orchestrates a pandas-driven pipeline: read via the model, render via the view.

---

## Contents

| Section | Description |
|---------|-------------|
| [Architecture](architecture.md) | MVC layer structure, folder layout, and design decisions |
| [API Reference](api/index.md) | Engine/session factory, model/view usage, and extension patterns |

---

## Quick start

```bash
make init          # bootstrap virtual environment and install pre-commit hooks
make start         # run the application (src/controller/main.py)
make docs_server   # serve this documentation at http://0.0.0.0:8000
```

---

Generated from the **MVC Service (ORM)** template via [BlueprintX](https://github.com/guilhermegor/BlueprintX).
