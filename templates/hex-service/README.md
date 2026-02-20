# ${PROJECT_NAME}

Generated with blueprintx (skeleton: hex-service).

## Tech stack

- Python (managed via pyenv: see `.python-version`)
- Dependencies via `uv` using `pyproject.toml`
- Uvicorn

## Quickstart

1. Ensure you have `pyenv` and `uv` installed.

2. Set Python version (pyenv will pick up `.python-version` automatically):

   ```bash
   pyenv install --skip-existing 3.12.2
   pyenv local 3.12.2
   ```

3. Install dependencies with `uv`:

   ```bash
   uv sync
   ```

4. Run the app:

   ```bash
   uv run uvicorn src.main:main --reload
   ```

## Structure

- `src/core`: core/domain, infra and services
- `src/modules`: business modules
- `src/utils`, `src/config`, `tests`, `docs`, etc.
