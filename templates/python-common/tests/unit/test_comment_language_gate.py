"""Unit tests for the documentation-language gate (no network; discovery reads local `git`).

**The calibration is the thing under test.** The gate's first draft reported 19 findings of
which 18 were false, and a gate that cries wolf gets switched off — so each test below pins one
measured class of false positive **by name**. A "simplification" that drops a redaction rule
keeps the true positives passing and silently restores the noise, which is why the negative
half of this file is larger than the positive half.

Discovery (blueprintx#331) reads ``git ls-files`` rather than walking the filesystem, so the
audit-mode tests below run against the REAL checkout — this file's own repo — where `git` is
already available and every file under test is already tracked. The one test that fabricates a
throwaway tree (``test_skip_dirs_are_matched_relative_to_the_repo_not_the_filesystem``) `git
init`s and commits it for the same reason: an untracked ``tmp_path`` fixture is invisible to
``git ls-files`` by construction, which is the property the migration exists to rely on.
"""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"


def _load(str_name: str) -> ModuleType:
	"""Load a ``bin/`` script by path (``bin/`` is not a package).

	Parameters
	----------
	str_name : str
		Module stem under ``bin/``.

	Returns
	-------
	ModuleType
		The imported module.
	"""
	cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules[str_name] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load("check_comment_language")


# --------------------------
# True positives — the gate must actually fire
# --------------------------


def test_a_portuguese_sentence_is_flagged() -> None:
	"""The base case: prose genuinely written in the other language is caught."""
	assert gate.portuguese_words("Este bloco valida os dados que vem da API")


def test_one_function_word_is_enough_signal() -> None:
	"""Every listed word was checked against English, so a single hit is a verdict."""
	assert gate.portuguese_words("returns the value quando the flag is set") == ["quando"]


# --------------------------
# False positives — each one was MEASURED, each is pinned by name
# --------------------------


def test_accented_data_labels_do_not_trigger() -> None:
	"""Accent-hunting was the rejected design: it flags every legitimate data label.

	``Saídas`` and ``Ativos Líquidos`` are column names an English comment may name freely.
	Matching function words instead is what makes them pass.
	"""
	assert gate.portuguese_words("The report labels the column Saídas") == []
	assert gate.portuguese_words("Sums the Ativos Líquidos column") == []


def test_all_caps_acronyms_are_not_read_as_words() -> None:
	"""Microsoft ``COM`` read as the preposition "com" was **5 findings on its own**.

	Accented capitals are included in the rule, so ``NÃO`` is caught by the same pass.
	"""
	assert gate.portuguese_words("Uses the Microsoft COM bridge") == []
	assert gate.portuguese_words("The NAO and NÃO markers are unrelated") == []


def test_dotted_tokens_are_redacted() -> None:
	r"""Without this, ``\bcom\b`` matches inside every e-mail address and hostname."""
	assert gate.portuguese_words("Reads emails.yaml from bradesco.com.br") == []


def test_urls_are_redacted() -> None:
	"""A URL path segment is not prose, however Portuguese it looks."""
	assert gate.portuguese_words("See https://example.com/para/que/nao for details") == []


def test_backticked_and_quoted_spans_are_redacted() -> None:
	"""An English comment naming a Portuguese identifier or quoting text is correct."""
	assert gate.portuguese_words("Skips the `saidas_zeradas` block entirely") == []
	assert gate.portuguese_words('The subject line is "para todos os fundos"') == []


def test_double_backtick_spans_are_redacted_before_single() -> None:
	"""Order matters: a single-backtick regex run first eats the opening ``pair``.

	It would consume the two opening backticks and leave the words inside bare, so the
	double-backtick pattern must be tried first. This pins the ordering, not just the outcome.
	"""
	assert gate.portuguese_words("The ``para cada fundo`` directive is documented") == []


# --------------------------
# 🔴 Blocks, not lines — the subtlest class
# --------------------------


def test_a_quotation_spanning_lines_does_not_charge_the_comment() -> None:
	"""Reading comments line by line sees an opening quote and never its closing one.

	The quoted span then survives redaction and the quotation's language is charged to the
	English comment around it. Measured against a verbatim user decision quoted across two
	lines. Joining consecutive comment lines into one block is what fixes it.
	"""
	str_source = (
		'# The user decided: "nao vamos usar isso, para nada"\n'
		"# -- quoted verbatim, so the comment itself stays English.\n"
		"x = 1\n"
	)
	list_blocks = gate.marker_comments(str_source, "#")
	assert len(list_blocks) == 1, "consecutive comment lines must join into ONE block"
	assert gate.portuguese_words(list_blocks[0][1]) == []


def test_a_blank_line_separates_two_blocks() -> None:
	"""Joining must not run past a non-comment line, or unrelated comments merge."""
	str_source = "# first block\nx = 1\n# second block\n"
	assert len(gate.marker_comments(str_source, "#")) == 2


# --------------------------
# Geometry — a finding must name the right line
# --------------------------


