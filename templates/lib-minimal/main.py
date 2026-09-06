"""Library entry point.

Rename or split this module as the library's public API grows.
"""

# ⚠️ RELATIVE IMPORT, deliberately — this is the one module in the tier that needs one.
# The curated helpers under `_internal/` are copied verbatim from python-common and have their
# bare `utils.`/`config.`/`chassis.typing` imports rewritten to `<pkg>._internal.…` by
# `rewrite_internal_imports` at scaffold time. That rewrite is scoped to the `_internal/` tree,
# and this file is copied to `src/<pkg>/main.py` — outside it. A bare `from utils.typing import
# …` here would therefore ship unrewritten and fail at import; a package-qualified absolute
# import cannot be written at all, because `<pkg>` is only known at scaffold time. The relative
# form is correct under every package name and needs no rendering step.
from ._internal.utils.typing import type_checker


@type_checker
def main() -> None:
    """Print a greeting — the placeholder entry point for a new library."""
    print("Hello from lib-minimal!")
