"""Resolve a sender's HTML e-mail signature.

The signature for a sending account lives at
``src/config/signatures/<sender>.html``; when that file is absent the shared
``default.html`` is used. Any e-mail notifier resolves it the same way, so the
logic lives here once.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). TYPE_CHECKING stubs the decorator's shape
# locally instead of importing: mypy treats a try/except import as executed code and flags
# the redefinition once actually checked, so this branch can't pick either layout
# (blueprintx#360). Runtime still resolves the real engine via try/except below.
if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    _F = TypeVar("_F", bound=Callable[..., object])

    def type_checker(fn: _F) -> _F:
        """Type-only stub — see src/utils/CLAUDE.md."""
else:
    try:
        from utils.typing import type_checker
    except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
        from chassis.typing import type_checker


@type_checker
def resolve_signature(path_signatures_dir: Path, str_sender_email: str) -> str:
    """Return the sender's signature HTML, falling back to the default.

    Parameters
    ----------
    path_signatures_dir : pathlib.Path
            Directory holding ``<sender>.html`` / ``default.html``.
    str_sender_email : str
            Sender account; selects ``<sender>.html``.

    Returns
    -------
    str
            Signature HTML (``<sender>.html``, else ``default.html``, else empty).
    """
    # "First existing candidate, else empty" stated as a search rather than a loop with an
    # exit in the middle. The preference order stays visible in the tuple, which is where a
    # reader looks for it.
    list_candidates = [
        path_signatures_dir / str_name for str_name in (f"{str_sender_email}.html", "default.html")
    ]
    path_sig = next((path for path in list_candidates if path.exists()), None)
    return path_sig.read_text(encoding="utf-8") if path_sig is not None else ""


@type_checker
def to_html(str_body: str) -> str:
    """Convert a plain-text body to minimal HTML (newlines to ``<br>``).

    Parameters
    ----------
    str_body : str
            Plain-text body.

    Returns
    -------
    str
            HTML body.
    """
    return str_body.replace("\n", "<br>\n")