def test_redaction_preserves_length_so_offsets_survive() -> None:
	"""Substituting one space instead of N shifts every later column and line.

	The finding would then name the line the block *starts* on rather than the line the
	offending word is really on, which is what a reader jumps to.
	"""
	str_text = 'a "quoted span here" b'
	assert len(gate.redact(str_text)) == len(str_text)


def test_the_reported_line_is_the_word_s_own_line(tmp_path: Path) -> None:
	"""A violation deep inside a long block reports its own line, not the block's first.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir holding the probe file.
	"""
	path_file = tmp_path / "probe.py"
	path_file.write_text(
		"# English line one\n# English line two\n# esta linha nao esta em ingles\nx = 1\n",
		encoding="utf-8",
	)
	list_problems = gate.file_problems(path_file)
	assert len(list_problems) == 1
	assert ":3:" in list_problems[0], "must name line 3, not the block start at line 1"


# --------------------------
# Escape hatch — per line, never per block
# --------------------------


def test_the_escape_marker_exempts_only_its_own_line() -> None:
	"""A block-scoped marker would exempt a whole 40-line header in one stroke."""
	str_text = f"esta linha foi isentada {gate.STR_ESCAPE}\noutra linha que nao foi isentada"
	list_hits = gate.portuguese_words(str_text)
	assert list_hits, "the unescaped neighbour must still be reported"


# --------------------------
# Python exactness
# --------------------------


def test_a_hash_inside_a_string_literal_is_not_a_comment() -> None:
	"""``tokenize`` is what makes Python exact — a naive line scan would flag this."""
	str_source = 'STR_X = "# esta nao e uma linha de comentario, e uma string"\n'
	assert gate.python_comments(str_source) == []


def test_docstrings_are_read() -> None:
	"""Docstrings are the other place prose lives in a module."""
	str_source = 'def f() -> None:\n\t"""Retorna nada, apenas para o teste."""\n'
	list_comments = gate.python_comments(str_source)
	assert list_comments
	assert gate.portuguese_words(list_comments[0][1])


def test_an_unparseable_file_yields_nothing_rather_than_crashing() -> None:
	"""A syntax error is ruff's finding to report, not this gate's — and must not crash it."""
	assert gate.python_comments("def (((\n") == []


# --------------------------
# Discovery — a gate that scans nothing must not report success
# --------------------------


