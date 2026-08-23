"""Integration tests for the project's shared ``bin/`` shell seams.

Bash scripts have no conventional unit test, so this project maps the
tests-with-every-change rule onto shell like this:

- **Unit gate** = ``shellcheck --severity=warning --exclude=SC1091`` + ``bash -n``
  (run by ``bin/lint_shell.sh`` and the ``lint-shell`` pre-commit hook).
- **Integration** = invoke the script via ``subprocess`` and assert on observable
  behaviour (exit code, a created file/dir, a status line) — this module.

See ``tests/CLAUDE.md`` (Testing shell scripts) for the convention. Two seams are
covered: ``bin/poetry_exec.sh`` (the Poetry resolver wrapper every recipe routes
through) and ``bin/precommit.sh`` (hook install that must skip gracefully off a git
work tree instead of aborting ``init``).
"""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


# --------------------------
# Module Utilities
# --------------------------


# Environment probes resolved ONCE at import time, so the tests that depend on them use
# `skipif` decorators instead of a guard clause in the body. A runtime `if … pytest.skip(…)`
# reads as a path THROUGH the test — to a reader and to mccabe alike — when it is really a
# statement about the machine. tests/ is capped at complexity 1 by bin/check_complexity.sh.
_STR_GIT = shutil.which("git")
_STR_BASH = shutil.which("bash") or "bash"


def _skip_unless(bool_available: bool, str_reason: str) -> None:
	"""Skip the calling test when a capability discovered AT RUNTIME is missing.

	Only for conditions that cannot be known at import time (what a subprocess actually did).
	Anything knowable up front belongs in a ``skipif`` decorator instead.

	Parameters
	----------
	bool_available : bool
		Whether the capability is present.
	str_reason : str
		Message shown for the skip.

	Returns
	-------
	None
	"""
	# Short-circuit evaluation makes this an expression rather than a branch. Behaviour is
	# the same, and the helper stays inside the very ceiling it exists to serve.
	bool_available or pytest.skip(str_reason)


def _materialise_bin_lib(path_bin: Path) -> None:
	"""Copy the repo's ``bin/lib`` into a throwaway tree so a sourced lib can run there.

	⚠️ Copies the WHOLE directory rather than globbing chosen extensions. The lib directory
	holds shell libs plus the Python helpers they invoke — code that used to be inline
	heredocs — and the earlier glob-for-shell-only form built a lib directory that cannot
	exist in a real project, so the test failed on a missing file instead of on the behaviour
	it asserts. copytree cannot miss the next extension somebody adds.

	Parameters
	----------
	path_bin : pathlib.Path
		The throwaway ``bin`` directory; ``lib`` is created inside it.

	Returns
	-------
	None
	"""
	path_source = Path(__file__).resolve().parents[2] / "bin" / "lib"
	shutil.copytree(path_source, path_bin / "lib", dirs_exist_ok=True)


def _bin_script(str_name: str) -> Path:
	"""Return the absolute path to a script under the repository's ``bin/``.

	Parameters
	----------
	str_name : str
		The script filename, e.g. ``poetry_exec.sh``.

	Returns
	-------
	pathlib.Path
		Absolute path to ``bin/<str_name>`` at the repository root.
	"""
	return Path(__file__).resolve().parents[2] / "bin" / str_name


# --------------------------
# print_status — an unknown status must not look like ordinary output
# --------------------------


def _print_status(str_status: str) -> subprocess.CompletedProcess:
	"""Source ``bin/lib/common.sh`` and call ``print_status`` with one status.

	Parameters
	----------
	str_status : str
		The status word to pass, valid or not.

	Returns
	-------
	subprocess.CompletedProcess
		The completed ``bash -c`` run, with stdout and stderr captured separately.
	"""
	path_lib = Path(__file__).resolve().parents[2] / "bin" / "lib" / "common.sh"
	str_bash = shutil.which("bash") or "bash"
	return subprocess.run(  # noqa: S603
		[str_bash, "-c", f'source "{path_lib}"; print_status {str_status} "probe message"'],
		capture_output=True,
		text=True,
		check=False,
	)


def test_a_known_status_prints_its_marker_on_stdout() -> None:
	"""A valid status keeps its coloured marker and stays on stdout."""
	cls_result = _print_status("warning")

	assert "probe message" in cls_result.stdout
	assert "[!]" in cls_result.stdout


def test_an_unknown_status_is_named_on_stderr_not_printed_as_plain_output() -> None:
	"""A typo'd status must be visibly wrong, not silently downgraded.

	The fallback branch used to print an UNMARKED ``[ ] message`` on stdout, so a
	misspelled ``warn`` rendered exactly like neutral chatter — 35 such calls existed
	across the scaffolds, every one a warning nobody could pick out of the log. The
	branch now routes to stderr and names the offending status.
	"""
	cls_result = _print_status("warn")

	assert cls_result.stdout == ""
	assert "unknown status 'warn'" in cls_result.stderr
	assert "probe message" in cls_result.stderr


