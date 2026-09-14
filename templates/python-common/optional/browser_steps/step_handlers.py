"""Recorded-browser-step runner — dict dispatch over the fixed step vocabulary.

Each step in ``data/browser-steps/*.json`` is ``{"kind": <name>, ...fields}``. The set
of valid ``kind`` values is :data:`STEP_KINDS`, derived from :data:`_DICT_STEP_HANDLERS`
itself rather than kept as a second, hand-maintained list — adding a step kind means
adding a dict entry, not another ``elif`` branch (see ``common.md`` — Design Patterns →
dict dispatch).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from .ports import BrowserPage, BrowserStep, BrowserStepError
from .secrets import resolve_placeholders


async def _navigate(cls_page: BrowserPage, dict_step: BrowserStep, path_root: Path) -> None:
    """Load ``url`` in the page."""
    await cls_page.goto(resolve_placeholders(dict_step["url"]))


async def _fill(cls_page: BrowserPage, dict_step: BrowserStep, path_root: Path) -> None:
    """Type ``value`` into the element at ``selector``."""
    await cls_page.fill(dict_step["selector"], resolve_placeholders(dict_step["value"]))


async def _fill_date(cls_page: BrowserPage, dict_step: BrowserStep, path_root: Path) -> None:
    """Type a formatted date ``value`` into a plain masked-text date input.

    Kept distinct from ``datepicker`` because a masked text input and a vendor calendar
    widget need different interactions, not the same ``fill``.
    """
    await cls_page.fill(dict_step["selector"], resolve_placeholders(dict_step["value"]))


async def _click(cls_page: BrowserPage, dict_step: BrowserStep, path_root: Path) -> None:
    """Click the element at ``selector``."""
    await cls_page.click(dict_step["selector"])


async def _select(cls_page: BrowserPage, dict_step: BrowserStep, path_root: Path) -> None:
    """Choose ``option`` from the ``<select>`` at ``selector``."""
    await cls_page.select_option(dict_step["selector"], dict_step["option"])


async def _wait(cls_page: BrowserPage, dict_step: BrowserStep, path_root: Path) -> None:
    """Pause for ``timeout_ms`` milliseconds (use only when no selector settles the wait)."""
    await cls_page.wait_for_timeout(dict_step["timeout_ms"])


async def _datepicker(cls_page: BrowserPage, dict_step: BrowserStep, path_root: Path) -> None:
    """Open a vendor calendar widget at ``selector`` and click the day cell ``value``.

    The widget-specific mechanics (which selector reaches which day cell) live in the
    recording, not in this handler — a re-record after a vendor UI change is the fix.
    """
    await cls_page.click(dict_step["selector"])
    await cls_page.click(resolve_placeholders(dict_step["value"]))


async def _download(cls_page: BrowserPage, dict_step: BrowserStep, path_root: Path) -> None:
    """Click ``trigger_selector`` and save the resulting download to ``save_path``."""
    async with cls_page.expect_download() as cls_download_info:
        await cls_page.click(dict_step["trigger_selector"])
    cls_download = await cls_download_info.value
    await cls_download.save_as(
        str(_contained_path(resolve_placeholders(dict_step["save_path"]), path_root))
    )


def _contained_path(str_raw: str, path_root: Path) -> Path:
    """Resolve ``str_raw`` under ``path_root`` and refuse anything that escapes it.

    Parameters
    ----------
    str_raw : str
            The recorded ``save_path``, already placeholder-expanded.
    path_root : Path
            The only directory a recording is allowed to write into.

    Returns
    -------
    Path
            The resolved destination, guaranteed to sit under ``path_root``.

    Raises
    ------
    BrowserStepError
            If the destination resolves outside ``path_root``.

    Notes
    -----
    A recording is DATA an analyst re-records from a vendor UI, so ``save_path`` is
    untrusted input: an absolute path or ``../`` writes wherever the process can.
    ``resolve()`` is what makes this hold — it expands symlinks, so a root containing a
    symlink out of the tree cannot be used to escape by following it.
    """
    path_root = path_root.resolve()
    path_target = (path_root / str_raw).resolve()
    if not path_target.is_relative_to(path_root):
        raise BrowserStepError(
            f"save_path {str_raw!r} resolves outside the download root {path_root}"
        )
    path_target.parent.mkdir(parents=True, exist_ok=True)
    return path_target


_DICT_STEP_HANDLERS: dict[str, Callable[[BrowserPage, BrowserStep, Path], Awaitable[None]]] = {
    "navigate": _navigate,
    "fill": _fill,
    "fill_date": _fill_date,
    "click": _click,
    "select": _select,
    "wait": _wait,
    "datepicker": _datepicker,
    "download": _download,
}

STEP_KINDS = frozenset(_DICT_STEP_HANDLERS)

# The fields each kind needs, and their type. A second dict keyed by the same kind IS the
# drift this module's dispatch design exists to avoid, so test_step_handlers.py asserts the
# two keysets are equal — a new handler with no entry here fails the suite, it does not
# silently skip validation.
_DICT_REQUIRED_FIELDS: dict[str, tuple[tuple[str, type], ...]] = {
    "navigate": (("url", str),),
    "fill": (("selector", str), ("value", str)),
    "fill_date": (("selector", str), ("value", str)),
    "click": (("selector", str),),
    "select": (("selector", str), ("option", str)),
    "wait": (("timeout_ms", int),),
    "datepicker": (("selector", str), ("value", str)),
    "download": (("trigger_selector", str), ("save_path", str)),
}


def _validate_step(int_index: int, str_kind: str, dict_step: BrowserStep) -> None:
    """Check that ``dict_step`` carries every field its kind needs, at the right type.

    Parameters
    ----------
    int_index : int
            Position in the recording, named in the error so a bad file is findable.
    str_kind : str
            The already-validated step kind.
    dict_step : BrowserStep
            The raw parsed step.

    Raises
    ------
    BrowserStepError
            If a required field is absent or of the wrong type.

    Notes
    -----
    Without this, a hand-edited recording reaches the handler and fails with a raw
    ``KeyError``/``TypeError`` carrying neither the step index nor the file — the runner
    reports a Python internal instead of "step 4 of this recording is missing url".
    ``bool`` is rejected for ``int`` on purpose: ``True`` is a valid ``int`` to
    ``isinstance`` and a nonsense timeout.
    """
    for str_field, cls_type in _DICT_REQUIRED_FIELDS[str_kind]:
        if str_field not in dict_step:
            raise BrowserStepError(
                f"Step {int_index} ({str_kind!r}): missing required field {str_field!r}"
            )
        obj_value = dict_step[str_field]
        bool_wrong_type = not isinstance(obj_value, cls_type)
        bool_bool_as_int = cls_type is int and isinstance(obj_value, bool)
        if bool_wrong_type or bool_bool_as_int:
            raise BrowserStepError(
                f"Step {int_index} ({str_kind!r}): field {str_field!r} must be "
                f"{cls_type.__name__}, got {type(obj_value).__name__}"
            )


async def run_browser_steps(
    list_steps: list[BrowserStep],
    cls_page: BrowserPage,
    path_download_root: Path | None = None,
) -> None:
    """Run a recorded flow: interpret each step in ``list_steps`` in order.

    Parameters
    ----------
    list_steps : list[BrowserStep]
            Parsed from a ``data/browser-steps/*.json`` file.
    cls_page : BrowserPage
            A live Playwright page, or a test double satisfying the same Protocol.
    path_download_root : Path or None, optional
            The ONLY directory a ``download`` step may write into; defaults to
            ``data/downloads`` under the current directory. A recorded ``save_path`` is
            resolved under it and refused if it escapes.

    Raises
    ------
    BrowserStepError
            If a step's ``kind`` is not one of :data:`STEP_KINDS`, a step is missing a
            required field or has one of the wrong type, a ``download`` step's ``save_path``
            escapes ``path_download_root``, or a step references an unset secret placeholder.
    """
    path_root = Path("data/downloads") if path_download_root is None else path_download_root
    for int_index, dict_step in enumerate(list_steps):
        str_kind = dict_step.get("kind", "")
        if str_kind not in _DICT_STEP_HANDLERS:
            raise BrowserStepError(
                f"Step {int_index}: unknown kind {str_kind!r}; expected one of "
                f"{sorted(STEP_KINDS)}"
            )
        _validate_step(int_index, str_kind, dict_step)
        await _DICT_STEP_HANDLERS[str_kind](cls_page, dict_step, path_root)
