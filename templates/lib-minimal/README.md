# ${PROJECT_NAME}

Generated with blueprintx (skeleton: lib-minimal).

## Tech stack

- Python (managed via pyenv: see `.python-version`)
- Dependencies via `uv` using `pyproject.toml`
- Optional dev dependencies: `pytest`

## Quickstart

1. Ensure you have `pyenv` and `uv` installed.

2. Set Python version:

   ```bash
   pyenv install --skip-existing 3.12.2
   pyenv local 3.12.2
   ```

3. Install dependencies with `uv`:

   ```bash
   uv sync
   ```

4. Run tests:

   ```bash
   uv run pytest
   ```

5. Use the library:

   ```bash
   uv run python -c "from ${PROJECT_NAME}.main import main; main()"
   ```
