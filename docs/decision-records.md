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
