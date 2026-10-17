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