def _run(
	str_script: str,
	*args: str,
	cwd: Path | None = None,
	dict_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
	"""Run a ``bin/`` script via bash and capture stdout/stderr separately.

	Parameters
	----------
	str_script : str
		The script filename under ``bin/``.
	args : str
		Arguments forwarded to the script.
	cwd : pathlib.Path or None, optional
		Working directory to run from; defaults to the current directory.
	dict_env : dict of {str: str} or None, optional
		Extra environment variables layered on top of the current environment; ``None``
		inherits the environment unchanged.

	Returns
	-------
	subprocess.CompletedProcess[str]
		The finished process with decoded ``stdout`` and ``stderr``.
	"""
	str_bash = shutil.which("bash") or "bash"
	dict_full_env = {**os.environ, **dict_env} if dict_env else None
	# The argument vector is constant and trusted -- a resolved bash plus the repo's own
	# script -- with no untrusted input interpolated, so the bandit subprocess warning is
	# a false positive here.
	return subprocess.run(  # noqa: S603
		[str_bash, str(_bin_script(str_script)), *args],
		capture_output=True,
		text=True,
		check=False,
		cwd=str(cwd) if cwd is not None else None,
		env=dict_full_env,
	)


# --------------------------
# bin/poetry_exec.sh
# --------------------------


def test_poetry_exec_no_args_exits_with_usage_error() -> None:
	"""No arguments yields exit code 2 and a usage message routed to stderr."""
	cls_result = _run("poetry_exec.sh")

	assert cls_result.returncode == 2
	assert "Usage" in cls_result.stderr
	assert cls_result.stdout == ""


def test_poetry_exec_version_keeps_stdout_clean() -> None:
	"""``version -s`` returns only the version on stdout; chatter goes to stderr."""
	cls_result = _run("poetry_exec.sh", "version", "-s")
	_skip_unless(
		cls_result.returncode == 0,
		"Poetry could not be resolved -- offline/CI integration guard only",
	)

	# stdout is exactly the project version -- no resolution chatter leaked in.
	str_version = cls_result.stdout.strip()
	assert str_version != ""
	assert "\n" not in str_version
	assert "Detected OS" not in cls_result.stdout

	# The resolution status the wrapper emits lands on stderr, not stdout.
	assert "Detected OS" in cls_result.stderr


# --------------------------
# bin/precommit.sh
# --------------------------


def test_precommit_skips_gracefully_off_git_tree(tmp_path: Path) -> None:
	"""Run outside a git work tree, the script skips without aborting or creating a repo.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest-provided throwaway directory used as a non-git work tree.
	"""
	cls_result = _run("precommit.sh", cwd=tmp_path)

	# Skip-gracefully default -- init must still complete, so exit 0.
	assert cls_result.returncode == 0
	# No repository is fabricated; the template default never runs git init.
	assert not (tmp_path / ".git").exists()
	# The skip is announced, so a missing repo is visible, not silent.
	str_output = cls_result.stdout + cls_result.stderr
	assert "skipping pre-commit hooks" in str_output


@pytest.mark.skipif(_STR_GIT is None, reason="git not available -- integration guard only")
def test_precommit_registers_safe_directory_for_shared_worktree(tmp_path: Path) -> None:
	"""A dubious-ownership work tree self-heals: the script registers a git safe.directory.

	Simulates a shared / network checkout owned by another user via
	``GIT_TEST_ASSUME_DIFFERENT_OWNER=1`` plus a throwaway global git config, then asserts the
	script registered the tree (git's own suggested path) instead of mis-detecting it as "no
	repo". The final hook-install step may fail offline (no Poetry), but the safe.directory
	write happens first in ``ensure_git_repo``, so the assertion holds regardless of exit code.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir; a real git work tree is initialised inside it.
	"""
	path_repo = tmp_path / "repo"
	path_repo.mkdir()
	path_home = tmp_path / "home"
	path_home.mkdir()
	path_global_cfg = path_home / ".gitconfig"
	# A real work tree; the throwaway HOME/config isolates the global safe.directory write.
	subprocess.run(  # noqa: S603
		[str(_STR_GIT), "init", "-q", str(path_repo)], check=True
	)

	dict_env = {
		"GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
		"GIT_CONFIG_GLOBAL": str(path_global_cfg),
		"HOME": str(path_home),
	}
	cls_result = _run("precommit.sh", cwd=path_repo, dict_env=dict_env)
	str_output = cls_result.stdout + cls_result.stderr
	_skip_unless(
		"dubious ownership" in str_output or path_global_cfg.exists(),
		"git build does not honour GIT_TEST_ASSUME_DIFFERENT_OWNER -- guard only",
	)

	# The throwaway global config now holds git's own suggested path, which proves the tree
	# resolved and init could keep going instead of the probe misreading it as absent.
	str_cfg = path_global_cfg.read_text(encoding="utf-8") if path_global_cfg.exists() else ""
	assert "safe" in str_cfg
	assert str(path_repo) in str_cfg or "%(prefix)" in str_cfg
	# The self-heal never fabricates a repo and never emits the "no git repo" skip.
	assert "No git repository here" not in str_output


# --------------------------
# pip_fallback.sh — DB driver pruning
# --------------------------


def _run_prune(tmp_path: Path, str_backend: str) -> list[str]:
	"""Source ``pip_fallback.sh`` and prune a requirements file for one ``DB_BACKEND``.

	Parameters
	----------
	tmp_path : pathlib.Path
		Temporary directory standing in for the project root (holds ``.env``).
	str_backend : str
		The ``DB_BACKEND`` value to write into ``.env``.

	Returns
	-------
	list of str
		The requirement lines that survived pruning.
	"""
	path_lib = Path(__file__).resolve().parents[2] / "bin" / "lib"
	path_req = tmp_path / "req.txt"
	(tmp_path / ".env").write_text(f"DB_BACKEND={str_backend}\n", encoding="utf-8")
	path_req.write_text(
		"beartype>=0.22\npandas>=2.0\npyodbc>=5.0\noracledb>=2.0\n"
		"psycopg>=3.1\nmysql-connector-python>=8.3,<9.0\n",
		encoding="utf-8",
	)
	str_bash = _STR_BASH
	str_script = (
		f'export PROJECT_ROOT="{tmp_path}"; '
		f'source "{path_lib}/common.sh"; source "{path_lib}/bootstrap.sh"; '
		f'source "{path_lib}/pip_fallback.sh"; '
		f'pip_fallback_prune_unused_db_drivers "{path_req}"'
	)
	# Constant, trusted argv built from repo-internal paths — no user input reaches it.
	subprocess.run([str_bash, "-c", str_script], check=True, capture_output=True)  # noqa: S603
	return [line for line in path_req.read_text(encoding="utf-8").splitlines() if line]


def test_prune_drops_every_db_driver_for_sqlite(tmp_path: Path) -> None:
	"""A SQLite project asks the index for no DB driver at all.

	This is the regression that motivated the change: the tiers declare all four drivers
	unconditionally, so a SQLite project fetched ``mysql-connector-python`` — and a corporate
	index that 403s that one package killed the whole install over a package the project can
	never import.
	"""
	list_kept = _run_prune(tmp_path, "sqlite")
	assert list_kept == ["beartype>=0.22", "pandas>=2.0"]


@pytest.mark.parametrize(
	("str_backend", "str_driver"),
	[
		("postgresql", "psycopg"),
		("mysql", "mysql-connector-python"),
		("mariadb", "mysql-connector-python"),
		("mssql", "pyodbc"),
		("oracle", "oracledb"),
		# config/connection_db.py lowercases DB_BACKEND before dispatching, so these spellings
		# are valid app configuration. The pruner must agree, or it drops the one driver the
		# project is configured to use — the exact failure the pruning exists to prevent.
		("PostgreSQL", "psycopg"),
		("ORACLE", "oracledb"),
	],
)
def test_prune_keeps_only_the_configured_backends_driver(
	tmp_path: Path, str_backend: str, str_driver: str
) -> None:
	"""Each backend keeps its own driver and drops the other three.

	The negative half matters as much as the positive one: pruning that dropped the driver the
	project actually needs would break the install it exists to protect.
	"""
	list_kept = _run_prune(tmp_path, str_backend)
	set_known_drivers = {"pyodbc", "oracledb", "psycopg", "mysql-connector-python"}
	list_drivers = [
		line for line in list_kept if line.split(">")[0].split("<")[0] in set_known_drivers
	]
	assert len(list_drivers) == 1
	assert list_drivers[0].startswith(str_driver)


# --------------------------
# bin/check_*.py — Windows cp1252 stdout
# --------------------------

_GLYPH_GATES = (
	"check_backlog_ledger.py",
	"check_contract_drift.py",
	"check_docs_sections.py",
	"check_docstrings.py",
	"check_dtypes.py",
	"check_provenance.py",
	"check_typing.py",
	"pr_gate.py",
)


def test_gate_reports_a_finding_under_cp1252_stdout(tmp_path: Path) -> None:
	"""A gate must survive a cp1252 stdout while PRINTING its non-ASCII status glyph.

	Windows defaults stdout to cp1252, which cannot encode ``❌``, so the script died with
	UnicodeEncodeError before reporting anything — and because these back an ``always_run``
	pre-commit hook, that crash blocked every commit from a Windows checkout instead of
	failing the file under check.

	The violation is deliberate: a gate run over clean sources prints no glyph and would pass
	this test with the fix removed. ``PYTHONIOENCODING`` turns an OS-specific defect into an
	ordinary local test.
	"""
	path_src = tmp_path / "src"
	path_src.mkdir()
	# A banned binary float dtype — the finding that makes check_dtypes print its glyph.
	(path_src / "loader.py").write_text('dict_dtypes = {"amount": "float64"}\n', encoding="utf-8")
	dict_env = dict(os.environ)
	dict_env["PYTHONIOENCODING"] = "cp1252"
	str_python = shutil.which("python3") or shutil.which("python") or "python3"
	# Constant, trusted argv built from repo-internal paths — no user input reaches it.
	cls_run = subprocess.run(  # noqa: S603
		[str_python, str(_bin_script("check_dtypes.py"))],
		cwd=tmp_path,
		env=dict_env,
		capture_output=True,
		encoding="utf-8",
		errors="replace",
		check=False,
	)
	str_output = (cls_run.stdout or "") + (cls_run.stderr or "")
	assert "UnicodeEncodeError" not in str_output
	assert cls_run.returncode == 1, "the gate must still report the violation, not crash"


@pytest.mark.parametrize("str_script", _GLYPH_GATES)
def test_every_glyph_printing_gate_reconfigures_its_streams(str_script: str) -> None:
	"""Structural sweep: the whole family carries the fix, not just the one that was caught.

	A shared-shape defect is never in one file, and only one of these is cheap to execute
	end-to-end (the others reach the network or the GitHub API), so the family is held to the
	convention structurally while the mechanism above is proven for real once.
	"""
	str_source = _bin_script(str_script).read_text(encoding="utf-8")
	str_main = str_source.split('if __name__ == "__main__":')[-1]
	assert 'reconfigure(encoding="utf-8"' in str_main, (
		f"{str_script} prints status glyphs but never reconfigures stdout/stderr"
	)


# --------------------------
# bootstrap.sh — corporate CA must UNION, never replace
# --------------------------


_CA_ENV_VARS = ("PIP_CERT", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE")


def _fake_pem(str_marker: str) -> str:
	"""Build a syntactically valid PEM block whose body identifies it.

	Parameters
	----------
	str_marker : str
		A base64-safe token embedded in the certificate body so the test can find it.

	Returns
	-------
	str
		One ``BEGIN/END CERTIFICATE`` block.
	"""
	return f"-----BEGIN CERTIFICATE-----\n{str_marker}\n-----END CERTIFICATE-----\n"


def test_corporate_ca_bundle_is_a_union_not_a_replacement(tmp_path: Path) -> None:
	"""The generated bundle must ADD the corporate CA to the existing trust, never replace it.

	Pointing SSL_CERT_FILE/REQUESTS_CA_BUNDLE/PIP_CERT at the corporate CA alone narrows the
	trust store to one certificate, so every TLS connection not through the proxy breaks —
	measured, Poetry went from "0 candidates" to "All attempts to connect to pypi.org failed"
	BECAUSE the helper ran.

	The certificate COUNT is the assertion that distinguishes a union from a replacement: both
	implementations write a file containing the corporate CA, and only the union keeps the
	rest.
	"""
	path_bin = tmp_path / "bin"
	_materialise_bin_lib(path_bin)

	path_corporate = path_bin / "corporate_ca.pem"
	path_corporate.write_text(_fake_pem("Q09SUE9SQVRFQ0E="), encoding="utf-8")
	path_host = tmp_path / "host_bundle.pem"
	path_host.write_text(_fake_pem("SE9TVEJVTkRMRQ=="), encoding="utf-8")

	dict_env = dict(os.environ)
	dict_env["PIP_CERT"] = str(path_host)
	str_bash = shutil.which("bash") or "bash"
	str_script = (
		f'source "{path_bin}/lib/common.sh"; source "{path_bin}/lib/bootstrap.sh"; '
		f'BIN_DIR="{path_bin}"; PYTHON="$(command -v python3 || command -v python)"; '
		f'build_union_ca_bundle "{path_corporate}"'
	)
	# Constant, trusted argv built from repo-internal paths — no user input reaches it.
	cls_run = subprocess.run(  # noqa: S603
		[str_bash, "-c", str_script],
		env=dict_env,
		capture_output=True,
		encoding="utf-8",
		errors="replace",
		check=False,
	)
	assert cls_run.returncode == 0, cls_run.stderr

	str_bundle = (path_bin / "ca_bundle.pem").read_text(encoding="utf-8")
	assert "Q09SUE9SQVRFQ0E=" in str_bundle, "the corporate CA must be in the bundle"
	assert "SE9TVEJVTkRMRQ==" in str_bundle, "the host's existing bundle must survive"
	# A replacement writes exactly one block; only a union carries the roots as well.
	assert str_bundle.count("BEGIN CERTIFICATE") > 2


def test_bundle_construction_refuses_when_only_the_corporate_ca_is_available(
	tmp_path: Path,
) -> None:
	"""With no certifi and no host bundle, writing the file would narrow the trust store.

	A union of exactly one source is a replacement wearing the word "union" — the same defect
	this function exists to remove, reached from the other direction. It must fail loudly so
	the caller leaves TLS settings untouched, rather than write a one-certificate bundle that
	breaks every connection not through the proxy.
	"""
	path_bin = tmp_path / "bin"
	_materialise_bin_lib(path_bin)
	path_corporate = path_bin / "corporate_ca.pem"
	path_corporate.write_text(_fake_pem("Q09SUE9SQVRFQ0E="), encoding="utf-8")

	dict_env = {k: v for k, v in os.environ.items() if k not in _CA_ENV_VARS}
	# Stand in for a host where certifi was never installed by hiding it from the child.
	path_sitecustomize = tmp_path / "sitecustomize.py"
	path_sitecustomize.write_text(
		# Written against the modern finder protocol. The older two-method form was dropped
		# in Python 3.12, where a finder shaped that way is skipped without any warning.
		"import sys\n"
		"from importlib.abc import MetaPathFinder\n"
		"class _Block(MetaPathFinder):\n"
		"    def find_spec(self, fullname, path=None, target=None):\n"
		"        if fullname == 'certifi':\n"
		"            raise ModuleNotFoundError(fullname)\n"
		"        return None\n"
		"sys.meta_path.insert(0, _Block())\n",
		encoding="utf-8",
	)
	dict_env["PYTHONPATH"] = str(tmp_path)

	str_bash = shutil.which("bash") or "bash"
	str_script = (
		f'source "{path_bin}/lib/common.sh"; source "{path_bin}/lib/bootstrap.sh"; '
		f'BIN_DIR="{path_bin}"; PYTHON="$(command -v python3 || command -v python)"; '
		f'build_union_ca_bundle "{path_corporate}"'
	)
	# Constant, trusted argv built from repo-internal paths — no user input reaches it.
	cls_run = subprocess.run(  # noqa: S603
		[str_bash, "-c", str_script],
		env=dict_env,
		capture_output=True,
		encoding="utf-8",
		errors="replace",
		check=False,
	)
	assert cls_run.returncode != 0, "a corporate-only bundle must not be written"
	assert not (path_bin / "ca_bundle.pem").exists()
	assert "narrows the trust store" in cls_run.stderr


def test_corporate_ca_wiring_never_disables_verification_for_pypi() -> None:
	"""PIP_TRUSTED_HOST must not be exported — it defeats the bundle being built.

	Trusting a host outright skips certificate verification for it, so shipping both is worse
	than shipping neither: the bundle looks like the control while the trusted-host list is
	what actually decides.
	"""
	str_source = (Path(__file__).resolve().parents[2] / "bin" / "lib" / "bootstrap.sh").read_text(
		encoding="utf-8"
	)
	assert "export PIP_TRUSTED_HOST" not in str_source


# --------------------------
# bin/get_corporate_ca.sh
# --------------------------


@pytest.mark.skipif(os.name == "nt", reason="this asserts the non-Windows refusal path")
def test_get_corporate_ca_refuses_with_guidance_off_windows(tmp_path: Path) -> None:
	"""On a non-Windows host the script refuses and names the system trust store.

	The rewrite deliberately removed the old behaviour of opening a TLS connection with
	verification disabled and saving whatever certificate the network presented — that
	captured the LEAF, not the CA, and trusted whatever a hostile network offered. There is
	no automatic substitute off Windows, so refusing with the path to the OS bundle is the
	feature, and this pins it: a future edit that silently "restores" extraction would fail
	here rather than in production behind a proxy.
	"""
	cls_result = _run("get_corporate_ca.sh", cwd=tmp_path)

	assert cls_result.returncode != 0, "the script must not report success without a pem"
	str_output = cls_result.stdout + cls_result.stderr
	assert "Windows only" in str_output
	# The refusal carries the remedy, not just the verdict.
	assert "ca-certificates.crt" in str_output or "ca-bundle.crt" in str_output
	# Nothing is written on the refusal path.
	assert not (tmp_path / "bin" / "corporate_ca.pem").exists()


def _init_repo_with_one_commit(path_repo: Path) -> str:
	"""Create a git work tree with one commit and return the resolved ``git`` binary.

	Parameters
	----------
	path_repo : pathlib.Path
		Directory to initialise as a git work tree; created if absent.

	Returns
	-------
	str
		Absolute path to the ``git`` executable.
	"""
	_skip_unless(_STR_GIT is not None, "git not available -- integration guard only")
	str_git = str(_STR_GIT)

	path_repo.mkdir(parents=True, exist_ok=True)
	list_identity = ["-c", "user.email=t@t.invalid", "-c", "user.name=t"]
	# Constant, trusted argv -- a resolved git plus repo-internal paths.
	subprocess.run([str_git, "init", "-q", str(path_repo)], check=True)  # noqa: S603
	(path_repo / "seed.txt").write_text("seed\n", encoding="utf-8")
	subprocess.run(  # noqa: S603
		[str_git, "-C", str(path_repo), "add", "seed.txt"], check=True
	)
	list_commit = [str_git, "-C", str(path_repo), *list_identity]
	list_commit += ["commit", "-q", "--no-verify", "-m", "seed"]
	subprocess.run(list_commit, check=True, capture_output=True)  # noqa: S603
	return str_git


def test_clean_index_guard_allows_a_push_with_an_empty_index(tmp_path: Path) -> None:
	"""The routine case -- nothing staged -- must pass, or the guard gets disabled.

	This is the half that decides whether the guard survives: it fires on a POPULATED index,
	never on a merely dirty tree, so an unstaged edit while pushing (which is normal) is not
	blocked.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir holding the git work tree.
	"""
	path_repo = tmp_path / "repo"
	_init_repo_with_one_commit(path_repo)
	# Edit a tracked file without staging it. The tree is now dirty while the index stays
	# empty, which is the routine state the guard must never block.
	(path_repo / "seed.txt").write_text("edited\n", encoding="utf-8")

	cls_result = _run("check_clean_index.sh", cwd=path_repo)

	assert cls_result.returncode == 0, cls_result.stdout + cls_result.stderr


def test_clean_index_guard_blocks_a_populated_index(tmp_path: Path) -> None:
	"""The should-fail proof: staged-but-uncommitted work stops the push.

	A guard that has never been observed failing is indistinguishable from one wired to a
	condition that cannot occur, so the negative control is the test that matters here. The
	staged file is named in the output, because the whole point is that the rejected commit
	left work behind that nobody was told about.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir holding the git work tree.
	"""
	path_repo = tmp_path / "repo"
	str_git = _init_repo_with_one_commit(path_repo)
	(path_repo / "left_behind.py").write_text("x = 1\n", encoding="utf-8")
	# `git add` ran and no commit consumed it -- the fingerprint of a rejected commit.
	subprocess.run(  # noqa: S603
		[str_git, "-C", str(path_repo), "add", "left_behind.py"], check=True
	)

	cls_result = _run("check_clean_index.sh", cwd=path_repo)

	assert cls_result.returncode != 0, "a populated index must block the push"
	str_output = cls_result.stdout + cls_result.stderr
	# The verdict names the likely cause and the file, not just "blocked".
	assert "REJECTED" in str_output
	assert "left_behind.py" in str_output
	# The remedy travels with the refusal, including the escape hatch.
	assert "--no-verify" in str_output


def test_clean_index_guard_is_inert_off_a_git_tree(tmp_path: Path) -> None:
	"""Outside a git work tree there is nothing to guard, and the hook must never block.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir that is deliberately not a git repository.
	"""
	cls_result = _run("check_clean_index.sh", cwd=tmp_path)

	assert cls_result.returncode == 0


# --------------------------
# tasks.sh — the no-make interface
# --------------------------


def test_tasks_sh_resolves_the_print_status_it_calls() -> None:
	"""``tasks.sh`` must source the lib defining ``print_status``, which it calls.

	Measured before the fix: ``./tasks.sh init`` exited **127** at ``enable_repo_rules`` with
	``print_status: command not found``, so its last two steps never ran in any scaffolded
	project. The Makefile was unaffected -- its recipes shell out to ``bin/*.sh``, which source
	the lib themselves -- so the break was invisible to anyone using ``make``, and ``tasks.sh``
	is exactly the interface for a box without make.

	Driven through the usage guard because that path calls ``print_status`` and then returns,
	touching neither the network nor Poetry.
	"""
	str_bash = shutil.which("bash") or "bash"
	path_tasks = Path(__file__).resolve().parents[2] / "tasks.sh"
	# Constant, trusted argv built from repo-internal paths -- no user input reaches it.
	cls_result = subprocess.run(  # noqa: S603
		[str_bash, str(path_tasks), "check_commit_msg"],
		capture_output=True,
		text=True,
		check=False,
		cwd=str(path_tasks.parent),
	)
	str_output = cls_result.stdout + cls_result.stderr
	assert "command not found" not in str_output
	assert cls_result.returncode == 2, "the usage guard exits 2, not 127"
	assert "FILE=" in str_output


def test_get_corporate_ca_never_disables_tls_verification() -> None:
	"""The script must not reach the network with verification switched off.

	Structural, because the behaviour it excludes cannot be observed from a passing run: the
	previous version set ``CERT_NONE`` and ``check_hostname = False`` to capture a proxy's
	substituted certificate. Reading the OS trust store needs neither.
	"""
	str_source = _bin_script("get_corporate_ca.sh").read_text(encoding="utf-8")
	assert "CERT_NONE" not in str_source
	assert "check_hostname" not in str_source
	# The supported path reads the store the browser already trusts.
	assert "enum_certificates" in str_source


# --------------------------
# bin/export_deps.sh
# --------------------------


def _stub_poetry(path_dir: Path, str_export_body: str) -> dict[str, str]:
	"""Put a fake ``poetry`` first on PATH and return the env that selects it.

	``resolve_poetry`` takes the first ``command -v poetry`` hit, so a stub earlier on PATH
	is how this seam is exercised without a real Poetry install — and without the network.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory the stub is written into (prepended to ``PATH``).
	str_export_body : str
		Shell body run for the ``export`` subcommand; ``--version`` always succeeds.

	Returns
	-------
	dict of {str: str}
		Environment overrides placing the stub ahead of any real Poetry.
	"""
	path_stub = path_dir / "poetry"
	path_stub.write_text(
		"#!/usr/bin/env bash\n"
		'if [[ "$1" == "--version" ]]; then echo "Poetry (version 2.4.0)"; exit 0; fi\n'
		'if [[ "$1" == "export" ]]; then\n'
		f"{str_export_body}\n"
		"fi\n"
		"exit 0\n",
		encoding="utf-8",
	)
	path_stub.chmod(0o755)
	return {"PATH": f"{path_dir}{os.pathsep}{os.environ['PATH']}"}


def test_export_deps_writes_the_lock_file(tmp_path: Path) -> None:
	"""The happy path forwards ``--output`` and reports the artifact it wrote."""
	path_out = tmp_path / "requirements-lock.txt"
	dict_env = _stub_poetry(tmp_path, '\tprintf "pandas==2.2.0\\n" >"$5"; exit 0')
	dict_env["OUTPUT_FILE"] = str(path_out)

	cls_result = _run("export_deps.sh", dict_env=dict_env)

	assert cls_result.returncode == 0
	assert path_out.read_text(encoding="utf-8") == "pandas==2.2.0\n"
	assert "requirements-lock.txt" in cls_result.stdout + cls_result.stderr


def test_export_deps_reprints_what_poetry_said_on_failure(tmp_path: Path) -> None:
	"""A failure must surface Poetry's OWN words, never a guess about discarded output.

	The defect this guards is diagnosing a command whose output you threw away: the original
	handler asserted "the plugin is missing" about text it had sent to /dev/null, and was
	wrong. The message below is the one only Poetry could have produced.
	"""
	dict_env = _stub_poetry(
		tmp_path, '\techo "The command \\"export\\" does not exist." >&2; exit 1'
	)
	dict_env["OUTPUT_FILE"] = str(tmp_path / "requirements-lock.txt")

	cls_result = _run("export_deps.sh", dict_env=dict_env)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode != 0
	# Poetry's verbatim words survived to the operator.
	assert 'The command "export" does not exist.' in str_all
	# ... and the remedy names the RESOLVED binary, not a bare `poetry`.
	assert "Resolved Poetry:" in str_all
	assert "self add poetry-plugin-export" in str_all


# --------------------------
# check-urls — every docstring SHAPE must actually be scanned (blueprintx#206)
# --------------------------

_URL_404 = "https://example.invalid/blueprintx/does-not-exist"

# The three shapes the delimiter-line `continue` used to swallow. Each holds the SAME
# unreachable URL, so a shape that reports clean is reporting a check nobody ran.
DICT_DOCSTRING_SHAPES = {
	"one_line": f'"""A one-line docstring holding {_URL_404} inline."""\n',
	"opening_line": f'"""Summary carrying {_URL_404}.\n\n\tMore prose.\n\t"""\n',
	"closing_line": f'"""Summary.\n\n\tMore prose, then the link {_URL_404}"""\n',
	"body_line": f'"""Summary.\n\n\tThe link sits on its own line: {_URL_404}\n\t"""\n',
}


def _seed_url_cache(path_root: Path, str_url: str, str_status: str) -> None:
	"""Seed the hook's on-disk cache so the scan resolves offline.

	The cache is keyed by the md5 of the URL (see ``get_cache`` in the hook), and a cache
	hit short-circuits every network path. That makes this an OFFLINE negative control —
	and a sharper one than a live fetch, because only a line the scanner actually read can
	consult the cache at all.

	Parameters
	----------
	path_root : pathlib.Path
		The directory the hook will run in (the cache is CWD-relative).
	str_url : str
		The URL to pre-resolve.
	str_status : str
		The HTTP status to serve for it, e.g. ``"404"``.

	Returns
	-------
	None
	"""
	import hashlib

	path_cache = path_root / ".url_check_cache"
	path_cache.mkdir(exist_ok=True)
	# Not a security use — mirrors the hook's own `md5sum` cache key.
	str_key = hashlib.md5(str_url.encode()).hexdigest()  # noqa: S324
	(path_cache / str_key).write_text(f"{str_status}\n", encoding="utf-8")


def _run_url_hook(path_root: Path) -> subprocess.CompletedProcess:
	"""Run the check-urls hook against a directory.

	Parameters
	----------
	path_root : pathlib.Path
		Directory to scan; also the hook's CWD, so its cache resolves there.

	Returns
	-------
	subprocess.CompletedProcess
		The completed run.
	"""
	# Constant, trusted argv; no shell involved.
	return subprocess.run(  # noqa: S603
		[shutil.which("bash") or "bash", str(_bin_script("test_urls_docstrings.sh")), "."],
		cwd=path_root,
		capture_output=True,
		text=True,
		check=False,
	)


@pytest.mark.parametrize("str_shape", sorted(DICT_DOCSTRING_SHAPES))
def test_check_urls_fails_on_unreachable_url_in_every_docstring_shape(
	tmp_path: Path, str_shape: str
) -> None:
	"""A 404 must fail the gate whatever docstring shape holds it.

	⚠️ Negative control. Before blueprintx#206 the hook `continue`d past every delimiter
	line, so three of these four shapes reported ``All docstring URLs are reachable`` and
	exited 0 — the failure mode this repo writes gates to prevent: a green that asserts a
	check nobody ran.
	"""
	(tmp_path / "module_under_test.py").write_text(
		DICT_DOCSTRING_SHAPES[str_shape], encoding="utf-8"
	)
	_seed_url_cache(tmp_path, _URL_404, "404")

	cls_result = _run_url_hook(tmp_path)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode != 0, f"{str_shape} reported clean: {str_all}"
	assert _URL_404 in str_all
	assert "All docstring URLs are reachable" not in str_all


def test_check_urls_passes_when_the_same_url_resolves(tmp_path: Path) -> None:
	"""The positive control: the identical fixture passes when the URL answers 200.

	Without this pair, the test above could be satisfied by a hook that fails on everything.
	"""
	(tmp_path / "module_under_test.py").write_text(
		DICT_DOCSTRING_SHAPES["one_line"], encoding="utf-8"
	)
	_seed_url_cache(tmp_path, _URL_404, "200")

	cls_result = _run_url_hook(tmp_path)

	assert cls_result.returncode == 0
	assert "All docstring URLs are reachable" in cls_result.stdout + cls_result.stderr


def test_check_urls_ignores_a_url_outside_any_docstring(tmp_path: Path) -> None:
	"""A URL in ordinary code or a ``#`` comment is out of scope and must not fail the gate.

	Scanning the delimiter line widened what the hook reads; this pins that it did not widen
	into non-docstring lines.
	"""
	(tmp_path / "module_under_test.py").write_text(
		f'STR_ENDPOINT = "{_URL_404}"  # not a docstring\n', encoding="utf-8"
	)
	_seed_url_cache(tmp_path, _URL_404, "404")

	cls_result = _run_url_hook(tmp_path)

	assert cls_result.returncode == 0


# --------------------------
# check_complexity.sh — the per-tree cyclomatic ceiling (blueprintx#167)
# --------------------------

# Complexity 3 (two `if`s + the implicit path). Over src/'s ceiling of 2, under bin/'s 8.
_STR_BRANCHY = (
	'def branchy(a, b):{marker}\n\t"""Doc."""\n'
	"\tif a:\n\t\treturn 1\n\tif b:\n\t\treturn 2\n\treturn 3\n"
)
_STR_SIMPLE = 'def simple():\n\t"""Doc."""\n\treturn 1\n'


def _seed_tree(path_dir: Path) -> None:
	"""Create one tree of the complexity fixture with a complexity-1 filler module.

	Parameters
	----------
	path_dir : pathlib.Path
		The directory to create and seed.

	Returns
	-------
	None
	"""
	path_dir.mkdir(exist_ok=True)
	(path_dir / "filler.py").write_text(_STR_SIMPLE, encoding="utf-8")


def _complexity_tree(path_root: Path, str_marker: str = "", str_tree: str = "src") -> None:
	"""Materialise a minimal project the complexity gate can run against.

	Parameters
	----------
	path_root : pathlib.Path
		Directory to build the tree in; becomes the gate's ``--root``.
	str_marker : str
		Text appended to the ``def`` line, e.g. an escape-hatch comment.
	str_tree : str
		Which tree receives the branchy function (``src``, ``tests`` or ``bin``).

	Returns
	-------
	None
	"""
	shutil.copy(Path(__file__).resolve().parents[2] / "ruff.toml", path_root / "ruff.toml")
	# Written out rather than looped. At three entries the unrolled form is both shorter and
	# plainer than any machinery that would dodge the loop.
	_seed_tree(path_root / "src")
	_seed_tree(path_root / "tests")
	_seed_tree(path_root / "bin")
	(path_root / str_tree / "under_test.py").write_text(
		_STR_BRANCHY.format(marker=str_marker), encoding="utf-8"
	)


def _run_complexity(path_root: Path) -> subprocess.CompletedProcess:
	"""Run the complexity gate against a prepared tree.

	Parameters
	----------
	path_root : pathlib.Path
		The ``--root`` to scan.

	Returns
	-------
	subprocess.CompletedProcess
		The completed run.
	"""
	# Constant, trusted argv; no shell involved.
	return subprocess.run(  # noqa: S603
		[
			shutil.which("bash") or "bash",
			str(_bin_script("check_complexity.sh")),
			"--root",
			str(path_root),
		],
		capture_output=True,
		text=True,
		check=False,
	)


def test_complexity_gate_fails_on_a_function_over_the_ceiling(tmp_path: Path) -> None:
	"""⚠️ The should-fail control (blueprintx#111): a deliberately complex module must fail.

	Without this, every later assertion is satisfied by a gate that passes everything —
	which is precisely how this gate shipped its first draft green over 79 known violations.
	"""
	_complexity_tree(tmp_path)

	cls_result = _run_complexity(tmp_path)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode != 0
	assert "branchy" in str_all
	assert "C901" in str_all


def test_complexity_gate_passes_a_clean_tree(tmp_path: Path) -> None:
	"""The positive control, and it prints WHAT it checked — a silent gate reads as absent."""
	_complexity_tree(tmp_path, str_marker="")
	(tmp_path / "src" / "under_test.py").write_text(_STR_SIMPLE, encoding="utf-8")

	cls_result = _run_complexity(tmp_path)

	assert cls_result.returncode == 0
	assert "Python file(s)" in cls_result.stdout


def test_complexity_gate_honours_a_reasoned_escape_hatch(tmp_path: Path) -> None:
	"""A validator may keep its branching — with the reason written down."""
	_complexity_tree(tmp_path, str_marker="  # complexity-ok: validator, branching IS the work")

	cls_result = _run_complexity(tmp_path)

	assert cls_result.returncode == 0


def test_complexity_gate_rejects_a_hatch_with_no_reason(tmp_path: Path) -> None:
	"""A bare marker is not a hatch: the sentence IS the point of the mechanism."""
	_complexity_tree(tmp_path, str_marker="  # complexity-ok:")

	cls_result = _run_complexity(tmp_path)

	assert cls_result.returncode != 0
	assert "branchy" in cls_result.stdout + cls_result.stderr


def test_complexity_gate_applies_a_different_ceiling_per_tree(tmp_path: Path) -> None:
	"""The same function fails under src/ (max 2) and passes under bin/ (max 8).

	This is the property that needs TWO ruff invocations: ruff's per-file-ignores can switch
	a rule off for a path but cannot give that path a different max-complexity.
	"""
	_complexity_tree(tmp_path, str_tree="bin")
	(tmp_path / "src" / "under_test.py").write_text(_STR_SIMPLE, encoding="utf-8")

	assert _run_complexity(tmp_path).returncode == 0

	_complexity_tree(tmp_path, str_tree="src")
	(tmp_path / "bin" / "under_test.py").write_text(_STR_SIMPLE, encoding="utf-8")

	assert _run_complexity(tmp_path).returncode != 0


def test_complexity_gate_refuses_to_report_success_on_an_empty_tree(tmp_path: Path) -> None:
	"""Zero discovered files must FAIL, never read as clean.

	A broken glob otherwise reports success forever — the same blindness the gate exists to
	catch, wearing the gate's own uniform.
	"""
	shutil.copy(Path(__file__).resolve().parents[2] / "ruff.toml", tmp_path / "ruff.toml")

	cls_result = _run_complexity(tmp_path)

	assert cls_result.returncode != 0
	assert "refusing to report success" in cls_result.stdout + cls_result.stderr
