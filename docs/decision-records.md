# Decision records

Resolves blueprintx#239. This page is the destination for **decision-record**
comments — the `SUPERSEDED …` blocks that narrate what a nearby line of code
*used to* say and why that reasoning was replaced — split out from **guidance**
comments, which explain what a future editor must not break.

The test (from blueprintx#239): a comment earns its inline place if removing it
would let someone make a *wrong edit to this line*. If removing it only loses
*history*, it belongs here (or the ledger, the issue, the commit message —
whichever already holds it), not inline. The rule is stated for future comments
in `templates/python-common/bin/CLAUDE.md` ("Decision records move to docs, not
a changelog inside the comment").

⚠️ **Not every long or dated comment qualifies.** A measurement that is *why the
code is shaped the way it is today* (no superseded claim, nothing rejected)
stays inline — moving it would turn a justified constant into a magic one. Only
blocks marked `SUPERSEDED` — a changelog entry inside the file — move here.

## `.review-bots.yaml` — zero threads is not a pass (#208)

Applies to `.review-bots.yaml` (root) and `templates/python-common/.review-bots.yaml`
(identical roster comment in both). `.review-bots.yaml` (root, this repo's own data,
never shipped) now points back to this entry. `templates/python-common/.review-bots.yaml`
is copied verbatim into every generated project, so its pointer names the blueprintx
issue directly (`blueprintx#208`) rather than a doc path that would not exist in the
generated repo.

> ⚠️ SUPERSEDED 2026-08-22 (#208). This block used to end "…is a pass here rather than a
> failure", and that half was wrong. Zero threads is ALSO what you get when no reviewer ever
> ran — opposite facts, one number — and the gate reported the second as success: PRs #204
> and #213 merged unreviewed with every check green. Zero threads is now judged against a
> SUBMITTED REVIEW, not against silence. A reviewer that ran and found nothing still passes;
> one that never ran fails.

## `review_threads.yaml` — a required check that reports is safe to require (#173)

Applies to `templates/python-common/.github/workflows/review_threads.yaml` — shipped
into every generated project, so its pointer names `blueprintx#173` directly rather
than a doc path meaningless outside this repo. The live file keeps the load-bearing
half (why the job is safe as a required check and why `bin/enable_repo_rules.sh`
seeds `REQUIRED_CHECKS` with its name) inline; the changelog half moves here.

> ⚠️ SUPERSEDED 2026-08-17 (blueprintx#173). This block used to conclude "that is why this must
> NOT be a required check". That conclusion was WRONG, and it was load-bearing: while it stood,
> `REQUIRED_CHECKS` in bin/enable_repo_rules.sh shipped EMPTY, so a generated project ran its CI
> and blocked nothing. Measured upstream: a PR merged with 32 of 47 checks passed.

**Not yet applied** to `.github/workflows/review_threads.yml` (root) — that file
carries the same block (dated text: "SUPERSEDED 2026-08-17 (#173, PR #185)") plus
two more below, and is held by PRs #491/#492 as of this writing. Follow-up once
those land.

## `review_threads.yaml` — the resolve half must also catch outdated threads (#196)

Applies to `templates/python-common/.github/workflows/review_threads.yaml`. The
"split as it stood" bullet list a few lines below the live comment already states
the current three-layer split in full, so the narrative here is pure changelog.

> ⚠️ SUPERSEDED 2026-08-24 (blueprintx#196). `REVIEW_THREADS_REQUIRE_RESOLVED` IS NOW `1`.
>
> The split below handed the RESOLVE half to the ruleset's `required_review_thread_resolution`
> (`required_conversation_resolution` on classic branch protection) on the reasoning that a
> merge-time setting cannot go stale. True — and it does not check what it was given: GitHub
> DROPS AN OUTDATED THREAD from the blocking set. Measured upstream: the merge button was ENABLED
> over a thread reading `resolved=False outdated=True`, with 29 of 29 checks green and the
> setting confirmed `enabled`. A thread outdates when the author's own commit rewrites the lines
> it points at, so the reachable sequence is: reply thinly, rewrite those lines, merge. The half
> nobody could re-evaluate was also the half nobody was checking.

**Not yet applied** to `.github/workflows/review_threads.yml` (root, held by
#491/#492), `templates/python-common/bin/enable_repo_rules.sh` (the same #196
story, told from the ruleset side — held by the #129 dispatch claim), and
`templates/common/bin/check_review_threads.py` (held by PR #424). Follow-up
once those land.

## `review_threads.yaml` — no `concurrency:` block, ever (#216)

Applies to `templates/python-common/.github/workflows/review_threads.yaml`. The
full reasoning is already restated in the "NO `concurrency:` BLOCK, DELIBERATELY"
comment further down the same file — this block was a preview of that one,
so nothing but the changelog framing is lost by trimming it.

> ⚠️ SUPERSEDED 2026-08-22 (#216). This block used to say `cancel-in-progress` must stay
> **false** below because a cancelled run publishes a `cancelled` conclusion. There is no
> concurrency block at all now, and the reason is worse than that: see the note above `jobs:`.
> `false` does not stop a QUEUED run being cancelled by the next one, and a run cancelled before
> it starts publishes NOTHING — leaving the required context `Expected — Waiting for status to
> be reported`, which no re-run clears.
> Closing this properly inside Actions needs a webhook receiver or GitHub App dispatching a
> `repository_dispatch` on `resolved`; not worth a always-on listener for this repo.

**Not yet applied** to `.github/workflows/review_threads.yml` (root) — held by
PRs #491/#492. Follow-up once those land.

## `.greptile/` — Greptile reviews only when asked (#737)

Every scaffold ships `.greptile/config.json` (from `templates/common/`) with
`"autoReview": []`, plus a per-skeleton `rules.md` and a `files.json` pointing at the
project's `AGENTS.md` or `CLAUDE.md`. The reference default is `["open"]`, which reviews
every PR on open and spends the monthly credit allowance while another reviewer is up.
An empty array means never automatic; the review ladder asks for one explicitly. Do not use
the trigger-label route, which counts as an `open` event and would need `"open"` back.
`greptile-apps[bot]` posts inline review threads, so it is listed in every
`.review-bots.yaml` roster.

## Generated-project Python gates (`templates/python-common/bin`)

The Python gates every Python scaffold ships carry no comments. The module docstrings and the
test suite keep the contract; this section records the reasoning that lived beside the code.

### Rules shared by the gates

- **Fix the stdout encoding at the I/O seam.** Windows' stdout defaults to cp1252 and cannot
  encode the status glyphs the gates print. Because most of them back an `always_run` pre-commit
  hook, the `UnicodeEncodeError` would block every commit from a Windows checkout instead of
  failing the file under check. The glyphs stay; a test pins it with `PYTHONIOENCODING=cp1252`.
- **Zero discovery is a failure, not a clean tree.** A gate that scans nothing finds nothing wrong
  and reports success forever, green precisely because it checks nothing. This is the
  failure the gates exist to prevent in other people's data, and several had it (#111): globs
  are cwd-relative, so the wrong directory yielded an empty list, a sum of 0 and exit 0
  (`check_provenance.py`, `check_docstrings.py`). With filenames passed in, the hook is driving
  and receiving none just means nothing matching was staged. A file a gate cannot parse is a
  finding, not silence (`check_function_length.py`): the first version printed the error and
  returned nothing, so a malformed file passed by being unreadable.
- **Report what was checked.** A gate that prints nothing when clean is indistinguishable from
  one that did not run; success prints the file count.
- **`--root <dir>` is a flag plus its value**, so argv must hold at least two entries. The
  default root is derived from `__file__`, which lets BlueprintX run the same file over its own
  tree instead of keeping a second copy (the repo has been bitten by shared assets drifting; see
  `check_codespell_sync.sh`). Compare path parts relative to the root, never `path_file.parts`: a
  checkout under `.claude/worktrees/agent-*` carries `.claude` as an ancestor, and an
  ancestor-based match would skip every file on every such run (#331), the vacuous audit the
  gate exists to catch. The skip list for those worktrees is shared with
  `check_function_length.py`, `check_fixture_scope.py` and `check_dead_code.py`.
- **The reason after an escape hatch is required**, never a bare marker, matching
  `# complexity-ok: <reason>` and `gate-change-ok: <reason>`; a hatch is read from `COMMENT`
  tokens only, so a marker inside a string literal is data, not an exemption.
- **Name sentinels MARKER, not TOKEN.** A source-text sentinel named TOKEN reads as a credential
  to a reader and to bandit (S105).
- **Module-scoped constants** (ruff N806, #422): an ALL-CAPS name inside a function reads as a
  constant while behaving like a variable, so such names live at module level.
- **Constant, trusted argv built in-process.** The `subprocess` calls take no shell and no
  untrusted input; S607 (partial path) is accepted by design, since the hook must use the `git`
  the developer's `PATH`, shell, hooks and CI all select, not a hardcoded path.
- **`git show :<path>` with an empty ref reads the index blob**, which equals `HEAD` on a clean CI
  checkout and the staged content in a local pre-commit run; using it for both sides lets one code
  path serve both without branching on which is running (`check_gate_integrity.py`,
  `check_assertion_weakening.py`). A `git diff --name-status` row has two tab-separated fields,
  or three for a rename (`R100\t<old>\t<new>`), and both paths of the rename are kept.
- **Escape-hatch and bot rules.** A gate demanding a human-authored artifact permanently blocks
  every bot PR that trips it, and the real effect is training people to reach for `--admin`
  (measured: two Dependabot PRs differing only in which file the bump touched, one merged and
  one sat red for days). The `[bot]` login suffix is GitHub's own marker; an allow-list of bot
  names would rot.

### Per-gate notes

- **`check_all_exports.py`.** `__all__` may be a list or a tuple; accepting only a list made a
  complete tuple read as empty and every public member as missing, a gate that fails loudest on
  correct code. Vendored and generated trees are skipped.
- **`check_assertion_weakening.py`** (#289, #324, #590). Comparison operators weaker than `==`
  include the `in` example and `>=`; `Gt` and `Lt` are excluded because swapping equality for a
  strict inequality still excludes the old value, so it stays out of the decidable core. The
  unittest-style call list is the measured, decidable subset, with only exact equivalences paired
  with a bare `assert`. A rename removes its source, so a production file moved into `tests/`
  still counts; a non-test source moved into `tests/` defines no baseline and is newly added.
  The `skip` mark is read from the outer decorator chain only: walking it found `skip` in the
  arguments of `@pytest.mark.skipif(platform.skip, ...)`, contradicting the deliberate `skipif`
  exclusion (the walk returned `{'skip'}`). Minimum positional-arg count is 2 for
  `assertEqual(a, b)`. Dispatch is by basename or path shape, so each analyzer takes plain
  `(old_text, new_text, shown_path)` and never reaches for git.
- **`check_backlog_ledger.py`** (#123). The risk classes that require a ledger are kept narrow:
  docs, deps and tests-only branches are routine and a ledger for them would be noise nobody
  reads. The author is read from the event payload: once `GITHUB_EVENT_PATH` is set the payload
  is the only authority, and every failure to use it (missing file, bad bytes, malformed JSON, no
  login) is treated as human. Falling back to `GITHUB_ACTOR` would reintroduce the defect: the
  actor is whoever triggered the run, so a bot re-running or auto-merging a human's PR would
  exempt it. Fail closed. Outside a workflow (a local pre-commit) the actor is the best signal.
  Keyed on the author, never the path, so a human branch touching the same files still owes the
  ledger; the exemption is announced. Risk is judged per path: `classify_risk` over the whole list
  answers a different question and lets a mixed branch escape. On the default branch or with no
  merge base there is nothing branch-scoped to enforce.
- **`check_comment_language.py`.** The Portuguese function-word list holds only words that are not
  also English; "ver" and "dar" are absent (they collide with the abbreviation "ver" and a
  Danish/Dutch reading), as is every 1 or 2 letter word. Terms of art with no English equivalent
  are redacted whole before matching. The whitelist is deliberately empty, the stricter
  setting: `de-para` lived there until it was translated to "mapping" (2026-08-06, 10 sites),
  and every entry is a word the gate stops seeing anywhere. Audit mode is deny-by-default: every
  file whose extension is in `DICT_MARKERS` (plus `.py`) is scanned and only listed directories
  are skipped. It was an allow-list of globs that left 57 supported files unaudited in this
  template (`.pre-commit-config.yaml`, workflows, `mypy.ini`, the compose files, all of
  `optional/`), and the hook did check them when staged, so hook and CI disagreed. A gate written
  against "a partial sweep leaves a precedent" must not itself be a partial sweep, and an
  allow-list fails silently on every addition. Discovery walks `git ls-files` (#331), so an
  untracked copy of the tree is invisible by construction; `docs` and `fixtures` are skipped on
  purpose (locale, verbatim bytes) and the rest is defence against a force-added artifact. Redaction
  order is backticked spans, quoted spans, URLs, dotted tokens, then ALL-CAPS acronyms; the
  acronym rule keeps Microsoft `COM` from reading as the Portuguese "com" (five hits in the
  Outlook gateway). The escape works one line at a time, never per block, or one escaped line
  would silence its neighbours. Comments come from `tokenize` and docstrings from the AST as two
  independent extractions (they were one body, so a tokenize failure skipped the docstrings too).
  `.env.example` is picked up through the `.example` suffix with no special case. Audit mode
  fails on zero files; success reports the file count.
- **`check_contract_drift.py`.** `src` is put on `sys.path` so the driver can import the
  project's `config.contracts` and `utils.*` when run from the project root as the workflow does;
  the import order is stable only because `ruff.toml` declares `known-first-party`, since left to
  inference different ruff versions make `poe lint` modify a fresh scaffold. `timeout_s:` is a
  per-source override. The timeout is passed explicitly although the seam defaults it: this job
  runs unattended on a schedule, and a source that accepts the connection and never sends bytes
  would hang it until the runner's ceiling, which reports as `cancelled`, indistinguishable from
  a human pressing cancel. The fetch handler is deliberately broad: one source can never end the
  run, and every failure mode means "not checked", surfaced as SKIPPED. The source dropping
  something we require is always checked; the opposite direction (the source has a column the
  contract does not list) is gated on a full-header pinned-oracle contract. The all-clear line is
  never printed when anything went unchecked, and skipped sources stay out of the report body
  because the report opens an issue and "the source is down" must not look like "our contract is
  wrong".
- **`check_coverage_floor.py`** (#149). A whole-capability omission (such as
  `src/capabilities/example_feature/*`) is matched against the omit list itself, never
  hardcoded. Patterns are expanded exactly as Coverage.py expands them before applying `omit`
  (`${PWD}/src/...`), or comparing against the raw text would never match a real module path and
  the omission would be real while the gate reported clean: logic dropped from the denominator,
  silently. Both spellings are matched because an expanded pattern is absolute and the module
  path is relative to the project root.
- **`check_dead_code.py`.** The skip list mirrors `check_function_length.py`. A half-removed
  vulture install still reports `name == "vulture"`, and the metadata probe separates "never
  installed" from "installed but its package is gone". Parts are compared relative to `path_src`
  (#331). vulture is handed the explicit filtered file list, not the directory, because its own
  `exclude` matches against the full, often absolute, path, so a `.claude` pattern would match
  every real file under a worktree checkout.
- **`check_docs_code_refs.py`** (#159). The root defaults to the project root and is overridable
  with `--root`. The layer-name vocabulary is the one every skeleton uses (DDD hexagonal,
  `utils`/`config`, `app`, MVC), unioned with whatever really exists under `src/`, never in place
  of it, so a whole top-level rename is still caught: `core` was a real historical name for what
  generated DDD-ORM projects ship as `chassis`, found in a template's own docstring example
  (`>>> from core.infrastructure.database import ...`). The list is small and hand-maintained;
  widening it to "any prefix mentioned twice in docs" reopens the prose false-positive problem.
  The import pattern anchors at column 0: an indented import sits inside a function or branch,
  where the reader has less context, and is treated like a relative import (out of scope). Each
  fragment's comment is stripped before testing for the closing `)` and before joining; a `)` in a
  comment used to end the scan early and a `#` swallowed every later name, silent misses where
  the gate passed having looked at less than it reported.
- **`check_docs_gap.py`.** Matching uses the same engine MkDocs 1.6 builds with
  (`mkdocs/structure/files.py`): a hand-rolled matcher diverged on basename-at-any-depth,
  anchored `/x`, `**` and `!`. A heading followed only by prose is not a table, or enabling
  Layer 2 on it would report every page missing from an index that was never a table. A relative
  `docs_dir` resolves against `mkdocs.yml`'s folder and `/` on an absolute right-hand side keeps
  the absolute path, so both documented forms land. An empty `mkdocs.yml` or a scan that found
  nothing has failed to run: 0 errors over 0 pages is a gate declaring its own blindness as OK.
- **`check_docs_sections.py`.** The canonical skeleton is English slugs present in every tier; a
  repo replaces it with `required_pages:` in `docs/.docs-skeleton.yaml`. The loader is
  SafeLoader-derived: unknown tags (including `!!python/object`) hit a catch-all constructor and
  resolve to `None`, so it never constructs arbitrary Python and is safe despite `yaml.load`.
- **`check_docstrings.py`.** A NumPy parameter line is one name or several comma-separated names
  followed by ` : <type>`; the combined form (`a, b : dict`) documents every listed name.
  Connector and filler words carry no type identity, so prose like `pathlib.Path or None` or
  `list of dict` or `str, optional` reads naturally and still matches the bare annotation;
  container synonyms are collapsed to one spelling. `Optional[...]` in brackets means the value may
  be `None`, so that token is emitted before the brackets are flattened and `optional` is dropped.
  Prose is routinely less specific than the annotation (it omits inner generics and the
  Optional arm), so a documented token set that is a subset of the annotation's is accepted;
  exact equality is the common case. Finding the Raises section and interpreting one entry are
  kept apart: they were one loop, so a change to either had to be made inside the other. Both
  globs are cwd-relative, and every tier ships both trees, so zero is always a broken invocation.
- **`check_dtypes.py`.** Matching is text-based, not AST: the target is a string literal in a
  class-level dict (`"COL": "float64"`) or a bare pandas/numpy spelling, which an AST walk
  complicates without buying accuracy. The opt-out marker takes a reason after the colon. Exempt
  trees are the runtime type-checking engine (which names float as a type, not a dtype) and the
  gate's own documentation of the banned spellings.
- **`check_fixture_scope.py`** (#442). Widening any of the listed scopes away from the implicit
  `function` shares the fixture's instance across more than one test, the shape the gate exists
  to catch. The marker mirrors `complexity-ok:` and `test-change-ok:`. Zero discovered files in
  audit mode fails, since a renamed `tests/` layout or a wrong `--root` would report clean forever.
- **`check_function_length.py`.** One ceiling for Python and shell on purpose: two numbers for
  one rule is the shape that rots, and once shell gets a bigger allowance nobody remembers which
  applies where. Directories skipped hold code we did not write or generated code; `typing` is
  not among them, since the runtime type-checking engine is exempt from type analysis but a long
  function is as hard to read there as anywhere. Unlike the comment-language gate, whose root is
  fixed to `templates/python-common`, this one needs the `.claude` entry because `--root` can
  point at a real repo root. `PLW0603` (a module-level default set once by the entrypoint) is
  accepted with its upgrade path: threading the root through every signature is the proper fix
  and a wider change than this one.
- **`check_gate_integrity.py`** (#309, #310, #312, #313, #337). The reason is required.
  `!=` belongs in the weakening set and is the weakest of it: `assert actual != expected` accepts
  every value except one, so a concurrent code-plus-test change could flip `==` to `!=` and keep a
  green test that asserts almost nothing. Git output is read as bytes, not `text=True`: with
  `text=True` one binary path (`docs/assets/logo.png`, a JPEG SOI marker, `0xff` at position 0)
  raised `UnicodeDecodeError` and took the whole gate down. A crash reports as the check's
  name, accusing a PR that only added a logo, and the traceback stopped collection at the first
  binary path so every later file went unexamined: its own blindness reported as a rejection.
  Skipping by extension is not the fix, since that `.png` contains JPEG bytes; a decode attempt
  asks the blob itself. For `mypy.ini` the effective value is compared, not section presence: a
  pre-existing `[mypy-<module>]` that flips `ignore_errors` from false or absent to true is as
  much a weakening as a new section carrying it (#313). `CI` and `GITHUB_ACTIONS` exist to make
  the `GATE_CHANGE_OK` hatch local-only (see `env_reason`).
- **`check_identifier_masking.py`.** The 11-digit CPF mask is `123.456.789-01`. The 2026 CNPJ is
  alphanumeric in the base (the mod-11 check digits stay numeric, see `br_identifiers.py`), so
  the pattern accepts letters in every group but the trailing check-digit pair. A column-ish
  token followed by an equality against a quoted value is matched against SQL text (a Python
  string or f-string segment, or a raw `.sql` file), not Python syntax.
- **`check_layer_imports.py`** (#139, #140, #224). Modules directly under `src/` (an entrypoint
  such as `src/main.py`) get their own layer name so the policy can speak about them;
  skipping them would let `main.py` import any vendor and bypass the policy. A layer is matched
  against every ancestor of the file's directory, deepest first: `fnmatch`'s `*` does not stop at
  `/`, but the pattern must still match the whole string, so `capabilities/*/domain` matches
  `capabilities/notes/domain` and not `.../domain/entities`; a module one package deeper would
  fall back to the broad `capabilities` key and lose the sublayer rules. Longest-first applies
  to keys and deny entries. Three kinds of module are not the gate's business: the stdlib carries
  no coupling, first-party code is ours, and an allowed vendor already has its written reason.
  A star import cannot be annotation-only: the recorded alias would be the literal `*`, so
  nothing in the body matches it and every use of the vendor passes unexamined; the bound names
  are not knowable without importing the vendor, so the verdict is refusal. One statement binding
  several names is one violation. Scope does not change the verdict: a deferred import still
  couples the layers. Deny entries use full dotted paths, so `chassis.db_schema` (the DB
  providers) can be forbidden without forbidding the runtime type-checking engine beside it, which
  is mandated on every class; a rule that fires on correct code is a rule someone deletes.
  Relative imports are resolved from the file's own position, since the dot count alone is not
  the layer. A malformed policy is a failure with a readable message, not a traceback, because
  the reader is looking at CI output. `lib-minimal` nests its layers inside the distributable
  package (`src/<pkg>/_internal/<layer>/...`) and strips two leading components, so one engine
  serves both shapes instead of the layer resolving to the package name and matching no entry.
- **`check_migration_graph.py`** (#308). A `down_revision` has three states the gate must not
  collapse: a genuine root (`None`), the key absent, and a value this reader cannot evaluate (a
  name, a call, an f-string). `.get()` returns `None` for all three, which reads as root, so an
  unverifiable file would silently become a head and the head count would be wrong either way.
  Distinct sentinels keep them apart.
- **`check_one_assert.py`** (#431, #544). The unit suite's cap of one is blocking by default;
  `--max-per-test 0` turns the cap off and leaves the zero-assertion check alone, since 0 cannot
  mean "cap at zero" (a test with zero sites is already the unconditional finding). Every flag
  takes a value, so one table handles them all: adding a flag is adding a key, not a branch,
  which keeps the file under `bin/`'s complexity ceiling of 8. `pytest.raises` and `warns` are the
  context-manager form of a check, not its absence; bare `ast.Assert` alone misreads them as
  zero. A trailing hatch past the last statement's column, which `ast.get_source_segment` would
  cut off, is still found because tokens carry the whole physical line's comments.
- **`check_orm_model_guards.py`.** A later declarer that maps its own table (`__tablename__`) is
  a parent in a joined or concrete inheritance chain: its `__table_args__` applies to its own table
  and is not discarded. Only table-less mixins are truly shadowed.
- **`check_provenance.py`.** The read is the call form (`read_table(`), so the trailing paren
  matters; the stamp is the marker that must accompany it. Excluded directories mirror
  `check_typing.py`: `typing` (the engine), `chassis` (cross-cutting reference scaffolding) and
  `example_feature` (the DDD example capability). The seam files that define the markers are
  exempt from pairing. Every tier inherits `utils/` and `config/`, so a real project can never
  legitimately reach zero.
- **`check_quality_rules.py`** (#503). The only `status:` value that waives the tool-plus-rule
  requirement is matched exactly, never by truthiness: any non-empty string would otherwise
  satisfy coverage, so a typo (`not_implemented`) or an invented value (`planned`) would buy an
  exemption the registry never granted, the gate failing open on the one field that waives the
  requirement. `status: not-implemented` and `overridden_by:` are permitted by `CONTRIBUTING.md`
  and need no tool or rule; the `note` they owe is `reason_required_problems`' job. An unquoted
  `#` opens a YAML comment, so `note: # reason` is a note with no value, not a note whose text
  is "# reason"; returning the raw text let a comment satisfy the non-empty check and take the
  hatch with the explanation unwritten. A quoted value is untouched. An empty value in a
  language block opens a list; one after `key:` only opens a nested language block in this file's
  restricted schema.
- **`check_rmw_race.py`** (#385, #392). `.first()` and `.one()` alone are not signal, since they
  exist on plenty of non-ORM objects; the read is pinned to a model only when the same chain also
  calls `.query(Model)`. Every binding that can reach the write counts and the unlocked one
  decides: `if cond: row = get(..., with_for_update=True)` / `else: row = get(...)` gives two
  definitions of one name, and keeping the last seen suppressed the finding whenever the locked
  branch came second, a race hidden by source order. `x.qty -= n` is `x.qty = x.qty - n`, so the
  target is the self-reference. The S608 `noqa` is a false positive: it builds a remedy message
  containing SQL vocabulary, never a query that reaches a cursor.
- **`check_sql_guards.py`** (#355). `WITH (NOLOCK)` is MSSQL-only syntax and a very specific
  token, so a plain keyword search has near-zero false positives. The module alias is recorded,
  not just the import: `import sqlalchemy as sa` makes `sa.delete(t)` a Core builder call, but
  it reaches the classifier as an attribute call, the same shape as `dict.update()`. The
  attribute branch demands a `.query(` anchor to stay out of that false positive, and without the
  alias a module-qualified WHERE-less delete is reported OK; with the alias no anchor is needed
  and demanding one would skip it. The anchor turns "any `.update()` or `.delete()`" into "a
  SQLAlchemy Query mutation"; `session.delete(record)` is primary-key-scoped, has no `.query()`
  in its chain, and is correctly left alone. The hatch is matched per match, never per constant:
  `search()` returns one boolean for the whole literal and `lineno` is where it opens, so a hatch
  on the first line suppressed every hint inside it, and implicit concatenation made that a
  two-line edit (approved hint on line 1, unannotated on line 2, exit 0, measured). It is matched
  against the literal's source segment, not its parsed value: implicit concatenation collapses
  `"a" "b"` into one `Constant` whose value holds no newline, which maps every match to the
  opening line. NOLOCK is searched as one text stream, never line by line, because the pattern
  tolerates whitespace and in SQL that whitespace is routinely a newline (`WITH\n(NOLOCK)`); a
  per-line search can never match across the break and reports clean. The reported line is where
  the match starts, which is where a deliberate hint needs its hatch.
- **`check_typing.py`.** The checked metaclasses come from `_internal.utils.typing`. Metaclasses
  are inherited, so only a hierarchy root (no base) must declare one. The excluded directories
  are `typing`, `chassis` and `example_feature`, mirroring the `ruff.toml` and `mypy.ini` excludes;
  keeping the three boundaries identical avoids a file that ruff and mypy ignore tripping this
  hook.
- **`lib/ca_bundle.py`.** The bundle variables tools consult are listed in the order they consult
  them; a corporate image often provisions one, and replacing it is how a working box stops
  working. A bundle generated on a previous run is skipped, or the union grows forever.
  Certificates are deduplicated on the base64 body, never on the `BEGIN` line every certificate
  shares.
- **`lib/pip_requirements.py`.** Poetry's caret and tilde grammar has no pip equivalent, so it is
  expanded to an explicit range and everything pip understands passes through. A dependency
  declared by path, git or url cannot be a plain requirement line without reproducing Poetry's
  resolution, so it refuses loudly instead of emitting something that installs the wrong thing.
  A version is padded to three components before comparison. Poetry owns the bare tilde; the
  two-character compatible-release operator is pip's own and passes straight through. The
  interpreter, which Poetry declares as a dependency, has no pip concept and is dropped. Zero
  requirements for a non-empty group request is a symptom, not an answer: the caller writes them
  to `requirements-lock.txt`, an empty file reads as "no dependencies", and the hosts that reach
  this code are constrained boxes where nobody watches closely.
- **`lib/verify_venv_imports.py`.** Some wheel-built distributions omit `top_level.txt`. The
  candidates are derived from the files the distribution installed rather than guessed from its
  name: a guess that misses rejects a correctly installed package, and the normalised-name rule
  is wrong for every distribution whose module differs from its PyPI name. `argv` is the script
  path plus one requirement-file argument.
- **`lib/wheelhouse_select.py`** (#299). `"3.11"` needs a `.0` appended before it can stand in for
  `python_full_version` in a marker environment. `pip download` without `--only-binary` falls
  back to an sdist for a package with no matching wheel, and zipping only `*.whl` would drop it
  silently, so the offline install would fail. `read(0)` returns `b""` at once: no parts, a
  deleted archive and a "successful" manifest. A rebuild with fewer parts must not leave older
  `<zip>.NNN` files to be copied to the target. Archive members are taken by basename: a
  hand-made zip of the `wheels/` folder nests its members, pip's `--find-links` does not recurse,
  and the basename also rules out a path-traversal member. The reassembled archive is written
  then unlinked so it is not an input it reads; extraction happens only after verification, so a
  failed one leaves the existing wheels untouched, and a failed archive left behind could later be
  extracted as "unverified".
- **`pr_gate.py`.** The sticky comment carries a hidden marker so it finds itself and updates in
  place instead of stacking. The `do-not-merge` label is the opt-out, present means never
  auto-merge whatever the classification says. The lockfile name is one constant because it is
  both a `deps` trigger path and the size-veto exemption, and two literals would drift; change it
  for a non-Poetry project (`package-lock.json`, `uv.lock`, `Cargo.lock`). Risk classes are
  ordered most dangerous first and the first present wins, so a PR touching `docs/` and `src/`
  is `src`; `other` outranks `ci`, `deps` and `docs` on purpose because an unmatched path is
  unknown and unknown is unsafe (default-deny). `src` and `tests` never auto-merge, since they
  define what passing means, nor does `other`. A failing axis must name its checks: "1 check(s)
  failing" tells the reader nothing. The auto-merge is armed after the poll, never up front:
  arming `enablePullRequestAutoMerge` on a PR fresh from `opened` finds nothing pending, because
  sibling workflows have not registered their check-runs, so GitHub merges too early or refuses
  the mutation (measured). After the poll those check-runs exist and native auto-merge has a real
  blocker to wait on, checks and unresolved threads alike; a thread resolved later needs no
  extra trigger, since `pull_request_review_thread` is a webhook event and not a workflow trigger
  and adding it to `on:` makes GitHub reject the whole file. The CodeQL axis matches the
  analyses, not the umbrella check. A poll count below one observes nothing and `gate_state({})`
  is "success", which would label a PR green having read no check run, so it is clamped rather than
  trusted from the environment. A check still pending is pending, not a failure.
- **`retry_rate_limited_review.py`.** The `review_retry.yml` record in
  [Root workflows](#root-workflows-why-each-is-shaped-as-it-is) covers the workflow; the points that
  lived in this file:
    - The marker is an HTML comment (renders as nothing) that makes our own request recognisable,
      so a scheduled run asks once per window instead of every tick.
    - The command is `@coderabbitai full review`, not a plain `review`: an incremental reviewer
      answers "already reviewed" for commits it has seen, and only the full form disregards that.
      Keep the spelling identical to the gate's own remedy text.
    - The rate-limit pattern is deliberately broad: any spelling of the reviewer saying it is
      throttled; being generous is the safe direction, the cost being one extra request.
    - The reviewer declares its own wait ("Your next included review will be available in 35
      minutes"), so read it instead of guessing. A hardcoded cooldown is a guess about someone
      else's quota and was measured wrong three times (31, 34 and 35 minutes against a constant of
      30), and since a refused request still counts as traffic, guessing pushes the window out.
    - Two states wear the same words and want opposite behaviour: a transient throttle (retry
      soon) and the included-quota state under Fair Usage, an account-level budget ("may still
      proceed through usage-based billing if eligible"). The pattern cannot tell them apart, so
      the declared wait is the only reliable signal and wins over any local constant. The
      fallback, for a refusal that declares no wait, sits above every window measured (31, 34,
      35 minutes): asking early buys a declined request, an ack comment and a pushed-out window,
      asking late only delays a PR that is already waiting.
    - Skip-after-N over strict FIFO (#280): strict FIFO re-picks a permanently unreviewable
      oldest PR forever and every younger PR starves. 18 of 19 rate-limited PRs were eventually
      reviewed, so one still stuck after several genuine retries is the 1-in-19 case, worth
      surfacing to a human. Five attempts at `*/10` is most of an hour, past every declared window
      measured (20 to 35 minutes), so it does not fire on a PR merely waiting out a normal window.
    - Never decide from a display string: `summarise_reviewer_notice` truncates to 200 characters
      after stripping markup and can cut the very sentence being matched.
    - The digits come from an external service, so they are untrusted. `int()` raises `ValueError`
      above `sys.get_int_max_str_digits()` (4300, the CVE-2020-10735 mitigation) first, and
      `timedelta(minutes=...)` then raises `OverflowError` for a value that converts but is not
      representable. Guarding only the deeper one leaves the shallower live. The first guard
      covered only `OverflowError` and its test used 100 digits, under 4300, so the suite passed
      with the `ValueError` path open; a should-fail test proves the code survives the case you
      thought of, never the boundary you did not (raised by review on #278, twice). A wait that
      is not representable is not a wait: fall through to the marker cooldown. A wait we cannot
      anchor in time falls through too; returning True would stall the retry on one unreadable
      timestamp.
    - A cooldown, not an ordering test: the first implementation asked whether our marker was
      newer than the reviewer's newest notice, which reads as right and loops. Measured on #270,
      the reviewer acknowledges every request within seconds (13 seconds later), and that ack is
      a roster comment newer than our marker; the newest-first scan met the ack first, concluded
      "not asked yet" and asked again every ten minutes for ever, while the ack itself carried the
      rate-limit wording. The unit test for the ordering version passed because it was written
      from the same mental model: it asserted the roster notice after our marker means a new
      window, which is precisely the case the ack occupies. A test built on the code's assumption
      is the assumption agreeing with itself. Time cannot be confused this way, we asked recently
      or we did not, and an unreadable timestamp on our own marker is treated as recent.
    - Comments come from REST, not the gate's GraphQL query, which returns `{author, body}` with
      no timestamps because it never needed them; rather than widen a shared query for one
      consumer, the retry reads what it needs. The reviewer's deadline comes first (the only
      statement about the quota by the thing that owns it) and the marker cooldown is the second
      guard, answering a different question (did we ask recently).
    - The author type is the whole point: a `Bot` comment is silently ignored, so posting one and
      reporting success would be a no-op wearing a success message. The PAT's identity is resolved
      from the token, not configured, so the two cannot disagree after the PAT is reissued on
      another account.
    - `--slurp` yields a list of pages, so flattening goes one level deeper than the obvious
      comprehension, which would iterate pages and yield nothing; it is a pure function so the
      multi-page shape is testable without a network. It sorts by `created_at` (REST's field,
      ISO-8601, lexically chronological) because FIFO ordering is a guarantee, not an assumption
      left to the caller. `--paginate`, not a bare `per_page=100`, or a rate-limited PR on page
      two is never retried. No `--jq` there, measured on gh 2.96.0: `--slurp` is rejected with
      `--jq`, and `--paginate` alone emits one array per page, which does not parse, so the
      function would take its early return and the janitor would quietly do nothing every tick.
    - One PR's failure must not end the sweep: `fetch_pull_request` raises on an API failure (four
      `raise RuntimeError` sites) and indexes a `pullRequest` node that can be null, so one
      deleted, transferred or transiently-500ing PR would abort the loop and leave every later PR
      unexamined, silently. The catch is deliberately broad. The setup step raises too and looks
      like configuration: `exec_module` propagates any import-time error from the gate and
      `load_roster` raises on a malformed roster (an unknown or missing `posts:`, only status
      members). An absent roster is fine, the gate self-skips; a broken one would end the job with
      a traceback on every tick for ever.
    - Whether a PR is structurally waiting is decided apart from whether to ask it now (#280):
      the cooldown and declared-wait gating needs the whole open-PR set first, because the
      account-level quota means one PR's declared wait binds every other PR too.
    - Account level, not per PR (#280): six PRs asked inside four minutes after a quota reset
      were all rate limited, because the quota is shared. The newest refusal across every waiting
      PR is read, and when it declares a wait not yet elapsed it binds every other PR. The latest
      deadline wins, never the deadline of the latest notice: across PRs these are independent
      statements about one shared quota, so the binding moment is the furthest out; taking the
      newest `created_at` and reading only that notice loses the window whenever the newest
      refusal names no number.
    - One ask per run, ever (#280): the old loop asked every eligible PR, which at `*/10` against N
      open PRs is `6*N` requests an hour against about one of quota (96:1 at N=16), so the retry
      that exists to unblock the queue kept it blocked. The schedule is the only rate limiter left.
    - The helper that owns every reason to ask nobody this run (no candidate, an open
      account-level block, every candidate cooling down or exhausted) was split out of `main` to
      stay under the PLR0911 return-count ceiling.

## The comment-budget gate and its data files (`templates/python-common/bin`)

`check_comment_budget.py`, `comment_budget_allowlist.txt` and `required-checks.txt` carry no
comments. The module docstring of the gate is the contract; this section records the reasoning
that lived beside the constants and the data.

### `check_comment_budget.py`

- **`INT_MAX_RUN = 85`** is just above the worst block measured on the tree (80 lines), so the
  tree had zero run-length violations when the gate shipped and #304 is what tightens it, not
  the gate. The ratchet, not this ceiling, is the live constraint.
- **The structural-line limit (2)** is not a number to tune: a shebang or PEP 263 coding cookie
  only ever sits on line 1 or 2. A decorative banner is exactly rule, title, rule: three lines.
- **`.py` is deliberately absent from the `#`-suffix tuple**: its blocks come from `tokenize`,
  since a `#` inside a string literal is not a comment and only the tokenizer knows. But
  `marker_for` must still recognise `.py` explicitly, or `file_problems` short-circuits on its
  `not str_marker` guard before the `.py` branch and every Python file goes unchecked while
  `audit_paths` reports it "checked" (#466; measured 228 of 499 files "checked", 0 findings,
  discovery non-zero and looking like coverage). `Makefile` (no suffix) and `.mk` are matched by
  name in `audit_paths` and `marker_for`; the issue's own table missed `Makefile` for this reason.
- **`//` file types.** `/* */` block comments are a known ceiling, not a gap: every measured
  violation in the issue's table is a line-comment block, and a second comment grammar for zero
  measured evidence is the unrequested generality this repo argues against.
- **The skip list** mirrors `check_function_length.py`, `.claude` included: `--root` is
  overridable to the real repo root, which commonly sits under a `.claude/worktrees/<agent>/`
  copy of itself.
- **A decorative banner** is a comment whose stripped content is only rule punctuation
  (`# -------`).
- **The test-section banner exemption was removed (slice 9d).** `tests/CLAUDE.md` used to
  mandate a banner triple (dash rule, section name, dash rule) in every test module, and the gate
  exempted it by file type (`is_test_module`, `is_exempt_section_banner`, `STR_TEST_SECTION_RULE`).
  The rule line was measured (#466) to occur nowhere else in the tree. It was matched
  structurally in `banner_findings` and not through the pragma allowlist, because a pragma breaks
  a run (`line_breaks_run`): listing the string there would let one dash line split an
  oversized block into two under-ceiling halves (#479; reproduced: 44 lines, one dash line,
  44 lines passed clean), so the two rule lines counted toward the block's length and only the
  banner finding was suppressed, never the run. The convention left `tests/CLAUDE.md` and the
  suite in slice 8, so the exemption had no purpose and was deleted with a should-fail test
  that the same triple in a test module is a finding. The split-run and run-length witnesses
  stay: a lone rule line never splits an oversized run, and a triple inside one still counts.
- **A bare `# comment-budget-ok:`** with no reason and no trailing newline leaves
  `.splitlines()` on the tail empty, not `[""]`; indexing `[0]` crashed the first draft instead of
  failing the exemption, which is what a bare marker must do.
- **`--root <dir>`** is a flag plus its value, so argv must hold at least two entries. Zero
  discovered files in audit mode is a failure, not a pass, matching every sibling gate.

### `comment_budget_allowlist.txt`

- **Format.** One substring per line. A comment line that starts with an entry is
  machine-read configuration in comment syntax, not prose being budgeted: it never counts toward
  a run, is never flagged as a banner and is never stripped, and it breaks a run instead of
  extending it (#303). A leading `~` means "contains", for generated-file banners, matched only
  in a file's first lines. Lines starting with `#` are ignored, as are blank lines.
- **Anticipatory, not a census.** Add every pragma form the toolchain in `templates/python-common/`
  can emit, even with zero occurrences today: `codespell:ignore` has no inline use (codespell is
  configured through `.codespellrc`) and belongs anyway, because the first person who legitimately
  needs one must not be the one who finds out the gate has never seen it.
- **The groups**, in file order: ruff, pyright, mypy, pytest/coverage, shellcheck, codespell, this
  repo's own gates (`*-ok:` markers, `pairing:internal`, `pipeline-mode:`, `offline-mode:`,
  `layer-policy`, `gate-change-ok:`), deptry (`per_rule_ignores` and `DEP00N` codes), hadolint and
  Dockerfile parser directives, markdownlint, yamllint, sqlfluff, secrets scanners, formatters,
  the TypeScript and JavaScript toolchain, pylint, generic "do not analyze" markers, dependency
  bots, and ponytail. The last group is structural exemptions (#303): SPDX headers and
  generated-file banners are not the essay or decorative-banner defect the gate polices.
- **The test-section banner is not listed here.** Every entry is a pragma, and a pragma breaks
  the current run. That is right for a QA suppression, but a "banner is a pragma" entry lets one
  dash line split an oversized block into two under-ceiling halves (reproduced as above).
  The exemption that once lived in `check_comment_budget.py` is gone; do not add the string here.

### `required-checks.txt`

- It lists the status-check names `enable_repo_rules.sh` makes merge-blocking on the default
  branch, one per line, verbatim as GitHub reports them; blank lines and `#` comments are ignored.
- Add a name only after confirming a real PR emits it
  (`gh api repos/:owner/:repo/commits/<pr-head-sha>/check-runs --jq '.check_runs[].name' | sort -u`).
  A name nothing emits blocks every PR forever, since GitHub cannot tell "has not reported yet"
  from "will never report". Deleting a line is always safe; adding an unverified one is not.
- `Review threads answered` is the `review_threads.yaml` job: `on: pull_request` with no filter,
  so it reports from the moment a PR opens, and it fails both when a thread is unanswered and when
  no reviewer ran at all.
- `Classify and gate this PR` is the `pr-gate.yaml` job: `on: pull_request` with
  `types: [opened, synchronize, reopened, labeled, unlabeled]`, and its job-level
  `if: github.event_name == 'pull_request'` is true for every one of those. Without this line the
  gate classifies and fails while nothing stops the merge (#564).

## Generated-project test suite (`templates/python-common/tests`)

The tests every Python scaffold ships carry no comments. The shapes below recur across the
suite; each exists because a simpler form was measured to be wrong or to hide a failure. The
module layout the old banners spelled out is plain order now: helpers, fixtures, then tests.

### Shapes forced by the complexity ceiling

`tests/` is held to cyclomatic complexity 1 by `bin/check_complexity.sh`, so a test body has no
branch. That is the mechanical form of "a test exercises one path"; a branch in a test means the
green never says which side ran.

- **Comprehensions, generators and `contextlib.suppress`** replace loops with skip guards,
  `try` handlers and flag variables: mccabe charges a comprehension nothing and charges every
  loop, guard and handler a point (`test_startup_fragility_order`, `test_contract_family_conventions`,
  `test_integration/test_bin_scripts`, `test_wheelhouse_select`). A short run of three calls or
  entries is written out rather than looped for the same reason.
- **`skipif` decorators over a body guard.** An environment probe is resolved once at import time
  and feeds a `skipif`, because `if ...: pytest.skip(...)` in the body reads as a path through
  the test to a reader and to mccabe alike. The same applies to "does this tier ship the package
  or driver" (`test_all_exports_gate`, `test_daily_cache`, `test_ruff_ret_rule`, `lint_deps`).
- **Module-level helpers and stubs, never nested `def`s.** A nested function costs the enclosing
  test one point, so a branch-free stub would spend the budget reserved for branching
  (`test_pr_gate`, `test_sidecar_metadata`, `test_retry`).
- **`Mock(side_effect=[...])` for a flaky callable** (`test_retry`, `test_review_retry`): the call
  sequence "raise, raise, return" is data where a reader looks for it, not an `if` on a counter,
  and `functools.wraps` tolerates a Mock. A conditional expression keeps the opt-out fixture in
  `conftest.py` at complexity 1: a test that opted out is patched back to the real primitives,
  a no-op that monkeypatch undoes at teardown anyway.
- **`parametrize`, not a `for` in the body.** A loop asserts N cases behind one green: the report
  cannot say which case ran and the first failure hides the rest. A reference date, one token
  map and three documented tokens is one assertion over different keys (`test_paths`).
  Where a case list must be flattened, flatten first and assert once on the collected names so
  every offender is reported (`test_startup_fragility_order`).
- **An immutable default for env-override parameters.** A mutable `{}` default is a bugbear B006
  finding and a `dict_extra or {}` guard costs a decision point; short-circuit evaluation makes
  a helper an expression instead of a branch (`test_bin_scripts`).
- **One build, several facets.** The "expensive shared setup" pattern in `tests/CLAUDE.md`,
  module-scoped, stops the one-assert rule from turning three claims about one read-only frame
  into three rebuilds of it (`test_frames`, #544). `pytest.raises` plus its `match=` is one
  assertion site with one failure mode, not two (`test_pip_requirements`).
- **Split rather than combine.** A conjunction in one assertion reports only that the whole was
  false: an absent loader and an absent spec are different faults (`test_all_exports_gate`,
  `test_layer_imports_gate`, `test_review_retry`). An introspective test over `__all__` beats
  five hand-listed imports, so a name added to a package without being exported is what fails
  (`test_retry`, the surface added in #116).

### Witnesses and negative controls

- **Every gate needs a test that has seen it fail** (#111). A gate with no should-fail witness
  is indistinguishable from one that is not wired up, since both print green. Writing the first
  eight found three live defects: `check_provenance.py` and `check_docstrings.py` both exited 0
  printing nothing when their cwd-relative globs matched nothing, and `lint_actions.sh` accepted
  any file named `actionlint` on `PATH` as a working one. The `lint_*.sh` wrappers need a
  witness for both the missing-tool branch and the zero-discovery branch, since "tool not found"
  and "tool ran and passed" look identical from outside.
- **A healthy tool is required for the zero-discovery witness.** With actionlint absent the run
  stops in the required-tool branch and never reaches discovery, so an assertion that also
  accepts "required" stays green with the guard deleted. Poetry is shadowed there so resolution
  cannot take the vendored path.
- **A fixture must reach the boundary it claims to test.** A 100-digit input sat under Python's
  4300-digit conversion limit, exercised only the `OverflowError` path and passed while the
  `ValueError` path was open; it is 5000 digits (`test_review_retry`). A multi-line docstring
  that closes on a line starting with text is required for #206's third shape: a one-line
  docstring matched the old start-anchored guard and proved nothing. Fixture halves that a gate
  keys on disagreement over must genuinely differ (annotated `-> int`, documented as `str`).
- **A scanned-nothing control keeps a gate from becoming decorative.** A gate that scanned
  nothing also found nothing wrong and would report OK forever after a rename; the zero-discovery
  and could-not-parse cases pin that for each gate (`test_all_exports_gate` and siblings).
- **Real wording, verbatim.** The reviewer's refusal text and declared wait come from the live
  message (#275, 2026-08-26): the phrase is the interface, and a paraphrase would test our idea
  of the message while the parser only ever meets the real one (`test_review_retry`).
- **Relative paths where the gate takes relative paths.** `swallowed_by_omit` is called with a
  relative `path_module` after a `chdir` to the project root. Passing an absolute path makes each
  test vacuous: it matches the absolute branch and the relative pattern is compared with a path
  that can never match. With the absolute branch reverted out of the gate, the earlier versions
  still reported `2 passed` (`test_coverage_floor_gate`). Gates that derive `PATH_ROOT` from
  `__file__` (`check_docs_code_refs.py`, `check_function_length.py`) are pointed at a throwaway
  tree with `--root`, because `cwd=` alone would scan the real repo.

### The dual import root

`pytest.ini` puts both `.` and `src` on the path, so one file is importable as `utils.x` and as
`src.utils.x`, and Python loads it twice with distinct class objects. A module that annotates a
parameter with a class it imports bare (`ProblemReport`, `FileContract`, `RegimeWindow`,
`LogEmitter`) is guarded by beartype or the runtime TypeChecker, whose nominal check rejects an
instance built from the other copy. So these tests import bare (`utils.`, `config.`), never
`src.utils.`; `tests/CLAUDE.md` ("The dual-import-root trap") has the rule. The names are
interchangeable until a class crosses between them. Affected modules: `test_daily_cache`,
`test_provenance`, `test_regime_adapters`, `test_ms_office_excel_sheet_names`, `test_xml_reader`,
`test_sidecar_metadata`, `test_config_schemas_example`, `test_contract_oracle_example`.

### Per-suite notes

- **`test_bin_scripts` (integration).**
    - Subprocess argv is a constant, trusted list built from repo-internal paths with no shell,
      so bandit's subprocess warning is a false positive; each call carries its own `noqa`.
    - The environment is inherited, not scrubbed: an emptied `PATH` takes `dirname` with it, so
      `SCRIPT_DIR` never resolves and the run fails for a reason unrelated to the claim
      (measured). `poe_exec.sh` is run under either branch of the resolver, since a resolved Poe
      and the "none found" diagnostic are both built from `print_status`, so either proves the
      lib is reachable.
    - `poetry_exec.sh`: stdout is exactly the project version, and the resolution status lands
      on stderr. `precommit.sh`: the skip-gracefully default exits 0 and announces the skip
      without fabricating a repository or running `git init`; with a real work tree a throwaway
      `HOME` isolates the global `safe.directory` write, and the self-heal never emits the
      "no git repo" skip.
    - `pip_fallback.sh` driver pruning: `config/connection_db.py` lowercases `DB_BACKEND` before
      dispatching, so those spellings are valid configuration and the pruner must agree, or it
      drops the one driver the project uses.
    - `bin/check_*.py` on Windows: cp1252 stdout must not crash the glyph that `check_dtypes`
      prints for a banned binary float dtype.
    - `bootstrap.sh`: a corporate CA must be unioned with the existing roots, never replace them.
      A replacement writes exactly one block, while only a union carries the roots too. certifi's
      absence is simulated by hiding it from the child with a finder written against the modern
      protocol: the older two-method form was dropped in Python 3.12 and a finder shaped that
      way is skipped without a warning. The supported path reads the store the browser trusts.
    - `get_corporate_ca.sh`: the refusal carries the remedy, not only the verdict, and nothing is
      written on the refusal path. `check-clean-index`: editing a tracked file without staging it
      leaves the tree dirty and the index empty, the routine state the guard must never block;
      `git add` with no commit consuming it is the fingerprint of a rejected commit, and the
      verdict names the likely cause, the file and the remedy including the escape hatch.
    - `export_deps.sh`: Poetry's own words survive to the operator, and the remedy names the
      resolved binary, not a bare `poetry`. `print_status`: an unknown status must not look like
      ordinary output.
    - `check-urls` (#206, #224): every docstring shape must actually be scanned. The three shapes
      each hold the same unreachable URL, so a shape that reports clean is a check nobody ran.
      The third (a closing delimiter sharing a line with text) was never blind, since the URL was
      scanned as body text, but the state never flipped back, so every later line was read as
      still in the docstring. The cache key mirrors the hook's own `md5sum`, not a security use.
    - `check_complexity.sh` (#167, #254): a function with complexity 3 (two `if`s plus the
      implicit path) is over `src/`'s ceiling of 2 and under `bin/`'s 8. The colour-control
      variables are stripped from every run so a developer's shell cannot decide what the suite
      measures; the ANSI CSI pattern is matched so escapes never reach the gate's parsing;
      the reported finding is a regex over the whole line, and `print_status` adds colour, so
      only the ruff-derived remainder after `C901` is asserted clean.
    - `rerun_stale_gate_runs.sh`: a scriptable `gh` shadows the real one and records every call.
      Shadowing, not mocking, because it is deterministic on any machine including CI, where
      the real `gh` is installed and a `skipif` would drop the coverage where it matters. It
      does not evaluate `--jq`: filtering is GitHub's job, so the tests assert on the query sent.
    - `lint_deps.sh` (#238): the manifest declares nothing, so any third-party import under
      `src/` is undeclared by construction. PEP 621 is used rather than `[tool.poetry]`, which
      does not drift when the tier's Poetry moves. The test imports a package every tier
      declares, installed in the venv yet absent from the throwaway manifest: present at run
      time today and gone the day whatever pulled it in stops doing so. The wrapper's `shift 2`
      drops `run` and `deptry`, leaving its own arguments.
    - `run.sh` (#252): an argument passed to `poe run <x>` must reach the entrypoint; the test
      file is made newer than `pyproject.toml` with a margin so the `-nt` check in
      `runtime_env_needs_bootstrap` is unambiguous at any filesystem mtime resolution.
    - `test_resourcewarning_unraisable_gate`: constant trusted argv from `sys.executable` and
      repo-internal paths, so the bandit warning is a false positive.
- **`test_backlog_ledger` and the integrity gates.** `classify_risk` returns the single most
  dangerous class and ranks `tests` above `ci`, so a branch touching `bin/` and `tests/`
  collapses to `tests`, not a ledger class. One test pins that collapse, the other that asking
  per path still catches it; they are two tests because they assert different functions. The bot
  exemption (#123) is tested in both directions by name, because an exemption is one
  `return 0` from disabling the gate for everyone with the suite green. `robotics-team` and
  `dependabot` are the load-bearing cases: "bot" inside a name is not the suffix, and only
  GitHub's own marker counts. A gate demanding a human-authored artifact otherwise blocks every
  bot PR. Gate integrity (#309) is pure logic, offline; assertion integrity (#324) covers a
  test's expected value edited to match a bug, with the line number as a case, since a finding
  that cannot point at its assertion sends the author hunting. A renamed test file is read at
  its source path (#590), with padding to keep git's rename similarity above 50% after the
  one-line weakening; an expected-value change counts only when production code also changed
  (#289 is the live example). The `#334` review added three ways the guard could be defeated or
  misfire.
- **`test_pr_gate`.** Terminality differs from display state: `{"a": "failure", "b": "pending"}`
  displays as failure while not terminal, and breaking the poll loop on `gate_state() !=
  "pending"` would stop on the first transient red while other checks run, with nothing
  re-rendering the comment afterwards.
- **`test_regime_adapters`.** `resolve` returns the first covering window while the registry
  promises windows may arrive in any order, so two overlapping windows bind a period to whichever
  was listed first, a reader parsing a real file against the wrong published header with nothing
  reporting it (#344 review). Validation the caller can undo is not validation, hence the
  regression for it.
- **`test_paths`.** The premise (`PureWindowsPath("/home/x/out")` is rooted but driveless, so
  `is_absolute()` is False) and the behaviour (the function routes through `resolve()`) are
  separate claims and must not collapse (#544): asserting only the premise pins the platform and
  leaves our function untested, since a regression handing the driveless input back would pass.
  On POSIX CI the verdict is simulated and the real function is then called under it.
- **`test_daily_cache`.** `write_bytes` is not atomic, so an interrupted run can leave an empty
  file; serving it hands the caller a valid-looking path to nothing that fails later and far
  away. The miss, the hit on the same reference day, and the half-written file each get a case.
- **`test_frames`.** An empty frame with no columns makes the shape data-dependent: a caller that
  concatenates or renders it behaves differently depending on whether rows existed. Returning the
  declared columns keeps it constant; both seams owe the property, empty and still shaped.
  `apply_dtypes` needs disjoint column sets, so a date column is declared by `list_date_cols`
  alone, never also in `dict_dtypes`.
- **`test_startup_fragility_order`.** The reference block is an optional override and must never
  force a project to declare a source's `{dir, pattern}` twice; the tests pin the fallback chain
  (override wins, the real input's own spec otherwise, `None` only when neither exists), with the
  absent-override path asserted explicitly since every existing project has no `reference_files`
  and that path is where a regression lands first. The try-block check is scoped to the one that
  wraps the config read, since the module has a legitimate `except ModuleNotFoundError` for the
  typing shim. These tests live in this module because a new `tests/unit/*.py` needs its own
  scaffold copy-list wiring (`bin/ci/check_test_copy_lists.py`).
- **`test_contract_family_conventions`.** The list of column names two contracts legitimately
  share stays empty by default and a conscious list: two sources requiring `cnpj` is ordinary, so
  the check's value is that sharing is declared, not forbidden.
- **`test_comment_language_gate`.** Two consecutive comment lines form a quotation that opens on
  the first and closes on the second; read line by line, the opening quote never meets its
  closing one, the quoted span survives redaction and its language is charged to the English
  comment. Each false positive was measured and is pinned by name, accented capitals included
  (`NÃO`). The environment is inherited because a bare dict drops `PATH`; discovery reads
  `git ls-files` (#331), so an untracked fixture tree is invisible and the fixture must be a
  committed repo, with an orphan worktree stand-in present on disk but never staged. One
  representative long-lived file per location the allow-list once missed is checked.
  Registering the module root makes teardown undo the rebind the gate performs.
- **`test_comment_budget_gate`.** The ratchet ceiling, the escape hatch, pragma lines breaking
  a run, the decorative banner (regex-decidable, no ratchet), positional exemptions, the
  extensionless `Makefile` as the issue's own worked example, and that Python files are checked
  (#466).
- **`test_logs`.** A `StreamHandler` flushes on every record, so the old flush loop was dead
  code; the caller prefix is rebuilt by walking the stack, so the pattern asserts the shape and
  ends at the message, which also proves it was written; closing a `FileHandler` sets its stream
  to `None`, a deterministic signal independent of garbage collection.
- **`test_raw_workspace`.** The criterion is what is not on disk afterwards, so the assertion
  runs outside the block. A caller naming a leaf inside an unbuilt tree must not assume the
  parent exists, or a bronze write dies on the first run of a new dated folder. The runtime
  checker guards against the string form, which would otherwise fail at `str.mkdir` later.
- **`test_tabular_reader`.** A stray quote opens a free-text middle column; under default quoting
  the open quote swallows the separator and the trailing rows, while `QUOTE_NONE` keeps the three
  real fields.
- **`test_typing`.** Under the default policy a bool is rejected where an int is annotated;
  flipping the strict-bool knob off on the seam and rebuilding the config makes the bool satisfy
  it, proving the knob and not the adapter drove the change.
- **Smaller notes.** `test_decimals`: equality alone proves finiteness since NaN never compares
  equal, and a plain float-repr cell keeps its value and is not inflated tenfold.
  `test_docs_code_refs_gate` and `test_verify_venv_imports`: `in None` raises, so a missing
  finding fails there too. `test_dead_code_gate`: the duck-typed stand-ins for vulture's `Item`
  are a flat literal down to the one field read, not a comprehension.
  `test_family_convention_example`: the illustrative family stands in for `import myproj.section
  as family`; in a real project it is `family.__all__`, the declared public surface, and the
  members are discovered from it, never hand-listed. `test_env_config`: only `_dev` exists.
  `test_ruff_ret_rule`: the shipped config the test is the witness for is found by walking
  `tests/unit/ -> tests/ -> python-common/`. `test_wheelhouse_select`: built through `map`.

## Generated-project config files (`templates/python-common`)

The config files every Python scaffold ships carry no comments. This section records why each
is shaped as it is; a generated project gets the behavior, not the history.

### Small config files

- **`.codespellrc`.**
    - `skip` is the single source both gates read: `poe lint` scans the whole tree and
      pre-commit only staged files, so they agree only because the skip lives here.
      `*-lessons.md` is a git-ignored mirror that the lessons workflow writes, not a build
      output; without the skip, writing a lesson would flag the mirror and abort an unrelated
      commit. Use the basename glob, never `docs/*-lessons.md`: `codespell .` walks `./docs/...`
      and an anchored pattern silently fails to match.
    - `ignore-words-list` is the locale extension point. codespell only knows English, so a
      technical doc in another language (the seed is pt-BR) is flagged at the pre-commit
      boundary, and each rejected commit costs a full gate run. Extend the list with your
      locale's vocabulary; never `skip` a whole file, which hides real typos in identifiers.
      The second half of the list is commit and doc prose (`ser`, `vai`, `meu`, ...), not
      domain nouns. Write every entry lowercase: codespell lowercases the found word before the
      lookup, so a capitalised entry matches only itself. Keep it in sync with the repo-root
      `.codespellrc`; the two drifted in both directions and the stale copy was this one.
      Entries are pruned by measurement (#197): drop one, re-run, keep it only if a finding
      appears.
- **`.coveragerc`.** Branch coverage and the floor are measured as described in
  [Coverage floor](coverage-floor.md) (#427). `bin/check_coverage_floor.py` guards the patterns:
  one must never widen past `infrastructure/` (or a whole capability named outright) into a
  `domain/` or `application/` layer, which would drop real logic from the `fail_under`
  denominator (#149). `fail_under` is the single literal read by pytest-cov in both the
  pre-commit hook and the CI gate.
- **`.cz.toml`.** Commitizen config lives here, not in `pyproject.toml`, so the manifest stays
  near package identity and dependencies (#233); the keys were identical across the five Python
  tiers, so it is one file copied to each. Commitizen tries `pyproject.toml` first and skips it
  when it has no `[tool.commitizen]`, so this file is found; but if it ever stops being copied,
  commitizen does not fail: `cz version --project` prints "No project information" and exits 0,
  giving a differently formatted changelog and an unprefixed tag, never a red check. That is why
  `scaffold_lint_test.sh` asserts the file lands. Consumers: `poe bump_version`, `poe changelog`,
  the `commitizen` and commit-msg hooks, and the docs build. `version_provider = "poetry"` reads
  `[tool.poetry]` by project root, not by where the config lives. Services keep the version in
  `pyproject.toml`, tagged by `cz bump` (offline) or `release.yaml` (online); the library tier
  takes it from the git tag via poetry-dynamic-versioning. Either way `cz changelog` groups by tag.
- **`docker-compose.otel-collector.yml`.** Ports are bound to `127.0.0.1`, not published on every
  interface. The OTLP receivers are unauthenticated and the file is copied into every project that
  opts in, so a bare `4318:4318` would make an open log sink the default on whatever network the
  box sits on. A deployed collector belongs behind a real ingress with credentials. 4318 is
  OTLP/HTTP, which `OTEL_EXPORTER_OTLP_ENDPOINT` points at; 4317 (gRPC) is unused by the HTTP
  exporter and kept for a gRPC one.
- **`otel-collector-config.yaml`** (#438). The collector is the decoupling point: repoint the
  `logging` exporter at Axiom, Loki, Datadog, SigNoz, Honeycomb, Elastic or any OTLP backend,
  a config change and never an application change. `0.0.0.0` is correct and must not be
  hardened to `127.0.0.1`: it is the bind address inside the container, whose loopback is not
  the host's, and narrowing it makes the collector unreachable through the port mapping while
  the fire-and-forget exporter reports nothing. Host exposure is controlled in the compose file.
  The `logging` exporter prints to the collector's stdout, enough to prove the seam end to end.
- **`docs/.docs-skeleton.yaml`.** Overrides the required-page set `check_docs_sections.py`
  enforces. It adds `architecture.md`, which describes a service's layer structure and was
  scaffolded but never enforced (#130). It is copied into the four service tiers;
  `lib-minimal` has no `architecture.md`, never receives the file and keeps the default set.
- **`.gitignore`.** `dist/` is ignored but `dist/.keep` is tracked, so the directory ships.
  Only the curated VS Code settings and tasks are tracked. `coverage.svg` is tracked (the
  README badge references it); `coverage.xml` is regenerated on every run. The Claude Code
  `.tmp.<pid>.<hash>` mid-save sibling is ignored so a racing `git add -A` cannot sweep it into
  a commit. The scaffoldable-lessons working copies are local; the canonical stores are global.
  The SQLite file is the `DB_BACKEND=sqlite` default `DB_PATH=./data/app.db` and is never
  committed. The corporate CA and the union bundle derived from it are generated locally.
- **`.gitleaks.toml`.** It extends the default ruleset rather than replacing it, and keeps the
  allowlist to what a fresh project measurably needs, not a speculative list copied from
  another app's surface (#305). Extend it as real false positives are measured, as
  `.codespellrc` grows. The stopwords are the placeholder markers in `.env.example` and the
  README, never real secrets; a value containing one is ignored. The lockfile is allowlisted
  for pinned package-hash entropy.
- **`.gitlint`.** The limits were implicit (gitlint's defaults) and were found only when a
  commit was rejected after the slow hook chain had run. Commitizen enforces the
  Conventional-Commits format; gitlint owns the length limits.
- **`.hadolint.yaml`.** A project may ship no Dockerfile, in which case the `hadolint-docker`
  hook skips. The baseline lets one that adds a Dockerfile inherit a starting point. hadolint
  lints Dockerfiles only; compose files are covered by `check-yaml` and yamllint. It fails on
  warnings and above (info and style are advisory). Seed `trustedRegistries` (DL3026) and
  `ignored` per project, for example `DL3008` (pin apt-get versions) or `DL3059`.
- **`.layer-policy.yaml`** (this directory's own copy, checking `python-common/src`). The
  directory is a staging area, not a project, which is why it went unchecked: the gate
  self-skipped without a policy, so the code shipped to every tier was the one tree the boundary
  was never applied to. A third-party dependency is reached through a seam in `utils/`, never
  imported by `model/`, `view/` or `controller/`, so a vendor change stays in one adapter.
  Deferring an import into a function buys no exemption. Every `allow` entry carries a reason,
  since an unexplained allowlist entry is one the first inconvenienced person widens.
  `chassis` is first-party but absent from this layout (the DDD name for the typing shim's
  home). pandas is allowed as a type annotation only: `-> pd.DataFrame` is shared vocabulary,
  `pd.read_sql(...)` is a vendor API call every copy inherits. `utils/` is the seam layer and is
  listed explicitly so a new vendor needs a conscious decision. A stray module directly under
  `src/` is named so it cannot bypass the policy. The composition root knows concrete
  implementations but not the domain.
- **`.pydocstyle`.** Ruff already enforces the NumPy docstring set; pydocstyle adds the two
  checks ruff lacks, D412 and D417. The list matches the hook's `--select`, so `poe lint` (a
  bare `pydocstyle .`) and the hook enforce the same thing.
- **`pytest.ini`.** `PytestUnraisableExceptionWarning` is escalated as well as
  `ResourceWarning`: a warning raised inside `__del__` is unraisable, so pytest re-emits it as
  the other class and `error::ResourceWarning` alone never sees it, letting a leaked file handle
  pass (#294, the shape #223 shipped). The second line is the whole mechanism for `__del__`; do
  not delete it as noise. A warning is ignored by source, never by class alone: a bare
  `ignore::DeprecationWarning` hides every deprecation, including ones aimed at this code.
  With the four blanket lines removed the suite emitted four warnings, all from one vendor.
- **`requirements.txt`** is the bootstrap install. `poetry-plugin-export` is pinned here and not
  only as a dev dependency: a dev dependency reaches the project venv and nothing else, so the
  recipe would work from an activated shell and fail from cron, CI and the offline host it
  serves. `poetry-plugin-shell` (Poetry 2.x dropped `poetry shell`) lives here for the same
  reason: a Poetry plugin must live in the interpreter Poetry runs from, and as a project
  dependency it would sit in `.venv`, where no Poetry exists to load it.
- **`.review-bots.yaml`.** The roster is the provider-agnosticism: the gate names no tool, it
  subtracts these logins from a thread's authors. Reviewer shapes differ: some post inline
  threads, some post only a status check. `posts:` is required on every row and decides more
  than authorship (#218): a `posts: status` member is excluded from the missing-review gate too,
  so a workflow submitting a review with the ambient `GITHUB_TOKEN` cannot satisfy a gate that
  exists to say a real reviewer looked. A row that omits it or spells it otherwise fails loudly;
  at least one `posts: threads` member is required. Zero threads is judged against a submitted
  review, never against silence (#208). Delete the file to opt out: the gate self-skips with a
  message. See also the records at the top of this page.
- **`.shellcheckrc`.** `severity=warning` is the level at which the scripts are clean while still
  catching real bugs (unquoted expansions, undefined variables, bad test syntax). SC1091 is
  disabled because `lib/common.sh` is resolved at run time, not lint time.
- **`.sqlfluff`.** The top-level dialect is a fallback for a `.sql` file outside the per-engine
  layout. Mixing engines needs no change here or in `bin/lint_sql.sh`: queries live in
  `src/config/queries/<engine>/<table>__<purpose>.sql` and sqlfluff resolves config per
  directory, so each engine's folder carries a one-line `.sqlfluff` with its dialect. The engine
  is a directory, never a filename prefix, which would declare it twice and could disagree.
  Positional `?` bind parameters are swapped for a stub by the placeholder templater, since a
  bare `?` is not SQL. Indentation is a tab, matching the project convention (ruff, shfmt and
  Make use tabs; only YAML is forced to spaces). Hand-written SQL keeps a readable style with
  identifier casing dictated by the source schema, so those opinion groups are excluded while
  parse-correctness and keyword capitalisation stay on.
- **`.yamllint`** complements `check-yaml`, which only validates that YAML parses, with style
  checks. It is relaxed where the config YAMLs are intentional: no line-length cap (long
  documentation comments and email bodies), no `---` start marker, aligned values with extra
  spaces after the colon (`outputs_*.yaml`), and truthy values that appear inside quoted
  strings, not as bare booleans.

### `mypy.ini`

- **Run from `src/`** (`cd src && mypy --config-file ../mypy.ini .`, in the pre-commit hook, CI
  and `poe`). That makes `src` the single package base, so the bare imports (`config.x`,
  `utils.x`, `model.x`) resolve as at run time (`pythonpath = . src` in `pytest.ini`). From the
  repo root, with `mypy_path = src` and `files = src`, the root and `src` compete as bases and
  a file resolves twice ("found twice under different module names") on the deeper DDD tree.
- **No `python_version` pin.** Pinning below the running interpreter makes mypy parse the
  installed third-party stubs under older syntax rules. On Python 3.12 Poetry resolves
  numpy 2.5 or newer, whose `.pyi` files use PEP 695 `type` statements, and `python_version =
  3.10` fails on `numpy/__init__.pyi` in every tier that imports pandas. Capping numpy would
  move the break to the next dependency that adopts PEP 695. The floor is enforced where it is
  sound: the CI 3.10 matrix leg runs mypy on 3.10, and ruff's `target-version = py310` catches
  too-new syntax in our own code.
- **`ignore_missing_imports = False`** (#376). A global `True` cannot tell "pandas ships no
  stubs" from "this first-party module does not exist in this layout", so a typo'd `utils.x`
  reported `Success`. Stub-less vendors get one `[mypy-<vendor>.*]` block each, derived by
  measurement (flip the line locally, scaffold, read the `import-not-found` errors), because a
  hand-written list that misses one turns a green gate red in every generated project.
  Current blocks and their import sites: pandas (the `utils` readers, `dtypes`, `frames`,
  `provenance`; MVC controller, model and view), wwdates (`utils/dates.py`), defusedxml
  (`utils/xml_reader.py`), win32com (`utils/ms_office/outlook_gateway.py`), yaml
  (`config/startup.py`), pyodbc (the native-DB MSSQL handler, the only one of the five native
  drivers with no stubs) and joblib (the schema-less opt-in's `joblib_handler.py`, #650, which a
  scaffold with no opt-ins never imports). openpyxl is named in docstrings but never imported,
  so it is absent: an unmeasured entry is the guess this scheme exists to stop.
- **Baseline strictness.** Annotations and obvious type errors are enforced, not `--strict`,
  so the runtime-TypeChecker metaclass machinery does not drown the signal. Tighten later.
- **The one exclude** is the runtime type-checking engine (`utils/typing` or `chassis/typing`,
  nested at `<pkg>._internal.utils.typing` in `lib-minimal`): intrinsic metaprogramming mypy
  cannot analyse, the same reason it is ANN401-exempt. It matches `ruff.toml`'s `exclude`
  (#203). `^chassis/` and `^capabilities/example_feature/` were both removed in #190:
  `chassis` was unchecked and had accumulated 20 errors in the DB handlers while shipping into
  every DDD project; `example_feature` was excluded yet checked anyway, because `main.py` and
  `app/container.py` import it. Dropping it took the DDD native tier from 58 to 69 checked
  files with zero new errors. An exclude that excludes nothing advertises a protection that is
  not there.
- **Keep both mechanisms**, `exclude` and the per-module `ignore_errors` sections. `exclude`
  filters discovery only and does not apply to a module reached through an import, so it holds
  only while nothing outside the tree imports it, a property of the wiring and not of the
  config. Adding `config/query_loader.py` (#119) took the DDD native tier from "no issues in 31
  files" to "20 errors in 5 files", none in a file the change touched. Those 20 were fixed (#190),
  which is why no `[mypy-chassis.*]` section exists. Do not add one to quiet a new error.
- **The typing-engine sections carry `ignore_missing_imports` as well as `ignore_errors`**
  (#376). Every shared `src/utils/*.py` helper reaches the engine through one `try: from
  utils.typing import type_checker / except ModuleNotFoundError: from chassis.typing import
  type_checker`; a separate `TYPE_CHECKING` branch was measured not to change which import mypy
  reports (#360). mypy always tries `utils.typing` first, and on a DDD layout it genuinely does
  not exist: a deliberate shim, the one first-party import still tolerated. Narrowing `[mypy]`
  alone turned every shared `utils/*.py` red on DDD; MVC reports 0 errors either way.

### `ruff.toml`

- **`target-version`** is the floor of `requires-python` (`>=3.10`); bump it in lockstep with
  `pyproject.toml`.
- **`exclude`.** `src/chassis` and `src/capabilities/example_feature` were excluded until #203,
  mirroring #190's mypy fix. They ship verbatim into every DDD project, so a defect or a style
  violation the rest of the tree is held to propagates. About 230 findings were fixed in place
  (D202, S608 `noqa`'d per line, UP007/UP035, missing ANN204/ANN202, a docstring hanging indent
  authored before the tree was tabified); a few per-file ANN401 ignores remain where `Any` is
  honest. `lib-minimal` vendors the typing engine at a nested private path whose imports are
  rewritten to `<pkg>._internal.*` and can exceed the line length, so it is excluded in full
  (mypy excludes it too).
- **Preview mode is for PLR1702 only** (too-many-nested-blocks, still preview-only in ruff
  0.11.13). It also activates 10 tag-along preview rules in the `PL` and `S` families, never
  chosen on their merits, so they are ignored explicitly (#434): `--preview` alone raised
  findings from 21 to 81 on `templates/`, and ignoring exactly those 10 restores 21. Revisit
  each on its own measurement the day PLR1702 leaves preview. Why nesting is gated at all is in
  `check_complexity.sh`'s header and [Complexity ceilings](complexity-ceilings-measured.md).
- **PLR1702 pairs with `max-complexity = 3` for `src/` only.** Ceiling 3 alone would admit the
  nested `if`/`for` that ceiling 2 exists to forbid, and PLR1702 alone would not solve the
  guard-plus-try/except case. Per-tree ceilings live in `check_complexity.sh`, since
  `per-file-ignores` can switch a rule off but cannot set a different threshold.
- **Rules adopted by measurement** (ruff 0.11.13), recorded in the Ruff Rule Adoption Log in
  `CONTRIBUTING.md`:
    - `RET` (#426): 0 RET505 and 11 RET501 (a trailing `return None` in a `-> None` function),
      all removed; 5 were reachable from `templates/python-common`, the other 6 needed a scaffold.
    - `A` (#418): `from re import compile` shadows a builtin with no signal today; zero findings
      across `src/ bin/ tests/ optional/`. Do not also set `[lint.flake8-builtins]
      strict-checking = true`: it enables A005 and fires on `utils/typing` and `chassis/typing`,
      which shadow stdlib `typing` on purpose as the engine's layout shim (#360), putting a gate
      violation on correct design and teaching everyone to disable it.
    - `BLE` (#440): `E722` only catches bare `except:`. Two `BLE001` findings, both the
      `_pipeline.py` five-mode degradation, now `# noqa: BLE001`; nine other broad handlers
      already carried one that nothing enforced. `RUF` was measured in the same pass and not
      adopted (150 findings, 138 of them RUF100 unused-noqa), a separate decision.
    - `N` (#422): 9 findings across 3 rules, adopted with two narrow per-file ignores.
- **Ignored rules.** `D206` and `W191` existed only so the linter did not fight an
  `indent-style = "tab"` formatter; #419 moved the formatter to spaces, so neither fires, and
  re-measuring with both enabled gave zero findings (the 6022 of #222 was measured under tabs).
  `E701` is deliberately not ignored: `ruff format` expands a compound statement back onto its
  own line whatever the lint rule says, so ignoring it would be dead config. Reach for the
  expression form (`return not cond`, a comprehension, `any(...)`, a ternary). Before
  suppressing a rule for a style, check whether the formatter already forbids it.
- **`dummy-variable-rgx`** allows an underscore-prefixed name followed by alphanumerics.
- **Banned APIs (`TID251`).** Bare pandas readers are banned so every file or SQL read funnels
  through `utils/tabular_reader`, which enforces a `FileContract` and `apply_dtypes`; the seam
  and the tests (round-trip read-backs) are exempt. `FileContract` is constructed only in
  `config/contracts/`; elsewhere both import paths of the class are banned, and a file that
  imports it for an annotation carries a line-scoped `# noqa: TID251`. The ORM reference entity
  was once exempt, but it is the file each tier's `CLAUDE.md` says to copy per entity, so
  exempting it exempted the pattern (#172); it now reads through the session and builds its
  frame with `utils.frames.from_records`.
- **`known-first-party` is declared, never inferred**, as a superset of every tier's layer
  names (one that does not exist in a tier never matches). Otherwise ruff guesses, and versions
  guess differently: a script that puts `src` on `sys.path` was sorted one way by the ruff that
  wrote it and the other by the newer ruff in a generated project, so `poe lint` modified a
  fresh tree and the scaffold check failed on the diff with no rule named.
- **`max-args = 8`**, not pylint's 5, by measurement: the reader and mail seams take a genuine
  spread of options and a config object would only move the arguments. At 5 the gate reported
  12 functions; at 8 it reports one, `read_table` with 11, the widest public API and so the
  finding worth keeping visible.
- **No identifier-length ceiling** (#420), measured and rejected. Over `src/` and `bin/`: 493
  definitions, 63 over 20 characters, 4 over 30, none over 40, the longest 34
  (`assertion_value_or_operator_change`); the next-longest in any skeleton is 26. A ceiling at 40
  finds nothing, indistinguishable from a gate that never ran. Ruff has no length rule, so it
  would need a hand-rolled `bin/check_*.py`, and it would penalise the 3-to-5 character type
  prefix convention (`str_`, `df_`, `cls_`), pushing authors to drop the prefix or abbreviate
  the noun. Reopen only if the measured maximum crosses 40, or a concrete defect traces to a
  name's length.
- **`bin/` is linted like the rest** (#207). It was excluded for a hypothetical (ruff-format
  would tabify space-indented helpers and trip E101); the 27 E101s all sat in one genuinely
  mixed file, and the exclude hid the project's own quality machinery, with 73 findings behind
  it. Two rules are relaxed there: `ERA001` (100% false positives, 0 of 24 true: the gates'
  long wrapped prose comments contain `(`, `:` or `=` and read as code; per-line `noqa` would
  teach authors that `noqa` is how you write a comment; `src/` keeps it, and the global
  decision is open in #169) and `E101` (the 2-space hanging indent of a wrapped Markdown
  bullet in a module docstring is prose alignment, a tab would break the continuation, and a
  `noqa` cannot sit inside a docstring). A `src/` module with a numbered-list hanging indent
  carries the same E101 exemption (#203), and `lib-minimal`'s private-package path mirrors every
  exemption (`*` matches the single package segment; without the mirror only that tier goes
  red, #486).
- **Per-file ignores.**
    - `S101` and the magic-value rule are off in `tests/`: a literal in a test is the case
      under test (21 of 29 findings were in `tests/`). `TID251` is off there because tests read
      back outputs with `pd.read_*` to assert on them.
    - `N802` is off in `tests/`: a mixed-case name where the upper-case word is the point
      (`..._FAIL_rather_than_pass_silently`) is the behaviour description `tests/CLAUDE.md`
      asks for (5 findings, #422).
    - `ANN401` is ignored for the raw-driver connection factory (`config/connection_db.py`,
      MVC) and the DB handlers' `_connect` (psycopg, mysql-connector, pyodbc, oracledb), which
      have no shared type; `sqlite_handler.py` needs none, `sqlite3.Connection` being real.
      It is also ignored for the typing engine in both layouts (MVC `utils/typing`, DDD
      `chassis/typing`, #203) and for `SanityCheck.validate()`, which takes any joblib payload.
    - `N813` is ignored for `import defusedxml.ElementTree as defused_et`, a deliberate alias
      for the trust-boundary-safe parser; renaming would only hurt readability (#422).
    - `lib-minimal` mirrors the exemptions for `src/<pkg>/_internal/...`; its typing engine is
      fully excluded and needs none.

### `poe_tasks.toml`

- **It replaced the twin Makefile and `tasks.sh`**, two hand-kept implementations of one command
  list synchronised by a written rule that had already failed: `poe help` lacked
  `test_cov_report` and `test_cov_serve` (#189). There is no separate help file: bare `poe`
  lists the `help =` fields, so help and recipe are one declaration. A task without `help =`
  is invisible in that listing.
- **Three ways to run a task:** `poe lint` (the dev dependency in `.venv`, or a pipx install),
  `.venv/bin/python -m poethepoet lint` (the module is `poethepoet`, not `poe`), and
  `poetry poe lint` (only if you installed the plugin yourself). Scripts never hardcode one:
  `bin/poe_exec.sh` resolves them in order, as `bin/poetry_exec.sh` does for Poetry.
- **Tasks run inside the project venv automatically.** Poe detects `./.venv`, which
  `poetry.toml` forces in-project, so a task is a bare command (`pytest tests/unit/`), never
  `poetry run pytest`. `bin/poetry_exec.sh` survives only for Poetry management commands
  (`update`, `install --with docs`, `version`), which act on the venv and so route through the
  Poetry resolver.
- **Bootstrap tasks cannot assume the venv**, because they create it: `init`, `ensure_env`,
  `venv`, `precommit`, `update_venv`. Poe is a dev dependency, so it lives inside the venv it
  would have to create; run `bash bin/venv.sh`, `bin/ensure_env.sh` or `bin/precommit.sh`
  directly, which is exactly what these tasks call. The shell entrypoint is the second and
  last interface; do not add a third. `init` ends a seed step with `|| true` so a missing
  `.env.example` aborts only that step, not the venv and precommit steps after it.
- **Do not use `[tool.poetry.requires-plugins]`** to make tasks runnable via poe: it breaks
  `poetry install` (#232).
- **`bump_version`** has `cz` compute the next semver from Conventional Commits, write it to
  `pyproject.toml`, regenerate `CHANGELOG.md`, commit `bump: X.Y.Z` and create the tag. It
  passes `--no-verify` because that single-line message cannot satisfy gitlint's body rule and
  the format and test hooks are irrelevant to a version bump; run it on a feature branch. It is
  offline-tier only: the online scaffold strips it, since releases come from `release.yaml`.
  `changelog` previews locally; the published site regenerates it in the docs workflow and CI
  never commits it.
- **The HTML coverage task covers the whole tree.** Never narrow it to `--cov=<module>`, which
  reports "no data" on the full suite.
- **There is no `test_feat` task.** Poe passes extra tokens straight through to a task that
  declares no `args`: `poe unit_tests -k some_keyword` and `poe unit_tests -x --lf` work with
  no task per flag. Declaring `args` turns the passthrough off (poe then parses the tokens),
  as `check_commit_msg` does, so declare `args` only for a named, required parameter.
- **System `shellcheck` and `shfmt`** are optional, for boxes whose venv drive blocks executing
  the vendored binary; the primary route is the pip dev dependencies. The two single-rule lint
  tasks are reachable alone so one rule can be checked cheaply; `poe lint` covers both.
- **`check_commit_msg <file>`** runs only the commit-msg hooks against a message file in
  seconds, before `git commit -F <file>`. commitizen and gitlint reject after every pre-commit
  gate has run, so each rejected message costs a full gate run and the fixes arrive one at a
  time. It invokes the project's own hooks, so it cannot drift from what the commit enforces.
  When re-wrapping an over-long body line, re-wrap the whole paragraph (`textwrap.fill`,
  width 76); fixing one line by hand pushes the overflow into the next. Poe validates the
  required argument and prints a real usage line, so the Makefile's hand-written guard was
  deleted, not ported: a reimplemented check can disagree with the tool.
- **Alembic tasks** (#381). Online (`upgrade`, `downgrade`) is what a developer runs locally
  and a deploy runs; offline (`--sql`) is what goes to a DBA when production access is
  restricted. `db_up` already calls `alembic upgrade head`; these give the individual verbs a
  place in the command interface. On a tier with no `alembic.ini` Alembic errors loudly, as
  `db_backup` and `db_restore` do for a non-postgresql backend.
- **The offline wheelhouse tasks** (#299): build on a machine with internet access, copy the
  `WHEELHOUSE_DIR` payload to the offline target and run `wheelhouse_assemble` there. See
  [Offline wheelhouse](offline-wheelhouse.md).
- **Two task sets ship conditionally:** `poe_tasks.library.toml` (`install_dist_locally`, only
  `lib-minimal`) and `poe_tasks.offline.toml` (`new_branch`, `git_merge_to_main`,
  `git_diff_*`, only when scaffolded without a GitHub remote). The Makefile declared both with
  `-include make/*.mk`, whose leading `-` made a missing file silent. Poe's `include` is not
  equivalent: a missing path does not fail but prints `Warning: Poe could not include file from
  invalid path` on every invocation (measured), which teaches a team to read past warnings. So
  the scaffold appends the include list, naming only the fragments it copied
  (`add_poe_include` in `bin/lib/common.sh`); a `[tool.poe]` table declared after the task
  subtables is valid TOML and is how the appended block lands.

### `.pre-commit-config.yaml`

- **A default stage is declared.** `bin/precommit.sh` installs both `commit-msg` and
  `pre-push`, and pre-commit applies a hook to every installed hook type unless a stage is
  declared, so without it every static gate would run twice, on commit and on push. The fast
  hooks carry no `stages:` because they belong on commit, and nothing else says that silence
  also enlists them for the push; hooks that belong elsewhere say so (`commit-msg`, `pre-push`,
  `manual`).
- **`no-commit-to-branch`** is the online default. Offline scaffolds (no GitHub remote) swap it
  for the local `protect-branch` hook via `apply_offline_mode`, pointing at `poe new_branch`;
  online projects also get server-side protection through `gh`.
- **Whitespace and JSON hooks exclude** the verbatim external-byte fixtures (stripping trailing
  spaces or CRLF would corrupt a captured oracle) and the whole of `.vscode/`, which is JSONC:
  `settings.json`, `extensions.json` and `tasks.json` carry comments that `check-json` rejects.
- **`pydocstyle` is decoupled from ruff** because ruff lacks the DAR-style checks. It selects
  only D412 and D417 (no blank line after a section header, every parameter documented).
- **One structural gate per doctrine**, each a hook and a CI step:
    - `check-typing`: ruff and mypy cannot assert the presence of a checker metaclass or
      `@type_checker`.
    - `check-provenance`: a module that references `read_table` must also reference
      `stamp_provenance`, so a bronze row never ships without traceability columns.
    - `function-length`: 60 lines of code. Ruff has no per-function line rule (PLR0915 counts
      statements) and the docstring is subtracted because NumPy docstrings are mandatory, so a
      raw span would measure how well a function is documented.
    - `docs-boundary`: `.specs/` is working material and `docs/` is published documentation;
      layout rules are in `.specs/CLAUDE.md`. The script is BlueprintX's own, copied at scaffold
      time, so the root repo and a project run one implementation.
    - `identifier-masking`: a masked CPF or CNPJ compared with a stored unmasked column matches
      zero rows and raises nothing. Scans `.py` and `.sql`, since SQL reaches the database
      through both.
    - `fixture-scope`: a proxy, not a detector (#442). The real detector is pytest-randomly
      (no config; it self-activates once installed); this gate pins today's zero-shared-state
      baseline so the first `scope="module"` fixture does not remove it silently.
    - `gate-integrity`: diff-scoped against `merge-base(HEAD, main)`, unlike every other hook,
      because it checks a delta: a hook, rule or exclude that was removed without a
      `gate-change-ok: <reason>` is a violation (#309). The same script BlueprintX runs over
      itself.
    - `check-all-exports`: a package declaring `__all__` must name every public member of its
      submodules. The usual introspective test discovers the family through `__all__`, so it
      cannot see a missing member; this walks the files.
    - `check-complexity`: ceilings per tree (1 for `tests/`, 2 for `src/`, 8 for `bin/`).
      A test with a branch tests two paths and its green never says which ran. Two ruff
      invocations, since `per-file-ignores` cannot set a different `max-complexity`.
    - `one-assert`: assertion sites per `test_*` function; zero fails everywhere and
      `tests/unit/` is capped at one (#544), since a two-assert unit test goes red without
      saying which behaviour broke. `tests/integration/` stays zero-only: one call, several
      consequences. Blocking since the last split of #544 cleared the unit suites. See
      `tests/CLAUDE.md`.
    - `check-secrets`: gitleaks (#305) is a system binary resolved like shellcheck and
      actionlint; config is `.gitleaks.toml`; it skips gracefully locally and hard-fails only
      when `GITLEAKS_REQUIRED=1` (set by CI).
    - `check-dtypes`: no ingested column typed as a binary float: float64 stores
      1984223115.42 as 1984223115.4200000762939453125, an irreversible silent loss. Use
      `list_decimal_cols` or text; a dimensionless value opts out with `# dtype-ok: <reason>`.
    - `check-rmw-race`: the read-modify-write race (#385), an attribute reassigned from arithmetic
      over its own value, read by `session.get()` or `.query(...).first()/.one()` in the same
      function, with no `with_for_update()` and no `version_id_col`. Two writers can read one
      value and lose an update silently. A plain read-then-write is not gated. Escape hatch
      `# rmw-ok: <reason>`.
    - `check-layer-imports`: a third-party dependency is reached through a seam in `utils/`,
      never imported by model, view or controller. ruff's banned-api is a blocklist and cannot
      catch a vendor nobody listed; this is deny-by-default per layer. Self-skips when
      `.layer-policy.yaml` is absent.
    - `check-sql-guards` (#355): a `WHERE`-less `DELETE` or `UPDATE` mutates every row with no
      error, and `WITH (NOLOCK)` permits dirty reads, both reading as correct code. Escape
      hatch `# sql-guard-ok: <reason>`. It scans a `.py` file (AST) and a raw `.sql` file
      under `src/config/queries/` (text).
    - `check-migration-slugs` (#375): migration filenames lead with a known verb (Rails'
      `<verb>_<object>[_<qualifier>]`), so `ls migrations/versions/` sorts by date and reads
      as a changelog. Self-skips without `migrations/versions/` (only the ORM tier ships
      them, #373). Escape hatch `# migration-slug-ok: <reason>`.
    - `check-orm-model-guards` (#361, the model-side sibling of #355): bitwise `&`, `|`, `~`
      inside `.where()` or `.filter()` (Python binds them tighter than `==`), two
      `create_all` at Base or module scope (the second succeeds having created nothing), and
      a constraint `name=` duplicated across a mixin MRO (SQLAlchemy silently overwrites one).
      Escape hatch `# orm-guard-ok: <reason>`. Python and SQLAlchemy only; see the gate's
      module docstring for why each TypeScript/Prisma equivalent does not apply.
    - `check-docs-sections`: every canonical page (English slug) exists and is registered in
      `mkdocs.yml` nav; MkDocs builds an unregistered page anyway, so it silently vanishes
      from navigation. Keys on slugs, never localised titles.
    - `check-docs-code-refs` (#159): neither the slug gate nor `mkdocs build --strict` sees a
      `from x import Y` example, so a renamed module keeps being cited after every other gate
      goes green. Triggers on a docs edit or a `src/` move.
    - `check-backlog-ledger`: a branch whose cumulative diff touches `src/` or CI paths must
      add `.specs/backlog/<kebab>_YYYYMMDD_HHMMSS.md` with a checklist. It diffs the index
      against the merge base, so a staged-but-uncommitted ledger counts.
    - `check-comment-language`: prose for a reader (README, `docs/`) may be in the project's
      locale; code, comments, docstrings, symbol names, commit messages and CI output stay
      English. Prose alone failed: the rule was breached twice in one session, the second time
      because a sweep grepped only `.py` and left 55 Portuguese comment lines in
      `src/config/*.yaml`, which became the convention the next author copied. Hence every
      commented file type.
    - `check-comment-budget`: bounds comment volume in every code format, with QA suppressions
      exempt through the anticipatory allowlist (`bin/comment_budget_allowlist.txt`). Escape
      hatch `# comment-budget-ok: <reason>`.
- **mypy runs from `src/`** in the hook for the same reason as in CI; see `mypy.ini` above.
- **The non-Python lint gates share one wrapper with `poe lint`** (one home, zero drift), and
  each wrapper skips gracefully when its tool is absent.
- **actionlint beside yamllint:** yamllint asks whether the YAML is valid, actionlint whether
  GitHub will run it. A workflow can be impeccable YAML and be rejected wholesale, which
  produces no red check: the PR just looks like it is waiting, so a dead gate and a slow gate
  look the same from outside.
- **deptry** requires every package `src/` imports to be a direct dependency. Both triggers
  are needed: a new import in `src/` and a deleted line in `pyproject.toml` break the same rule
  from opposite sides, and the second leaves `src/` untouched. `pass_filenames` is false
  because the gate reads the whole manifest.
- **The unit-test hook tolerates pytest exit 5** (`|| [ $? -eq 5 ]`, no tests collected), so a
  fresh project with an empty suite does not block every commit; exit 1 still blocks.
- **The staged-index guard on pre-push:** a non-empty index at push time is the fingerprint of
  a rejected commit, where the push then ships the previous commit and prints success while the
  work stays behind. Neither CI (a commit that does not exist is not a diff) nor pre-commit (it
  already rejected) can see it. It guards the index, not the dirty tree: unstaged edits while
  pushing are routine, and a noisy guard gets disabled.
- **`coverage-floor`:** `fail_under` in `.coveragerc` is honest only if the `omit` list beside
  it never widens past a capability's `infrastructure/` into `domain/` or `application/`; the
  gate's module docstring explains the green, silent, wrong failure (#149).
- **Coverage is the slow full-suite gate**, so it runs on pre-push and day-to-day commits stay
  fast. The floor is single-sourced in `.coveragerc`, read by pytest-cov here and by the CI
  gate, so there is no duplicated literal to drift.
- **`genbadge`, not the abandoned `coverage-badge`,** which imports the removed `pkg_resources`
  and breaks on setuptools 81 or newer. It generates `coverage.xml`, then the SVG; the SVG is
  tracked (README badge) and the XML is ignored.

## Generated-project shell scripts (`templates/python-common/bin`)

The shell scripts every Python scaffold ships carry no comments. This section records why each
is shaped as it is.

### Rules that recur across the scripts

- **Resolve, don't install.** An optional linter or tool must never trigger an install. A
  missing tool is a graceful skip on a contributor's machine (exit 0 with a message) and a hard
  failure in CI, through a `*_REQUIRED=1` variable (`LINT_ACTIONS_REQUIRED`,
  `LINT_DOCKER_REQUIRED`, `GITLEAKS_REQUIRED`). A skip in CI is a gate reporting its own
  blindness as OK. Applies to `lint_shell.sh`, `lint_yaml.sh`, `lint_sql.sh`, `lint_actions.sh`,
  `lint_docker.sh` and `check_secrets.sh`; `lint_deps.sh` and `check_complexity.sh` are the
  exceptions that hard-fail, below.
- **Probe with `--version`, never `command -v` alone.** `command -v` answers "is there a file by
  that name on `PATH`", not "does it run". A shadowing stub, a half-installed package or a binary
  built for another libc satisfies it, and the wrapper then reports the tool's startup failure as
  a lint finding: a stub exiting 127 produced `actionlint [system]: 7 workflow(s)` and exit 127,
  blaming the workflows (#111). The poetry branch always probed; the system branch now does too.
- **Assert the discovery count.** Tools such as actionlint and deptry exit 0 when handed nothing,
  so a wrapper whose glob matched nothing reports success forever. Zero discovered files fails
  (`lint_actions.sh`, `lint_deps.sh`, `check_unix_filenames.sh`, `check_complexity.sh`);
  `lint_docker.sh` is the one deliberate exception, below.
- **Group a `find` expression.** `-name '*.yaml' -o -name '*.yml' -type f` parses as `(-name
  '*.yaml') OR (-name '*.yml' AND -type f)`, so a directory named `*.yaml` enters the list and
  fails the gate for an unrelated reason. The `\( ... \)` is load-bearing. A prune group must
  also come first with no test before it: a leading `-type f` is false for a directory, so
  `-prune` is never evaluated and `.venv` and `node_modules` get linted
  (`check_unix_filenames.sh`, measured).
- **`mapfile < <(producer)` discards the producer's exit status.** A `find`, `git` or `gh api`
  that dies midway hands over a partial or empty list that reads as complete, and the script
  announces "clean" over a query that never ran. Materialise to a temp file first (also because a
  bash variable cannot carry NUL bytes), check the status, then read
  (`lint_docker.sh`, `check_unix_filenames.sh`, `rerun_stale_gate_runs.sh`).
- **Never set a global inside `$(...)`.** `resolve_poetry` populates the `POETRY_CMD` array;
  command substitution runs in a subshell, so the caller's array stays unset, every later
  `run_poetry` fails and, with output suppressed, the gate reports a clean tree having run
  nothing: 79 known violations reported as success (`check_complexity.sh`, `lint_deps.sh`).
- **Capture an exit status where it is produced** (`|| int_status=$?`). A bare call is exempt
  from `set -e` only because a caller three levels up happens to suspend errexit, which is true
  today and not something anyone should have to know.
- **Keep a command's output when you explain its failure.** Never `>/dev/null 2>&1` a command
  and then blame a cause: the explanation becomes a guess about text you refused to read.
  Remedies name the resolved binary (`${POETRY_CMD[*]}`), never a bare `poetry`
  (`export_deps.sh`, `enable_repo_rules.sh`).
- **Verbatim wrapper discipline.** Each wrapper keeps the heavy logic out of heredocs: a heredoc
  is for inert text a script emits, not a program (`bin/CLAUDE.md`). The CA union and the pip
  requirement translation were `python - <<'PYEOF'` blocks of 66 and 151 lines that ruff never
  linted, mypy never checked and pytest could not import; they are `lib/ca_bundle.py` and
  `lib/pip_requirements.py` now, with the interface unchanged.
- **Sourcing `lib/bootstrap.sh` does no work.** It defines functions only; the caller invokes
  `bootstrap_init` and then the helpers it needs. It guards against being sourced twice.

### GitHub setup scripts (`enable_*.sh`)

- **Why they exist.** A workflow's `GITHUB_TOKEN` is an App installation token that cannot
  create a Pages site, change its source, set a ruleset or flip a security toggle ("Resource not
  accessible by integration"). Those need repo-admin rights, which a maintainer running
  `poe init` has through `gh auth` and CI does not. Merge protection kept in a maintainer's
  memory is protection a fresh clone or fork silently lacks. All are idempotent and
  non-blocking: `gh` absent, unauthenticated or not admin warns and returns 0 so `init`
  completes.
- **`enable_pages.sh`.** Two models, auto-detected from `mkdocs.yml`. With `provider: mike` the
  release workflow deploys to `gh-pages`, so Pages serves from that branch, flipped only once the
  branch exists (the first `mike deploy` creates it) so the live site never points at an empty
  branch. Without mike, `docs.yaml` deploys through `actions/deploy-pages`, so the source is
  "GitHub Actions" (`build_type=workflow`). The two models are mutually exclusive.
- **`enable_security.sh`.** The Settings checkboxes are not reproducible and are forgotten on a
  fork. Three plain `PUT`s (204): vulnerability alerts, then automated security fixes (which
  depend on alerts being on), then private vulnerability reporting, the intake channel
  `SECURITY.md` points at. Secret scanning and push protection are one `PATCH` of
  `security_and_analysis` with scanning first (push protection depends on it, and fields apply
  in order); free on public repos only, so on a private repo it warns and continues. Automated
  security fixes are for vulnerabilities, `.github/dependabot.yml` for ordinary version updates.
  GitHub detects a root `SECURITY.md` by itself. GitGuardian (#155) was evaluated for this role
  and deferred: the native toggles are free and need no third-party app on public repos;
  reconsider for private repos or an offline pre-commit scanner. `secret_scan.yaml` is a
  separate, opt-in decision made at scaffold time (#287), not here: `poe init` runs against an
  already-created repo, the wrong phase to gate a file's shipping. A self-audit of BlueprintX
  (#164, 2026-09-04) found no divergence; the script has no `verify` mode.
- **`enable_repo_rules.sh`.** Applies the `pr-quality-gate` ruleset by name (PUT when it exists,
  POST when it does not; never a blind POST, which would duplicate it):
    - `pull_request` with `required_approving_review_count: 0` and
      `required_review_thread_resolution: true`. Zero, because GitHub forbids authors approving
      their own PR, so any higher value locks a solo maintainer out; zero still forces every
      change through a PR, which is the guardrail.
    - `code_scanning` (CodeQL, alerts at `high_or_higher`), `non_fast_forward`, `deletion`.
    - `copilot_code_review` is its own rule type: the intuitive
      `pull_request.parameters.automatic_copilot_code_review_enabled` returns HTTP 422, which makes
      the feature look UI-only. The automatic/manual boundary is repo config versus account plan:
      without a qualifying Copilot plan the rule sits correctly configured and inert, with no
      error. `gh api user/copilot_billing` 404s for a personal account even when Free is active;
      read the plan page.
    - Deliberately not enabled, each a second source of truth: "Require code quality results"
      (subjective AI severity on the merge path) and "Restrict code coverage" (the floor is
      single-sourced in `.coveragerc`).
    - Settings the gate cannot set itself: code-scanning default setup, `allow_auto_merge`
      (without it the `enablePullRequestAutoMerge` mutation silently no-ops),
      `delete_branch_on_merge` and the `do-not-merge` opt-out label. Each is read back, since a
      green API call is not proof the mutation took.
    - `required_status_checks` only when the list is non-empty, because a required check that
      never reports blocks every PR forever. Do not guess names: they must match check-run
      names exactly (matrix values included); take them from a real PR with
      `gh api repos/:owner/:repo/commits/<sha>/check-runs --jq '.check_runs[].name' | sort -u`.
      The seeded entry is the `review_threads.yaml` job name, correct by construction and
      reporting on every PR from the moment it opens. A name qualifies only if it is a literal
      `jobs.<id>.name:` of a workflow the project ships, its `on: pull_request` has no
      `types:`/`branches:`/`paths:` filter, no job-level `if:` can skip it, and the workflow is
      shipped; `tests.yaml` fails the second rule and `coderabbit_trigger.yaml` the third. The
      list is data (`bin/required-checks.txt`, per template family, #164/#564), compared verbatim
      (stray space never matches). An empty list means CI runs on every PR and blocks nothing:
      measured on BlueprintX 2026-08-16, a PR merged with 32 of 47 checks passed.
    - A missing `required-checks.txt` is unknown, not an empty list (#585): it must not drive a
      PUT against an existing ruleset, which would silently strip its `required_status_checks`.
    - `REVIEW_THREADS_REQUIRE_RESOLVED=1` (#196) supersedes the earlier delegation of the
      resolve half to the ruleset, which drops a thread marked `isOutdated`; see the records
      above. The accepted cost is a red check after a resolve until a re-run.
    - `strict_required_status_checks_policy` must be true (#307, "Require branches to be up to
      date"). With it false a PR merges on a green run against a base that no longer exists
      (#302: six tier checks red only because #293 had not merged; a rebase fixed it). The cost
      is an update-branch for a PR whose base moved, the accepted trade.
    - The summary reads the server back, not the input: a provisioning step that reports its own
      input verified nothing. The strict check has three states with one exit contract (#311):
      0 confirmed strict, 1 confirmed not strict, 2 absent or unreadable. "Could not check" and
      "checked and it is fine" must never share an exit code, a failed read is never an empty
      answer, and an absent policy reads back as jq `null`, which is unknown, not a violation.
      `init` swallows non-zero with `|| true`; `verify` is the read-only CI guard (needs no
      admin) and fails loud on 1 and 2, requires at least one mechanism to confirm strict, and
      checks classic branch protection too, since BlueprintX's own `main` uses it. The default
      branch read has no `|| echo main` fallback (CWE-693): a substituted answer nobody
      confirmed lets verification inspect the wrong branch.
    - Apply errors keep the API's own words; the old form swallowed stderr and blamed admin
      rights for a malformed payload. `~DEFAULT_BRANCH` survives a rename.

### Linting wrappers

- **`lint.sh`** is the one list of every gate, called by `poe lint`, CI and
  `bin/ci/scaffold_lint_test.sh`. It replaced 14 inline recipe lines duplicated across two
  files that had already diverged (#189). Order is load-bearing: the two ruff steps come first
  and mutate the tree (`--fix`, then `format`), so every later gate judges the tree CI checks;
  `poe lint` must leave a clean checkout unchanged, and a diff means a gate and the formatter
  disagree. `set -e` with no masking: do not add `|| true`. mypy runs from `src/` (config path
  `../mypy.ini`) so `src` is the single package base. `check_provenance` was the one gate CI
  ran and this script did not, so "green locally, red in CI" was reachable on the gate that
  stops an ingested row shipping without its url and `updated_at` columns.
- **`lint_shell.sh`** resolves shellcheck and shfmt preferably through the Poetry venv, which
  finds the vendored wheel wherever the venv lives, including a Windows UNC or mapped drive;
  a bare-`PATH` lookup would silently skip both there. It falls back to a system binary
  (`install_shell_linters.sh`) and skips only when neither exists. Default mode formats in
  place; `--check` is `shfmt -d` for the hook. The canonical gate is warning-and-above with
  SC1091 excluded (siblings are sourced by runtime path). File discovery is find-only: a literal
  `tasks.sh` was left beside it after the poe migration and made shellcheck report "does not
  exist" for the whole run.
- **`install_shell_linters.sh`** is an optional convenience for machines that need a system
  binary (a venv on a share that blocks executing the vendored one). Each branch is guarded with
  `command -v` and skips with guidance; it never hard-fails. Order by OS: Windows chocolatey then
  scoop (both package shellcheck and shfmt), macOS brew, Linux apt-get, dnf, pacman, zypper
  (shfmt is rarely packaged, so it stays on the pip `shfmt-py` or `go install`). `--dry-run` or
  `DRY_RUN=1` previews through one guarded runner.
- **`lint_yaml.sh`, `lint_sql.sh`** resolve Poetry through the bootstrap lib (poetry, then
  `python -m poetry`) rather than a bare `command -v poetry`, which saw only a bare `poetry` and
  silently skipped a `python -m poetry`-only box. yamllint's real status propagates. One sqlfluff
  pass covers every engine: queries live in `src/config/queries/<engine>/`, sqlfluff resolves
  config per directory, and adding an engine is adding a folder, never a second pass with
  another `--dialect` or a dialect in the filename.
- **`lint_actions.sh`** exists because yamllint asks whether YAML is well-formed and actionlint
  asks whether GitHub will run it. A workflow that added `pull_request_review_thread` (a real
  webhook event, not a workflow trigger) was impeccable YAML, passed every hook, and GitHub
  rejected the entire file with no red check: the PR just looked like it was waiting, so a dead
  gate and a slow gate are indistinguishable. In CI the binary is installed at a pinned version
  with a verified SHA-256 and `LINT_ACTIONS_REQUIRED=1` makes absence a failure. It sets
  shellcheck options for the `run:` blocks actionlint shells out to, so one script does not pass
  one gate and fail the other. A comment line may not start with a tool's name, because it parses
  as a lint directive.
- **`lint_docker.sh`** is a wrapper, not a line in `lint.sh`, because hadolint is the only gate
  with no Python package: pre-commit runs `hadolint-docker`, which needs a Docker daemon, and
  calling that from `poe lint` would turn a lint run into an infrastructure requirement. It
  differs from `lint_actions.sh` deliberately: zero Dockerfiles is legitimate (no Python tier
  ships one, measured 2026-08-23; the only one is in `react-spa-webpack`). The rule is: no
  Dockerfile skips; Dockerfiles with no tool skips unless `LINT_DOCKER_REQUIRED=1`; both present
  lints. The count is asserted before the tool runs, so hadolint is never handed an empty list.
  The image is pinned by digest, not tag: the tag pins what is asked for, the digest what
  arrives, and the image is pulled and executed on the gate's machine (re-resolve with `docker
  buildx imagetools inspect hadolint/hadolint:<tag>`). It probes `docker info`, since the client
  binary is present on machines whose daemon is stopped. The tree is mounted read-only and the
  run happens inside it, so hadolint finds `.hadolint.yaml` and reports file names (stdin
  reports `-`); `--no-fail` is not passed, the container's status is the verdict.
- **`lint_deps.sh`** (deptry over `src/`). The rule "every imported package is a direct
  dependency" was written down and nothing checked it. The first run found both DDD tiers using
  pandas in five `src/utils` modules while declaring it nowhere (it arrived through `wwdates`);
  a calendar library dropping pandas would have broken every DDD project with an `ImportError`
  nobody could predict. It must run inside the project venv with no system fallback: deptry maps
  a module to its distribution through the metadata of the environment it runs in, and outside
  the venv the verdict inverts (9 findings on ddd-native, all false and two contradictory, while
  both real defects vanished). The config lives in `pyproject.toml` per tier, never a shared
  `deptry.toml`: `--config <file>` re-points deptry at that file as the manifest too, and it fell
  back to `requirements.txt` and relabelled beartype, python-dotenv, wwdates and every DB driver
  as transitive. `bin/` is out of scope, since one run cannot hold both profiles and each dev
  dependency would become a DEP004. Zero `.py` files under the tree fails.
- **`check_unix_filenames.sh`** rejects names outside `[a-zA-Z0-9._-]`. It has two callers:
  pre-commit passes staged files, and `poe lint`/CI pass nothing, in which case it discovers the
  tree itself with `git ls-files -z` (respecting `.gitignore`) and a `find` fallback for a
  scaffold not yet `git init`'d. The no-argument mode exists because the old script iterated an
  empty `$@` and printed "All filenames are valid" having examined nothing. Zero discovered files
  is never legitimate there, so it fails.
- **`check_secrets.sh`** (gitleaks, #305). GitGuardian (#155, #286) is the hosted product and
  BlueprintX's own `GITGUARDIAN_API_KEY` measurably fails auth (exit 3); live detection there was
  never proven. This repo is public, so shipping that key would either hand strangers the
  maintainer's quota or ship every project red. gitleaks needs no key or account, so it is the
  default scanner, additive to GitGuardian. One implementation: bulk-copied into every project
  and run by BlueprintX's own hook and workflow through `--root .`. Config is gitleaks' own:
  `.gitleaks.toml` at the root of the target. Resolve, don't install; `GITLEAKS_REQUIRED=1` in
  CI. Exit 0 or 1 are data and drive the script's exit.
- **`check_complexity.sh`.** The per-tree ceilings and their arguments are in
  [Complexity ceilings](complexity-ceilings-measured.md); the points that live in the script are:
    - Cyclomatic ceilings are tests 1, `src/` 2, `bin/` 8: a branching test tests two paths and
      its green never says which ran; branching that is the work of a validator or parser takes
      the escape hatch with a reason; the gates in `bin/` are parsing tools by nature and at 2
      they were 74% violating, a number nobody pays and so a gate nobody keeps. Nesting depth
      (PLR1702) is a separate table: tests 2, `src/` 3, `bin/` 5 (findings at one ceiling lower:
      2, 54 and 16 for tests, `src/` and `bin/`). An earlier revision asserted 1, 1 and 3 by
      analogy to the mccabe row; all three were wrong, and because the hook scans the whole tree
      each blocked every commit. An argument by analogy is not a measurement: mccabe counts
      branches and PLR1702 counts nesting. These are the zero-cost ceilings; the tighter ones
      (`src/`=2 costs 8 fixes, `bin/`=4 costs 2) are each their own measured slice.
    - Do not reimplement mccabe. ruff ships it as C901 and PLR1702; a draft counter that
      treated `assert` and `with` as decision points reported 85% of `tests/` violating where
      the real figure was 8%. A threshold agreed against one implementation and enforced by
      another is not the threshold anybody agreed to.
    - Two ruff invocations per rule: `per-file-ignores` can switch a rule off for a path but
      cannot give it a different threshold, so `run_ruff_check` takes the rule code and its
      config key (`lint.mccabe.max-complexity`, `lint.pylint.max-nested-blocks`) as arguments.
    - Escape hatch: `# complexity-ok: <reason>` on the `def` line (ruff anchors both rules
      there, not on a decorator), reason required, one marker for both rules. The whole signature
      is scanned, because `ruff format` re-wraps a long signature and moves a trailing comment to
      the closing-paren line; a hatch correct on the `def` stopped counting when the formatter
      touched the file (`CreateLog._validate_path`). The formatter wins, so the gate adapts. The
      signature scan is bounded so a malformed file is not turned into a file read.
    - Only `--root` is accepted, so BlueprintX runs this file over its own tree (#189).
    - ruff is probed with `--version` so a real lint exit code is never mistaken for "absent".
      The mode is set as a global, never printed for `$(...)`, for the subshell reason above.
      ruff exits 0 or 1 (data); anything else means it could not run and its output is
      re-printed. Output goes to a file, not `while read < <(...)`: a process substitution runs
      in a subshell, so a hard failure could only exit that subshell, the loop would read
      nothing and the gate would be blind a second time.
    - Colour: ruff wraps every `path:line:col:` separator in ANSI escapes when colour is on,
      and those travel into `cut -d:` and an arithmetic expansion, which dies with `[0m101[36m:
      syntax error: operand expected`, naming neither ruff, colour nor this gate (6 of 6 tiers
      red on 2026-08-23 because a shell exported `FORCE_COLOR`). `NO_COLOR=1` alone does not fix
      it: with `FORCE_COLOR=3` also set ruff still colours, and `TERM=dumb` does not change that.
      So the forcing variables are unset, in a subshell rather than `env -u` (the poetry branch
      calls a shell function `env` cannot exec) and rather than `local` (does not hide an
      exported global from a child). `NO_COLOR` stays as belt-and-braces.
    - ruff absent is not a graceful skip: it is a declared dev dependency, so its absence is a
      broken environment. A broken glob would otherwise report success forever.
- **`test_urls_docstrings.sh`** (hook) scans docstrings for URLs, cached for a week to avoid
  repeated network calls. Domains that answer a scripted probe with 403 or anti-bot pages
  regardless of method are treated as reachable, a deliberate false negative: the alternative
  is a permanently red hook that people learn to bypass. Match the hostname, never a substring:
  `*domain*` would allowlist `https://attacker.example/path/openai.com` and
  `https://openai.com.attacker.example/`; strip scheme, userinfo and everything from the first
  `/`, `?`, `#` or `:`, then require an exact match or a real subdomain. Probes go HEAD, then
  GET for servers that refuse HEAD, then wget for servers that refuse curl; each fallback exists
  for an observed failure, so the order is load-bearing. State is script-scoped because bash
  cannot return an associative array. A host-only URL is skipped (nothing to 404, and fetching
  it only rate-limits). A one-line docstring opens and closes on the same line and must not flip
  the state. A delimiter line is docstring content and is scanned before the state flips
  (#206, #224): the old `continue` blinded the gate on `"""One line https://..."""` and on the
  opening line of a multi-line docstring, and was self-concealing, since an unscanned URL is
  never fetched or cached. A closing delimiter sharing a line with text was never blind (the URL
  was scanned as body text) but the state never flipped back, so every later line was read as
  inside the docstring and over-scanned; both delimiters are now matched wherever they sit.
- **`check_clean_index.sh`** (pre-push). A non-empty index at push time is the fingerprint of a
  commit rejected after `git add`: the push ships the previous commit and prints success while
  the work stays behind, found only by comparing HEAD to `origin/<branch>`. No other layer sees
  it: CI sees only what was pushed, and pre-commit already did its job by rejecting. It also
  closes a hole a written rule did not: "never pipe `git commit` through `tail`/`grep`; confirm
  HEAD moved" existed and was violated hours after being quoted, because a rejection scrolling
  off screen is what a tired reader misses. It guards the index, not the dirty tree: unstaged
  edits while pushing are routine, a noisy guard gets disabled, and a populated index is nearly
  false-positive-free. Escape hatch: `git push --no-verify` or stash the index. With no work
  tree (a shipped zip) there is nothing to guard and it never blocks.

### Bootstrap, runtime and CI helpers

- **`lib/bootstrap.sh`.** `ensure_python_version` prefers pyenv (pinning the project version) and
  falls back to the system interpreter with a version-mismatch warning for corporate hosts that
  forbid pyenv. `to_native_path` turns `/a/foo/bar` into `A:/foo/bar` through `cygpath` on Git
  Bash/MINGW, shell-only and stripping stray CR and LF; `POETRY_CMD` is an array so a `python -m
  poetry` fallback stays quotable. `build_union_ca_bundle` writes `bin/ca_bundle.pem` as the
  union of certifi's roots, whatever bundle the host provisions and the corporate CA. Union is
  the point: pointing `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE` and `PIP_CERT` at the corporate CA
  alone narrows trust to one certificate and breaks every connection not through the proxy's CA
  (Poetry went from "0 candidates" to "All attempts to connect to pypi.org failed" because the
  helper ran), and it clobbers a bundle a corporate image provisions. A generated file also
  replaces the old append to certifi's `cacert.pem`, which mutated site-packages invisibly and
  was undone by any reinstall. `wire_corporate_ca` is a no-op without `bin/corporate_ca.pem`,
  so non-corporate setups keep full verification; it resolves the absolute Windows-safe path in
  shell, exports the union to every consumer, points Poetry's resolver at it best-effort, and
  deliberately does not export `PIP_TRUSTED_HOST`, which disables verification for PyPI outright.
- **`get_corporate_ca.sh`** generates `bin/corporate_ca.pem` from the OS trust store without
  touching the network or disabling TLS verification. It is the store the browser uses, which is
  why the browser works behind a TLS-inspecting proxy while pip, with certifi's own bundle,
  does not. On Windows it reads the store from Python directly, with no admin rights. On
  Linux/macOS the store is already a file and a corporate image normally installs the CA there,
  so it refuses with instructions rather than guess a path or capture whatever certificate the
  network presents. The pem is git-ignored and picked up by `poe venv` and `poe run`.
- **`lib/pip_fallback.sh`.** Every status is checked: the function used to return the pruning
  status, which succeeds on an empty file, so a failed TOML reader or emitter produced an empty
  requirements file and reported success, and install and verify both accept zero requirements
  (the venv was declared good having installed nothing). `_read_env_var` is anchored to the
  project, since its default `.env` is CWD-relative and reading the wrong one prunes the driver
  the project needs. Pruning: the service tiers declare all four DB drivers unconditionally
  (about 20 MB of pyodbc, oracledb, psycopg and mysql-connector a SQLite project never
  imports), and on a corporate index that answers 403 per package an unrequested dependency is a
  self-inflicted failure surface (2026-08-16, `mysql-connector-python` was refused and took the
  whole install down). `DB_BACKEND` is lowercased to match `config/connection_db.py`
  (`os.getenv("DB_BACKEND", "sqlite").lower()`), or `PostgreSQL` would drop psycopg. A driver not
  in the table is not a DB driver and is never pruned. `pip install -r` is atomic, so one
  refused wheel discards a batch whose other packages downloaded; the batch is only the fast
  path, and on failure it retries per requirement so everything installable is installed and the
  report names every refused package. A blocked index can report success with nothing usable
  (`already satisfied` without contacting the index), so the last word is a real import
  against the target venv's own interpreter (`verify_venv_imports.py`).
- **`lib/common.sh`** is kept byte-identical in `templates/common/bin/lib/` and here (CI enforces
  parity; offline scaffolds copy the common version over this one, so both carry
  `resolve_default_branch` and `_read_env_var`). `print_status <level> <message>` (success, error,
  warning, info, config, debug, section) sends errors to stderr and tees timestamped lines to
  `$LOG_FILE` when set. An unknown level names the bad status on stderr instead of printing an
  unmarked line: 35 calls spelled `warn` for `warning` across five scaffolds each rendered a
  warning like ordinary chatter. `resolve_default_branch`: explicit argument, `$DEFAULT_BRANCH`,
  `origin/HEAD`, local `main`, else `master`. `_read_env_var NAME` reads `.env` (override with
  `ENV_FILE`), returns the raw right-hand side without stripping an inline `#`, so passwords with
  `#` or `$` survive (the point of bypassing Make's expansion), removes one pair of surrounding
  quotes, last assignment wins, missing file or key is empty. `ensure_dir` checks existence
  before `mkdir -p`: over an existing path on Windows mapped or UNC drives a bare `mkdir -p` can
  fail with "Permission denied".
- **`poe_exec.sh` and `poetry_exec.sh`** are the single Poe and Poetry entrypoints for every
  hook, workflow and script, so nothing depends on a bare binary on `PATH`. Poetry may be
  reachable only as `python -m poetry` (the user-scripts directory is not on `PATH` on Git
  Bash/MINGW), so a bare `poetry run` dies "command not found" with Poetry installed;
  `resolve_poetry()` tries bare then `$PYTHON -m poetry`, and `ensure_poetry()` installs from
  `requirements.txt` when none resolves. Poe reaches a machine by three routes: the in-project
  `.venv` first (load-bearing: `poetry.toml` forces in-project, `poetry install` does not put poe
  on `PATH`, and `$PYTHON` is the system interpreter, so in CI after `poetry install --with dev`
  neither later route can see it), then `poe` on `PATH` or `$PYTHON -m poethepoet` (the module is
  `poethepoet`, not `poe`: `python -m poe` fails), probed by running the module because a `pip
  install --user` layout puts the package where the interpreter finds it but the console script
  nowhere useful, then `poetry poe` last. The plugin is no longer declared: a project-scoped
  `[tool.poetry.requires-plugins]` breaks `poetry install` (a plugin env keyed by project name,
  not path, measured), it is the slowest route, and poe's docs advise against it because
  Poetry's CLI mangles arbitrary task arguments and the plugin silently disappears if
  `--no-plugins` appears anywhere. Stdout discipline: resolution status goes to stderr so the
  task's own stdout and command substitution (`version -s`) stay clean. Zero arguments is valid
  and is the help path.
- **`precommit.sh`** installs `commit-msg` and `pre-push` hooks. `pre-commit install` needs git
  and a work tree; a deploy box (a shipped zip) has none and pre-commit aborts "FatalError: git
  failed", taking `init` down. Hooks are dev-only, so with no work tree it warns and skips,
  like the best-effort `ensure_env` and the Playwright install. Opt-in alternative: replace the
  skip with a loud `git init`, announced so a dev box surfaces a lost `.git`; never auto-init
  silently. On a shared network checkout (Windows UNC mapped to a drive) the first person to
  check it out owns it and any other domain user trips git's "dubious ownership" guard, which
  blocks every repo operation and makes `pre-commit install` die too. `ensure_safe_directory`
  registers a per-user `safe.directory` before the work-tree probe, which would otherwise fail
  under the guard and wrongly conclude "no repo" (a bogus `git init` over an existing tree).
  It lifts git's own suggested path rather than reconstructing it, and strips the UNC quote.
- **`venv.sh`, `run.sh`.** `run.sh` resolves the entrypoint, ensures a venv, prefers Poetry and
  falls back to stdlib venv plus pip requirements; the pinned interpreter is selected first so
  both branches use it. Tokens after the entrypoint are the user's argv: `poe run backfill`
  forwards `backfill`, and dropping it makes `main.py` fall back to `PIPELINE_INTENT` (#317).
  The Playwright install in `venv.sh` is best-effort and never aborts `init`: it warns and points
  at `poe fix_playwright`, since the environment is usable without browsers and `playwright
  install` fails on hosts without a compatible toolchain (`Error: spawn UNKNOWN` under Git Bash
  on Windows). `--with-deps` installs apt packages and is valid on Debian and Ubuntu only, so it
  is added on Linux only. `fix_playwright.sh` cleans and reinstalls the browsers.
- **`ensure_env.sh`** seeds `.env` from `.env.example` when `.env` is absent; if the template is
  missing it reports and aborts that script with non-zero, and the task runner ignores that
  failure so the venv and pre-commit steps still run. **`db.sh`** has `up` (idempotently start
  services, ensure schema, migrate), `backup` (dump to `BACKUP_STORE_PATH`) and `restore`
  (`DUMP=<path>`); Poetry is resolved robustly because a bare `poetry` may be absent.
- **`export_deps.sh`** writes `requirements-lock.txt` for hosts that can `pip install -r` but not
  Poetry (locked-down boxes, slim containers, air-gapped transfers). `export` is a plugin
  subcommand, so the question is "does the Poetry that resolves here carry the plugin?", and a
  `pip install --user` Poetry and the venv's Poetry report the same `--version` with different
  plugin sets. That is why the plugin is pinned in `requirements.txt` (what `ensure_poetry`
  installs from) and not only as a dev dependency, which reaches the venv and nothing else: the
  recipe would work from an activated shell and fail from a VS Code task, cron, CI and the
  offline host it serves. The artifact path is overridable so a test can redirect it.
- **`test_cov.sh`** is four steps that only make sense in order: pytest writes `.coverage`,
  `coverage report` prints it, `coverage xml` serialises it, genbadge renders `coverage.svg`.
  Splitting them across two recipe files put the order in two places. genbadge runs with
  `--local`: a build step that reaches the network fails behind a corporate proxy and on an
  air-gapped runner, and a badge is not worth either.
- **`build_wheelhouse.sh`** (#299, pieces 1 to 3 of #127). A corporate machine behind a
  TLS-inspecting proxy that blocks PyPI cannot install anything; `verify_venv_imports.py` makes
  that failure loud and this is the remedy: `poe wheelhouse` builds the payload on a machine
  with internet and `poe wheelhouse_assemble` rebuilds it on the offline target. See
  [Offline wheelhouse](offline-wheelhouse.md). Heavy logic (marker evaluation against a target
  environment, zip/split/manifest, verify-and-refuse) is in `lib/wheelhouse_select.py`; the shell
  owns only network I/O and orchestration. The default destination is a sibling of the repo:
  outside it, never a `git add` candidate, surviving a re-clone, per repo because sibling
  projects pin different versions. DB-driver pruning by `DB_BACKEND` took 65 MB to 45 MB (#299).
  Bash 3.2-safe (macOS system bash): no associative arrays, no `${var,,}`; `mariadb` shares
  mysql's driver. Cross-platform builds pass pip's own platform tags verbatim
  (`win_amd64`, `manylinux2014_x86_64`); unset, pip downloads for the build machine. The trap
  expands `dir_tmp` immediately: single-quoted it would hit an unbound variable under `set -u`
  after the function returned, leaking the directory and exiting non-zero.
- **`pr_reconcile.sh`** (#255) is the mechanism extracted from the `pr-reconcile.yaml` inline
  `run:` block so every workflow that ships it invokes one implementation, like
  `check_review_threads.py` and `rerun_stale_gate_runs.sh`. Inputs: `GH_TOKEN` and `GH_REPO`
  (required), `EVENT_PR` (one PR, the fast path) and `SWEEP_LIMIT` (default 30, the scheduled
  backstop). It acts only on a merged PR, so a closed-unmerged PR closes nothing. A linked
  issue's repository travels with its number: a cross-repo link would otherwise resolve
  `gh issue view 42` against `GH_REPO` and close an unrelated #42 there, silently. It closes only
  issues still open, and deletes only a same-repo head branch, and only while the ref still
  points at the commit the PR merged: this runs on a schedule, possibly days later, and a branch
  name is reusable (`fix/thing` cut again for new work would be deleted with unpushed commits,
  reporting success). An already-deleted branch is a no-op.
- **`rerun_stale_gate_runs.sh`** re-runs the stale failed runs of the review-thread workflow
  that still poison the merge rollup. The gate re-triggers on `pull_request`, `pull_request_review`
  and `pull_request_review_comment`, each creating a new check run, and branch protection reads
  the aggregate, so the push-time failure keeps the PR `BLOCKED` however many later runs pass
  (#262 one stale failure, #264 five, #265 seven; `gh run rerun <id> --failed` on only the stale
  failures flipped each to `CLEAN`). `concurrency:` was tried and is strictly worse: a queued run
  cancelled before it starts publishes no check run, leaving the required context at `Expected
  — Waiting for status to be reported`, which no re-run clears; a stale red is at least
  clickable. It exits 0 even when it cannot do its job, and that is not failing open: it is a
  janitor, if it fails the run stays red and the PR stays blocked (the status quo, visible),
  whereas failing the step would deposit one more failed run into the rollup it came to clean.
  It reports through one seam that emits both the `::warning::` annotation (a machine-read
  workflow command that puts the message in the run summary) and the status line, because three
  copies of that pair are where one loses its annotation. It refuses to act outside a
  pull-request run (an empty `HEAD_SHA` is ordinary on other events). It asks the API which
  workflow the current run belongs to, since the two shipped copies disagree on name and
  filename (`.yml` here, `.yaml` in a generated project). It scopes by `head_sha` so older
  commits' genuine failures are untouched, and skips `$GITHUB_RUN_ID`, the loop guard: it only
  runs on a successful run, so re-running itself would re-run a green run forever. Needs
  `actions: write`.

## Root workflows: why each is shaped as it is

These records explain the GitHub Actions workflows under `.github/workflows/` in this
repository. They were moved out of the workflow files, which now carry no prose.

### `coderabbit_trigger.yml` — a user PAT asks for the review

- **Why the workflow exists.** CodeRabbit declines automatic reviews on a repository with
  fewer than 10 stars, and the threshold is not configurable from `.coderabbit.yaml`. The
  consequence was PRs #204 and #213 merging with every check green and no review.
- **Why a PAT and not `GITHUB_TOKEN`.** CodeRabbit ignores bot-authored comments. A comment
  posted with `GITHUB_TOKEN` is authored by `github-actions[bot]` and was dropped silently
  (measured on #210: no reply in 5 minutes). A comment from a user PAT replied in 9 seconds
  (#215). Do not simplify this.
- **The secret is `GH_PAT_REVIEW_TRIGGER`.** The earlier name `CODERABBIT_TRIGGER_PAT` read as a
  CodeRabbit key and cost two rounds of `401 Bad credentials`. Actions reserves the
  `GITHUB_` prefix (`HTTP 422`), so `GH_` is the closest legal spelling. Setup: a fine-grained
  GitHub PAT for this repository with `Pull requests: Read and write`, then
  `gh secret set GH_PAT_REVIEW_TRIGGER --repo <owner>/<repo>`.
- **Fail, never skip, when the PAT is absent.** A skip would reproduce the original defect:
  no review and nothing says so. A fork PR gets no secrets and lands in the same failure,
  correctly.
- **The shape check.** A bare `401` cannot tell a wrong token from a token stored wrong
  (`gh secret set … < file` keeps the trailing newline). The step reports only the token
  class and booleans, never a value, a substring or its length, because the logs are public
  and a substring of a masked secret is not masked.
- **A 403 is a different failure.** It is GitHub's API rate limit for the PAT's user, not
  CodeRabbit's review quota, and clears by itself; it must not read as a bad token. Match on
  `rate limit` alone: the secondary limit's wording ("You have exceeded a secondary rate
  limit", 403 or 429) does not contain the primary's phrase.
- **Triggers.** `synchronize` was dropped in #454: only 5.4% of 773 post-open events produced
  a finding and 69.6% were rate-limit notices, and the required "Review threads answered"
  check already closes the unreviewed-merge hole. `opened` was kept in #567: asks on open are
  45% of all spent but win 26% of reviews, yet they enrol the PR for
  `retry_rate_limited_review.py`, which only adopts a PR whose newest reviewer comment is a
  rate-limit notice. Dropping it would leave a PR opened with no session running stalled.
  Drafts are skipped; `ready_for_review` brings them back.
- **Concurrency may cancel here.** Several pushes need one trigger, and this workflow publishes
  no verdict anyone waits on, unlike `review_threads.yml`.

### `review_retry.yml` — retry a rate-limited review on a timer

- It does not relax the gate. Of 112 PRs, 19 hit a rate limit and 18 were reviewed in the end,
  so a rate limit is a delay and the asking is automated. The 19th (#157) merged with no
  review while a notice stood, which is the hole the gate exists to close.
- A schedule is the only shape that works: nothing fires while a PR waits. Measured windows
  are 10 to 25 minutes, so `*/10` clears most on the first tick after the window.
- It needs the user PAT for the same reason as the trigger. The script reads back the
  comment's author type and warns if it posted as a Bot.
- It asks at most one PR per run, oldest first (#280), which matches the shared account's
  roughly one review per hour.
- It has no secret-shape preflight: with a missing PAT the gate still blocks the PR visibly,
  and a job failing every 10 minutes would be noise.
- Its concurrency group has `cancel-in-progress: false` so a queued run waits and re-reads the
  comments. That does not contradict the no-concurrency rule below: it is a janitor that
  publishes no required check.

### `review_threads.yml` — triggers, concurrency and the stale-run cleanup

- **Triggers are the point.** Under `pull_request` the verdict was computed at push time and
  went stale when a review landed (PR #180 merged with two unanswered threads).
  `pull_request_review` and `pull_request_review_comment` re-run it. `pull_request_review_thread`
  is a webhook event, not a workflow trigger; adding it makes GitHub reject the whole file
  silently (#156), and `bin/ci/check_actions.sh` now catches that class.
- **`issue_comment` is load-bearing.** A clean CodeRabbit review is a plain issue comment, so
  without this trigger the gate stays frozen on its push-time failure (measured on #342: the
  gate was wrong two seconds after the review finished). The job skips plain issues, and reads
  the PR number from `issue.number` on that event.
- **Resolution cannot re-trigger it.** Resolving a thread emits no workflow trigger, so after
  a resolve the run must be re-run once. The job asserts both halves (reply and resolve,
  `REVIEW_THREADS_REQUIRE_RESOLVED=1`) since #196; the earlier split gave the resolve half to
  `required_conversation_resolution`, which drops an outdated thread from the blocking set
  (#193: merge enabled, thread unresolved and outdated, 29 of 29 checks green).
- **It is safe to require.** The earlier note that it must not be a required check was wrong
  and left `required_status_checks` empty, so a PR merged with 32 of 47 checks passing (#173 and
  PR 185).
- **No `concurrency:` block, deliberately.** With `cancel-in-progress: false` only one run
  may sit pending, so each queued run cancels the waiting one (10 runs in 25 seconds on #216).
  A run cancelled while queued publishes no check run, leaving the required context at
  `Expected — Waiting for status to be reported`, which nothing clears.
- **The stale-run cleanup (#263).** Each trigger opens a new check run and branch protection
  reads the aggregate, so a correct push-time failure keeps the PR blocked behind any number
  of later passes (5 on #264, 7 on #265). The `Clear stale failed runs` step re-runs those
  failures. `if: success()` is the loop guard. On `issue_comment` the head SHA must be fetched
  because the event has no `pull_request` object, and an unresolved head fails loudly (#350).
- **Closing the ceiling properly** would need a webhook receiver or a GitHub App dispatching
  `repository_dispatch` on `resolved`. That was rejected as not worth an always-on listener
  for this repository.
- **Its own workflow.** It is kept out of `scaffold_checks.yml` so a review comment does not
  re-run the 29-job scaffold matrix: one job, a few seconds, as often as needed.
- **A finding takes both halves:** reply with what changed and why, then resolve. A bot
  resolves its own threads on seeing the fix, so `isResolved` records the reviewer's
  satisfaction, never the author's reasoning.

### Other workflows

- **`behind_base_gate_report.yml` (#368).** A PR runs every gate from its own checkout, so a
  branch behind `main` can fail or wrongly pass on an old gate. `gh pr update-branch` moves
  the head commit and can supersede a clean review, so the workflow only reports. Its
  schedule is coarse: a `*/10` schedule fired 6 times in 21 hours on this repository.
- **`pr-reconcile.yaml` (#255).** A PR merged by native auto-merge armed with `github.token`
  leaves the linked issue open and the branch undeleted, while a manual merge of the same PR
  closes it. The `pull_request: [closed]` path is an optimisation; the `schedule` path is the
  backstop and the fix, because scheduled events are exempt from the "no new workflow runs"
  suppression. It calls `templates/python-common/bin/pr_reconcile.sh`, the same script a
  generated project calls at `bin/pr_reconcile.sh`.
- **`issue_scope.yml`.** Its own workflow so an issue edit re-runs one job instead of the
  scaffold matrix. It listens to `issues` events because an edit changes the declaration the
  gate judges against, and checks out the base commit, never the merge ref, so a PR cannot
  rewrite `check_issue_scope.py` and judge itself. The only writing job posts a commit status
  on each affected PR head, since an `issues`-triggered job belongs to no PR's check suite.
- **`pr_template.yml`.** Separate because `edited` must re-run it and would otherwise re-run
  every scaffold check on a body edit. It reads the body live from the API, since a re-run
  replays the original event payload.
- **`release.yml`.** The version input is free text and is validated before `git tag`, the
  irreversible step, so a bad value is a no-op instead of a pushed tag with no artifacts.
  `release_snap.yml` fails before its 30-minute build when the credential is absent, because
  an `exit 0` there let v0.16.67 to v0.16.70 report green while nothing reached the store
  (#669). Every package job stamps the release version into the fallback literal of
  `blueprintx --version`, since packaged installs have no `.git`.
- **`verify_branch_protection.yml` (#307).** Guards the `strict` setting, which anyone with
  admin rights can flip with no red check. `GITHUB_TOKEN` cannot read branch protection
  (`administration` is not a grantable scope), so it reuses `GH_PAT_REVIEW_TRIGGER`. It runs
  on push to main, weekly and on dispatch, not on `pull_request`, because it checks a
  repository setting and is not a required check. It fails, never skips, without the PAT.
- **`docs.yml`.** Checks out full history so `cz changelog` sees the tags, and regenerates
  `CHANGELOG.md` fresh on every docs build; it is never committed back.
- **`secret_scan.yml`.** Scans full history. A pinned version fixes what is asked for, never
  what arrives, so the download is SHA-256 verified before extraction, as `lint-actions` does
  for actionlint. A graceful skip is right on a contributor's machine and a placebo in CI, so
  `GITLEAKS_REQUIRED=1` turns a missing install into a failure.

### `scaffold_checks.yml` — notes per job

- **No setup step** for the stdlib-only gates (function length, complexity of `bin/`, comment
  budget, test copy lists, sed portability, git remote guard, scaffold libs): a missing tool
  cannot make a gate report its own blindness as OK, so there is no `*_REQUIRED` flag. The
  complexity job on `templates/python-common` needs ruff, because C901 is the metric, and
  hard-fails when it cannot be resolved.
- **Complexity needs a second invocation (#271)**, scoped to `templates/python-common`, whose
  `src/` and `tests/` the top-level directory lookup cannot see. Function length is not
  duplicated: its discovery already walks the whole root (measured by planting a 66-line
  function there).
- **Sed portability.** GNU `sed -i` takes no argument and BSD requires one, so a bare
  `sed -i` aborts a scaffold on macOS. `sed_inplace()` in `bin/lib/common.sh` is the
  replacement.
- **Test copy lists.** A shared test no scaffold copies is committed and never run in any
  generated project. Its first run found `test_startup_fragility_order.py` absent from all
  five tiers.
- **actionlint.** yamllint asks whether the YAML is valid, actionlint whether GitHub will run
  it, and a workflow GitHub refuses produces no red check. The template workflows are in
  scope because they never execute here. Its tarball is SHA-256 checked for the reason above.
- **GitGuardian is not a required check (#155).** Its population is unmeasured. GitHub gives a
  Dependabot-triggered run a separate secret store holding none, so the key resolves to an
  empty string and `ggshield` exits 3 (#457, PR #400). The job is skipped on the PR author
  (`github.event.pull_request.user.login`, never `github.actor`) when that author is
  Dependabot. This is not a silent pass: `gitleaks` scans the same range unconditionally. The
  fix is `gh secret set GITGUARDIAN_API_KEY --app dependabot --repo <owner>/<repo>`. The
  probe is `gh api repos/<o>/<r>/dependabot/secrets --jq .total_count`, which returned 0, and
  until that secret exists a Dependabot PR trips the job on every run (the log shows
  `GITGUARDIAN_API_KEY:` blank and `Error: Invalid GitGuardian API key.`).
- **ggshield push range.** In ggshield 1.54.0 the previous-commit variable is
  `GITHUB_PUSH_BASE_SHA`, which must carry `github.event.before`; `GITHUB_PUSH_BEFORE_SHA`
  and `GITHUB_PULL_BASE_SHA` appear nowhere in its source, so setting them protects nothing.
  Without a usable previous commit it scans only `GITHUB_SHA~1`, one commit of a
  five-commit push, with exit 0. A branch-creating push (before is forty zeroes) and a manual
  dispatch run a separate full-repository scan in a separately named step, which is the
  correct range for a freshly scaffolded project's first push.
  `GITHUB_DEFAULT_BRANCH` is deliberately left unset, so do not re-add it as protection:
  with a real previous commit its fallback is unreachable, and on a branch-creating push
  its fallback is a bare ref (`main..<sha>`, no `origin/` prefix, because the remote prefix
  is applied only on the pull_request path). A detached checkout has no local `main`, so
  that resolves to nothing and lands back on `GITHUB_SHA~1`. Prefixing it with `origin/`
  does not help either: on the push that creates the branch `origin/main` already equals
  `HEAD`, so the range is empty. The pull_request path needs no variable, because ggshield
  reads `GITHUB_BASE_REF`, which Actions already sets.
- **Scaffold matrix.** `dry-run-smoke` and `scaffold-lint-test` are CI-only (#384): a
  `skeleton.meta` change would trigger one hook, never all six skeletons. `envsubst` is
  installed only when missing, because the unguarded `apt-get` hung two jobs for 6 hours
  (#192). `MULTI_PIPELINE_OPTIN=true` forces the MVC multi-intent prompt to yes. The
  storage opt-in job answers that prompt through the named-key spec on every tier that
  offers it (api-service-native-db uses the DDD key map, #668), because the plain scaffold
  never linted files that ship only on an opt-in (#650).
- **Codespell sync.** The vocabulary this repository learns must reach the copy that ships
  into every scaffold; the two lists drifted in both directions and the stale side was the
  template.
- **Pairing gate.** `Makefile` and `tasks.sh` exist only at this repository's root, so the
  script lives at `bin/`, not in a template.
- **pymarkdownlnt is pinned.** `.pymarkdown.json` enumerates rules one by one, so a rule a new
  release adds is enabled by default: 0.9.40 added MD049, MD050 and MD051 and turned 9 open
  PRs red (2026-09-18). Bump it deliberately and re-measure the rule set (#383).
- **Validate-meta tests (#407).** The gate blocks merge and had no tests for a missing key, an
  empty value or a dead `scaffold=` path.

### Dependabot (#471, #484)

- Version updates for this repository are monthly, not weekly: the three ecosystems (docs
  venv, `ts-common`'s toolchain, Actions runners) ship no runtime product code, grouping
  already caps noise at one PR per ecosystem per interval, and security updates run
  independently on their own toggle.
- `increase-if-necessary`, not `lockfile-only`: both manifests use caret ranges, so every
  major bump needs a manifest edit, and under `lockfile-only` no major PR would ever open.
- Groups are minor and patch only; a group without `update-types` would bundle majors with
  routine bumps. There is no `labels:` key, because `bin/pr_gate.py` already labels by path
  and Dependabot comments an error on every PR when a declared label does not exist.
- The `eslint`, `@eslint/js` and `typescript` majors are held because their peers
  (typescript-eslint peers on `typescript` below 6.1.0; the react, import and jsx-a11y plugins
  cap `eslint` at 9) exclude them; lift per #720. First match wins, so `@eslint/js` moves in
  lockstep with `eslint`.
- `@types/node` majors are held in both TypeScript tiers (#824, closing #798). The types must
  match the lowest Node a template supports, because newer types let code compile against APIs
  a Node 22 user lacks: the build passes and the program fails at run time. Both tiers pin
  `^22`, the `engines.node` floor line. Lift the `ignore` and raise the pin in the same PR when
  an `engines` floor moves to a newer major.
- Pinning actions by SHA (#369) does not self-update; the Actions ecosystem entry does.

## Generated-project workflows (`templates/python-common/.github`)

The workflows and `dependabot.yml` a Python scaffold ships carry no prose. Where a file is the
twin of a root workflow, the reasoning above applies unchanged (`review_threads.yaml`,
`coderabbit_trigger.yaml`, `review_retry.yaml`, `pr-reconcile.yaml`, `secret_scan.yaml`).
This section records what is specific to the generated copies.

### `tests.yaml`

- **No `outputs:` on `workflow_call`.** It once declared `ready_for_release` as
  `${{ jobs.test.result == 'success' }}`. Only `jobs.<id>.outputs.<name>` is in scope there,
  so the output was an empty string on every run while looking like a release gate. It had no
  consumers; a caller reads the verdict from `needs.<job>.result`.
- **The job name carries every matrix axis.** With only `os` in it, the 3x5 matrix produced 15
  check runs sharing 3 names. A required check is resolved by name, so a green and a red leg
  of one name are indistinguishable to the merge gate.
- **`fetch-depth: 0`.** The work-ledger gate resolves `merge-base(HEAD, default)`, which a
  shallow clone cannot find; the gate-integrity gate diffs against `main` for the same reason.
- **The lockfile check is an unconditional step before the pyproject rewrite.** Nested under
  the install's `if: cache-hit != 'true'` it never ran on a warm cache, which is exactly the
  condition that makes it cheap. A stale `poetry.lock` fails loud: regenerating would
  re-resolve every dependency to the newest in-range version, a non-reproducible build. A
  version bump does not invalidate the lock, so `poe bump_version` never trips it.
- **The cache holds `.venv` only, keyed on `poetry.lock` and `pyproject.toml`.** Caching the
  tracked lockfile lets a restored cache overwrite the committed one. Hashing `pyproject.toml`
  alone makes the lock-only diff Dependabot's `lockfile-only` produces a cache hit, so every
  bump PR would skip the install and test the pre-bump set.
- **Every gate is an explicit step as well as a pre-commit hook.** CI does not run
  pre-commit, so a gate listed only there is bypassed by a contributor who skips hooks;
  `check-sql-guards` shipped one-legged that way and a `WHERE`-less `DELETE` reached `main`
  (#355). Per-gate points:
    - `lint-deps` runs inside the Poetry venv and cannot become `pipx run deptry`: deptry maps a
      module to its distribution through the environment it runs in, and outside it the verdict
      inverts rather than degrades.
    - `check-comment-language` runs in audit mode (no filenames), sweeping every commented file
      type, because a partial sweep leaves a precedent the next author copies.
    - `function-length`, `fixture-scope`, `check-complexity` and `identifier-masking` fail when
      discovery matches zero files. `check-complexity` hard-fails when ruff cannot be resolved.
    - `gate-integrity` is diff-scoped (#309): a PR may not weaken a hook, rule, exclude or check
      without a `gate-change-ok: <reason>` marker.
    - `coverage-floor` exits 0 with a message on a tier with no `src/capabilities/` (MVC) and
      `migration-graph` self-skips on a tier with no `migrations/versions/`.
    - `fixture-scope` is a proxy, not a detector (#442); see the gate's module docstring.
    - The others pin one invariant each: `check-typing` (every `src/` class or function carries
      the runtime checker, Pydantic models excepted), `check-provenance` (a module that calls
      `read_table` also calls `stamp_provenance`), `check-all-exports` (a declared `__all__`
      names every public member, which an introspective test that discovers the family through
      `__all__` cannot catch), `check-dtypes` (no ingested column typed as a binary float, which
      stores 1984223115.42 as 1984223115.4200000762939453125), `check-layer-imports` (a
      third-party dependency is reached through a `utils/` seam, in any scope),
      `check-orm-model-guards` (#361: bitwise operators in `.where()`, two `create_all`, and a
      duplicate constraint `name=` across a mixin MRO, each a silent wrong answer at
      declaration time), `specs-structure` (a tree with no `.specs/` passes, a malformed one
      fails by name), `check-docs-sections`, `check-docs-code-refs` (#159) and
      `check-backlog-ledger`.
- **Pinning pins what is asked for, never what arrives.** `gitleaks` and `actionlint` are
  unpacked and executed on the runner, so each download is SHA-256 verified before
  extraction. `LINT_ACTIONS_REQUIRED=1` turns actionlint's graceful skip into a failure: the
  skip is right on a contributor's machine and a placebo in CI.
- **`ruff format` is a CI step** so unformatted code fails, not only lint findings. mypy runs
  from `src/`, the single package base, to avoid the "found twice" error on the deeper DDD
  tree. shellcheck and shfmt are installed so the shell gate runs instead of skipping.
- **`|| [ $? -eq 5 ]` on the integration run.** Pytest exit 5 means no tests collected, which
  a fresh project's empty suite must not turn into a red CI; exit 1 still fails.
- **The coverage floor runs on every PR.** The badge step runs only on main and tags, so
  without the floor step a PR could drop coverage uncaught. The badge uses `--local` because
  the default form fetches from img.shields.io, and no CI or release path may depend on a
  non-essential external host.

### Other generated workflows

- **`pr-gate.yaml`.** It triggers on `pull_request` only, never `workflow_run`, which fires
  only from the default branch's copy and so cannot run on the PR that introduces the gate.
  The gate polls the checks in-run instead. `labeled` and `unlabeled` are included so
  `do-not-merge` takes effect at once. A pull_request-driven gate never re-evaluates an
  already-open PR after a policy change; run the `workflow_dispatch` with `backfill: true`
  (or `@dependabot rebase`) to re-decide every open PR. A new push cancels the previous
  polling run so two gates do not race on one sticky comment. Event data reaches the script
  through `env:` only.
- **`release.yaml`.** A service is deployed, not published, so there is no PyPI step. The
  version input is free text and is validated before `git tag`, the irreversible half. The
  versioned-docs job runs only after the tag is cut, so the site never advertises a version
  that failed to ship. `mike` deploys `X.Y` under the `latest` alias; a prerelease suffix
  is skipped in-step so it never moves `latest`. The dropdown granularity is `X.Y`, so 1.4.2
  and 1.4.7 share an entry. `CHANGELOG.md` is regenerated by `cz` for that build and not
  committed back to protected `main`. GitHub Pages must serve from `gh-pages`
  (`poe enable_pages`).
- **`contract_drift.yaml`.** A weekly, non-gating reporter on `schedule` and manual dispatch,
  never `pull_request` or `push`, so it cannot gate a PR or a release. It opens or updates
  one deduplicated issue and never fails the run; it is inert until a source is added to
  `src/config/contract_oracles.yaml`. Dedupe is on the `contract-drift` label and a hidden
  body marker, since the label alone can be removed by hand and a job that files an issue per
  run gets switched off. The report goes in as `--body-file` so source-derived text cannot
  inject into a shell command.
- **`review_threads.yaml`.** `actions: write` is for the stale-run cleanup only. Set
  `REVIEW_THREADS_REQUIRE_RESOLVED` to `0` for a reply-only contract; the shipped value is `1`.
  `bin/enable_repo_rules.sh` seeds `REQUIRED_CHECKS` with this job's `name:`.
- **`coderabbit_trigger.yaml`.** The scaffolder sets `GH_PAT_REVIEW_TRIGGER` when it is exported
  at scaffold time and prints the command otherwise. Scope the PAT to all repositories if you
  scaffold often, since a per-repository PAT is edited for every new project. It ships with
  the review-thread gate: without the gate this workflow is a nicety, without the workflow
  the gate blocks every PR.
- **`secret_scan.yaml`.** It is opt-in (#287): copied only when `GITGUARDIAN_API_KEY` is set at
  scaffold time, the same presence check that propagates the key to the new repo's secrets.
  It is not in `REQUIRED_CHECKS`, since a required check that never reports blocks every PR.
  An absent key fails loud, never skips: ggshield exits 3, distinct from a clean exit 0.
- **`review_retry.yaml`.** GitHub disables a scheduled workflow after 60 days of repository
  inactivity without announcing it. If rate-limited PRs stop being re-asked, check that the
  workflow is still enabled before looking for a bug in the script.
- **`pr-reconcile.yaml`.** Cards in a Projects "closed to Done" automation key on the issue
  closing, so a missed close leaves them in "In review" while the code has shipped, and the
  problem grows with auto-merge adoption. The workflow calls `bin/pr_reconcile.sh`, the one
  implementation shared with the root workflow. On the event path it reconciles that PR; on
  `schedule` and dispatch it sweeps a window.

### `dependabot.yml`

- **Ordinary version updates only.** Security updates are a repository toggle
  (`poe enable_security`), not config.
- **`versioning-strategy: lockfile-only`.** CI installs from the committed lock and refuses to
  re-lock, so it tests the frozen versions while consumers get whatever the loose `>=` ranges
  allow. This refreshes the lock but never rewrites pyproject ranges: narrowing a library's
  range on a consumer's behalf is not the project's call, and pyproject and lock stay in sync.
- **Solo-maintainer tuning.** Minor and patch are grouped into one PR; majors arrive alone and
  get scrutiny. Each PR (one grouped minor-and-patch update, or one major) is isolated, so a bad bump reddens that PR and never `main`. A
  linter bump (ruff, mypy) can ask for a reformat, which is the system working.
- **No `labels:` key**, because `bin/pr_gate.py` already labels by changed path and Dependabot
  comments an error on every PR it opens when a declared label does not exist. When a scaffold
  ships both a bot config and a labelling gate, only one may own labels.
- **Major-line pins** go for dependencies whose major is a support decision. pandas is tested on
  both 2.x and 3.x, so its major bump is a project decision. Add one per such dependency and
  remove it when the project stops straddling.
- **The Actions ecosystem entry** keeps CI off deprecated runtimes, for example a Node version
  GitHub is sunsetting.

## Opt-in modules (`templates/python-common/optional`) and the OTel pin comments

The opt-in modules that a scaffold copies on request carry no comments, and the six Python
scaffold scripts no longer append comment lines to a generated `pyproject.toml`.

- **The OTel dependency block.** Each scaffold appends the pinned `opentelemetry-*` requirements
  to the generated `pyproject.toml`. The two lines that once preceded the pins said the OTLP
  export is opt-in (#438), that the pins are exact because the Logs signal is "Development"
  status upstream, and (for `lib-minimal`) that the consumer's own host process sets
  `OTEL_EXPORTER_OTLP_ENDPOINT` since a library ships no `.env`. Those lines were text written
  into the generated file, not comments of the script, so removing them changes the generated
  `pyproject.toml` by those comment lines only; the reason lives here and in the generated
  project's observability page.
- **`otel_logging.py`.**
    - The typing-engine import is layout-agnostic: `utils.typing` in MVC, `chassis.typing` in
      DDD, always injected at different paths. mypy reads the single `TYPE_CHECKING` import (no
      redefinition) and at run time the `try`/`except` picks whichever layout shipped.
    - Cleartext guard: an `http://` endpoint is a credential leak only when there is a credential
      and only when it leaves the machine. Both halves matter: refusing every `http://` endpoint
      would break the seam's own quickstart (`docker-compose.otel-collector.yml` serves
      `http://localhost:4318`), and refusing none would ship an API key in the clear. An
      unparseable endpoint with credentials is refused. The error names the endpoint, because the
      fix is to change it, and never the header values, which are the credential.
    - Redirects (CWE-319): the guard above vets the configured endpoint, but `requests` follows a
      3xx by itself and re-sends the OTLP headers, the API key, to whatever host the hop names, over
      `http://` if it says so. `max_redirects = 0` makes requests raise `TooManyRedirects` on the
      first hop. `_session` is a vendor internal read through `getattr` and its absence is fatal on
      purpose: if a future release renames it, the right outcome is "no export", never "export with
      credentials unprotected". The raise is caught by the fire-and-forget handler in the caller.
    - Fire-and-forget, deliberately: a failure must never become an application outage, raising
      would turn an unreachable collector into a crashed scaffolded project, and the `FileHandler`
      already gives the message somewhere to land. This is the one place a silently swallowed
      error is the correct choice.
    - The SDK classes already read the standard `OTEL_*` variables (endpoint, headers, service
      name, resource attributes), so none is passed explicitly: reimplementing the lookup would be
      a second, driftable copy.
- **`test_otel_logging.py`.** Clear both the signal-specific and the generic endpoint variable: the
  signal-specific one overrides the generic one, so an inherited value would silently decide the
  test's endpoint and make it pass or fail on the developer's environment. The endpoint is
  actionable and belongs in the message; the credential never does.
- **`joblib_handler.py`.** A `record_id` is `<name>_<date>_<time>_<sha8>`; the split count and the
  expected length derive from that one number so they cannot drift. Every path the store opens is
  built from a `record_id` that arrives from the caller, so a full match on the documented shape
  is what makes it a single filename component (no separator, no `..`, no drive); the name
  charset is the one `create()` can produce. Both paths are confined before anything is unlinked:
  resolving the sidecar after the artifact is gone would leave the store half-deleted when the
  sidecar is refused. `test_joblib_handler.py` uses zlib, not the default lz4, which is not a
  declared dependency of any tier; the tests are about the id, not the codec.
- **`webhook/` and `email/` ports.** `@runtime_checkable` is required, not cosmetic: the runtime
  type-checking engine performs an `isinstance` against the port, and a plain `Protocol` raises
  `TypeError` on that check at import time, not call time. `webhook/factory.py` maps an
  incoming-webhook URL to its platform by substring signature; Teams webhooks are hosted under
  `*.webhook.office.com` and `teams.microsoft.com`. `slack_notifier.py` validates an `https`
  scheme in the constructor, so the S310 audit warning about arbitrary schemes does not apply.
  `webhooks.yaml`: the target URL comes from `WEBHOOK_URL` in `.env`; the platform
  (teams or slack) is inferred from that URL by `build_webhook`; the named fields (`app_name`, `environment`,
  `hostname`, `user`, `log_path`) are substituted in `src/config/startup.py`.
- **`browser_steps/step_handlers.py`.** The fields each kind needs, and their type, live in a
  second dict keyed by the same kind, which is the drift this module's dispatch design exists to
  avoid, so `test_step_handlers.py` asserts the two keysets are equal: a new handler with no
  entry fails the suite instead of silently skipping validation.
- **`typing/policy.py`, `typing/type_checker.py`.** The policy knobs (`VIOLATION_TYPE`,
  `STRICT_BOOL`, ...) are edited there, not in the adapter; `VIOLATION_TYPE = TypeError` is
  load-bearing, see the module docstring. With no numeric override, the hint override is skipped
  entirely so beartype uses its own int handling rather than a redundant self-mapping. The
  `complexity-ok` hatch in `type_checker.py` is intrinsic type-system metaprogramming, which ruff
  already excludes outright for the DDD and `lib-minimal` layouts and mypy carries
  `ignore_errors` sections for in all three, so exempting it from the complexity ceiling applies
  the existing policy to one more tool and is not a new concession.

## Review-thread gate tests (`templates/python-common/tests/unit/test_review_threads_gate.py`)

The test module carries no comments. The points below recur through it; each exists because a
simpler form was measured to be wrong. The shapes forced by the complexity-1 ceiling (module
data in place of branches, split rather than combined assertions) are the ones recorded for the
rest of the suite.

- **Split the loader and the spec.** A conjunction in one assertion reports only that the whole
  thing was false; an absent loader and an absent spec are different faults.
- **Two roster shapes are not interchangeable.** `_ROSTER` is the raw member list; the normalised
  mapping (login without `[bot]` to its `posts:` class, as `load_roster` returns it) is what the
  notice helpers take. The thread half of the gate takes every member, the missing-review half
  only those that can review. Passing the raw roster to a helper that expects the normalised one
  matches nothing and returns `""`: a green-looking empty answer, not an error.
- **A review is pinned to a commit** (#220). The fixtures use two distinct oids, the PR head and a
  commit it superseded, because the gate's question is "which commit was this review written
  against?"; measured on #219, where the only review was attributed to a commit pushed five
  minutes before the head. A completion notice is evidence only when it postdates the head
  commit's `committedDate`, otherwise it describes code the branch has since moved past (raised
  by review on #339).
- **The pagination case is the "expensive shared setup" one** from `tests/CLAUDE.md` (#544): one
  two-page fetch backs five independent claims, so it runs once in a module-scoped fixture. The
  two pages are data in a `side_effect` sequence, not a stub that branches on its cursor
  arguments (a branch put a decision in the test and the green never said which side ran), and
  `Mock` records the calls for free.
- **The bot-login spelling** is why the gate was silently vacuous: REST spells the login with a
  `[bot]` suffix, GraphQL without, and before the fix the GraphQL spelling counted as an answer.
  The human login is the load-bearing third case: it passes through untouched, so nobody is
  normalised into looking like a reviewer.
- **The `REVIEW_THREADS_REQUIRE_RESOLVED` flag has three claims, one test each** (#544): three
  different verdicts, not one assertion over three inputs; collapsing them hid the third. CI no
  longer passes `False` (#196): delegating the resolve half to `required_conversation_resolution`
  looked safe, but that setting drops an outdated thread (#193: merge enabled over an unresolved
  outdated thread with 29 of 29 checks green). The flag survives for callers that cannot
  re-evaluate a resolve, so the reply-only mode must keep working and must not quietly disable
  the job altogether.
- **A redundant re-review is not an unreviewed PR** (#259). The reviewer's boilerplate is copied
  verbatim from #264's own comment stream; it is appended to every outcome (performed,
  rate-limited and failed alike), which is what defeated the first draft of the check.
- **Real notice bodies, never retyped** (#364, #433). The chat-quota notice (PR #363,
  2026-08-30T18:44:28Z), the review-quota notice (PR #317, 2026-08-29T17:11:51Z) and the file-cap
  notice (PR #424, 2026-09-11) are fetched with `gh api graphql`; the issue the first closed was
  itself written against retyped text that classified differently from the real bytes. A second,
  unrelated "Review skipped" reason (measured on PR #400, a one-file bot-authored PR, clearable
  simply by asking, unlike the structural cap) shares the bare prefix with the file-cap notice,
  which is what makes it a genuine negative control. The bot suffix is stripped first, or the
  notice lookup silently finds nothing.
- **Classification by declared structure** (#630, `docs/faq.md`). Each shape is a trimmed copy of
  a real body from this repo's PRs (#347, #671 to #687), and the witness is the same text with
  only its structural marker removed. The real CodeRabbit body from #347 has its only finding in
  a body section, not an inline thread.
- **The display budget must not reach a matcher** (#372). `summarise_reviewer_notice` cuts a
  notice to 200 characters so a failure message stays readable. Two matchers used to read that
  cut string, so a phrase past the budget read as absent. Over 112 real reviewer notices, 4
  flipped UNKNOWN to OK (phrase at offsets 394, 583, 583 and 2700) and 4 lost a completion
  phrase; both directions are silent.
- **A review carries forward across a merge of the base** (#698). The patch-id output is
  `<patch-id> <commit-id>`, and unpacking fails loudly on empty output instead of an
  `IndexError`. The `merge` of `main` into the branch conflicts by design.
