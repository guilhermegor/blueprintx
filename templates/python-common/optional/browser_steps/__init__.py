"""Recorded-browser-step runner (opt-in, service tiers only, blueprintx#228).

A recorded browser flow — clicking through a vendor screen with no API (JSF/PrimeFaces,
slickgrid, any stateful corporate UI) — is captured as **data**, never as Python: an
analyst re-records the screen in DevTools and an operator ships the fix without touching
code. ``data/browser-steps/*.json`` holds the recording; this package holds the runner
that interprets it.

The runner reads a fixed, small vocabulary via dict dispatch (:data:`STEP_KINDS` in
:mod:`.step_handlers`) — ``navigate`` / ``fill`` / ``fill_date`` / ``click`` /
``select`` / ``wait`` / ``datepicker`` / ``download`` — so the set of valid step kinds
is derived from the same place the behaviour lives, not duplicated in a schema someone
has to remember to update.

Two things a raw DevTools recording is missing, made explicit here:

- **Secrets never enter the JSON.** A step value may reference ``${ENV_VAR}`` (the same
  placeholder syntax this repo's own ``pyproject.toml`` templates use for ``envsubst`` —
  reused rather than inventing a second one); :func:`resolve_placeholders` substitutes it
  from the process environment and fails fast when the variable is unset.
- **Session state is not a step.** Login cookies/local storage are Playwright's own
  ``storage_state`` (``BrowserContext.storage_state()`` / ``new_context(storage_state=)``)
  — a native feature, not something this vocabulary reimplements. The caller persists it
  outside the step file and loads it when creating the browser context.

Public API (import from this package; the module split is an implementation detail):

- :class:`BrowserStep` — one recorded action, as it appears in the JSON file.
- :class:`BrowserPage` — the Playwright ``Page`` subset the handlers call (a
  ``Protocol``, so this package carries no hard dependency on ``playwright``).
- :class:`BrowserStepError` — raised for an unknown step kind or an unresolved secret.
- :data:`STEP_KINDS` — the frozenset of valid step kinds, derived from the dispatch table.
- :func:`run_browser_steps` — run a recorded flow against a live (or fake) page.
- :func:`resolve_placeholders` — resolve ``${ENV_VAR}`` references in one field value.

⚠️ Internal imports are **relative** (``from .ports import …``), unlike the sibling
``optional/webhook/`` seam (which hardcodes ``chassis.webhook`` and relies on the MVC
scaffold to rewrite it to ``utils.webhook``). Relative imports resolve unchanged under
either prefix, so this package needs no rewrite step once it is wired into a scaffold —
one fewer thing to keep in sync. It is also a flat package (no ``domain``/
``infrastructure`` split): this repo's ruff config bans parent-relative imports
(``TID252``), so a nested split would have forced the same absolute-prefix problem
straight back.
"""

from .ports import BrowserPage, BrowserStep, BrowserStepError
from .secrets import resolve_placeholders
from .step_handlers import STEP_KINDS, run_browser_steps


__all__ = [
    "STEP_KINDS",
    "BrowserPage",
    "BrowserStep",
    "BrowserStepError",
    "resolve_placeholders",
    "run_browser_steps",
]
