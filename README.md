# blueprintx

A lightweight Python project scaffolding tool based on Make + bash. Create consistent, production-ready project structures interactively.

## Features

- **Interactive project creation** with configurable options
- **Multiple project skeletons** for different use cases
- **Python environment management** via pyenv and uv
- **Clean, modular structure** with separated templates

## Supported Skeletons

### hex-service
Backend/service-oriented structure with core/modules separation, suitable for APIs and services using clean/hexagonal-ish design.

### lib-minimal  
Minimal library-style project, good for small libraries, tools, or starting points for simple CLIs or packages.

## Quick Start

```bash
make init
```

Then follow the interactive prompts to create your project.

To preview available structures:

```bash
make preview
```

## Requirements

- `bash` >= 4.0
- `pyenv` (for Python version management)
- `uv` (for dependency management)

## Project Structure

```
blueprintx/
├── Makefile
├── scripts/
│   ├── blueprintx.sh       # Main bootstrap script
│   ├── preview.sh          # Preview available skeletons
│   └── scaffold/
│       ├── python_hex_service.sh
│       └── python_lib_minimal.sh
└── templates/              # Template files for each skeleton
    ├── hex-service/
    └── lib-minimal/
```
