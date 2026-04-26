# **${PROJECT_DISPLAY_NAME}**

A Domain-Driven Design service with a hexagonal (ports-and-adapters) layout, using SQLAlchemy ORM for database access.

---

## Contents

| Section | Description |
|---------|-------------|
| [Architecture](architecture.md) | DDD layer structure, SQLAlchemy session management, and design decisions |
| [API Reference](api.md) | Session factory usage, use-case wiring, and extension patterns |

---

## Quick start

```bash
make init          # bootstrap virtual environment and install pre-commit hooks
make start         # run the application
make docs_server   # serve this documentation at http://0.0.0.0:8000
```

---

Generated from the **DDD Service (ORM DB)** template via [BlueprintX](https://github.com/guilhermegor/BlueprintX).
