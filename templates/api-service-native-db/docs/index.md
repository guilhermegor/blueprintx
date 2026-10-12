# **${PROJECT_DISPLAY_NAME}** <img src="assets/logo.png" align="right" width="200" style="border-radius: 15px;" alt="${PROJECT_DISPLAY_NAME}">

An HTTP API service with a hexagonal (ports-and-adapters) layout — a FastAPI transport layer
over Domain-Driven Design capabilities, using native database drivers for fine-grained control
over queries and connections.

---

## Contents

| Section | Description |
|---------|-------------|
| [Architecture](architecture.md) | Hexagonal layer structure, folder layout, and design decisions |
| [API Reference](api/index.md) | Router wiring, factory usage, use-case wiring, and extension patterns |

---

## Quick start

```bash
bash bin/venv.sh   # bootstrap the venv (poe lives inside it, so bootstrap is shell)
poe run            # serve the application (uvicorn on :8000)
poe docs_server   # serve this documentation at http://0.0.0.0:8000
```

---

Generated from the **API Service (Native DB)** template via [BlueprintX](https://github.com/guilhermegor/BlueprintX).
