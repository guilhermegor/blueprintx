"""Enforce that every file/scrape read is paired with a provenance stamp.

Ingestion honesty has two halves that must never drift apart: the ``read_table`` contract
check (already enforced — bare ``pd.read_*`` is banned by ruff ``TID251`` so every read funnels
through a contract) and the ``stamp_provenance`` call that makes the resulting bronze row
traceable. This hook is the second guardrail: for every ``.py`` under ``src/``, **if the module
calls ``read_table(`` it must also reference ``stamp_provenance``** — so a file/scrape read
cannot ship without a stamp.

The token is the **call form** ``read_table(``, deliberately, for two reasons:

- It excludes ``read_query`` (the SQL sibling) — a DataFrame read back from your own database is
  **not** internet-ingested and is out of provenance scope (see the dtypes/provenance lesson).
- It excludes prose mentions of the bare name (e.g. a ``FileContract`` module docstring that
  says "passed to ``read_table``") — those are declarations, not reads.

Inheritance is handled naturally: a base reader that calls both satisfies the check; thin
subclasses that inherit ``read()`` call neither and are fine. The seam module
``utils/tabular_reader.py`` — which *defines* ``def read_table(`` — is exempt (pairing it would
be circular).

Every finding is a hard error (exit 1).
"""

import pathlib
import sys


# The read whose provenance stamp this hook enforces (the CALL form — see the module docstring
# for why the trailing paren matters) and the stamp marker that must accompany it. MARKER, not
# token: these are source-text sentinels, and "TOKEN" reads as a credential to a reader and to
# bandit (S105) alike.
_READ_MARKER = "read_table("
_STAMP_MARKER = "stamp_provenance"

# Directory names excluded from the doctrine, mirroring bin/check_typing.py's excludes:
#   - ``typing``           — the runtime type-checking engine itself;
#   - ``chassis``          — cross-cutting reference scaffolding;
#   - ``example_feature``  — the DDD example capability, reference scaffolding, not production.
_EXCLUDED_PARTS = {"typing", "chassis", "example_feature"}

# The seam files that *define* the tokens (rather than *use* them) — exempt from pairing.
_SEAM_FILENAMES = {"tabular_reader.py", "provenance.py"}


def check_file(filepath: str) -> int:
	"""Return 1 when a module references a contract read without a provenance stamp.

	Parameters
	----------
	filepath : str
		Path to a Python source file under ``src/``.

	Returns
	-------
	int
		1 when ``read_table`` appears without ``stamp_provenance``, else 0.
	"""
	str_source = pathlib.Path(filepath).read_text(encoding="utf-8")
	if _READ_MARKER not in str_source:
		return 0
	if _STAMP_MARKER in str_source:
		return 0
	print(
		f"❌ {filepath}: calls '{_READ_MARKER}' but never references '{_STAMP_MARKER}' — a "
		f"file/scrape read must stamp provenance (utils.provenance.stamp_provenance) so its "
		f"bronze rows stay traceable."
	)
	return 1


def _source_files() -> list[pathlib.Path]:
	"""Collect every Python file under ``src/`` except the documented exempt trees and seams.

	Returns
	-------
	list[pathlib.Path]
		Python source files to check (``typing``/``chassis``/``example_feature`` trees and the
		``tabular_reader.py``/``provenance.py`` seam definitions are exempt).
	"""
	return sorted(
		p
		for p in pathlib.Path("src").rglob("*.py")
		if _EXCLUDED_PARTS.isdisjoint(p.parts) and p.name not in _SEAM_FILENAMES
	)


if __name__ == "__main__":
	# Windows' stdout defaults to cp1252, which cannot encode the status glyphs this
	# script prints: it would die with UnicodeEncodeError before reporting anything. And
	# because this backs an always_run pre-commit hook, that crash blocks EVERY commit from
	# a Windows checkout rather than failing the file under check. Fixed at the I/O seam so
	# the glyphs stay; a test pins it with PYTHONIOENCODING=cp1252.
	for cls_stream in (sys.stdout, sys.stderr):
		if hasattr(cls_stream, "reconfigure"):
			cls_stream.reconfigure(encoding="utf-8", errors="replace")

	# ⚠️ Zero discovery is a FAILURE, not a clean tree. `_source_files()` globs `src/`, so a
	# renamed layout, a wrong cwd, or an exclusion list that grew too broad all make this
	# gate iterate nothing, sum to 0 and exit 0 — reporting success for having checked
	# nothing, silently. That is the failure mode this gate exists to prevent in someone
	# else's data, and it had it (blueprintx#111). Every tier inherits python-common's
	# `src/utils/` + `src/config/`, so a real project can never legitimately reach zero.
	list_targets = _source_files()
	if not list_targets:
		print("❌ no Python files found under src/ — refusing to report success.")
		sys.exit(1)

	total_errors = sum(check_file(str(p)) for p in list_targets)
	if total_errors == 0:
		# Print WHAT was checked: a silent gate is indistinguishable from an absent one.
		print(f"✅ provenance stamp OK ({len(list_targets)} file(s) checked)")
	sys.exit(1 if total_errors > 0 else 0)
