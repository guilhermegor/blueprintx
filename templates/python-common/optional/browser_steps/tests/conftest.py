"""Make the standalone ``browser_steps`` package importable for these tests.

Every ``optional/*`` module is a copy-verbatim source snippet: its internal imports are
written assuming the scaffold has already placed it at ``src/chassis/`` or ``src/utils/``,
so nothing under ``optional/`` is importable from the template tree as-is (mirrors
``optional/webhook/``, which ships with no tests for the same reason). This package uses
relative imports internally (see the package docstring), so — unlike ``chassis.webhook``'s
hardcoded prefix — it only needs its **parent directory** on ``sys.path`` to import as a
plain top-level package; no scaffold copy is required to exercise the logic itself.
"""

from __future__ import annotations

from pathlib import Path
import sys


_PATH_OPTIONAL = Path(__file__).resolve().parents[2]
if str(_PATH_OPTIONAL) not in sys.path:
	sys.path.insert(0, str(_PATH_OPTIONAL))
