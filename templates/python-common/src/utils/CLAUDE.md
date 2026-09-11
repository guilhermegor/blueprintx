# CLAUDE.md

Conventions for every module in `utils/` and its subpackages (`ms_office/`, `email/`,
`retry/`). This directory ships verbatim into every Python skeleton's `src/utils/` (see the
root `templates/python-common/CLAUDE.md`) — it is the **seam layer**: the one place a
third-party dependency is imported, wrapped behind a first-party function or class the rest
of the project depends on instead.

## The seam rule

A vendor is imported here, never in `model/`/`view`/`controller` (MVC) or
`capabilities/*/domain`/`application` (DDD). This is enforced, not just documented —
`bin/check_layer_imports.py` reads `.layer-policy.yaml` and fails a layer other than
`utils/`/`chassis/` that imports a vendor directly. A new vendor added to `utils/` needs a
written `allow` entry in every tier's `.layer-policy.yaml` (the reason is required, not the
package name alone).

## `find_*_problems` — validate without raising, severity-typed (blueprintx#162)

Every read/write boundary that can fail exposes a `find_*_problems(...) -> ProblemReport`
sibling that **never raises**: `find_file_problems` / `find_contract_problems`
(`tabular_reader.py`, where `ProblemReport` is also defined), `find_xml_row_problems`
(`xml_reader.py`), `find_sheet_name_problems` / `find_workbook_sheet_name_problems`
(`ms_office/excel_sheet_names.py`).

`ProblemReport` carries two lists, `list_fatal` and `list_warnings`, rather than one flat
`list[str]` plus a severity field on each entry. A flat list forces every caller to guess —
from the wording alone — whether a finding means "abort" or "log and continue", and the
loader author and the caller author routinely guess differently. Two lists make the mistake
**unrepresentable**: a caller that reads only `list_warnings` (its "proceed with a note"
branch) cannot see a fatal problem, because a fatal one is never placed there. A caller
still decides what "empty" means for its own boundary — `list_fatal` non-empty means abort,
`list_warnings` non-empty means log and continue — but it can no longer misclassify a
finding it never had to inspect closely.

A stricter twin built on top (`read_table`, `read_query`, `read_xml`) is free to raise
(`ContractError`) on **either** list — it is the mandatory-contract path, not the tolerant
one, so it does not get to pick per severity. Only a caller reading the report directly
(`find_file_problems`, `find_sheet_name_problems`, …) makes that choice. Both share ONE
problem-finding implementation instead of the two drifting apart.

Adding a new finding to an existing validator means picking one of the two lists — there is
no default, and no third option that skips the choice.

⚠️ **"Never raises" includes a missing file.** The obvious reading is that the guarantee
covers validation findings and that a missing path may still raise, and that reading defeats
the contract: a caller would have to wrap the call whose job is to describe what is wrong in
a `try/except FileNotFoundError`, and a caller that trusted the promise crashes on the single
most common real problem at a read boundary. `find_file_problems` and `find_xml_row_problems`
therefore return a **fatal** finding for a missing file. Their strict twins (`read_table`,
`read_xml`) keep raising — those *are* the read boundary.

## The runtime-typing layout shim

Every function carries `@type_checker`; every class `metaclass=TypeChecker`. Because `utils/`
ships to **both** layouts (MVC's `utils.typing`, DDD's `chassis.typing`), the import is never
a bare one — copy this block verbatim into a new module rather than hand-rolling a variant:

```python
try:
	from utils.typing import type_checker
except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
	from chassis.typing import type_checker
```

⚠️ **No separate `if TYPE_CHECKING:` branch** (blueprintx#360). An earlier revision duplicated
the import under `if TYPE_CHECKING: ... else: try/except ...`, on the theory that mypy needed
a layout-blind branch to resolve statically. Measured: mypy does not special-case a
`try`/`except ModuleNotFoundError` import at all — gating one copy behind `TYPE_CHECKING`
changes nothing about which import it reports on, so the extra branch only duplicated the
`utils.typing`-first guess without fixing it. What actually keeps a DDD-scaffolded project's
`mypy` step green is `mypy.ini`'s scoped `[mypy-utils.typing.*]` / `[mypy-chassis.typing.*]`
`ignore_missing_imports` (blueprintx#376) — this file's single try/except is enough for both
mypy and the runtime.

## Scalar / Series twins

A pure transform written for one value (`to_decimal`, `mask_cnpj`, `is_valid_cnpj`) is
usually also needed over a whole column. Rather than forcing every caller through
`series.map(fn)` — slow, and it silently turns a per-element exception into `NaN` — the
convention is to ship **both** forms: the scalar function, plus a vectorised sibling built on
`numpy`/`pandas` operations, not a `.map()` wrapper. See `decimals.py` and `br_identifiers.py`
for worked examples.

## Vendor-scoped subpackages

Group a vendor's helpers under `utils/<vendor>/` once there is more than one module for it
(blueprintx#118) — `ms_office/` (Outlook automation, Excel sheet-name rules) is the precedent.
The placement test is *vendor behaviour* vs *a capability the vendor implements*: what Outlook
specifically does belongs in `ms_office/`; a capability any backend needs (e-mail dispatch
policy, body HTML-ization) belongs in its own backend-agnostic package (`email/`) instead, so
an SMTP-only deploy never has to import Outlook just to ask whether a block may send.

## One class per file, functions otherwise

A module here is a class only when it holds state + lifecycle, implements a port, or takes
injected collaborators (see the root `common.md` design-pattern rules) — `OutlookGateway`
qualifies (it owns a COM session's configuration). Everything else in `utils/` is a plain
function; do not wrap a stateless helper in a class for its own sake.