def test_audit_mode_fails_when_no_file_matches(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Scanning zero files produces zero findings, which reads exactly like a clean pass.

	A renamed layout that stops matching the globs would leave this gate green forever, green
	precisely because it checks nothing. Named files (pre-commit's mode) stay exempt, since
	pre-commit legitimately passes an empty list when nothing matching is staged.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Used to make discovery return nothing.
	"""
	monkeypatch.setattr(gate, "audit_paths", list)
	assert gate.main([]) == 1


def test_the_gate_discovers_this_project_s_own_sources() -> None:
	"""The positive half: discovery must actually match this layout.

	Without this, the test above passes while the real invocation still scans nothing.
	"""
	assert len(gate.audit_paths()) > 0


def test_audit_covers_every_supported_extension_anywhere_in_the_tree() -> None:
	"""Deny-by-default: a supported file may not sit outside the audit just by living elsewhere.

	The original allow-list of globs (``src/**/*.py``, ``bin/**/*.sh``, …) left **57** supported
	files unaudited in this template — `.pre-commit-config.yaml`, the workflow files, `mypy.ini`,
	`docker-compose.*.yml`, and all of `optional/`. Worse, the pre-commit hook *does* check those
	when staged, so hook and CI disagreed and a comment could pass CI then fail a later commit.

	An allow-list also fails silently on every future addition: a new top-level directory is
	simply never scanned, and nothing reports it.

	⚠️ Deriving the expectation from ``TUPLE_SKIP_DIRS`` alone would be tautological — adding a
	directory to the skip list moves both sides of the comparison together and the test keeps
	passing. (Verified: that version survived a mutation adding ``optional`` to the skips.) So
	this first names concrete LOCATIONS that must be covered, which a skip-list change genuinely
	breaks, and only then asserts the general property.
	"""
	set_audited = {path_file.resolve() for path_file in gate.audit_paths()}

	# One representative, long-lived file per location the allow-list used to miss entirely.
	list_required = [
		gate.PATH_ROOT / ".pre-commit-config.yaml",  # repo-root config
		gate.PATH_ROOT / "mypy.ini",  # root .ini
		gate.PATH_ROOT / ".github/workflows/tests.yaml",  # workflow
		gate.PATH_ROOT / "optional/typing/validate.py",  # app code that ships into projects
	]
	list_missing = [
		path_file
		for path_file in list_required
		if path_file.is_file() and path_file.resolve() not in set_audited
	]
	assert list_missing == [], f"supported but unaudited: {list_missing}"

	# And the general property, so a NEW location cannot quietly fall outside either. Compared
	# against TRACKED files, not a raw filesystem walk — discovery now reads `git ls-files`
	# (blueprintx#331), so an untracked file in a developer's working tree is correctly out of
	# scope, not a false "missed" here.
	set_supported = set(gate.DICT_MARKERS) | {".py"}
	list_missed = [
		path_rel
		for path_rel in gate.tracked_files()
		if path_rel.suffix in set_supported
		and not any(str_part in gate.TUPLE_SKIP_DIRS for str_part in path_rel.parts)
		and (gate.PATH_ROOT / path_rel).resolve() not in set_audited
	]
	assert list_missed == [], f"supported but unaudited: {list_missed[:10]}"


def test_published_docs_are_never_audited() -> None:
	"""``docs/`` is the OTHER half of the boundary — written in the locale on purpose.

	Scanning it would invert the rule the gate exists to enforce, so the exclusion is load-bearing
	rather than a performance tweak.
	"""
	assert "docs" in gate.TUPLE_SKIP_DIRS
	assert not [
		path_file
		for path_file in gate.audit_paths()
		if "docs" in path_file.relative_to(gate.PATH_ROOT).parts
	]


def _git_init_and_commit(path_repo: Path) -> None:
	"""Turn a throwaway directory into a minimal git repo with everything in it tracked.

	Parameters
	----------
	path_repo : pathlib.Path
		The directory to initialise and commit.
	"""
	# Inherit the environment; a bare dict drops PATH. See the backlog note for the measurement.
	dict_env = {
		**os.environ,
		"GIT_AUTHOR_NAME": "test",
		"GIT_AUTHOR_EMAIL": "test@example.com",
		"GIT_COMMITTER_NAME": "test",
		"GIT_COMMITTER_EMAIL": "test@example.com",
	}
	# Three calls in a row rather than a loop over the argv list — a loop costs complexity
	# points and tests/ is capped at 1. Constant, trusted argv; no shell involved.
	subprocess.run(["git", "init", "-q"], cwd=path_repo, env=dict_env, check=True)  # noqa: S603, S607
	subprocess.run(["git", "add", "-A"], cwd=path_repo, env=dict_env, check=True)  # noqa: S603, S607
	subprocess.run(  # noqa: S603
		["git", "commit", "-q", "-m", "fixture"],  # noqa: S607
		cwd=path_repo,
		env=dict_env,
		check=True,
	)


def test_skip_dirs_are_matched_relative_to_the_repo_not_the_filesystem(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A checkout living under a directory named ``docs`` must still be audited.

	``path_file.parts`` carries every ancestor above the repository, so matching the skip list
	against it makes the verdict depend on **where someone cloned**: a tree at ``~/docs/proj``
	or a CI workspace under ``fixtures/`` would match on every file, the audit would find
	nothing, and the gate would fail with the vacuous-audit error on a perfectly fine tree.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir; the fake repo is created under a ``docs`` ancestor.
	monkeypatch : pytest.MonkeyPatch
		Used to point the gate's ``PATH_ROOT`` at that fake repo.
	"""
	path_repo = tmp_path / "docs" / "proj"
	(path_repo / "src").mkdir(parents=True)
	(path_repo / "src" / "ok.py").write_text("# English comment\n", encoding="utf-8")
	# The repo's OWN docs/ must still be skipped — the exclusion is real, just repo-relative.
	(path_repo / "docs").mkdir()
	(path_repo / "docs" / "guia.py").write_text(
		"# esta linha nao esta escrita em ingles\n", encoding="utf-8"
	)
	# Discovery reads `git ls-files` (blueprintx#331) — an untracked fixture tree is invisible
	# to it by construction, so the fixture must actually be a committed repo.
	_git_init_and_commit(path_repo)

	monkeypatch.setattr(gate, "PATH_ROOT", path_repo)
	list_paths = gate.audit_paths()

	assert [p.name for p in list_paths] == ["ok.py"], (
		"the ancestor named 'docs' must not disqualify the tree, "
		"while the repo's own docs/ stays excluded"
	)


def test_untracked_files_are_invisible_but_tracked_ones_are_not(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""The blueprintx#331 property: discovery needs no skip-list entry for a stray worktree.

	`git ls-files` only ever returns TRACKED files, so a directory the audit was never told
	about — `.claude/worktrees/<agent>/`, a second checkout, any copy of the tree that was
	never `git add`-ed — cannot inflate the count, with nothing to remember. Both halves are
	asserted: the untracked file stays invisible, and a genuinely tracked file is still found.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir; holds the fake repo.
	monkeypatch : pytest.MonkeyPatch
		Used to point the gate's ``PATH_ROOT`` at that fake repo.
	"""
	path_repo = tmp_path / "proj"
	(path_repo / "src").mkdir(parents=True)
	(path_repo / "src" / "ok.py").write_text("# English comment\n", encoding="utf-8")
	_git_init_and_commit(path_repo)

	# An orphan worktree stand-in — present on disk, never staged, never committed.
	path_worktree = path_repo / ".claude" / "worktrees" / "orphan" / "src"
	path_worktree.mkdir(parents=True)
	(path_worktree / "bloat.py").write_text("# English comment too\n", encoding="utf-8")

	monkeypatch.setattr(gate, "PATH_ROOT", path_repo)
	list_names = sorted(p.name for p in gate.audit_paths())

	assert list_names == ["ok.py"], (
		f"untracked worktree content leaked into discovery: {list_names}"
	)
