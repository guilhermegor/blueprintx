# **pytho290** <img src="assets/logo.png" align="right" width="200" style="border-radius: 15px;" alt="pytho290">

A Domain-Driven Design service with a hexagonal (ports-and-adapters) layout, using native database drivers for fine-grained control over queries and connections.

---

## Contents

| Section | Description |
|---------|-------------|
| [Architecture](architecture.md) | DDD layer structure, folder layout, and design decisions |
| [API Reference](api/index.md) | Factory usage, use-case wiring, and extension patterns |

---

## Quick start

```bash
bash bin/venv.sh   # bootstrap the venv (poe lives inside it, so bootstrap is shell)
poe run            # run the application
poe docs_server   # serve this documentation at http://0.0.0.0:8000
```

---

Generated from the **DDD Service (Native DB)** template via [BlueprintX](https://github.com/guilhermegor/BlueprintX).
