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

from collections.abc import Mapping
import os
from pathlib import Path
import re
import shutil
import subprocess
from types import MappingProxyType

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

# An immutable empty default for the env-override parameters below. A mutable `{}` default
# is a bugbear B006 finding, and a `dict_extra or {}` guard would cost a decision point in a
# tree capped at cyclomatic complexity 1.
_MAPPING_NO_EXTRA_ENV: Mapping[str, str] = MappingProxyType({})


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
# poe_exec.sh — the task-runner resolver
# --------------------------


def test_poe_exec_resolves_the_print_status_it_calls() -> None:
	"""``poe_exec.sh`` must source the lib defining ``print_status``, which it calls.

	Inherited from the ``tasks.sh`` test this replaces, because the DEFECT outlived the file.
	Measured then: ``./tasks.sh init`` exited **127** at ``enable_repo_rules`` with
	``print_status: command not found``, so its last two steps never ran in any scaffolded
	project -- and the Makefile was unaffected, its recipes shelling out to ``bin/*.sh`` which
	source the lib themselves. The break was therefore invisible from the interface most people
	used.

	``poe_exec.sh`` now occupies that seat: it is the entry point every hook and workflow goes
	through, and its unresolved-Poe path is nothing but ``print_status`` calls -- the branch that
	runs on the machine LEAST able to diagnose it. An unsourced lib would turn a readable
	"install poe like this" into ``command not found``.
	"""
	str_bash = shutil.which("bash") or "bash"
	path_exec = Path(__file__).resolve().parents[2] / "bin" / "poe_exec.sh"
	# Constant, trusted argv built from repo-internal paths -- no user input reaches it.
	# The environment is inherited rather than scrubbed. An emptied PATH takes `dirname` with
	# it, so SCRIPT_DIR never resolves and the run then fails for a reason unrelated to the
	# claim. Measured while writing this test. Either branch of the resolver serves here, since
	# a resolved Poe and the diagnostic that reports none are both built from print_status
	# calls, so whichever one runs proves the lib is reachable.
	cls_result = subprocess.run(  # noqa: S603
		[str_bash, str(path_exec), "--version"],
		capture_output=True,
		text=True,
		check=False,
		cwd=str(path_exec.parents[1]),
	)
	str_output = cls_result.stdout + cls_result.stderr
	assert "print_status: command not found" not in str_output
	assert "print_status: not found" not in str_output


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
	# ⚠️ The third shape, deferred when the two blind ones were fixed and closed on review
	# (blueprintx#224): a closing delimiter sharing a line with text. It was never blind —
	# the URL was scanned as body text — but the state never flipped back, so every LATER
	# line was read as still inside the docstring and its URLs were fetched too.
	"closing_shares_the_line": f'"""Summary.\n\n\tProse, then the link {_URL_404}"""\n',
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


# The colour-control variables, stripped from every run so a developer's shell cannot decide
# what this suite measures. Unrolled at three entries for the same reason `_complexity_tree`
# unrolls its three trees, and a loop here would cost complexity in a tree capped at 1.
_MAPPING_NO_EXTRA_ENV: Mapping[str, str] = MappingProxyType({})

# Matches an ANSI CSI sequence — the escapes that must never reach the gate's parsing.
_RE_ANSI = re.compile(r"\x1b\[[0-9;]*m")
# The reported finding, whole line. A regex rather than a filtered generator because a
# comprehension `if` is a decision point, and tests/ is capped at complexity 1.
_RE_C901_LINE = re.compile(r"^.*C901.*$", re.MULTILINE)


def _run_complexity(
	path_root: Path, dict_extra: Mapping[str, str] = _MAPPING_NO_EXTRA_ENV
) -> subprocess.CompletedProcess:
	"""Run the complexity gate against a prepared tree.

	⚠️ The inherited colour variables are stripped before ``dict_extra`` is applied, so a
	run states its own colour environment rather than inheriting the developer's. Without
	this the tests below are decided by the ambient shell: with ``FORCE_COLOR`` exported,
	the clean-tree and escape-hatch cases went red against a correct gate (blueprintx#254).

	Parameters
	----------
	path_root : pathlib.Path
		The ``--root`` to scan.
	dict_extra : Mapping[str, str]
		Environment entries layered over the stripped environment.

	Returns
	-------
	subprocess.CompletedProcess
		The completed run.
	"""
	dict_env = dict(os.environ)
	dict_env.pop("FORCE_COLOR", None)
	dict_env.pop("CLICOLOR_FORCE", None)
	dict_env.pop("NO_COLOR", None)
	dict_env.update(dict_extra)

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
		env=dict_env,
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


# --------------------------
# check_complexity.sh — a colour-forcing shell must not change the verdict (blueprintx#254)
# --------------------------


@pytest.mark.parametrize("str_var", ["FORCE_COLOR", "CLICOLOR_FORCE"])
def test_complexity_gate_reaches_a_verdict_under_forced_colour(
	tmp_path: Path, str_var: str
) -> None:
	"""Ruff's coloured output must never reach the gate's parsing.

	The gate reads ruff's rendered ``path:line:col:`` line and feeds the line number into an
	arithmetic expansion. With colour on, the ANSI escapes travel with the digits and bash
	dies with ``[0m101[36m: syntax error: operand expected`` — a message naming neither ruff,
	nor colour, nor this gate. Measured 2026-08-23: six of six tiers red on a clean tree,
	purely because the developer's shell exported ``FORCE_COLOR``.

	⚠️ Do NOT "fix" a failure here by setting ``NO_COLOR=1`` in the gate. Measured against
	ruff 0.11.13: ``NO_COLOR`` does not win against ``FORCE_COLOR``, so that change would
	leave the defect live and this test green. The forcing variable has to be UNSET.
	"""
	_complexity_tree(tmp_path)

	cls_result = _run_complexity(tmp_path, {str_var: "3"})
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode != 0, f"no verdict under {str_var}: {str_all}"
	assert "C901" in str_all
	assert "syntax error" not in str_all


def test_complexity_gate_passes_a_hatched_tree_under_forced_colour(tmp_path: Path) -> None:
	"""The measured symptom was red on a tree that was actually FINE — pin that direction.

	⚠️ The tree here is *hatched*, not clean, and that is the whole test. A tree with no
	C901 findings cannot catch this bug: ruff prints nothing, the gate parses nothing, and
	no escape ever reaches the arithmetic. The crash needs a finding to read, and the tiers
	that went red all had hatched findings being parsed on their way to being excused.
	"""
	_complexity_tree(tmp_path, str_marker="  # complexity-ok: validator, branching IS the work")

	cls_result = _run_complexity(tmp_path, {"FORCE_COLOR": "3"})

	assert cls_result.returncode == 0, f"hatched tree red under colour: {cls_result.stderr}"


def test_complexity_finding_carries_no_ansi_escapes(tmp_path: Path) -> None:
	"""The printed finding must be plain text a human and a log can both read."""
	_complexity_tree(tmp_path)

	cls_result = _run_complexity(tmp_path, {"FORCE_COLOR": "3"})
	str_all = cls_result.stdout + cls_result.stderr
	cls_match = _RE_C901_LINE.search(str_all)

	assert cls_match, f"no C901 line to inspect: {str_all}"
	# `print_status` adds its own colour around the marker, so only the ruff-derived
	# remainder after "C901" is asserted clean.
	str_payload = cls_match.group().split("C901")[-1]
	assert not _RE_ANSI.search(str_payload), f"escapes leaked into: {cls_match.group()!r}"


def test_complexity_gate_refuses_to_report_success_on_an_empty_tree(tmp_path: Path) -> None:
	"""Zero discovered files must FAIL, never read as clean.

	A broken glob otherwise reports success forever — the same blindness the gate exists to
	catch, wearing the gate's own uniform.
	"""
	shutil.copy(Path(__file__).resolve().parents[2] / "ruff.toml", tmp_path / "ruff.toml")

	cls_result = _run_complexity(tmp_path)

	assert cls_result.returncode != 0
	assert "refusing to report success" in cls_result.stdout + cls_result.stderr


def test_complexity_hatch_survives_a_formatter_wrapped_signature(tmp_path: Path) -> None:
	"""⚠️ The hatch must be found anywhere in the SIGNATURE, not only on the ``def`` line.

	ruff anchors C901 on the ``def``, but ``ruff format`` re-wraps a long signature and pushes
	a trailing comment down onto the closing-paren line. A hatch written correctly therefore
	stopped counting the moment the formatter touched the file — measured on a real function
	in this template, whose reason-carrying hatch silently stopped applying.
	"""
	_complexity_tree(tmp_path)
	(tmp_path / "src" / "under_test.py").write_text(
		"def branchy(\n"
		"\ta,\n"
		"\tb,\n"
		") -> int:  # complexity-ok: validator, branching IS the work\n"
		'\t"""Doc."""\n'
		"\tif a:\n\t\treturn 1\n\tif b:\n\t\treturn 2\n\treturn 3\n",
		encoding="utf-8",
	)

	cls_result = _run_complexity(tmp_path)

	assert cls_result.returncode == 0, cls_result.stdout + cls_result.stderr


def test_complexity_hatch_is_not_read_from_the_function_body(tmp_path: Path) -> None:
	"""The scan stops at the end of the signature, so a marker in the body does not excuse.

	Without this bound, widening the search to "the next few lines" would let a comment
	anywhere near the top of a function silence the gate.
	"""
	_complexity_tree(tmp_path)
	(tmp_path / "src" / "under_test.py").write_text(
		"def branchy(a, b) -> int:\n"
		'\t"""Doc."""\n'
		"\t# complexity-ok: this is in the BODY and must not count\n"
		"\tif a:\n\t\treturn 1\n\tif b:\n\t\treturn 2\n\treturn 3\n",
		encoding="utf-8",
	)

	cls_result = _run_complexity(tmp_path)

	assert cls_result.returncode != 0
	assert "branchy" in cls_result.stdout + cls_result.stderr


def test_check_urls_stops_scanning_after_a_closing_delimiter(tmp_path: Path) -> None:
	"""⚠️ A URL in ORDINARY CODE after a docstring must not be fetched.

	The closing delimiter used to be recognised only at the start of a line, so a docstring
	that closed as ``text \"\"\"`` never flipped the state back — and every later line of the
	module was scanned as if it were still docstring. That is the over-scan direction: it
	fails a gate on a URL that was never in a docstring at all.
	"""
	# ⚠️ The docstring must be MULTI-line and close on a line that STARTS WITH TEXT. A
	# one-line docstring matched the old start-anchored guard perfectly well, so a fixture
	# using one passes against the bug and proves nothing.
	(tmp_path / "module_under_test.py").write_text(
		'"""Summary.\n\n\tProse, and the docstring closes right here."""\n\n'
		f'STR_ENDPOINT = "{_URL_404}"  # ordinary code, never a docstring\n',
		encoding="utf-8",
	)
	_seed_url_cache(tmp_path, _URL_404, "404")

	cls_result = _run_url_hook(tmp_path)

	assert cls_result.returncode == 0, cls_result.stdout + cls_result.stderr


# --------------------------
# Every gate needs a should-fail witness (blueprintx#111)
#
# ⚠️ A gate with no test that has SEEN IT FAIL is indistinguishable from a gate that is not
# wired up: both print green. These are the eight that had no such witness. Writing them
# found three live defects, which is the argument for the rule rather than a coincidence:
# `check_provenance.py` and `check_docstrings.py` both exited 0 printing NOTHING when their
# cwd-relative globs matched nothing, and `lint_actions.sh` accepted any file named
# `actionlint` on PATH as a working one.
# --------------------------


def _run_py_gate(str_gate: str, path_root: Path) -> subprocess.CompletedProcess:
	"""Run a ``bin/*.py`` gate with its cwd set to a prepared tree.

	These gates take no arguments (``pass_filenames: false``) and discover their own targets
	relative to the CWD, so the tree under test is selected by ``cwd``, not by argv.

	Parameters
	----------
	str_gate : str
		Gate filename, e.g. ``check_provenance.py``.
	path_root : pathlib.Path
		Directory to run the gate in.

	Returns
	-------
	subprocess.CompletedProcess
		The completed run, stdout and stderr captured as text.
	"""
	str_python = shutil.which("python3") or shutil.which("python") or "python3"
	# Constant, trusted argv built from repo-internal paths — no user input reaches it.
	return subprocess.run(  # noqa: S603
		[str_python, str(_bin_script(str_gate))],
		cwd=path_root,
		capture_output=True,
		encoding="utf-8",
		errors="replace",
		check=False,
	)


def _write(path_file: Path, str_text: str) -> Path:
	"""Write text to a path, creating parents.

	Parameters
	----------
	path_file : pathlib.Path
		File to write.
	str_text : str
		Contents.

	Returns
	-------
	pathlib.Path
		The written file.
	"""
	path_file.parent.mkdir(parents=True, exist_ok=True)
	path_file.write_text(str_text, encoding="utf-8")
	return path_file


# A module that reads a table without stamping provenance — the violation check_provenance
# exists for. The marker it keys on is the CALL form, so the parentheses matter.
_STR_UNSTAMPED_READ = (
	'"""Loader."""\n\n\ndef load():\n\t"""Load."""\n\treturn read_table("x.csv")\n'
)
_STR_STAMPED_READ = (
	'"""Loader."""\n\n\ndef load():\n\t"""Load."""\n'
	'\treturn stamp_provenance(read_table("x.csv"), url="u")\n'
)


def test_provenance_gate_fires_on_a_read_without_a_stamp(tmp_path: Path) -> None:
	"""The should-fail control: a read with no stamp must be reported, by filename."""
	_write(tmp_path / "src" / "loader.py", _STR_UNSTAMPED_READ)

	cls_result = _run_py_gate("check_provenance.py", tmp_path)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode == 1
	assert "loader.py" in str_all
	assert "stamp_provenance" in str_all


def test_provenance_gate_passes_a_stamped_read(tmp_path: Path) -> None:
	"""The positive control — and it must say WHAT it checked, not just stay quiet."""
	_write(tmp_path / "src" / "loader.py", _STR_STAMPED_READ)

	cls_result = _run_py_gate("check_provenance.py", tmp_path)

	assert cls_result.returncode == 0
	assert "file(s) checked" in cls_result.stdout


def test_provenance_gate_refuses_to_report_success_on_zero_discovery(tmp_path: Path) -> None:
	"""⚠️ No ``src/`` is a broken invocation, never a clean project.

	Measured before the fix: with no ``src/`` directory the gate printed **nothing** and
	exited 0 — reporting success for having checked nothing, which is the exact failure it
	exists to catch in someone else's data.
	"""
	cls_result = _run_py_gate("check_provenance.py", tmp_path)

	assert cls_result.returncode == 1
	assert "refusing to report success" in cls_result.stdout + cls_result.stderr


# Annotated `-> int`, documented as `str`. The gate keys on that disagreement, so the two
# halves must genuinely differ — a fixture where they agree proves nothing.
_STR_RETURN_TYPE_MISMATCH = (
	'"""M."""\n\n\ndef f() -> int:\n'
	'\t"""Do.\n\n\tReturns\n\t-------\n\tstr\n\t\tA thing.\n\t"""\n\treturn 1\n'
)


def test_docstrings_gate_fires_on_a_return_type_mismatch(tmp_path: Path) -> None:
	"""The should-fail control: the annotation and the docstring must agree."""
	_write(tmp_path / "src" / "m.py", _STR_RETURN_TYPE_MISMATCH)

	cls_result = _run_py_gate("check_docstrings.py", tmp_path)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode == 1
	assert "m.py" in str_all
	assert "Return type mismatch" in str_all


def test_docstrings_gate_refuses_to_report_success_on_zero_discovery(tmp_path: Path) -> None:
	"""⚠️ Neither ``src/`` nor ``tests/`` present means a wrong cwd, not a clean tree.

	Same measured defect as check_provenance: silent exit 0 over an empty glob.
	"""
	cls_result = _run_py_gate("check_docstrings.py", tmp_path)

	assert cls_result.returncode == 1
	assert "refusing to report success" in cls_result.stdout + cls_result.stderr


def test_docs_sections_gate_fires_on_a_missing_canonical_page(tmp_path: Path) -> None:
	"""The should-fail control: a nav that omits the canonical pages must be reported."""
	_write(tmp_path / "mkdocs.yml", "site_name: X\nnav:\n  - Home: index.md\n")

	cls_result = _run_py_gate("check_docs_sections.py", tmp_path)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode == 1
	assert "usage.md" in str_all


def test_docs_sections_gate_announces_its_skip_rather_than_passing_silently(
	tmp_path: Path,
) -> None:
	"""No ``mkdocs.yml`` is a legitimate skip — but it must SAY so.

	This is the property that separates an acceptable skip from the two defects above: a
	project may genuinely ship no docs site, so exit 0 is right, and the printed sentence is
	what stops that zero from being mistaken for "the docs skeleton is intact".
	"""
	cls_result = _run_py_gate("check_docs_sections.py", tmp_path)

	assert cls_result.returncode == 0
	assert "skipping" in cls_result.stdout


# --------------------------
# The lint_*.sh wrappers — their failure mode is distinct (blueprintx#111)
#
# "the tool was not found" and "the tool ran and passed" are indistinguishable from outside,
# so these need a witness for BOTH the missing-tool branch and the zero-discovery branch.
# --------------------------


def _materialise_gate_tree(path_root: Path, str_script: str) -> Path:
	"""Copy ``bin/lib`` plus one wrapper into a throwaway project tree.

	⚠️ Required rather than merely tidy. These wrappers open ``main()`` with
	``cd "$SCRIPT_DIR/.."``, so they audit the tree that contains the SCRIPT and ignore the
	caller's cwd entirely. Running the repo's own copy against a ``cwd=tmp_path`` therefore
	silently audits ``templates/python-common`` — measured while writing these tests, where a
	one-workflow fixture reported ``7 workflow(s)``. The script has to live in the tree.

	Parameters
	----------
	path_root : pathlib.Path
		Project root to build.
	str_script : str
		Wrapper filename, e.g. ``lint_actions.sh``.

	Returns
	-------
	pathlib.Path
		Path to the copied script inside the throwaway tree.
	"""
	path_bin = path_root / "bin"
	path_bin.mkdir(parents=True, exist_ok=True)
	_materialise_bin_lib(path_bin)
	path_script = path_bin / str_script
	shutil.copy(_bin_script(str_script), path_script)
	return path_script


def _shadow(path_dir: Path, str_tool: str) -> Path:
	"""Place a stub named ``str_tool`` in ``path_dir`` that fails every invocation.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory that will go first on ``PATH``.
	str_tool : str
		Executable name to shadow.

	Returns
	-------
	pathlib.Path
		``path_dir``, so calls chain in a caller without a loop.
	"""
	path_dir.mkdir(parents=True, exist_ok=True)
	path_stub = path_dir / str_tool
	path_stub.write_text("#!/bin/sh\nexit 127\n", encoding="utf-8")
	path_stub.chmod(0o755)
	return path_dir


def _stub_ok(path_dir: Path, str_tool: str) -> Path:
	"""Place a stub named ``str_tool`` in ``path_dir`` that succeeds at everything.

	The counterpart to ``_shadow``: it makes a tool resolve as PRESENT and healthy, so a test
	can reach a branch that lies *past* resolution — discovery, for instance — without needing
	the real tool installed.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory that will go first on ``PATH``.
	str_tool : str
		Executable name to provide.

	Returns
	-------
	pathlib.Path
		``path_dir``, so calls chain in a caller without a loop.
	"""
	path_dir.mkdir(parents=True, exist_ok=True)
	path_stub = path_dir / str_tool
	path_stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
	path_stub.chmod(0o755)
	return path_dir


def _path_with(path_dir: Path) -> str:
	"""Return a ``PATH`` value with ``path_dir`` first.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory to prepend.

	Returns
	-------
	str
		The composed PATH.
	"""
	return f"{path_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def _shadow_tool_and_poetry(path_root: Path, str_tool: str) -> str:
	"""Build a ``PATH`` on which ``str_tool`` is unresolvable by EITHER branch.

	⚠️ Shadowing the tool alone is not enough, and CI is where that shows. These wrappers
	resolve a vendored copy first (``run_poetry run <tool> --version``) and only then look on
	``PATH``; on a developer box neither exists so a tool-only stub looks sufficient, while in
	CI the vendored copy resolves, the gate really runs, and a test asserting the missing-tool
	contract fails for the opposite of the reason it was written.

	Stubbing ``poetry`` closes the first branch because ``resolve_poetry`` accepts it on a bare
	``command -v`` and the following ``run_poetry run … --version`` then fails — so both
	branches report absent, on any machine.

	Parameters
	----------
	path_root : pathlib.Path
		Directory to create the stub directory under.
	str_tool : str
		The gate's tool, e.g. ``actionlint``.

	Returns
	-------
	str
		A PATH value with the stub directory first.
	"""
	path_stub_dir = path_root / "_stubbin"
	_shadow(path_stub_dir, str_tool)
	_shadow(path_stub_dir, "poetry")
	return _path_with(path_stub_dir)


def _shadow_hadolint_completely(path_root: Path) -> str:
	"""Build a ``PATH`` on which lint_docker.sh can resolve NO hadolint at all.

	⚠️ Three names, because this wrapper has three ways to find the tool: a vendored copy via
	poetry, a system ``hadolint``, and — deliberately — the official image run through
	``docker``. GitHub runners have Docker, so stubbing only ``hadolint`` leaves the image
	branch live and the gate really lints, which is the opposite of the contract under test.

	Parameters
	----------
	path_root : pathlib.Path
		Directory to create the stub directory under.

	Returns
	-------
	str
		A PATH value with the stub directory first.
	"""
	path_stub_dir = path_root / "_stubbin"
	_shadow(path_stub_dir, "hadolint")
	_shadow(path_stub_dir, "docker")
	_shadow(path_stub_dir, "poetry")
	return _path_with(path_stub_dir)


def _run_sh_gate(
	path_script: Path, dict_extra: Mapping[str, str] = _MAPPING_NO_EXTRA_ENV
) -> subprocess.CompletedProcess:
	"""Run a wrapper from inside its materialised tree.

	Parameters
	----------
	path_script : pathlib.Path
		The copied script, as returned by ``_materialise_gate_tree``.
	dict_extra : Mapping[str, str]
		Environment entries layered over the inherited environment.

	Returns
	-------
	subprocess.CompletedProcess
		The completed run.
	"""
	dict_env = dict(os.environ)
	dict_env.update(dict_extra)
	# Constant, trusted argv built from repo-internal paths — no user input reaches it.
	return subprocess.run(  # noqa: S603
		[_STR_BASH, str(path_script)],
		capture_output=True,
		text=True,
		check=False,
		env=dict_env,
	)


_STR_VALID_WORKFLOW = (
	"name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
	"    timeout-minutes: 5\n    steps:\n      - run: echo hi\n"
)


def test_lint_actions_required_flag_makes_the_skip_impossible(tmp_path: Path) -> None:
	"""⚠️ The witness for the missing-tool branch: in CI a skip is not an acceptable green.

	A graceful skip is right on a contributor's box and placebo in CI, which is why
	``LINT_ACTIONS_REQUIRED=1`` exists. Without a test, that flag is a claim nobody checked.
	"""
	path_script = _materialise_gate_tree(tmp_path, "lint_actions.sh")
	_write(tmp_path / ".github" / "workflows" / "w.yaml", _STR_VALID_WORKFLOW)

	cls_result = _run_sh_gate(
		path_script,
		{"PATH": _shadow_tool_and_poetry(tmp_path, "actionlint"), "LINT_ACTIONS_REQUIRED": "1"},
	)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode != 0
	assert "required" in str_all


def test_lint_actions_skips_gracefully_when_not_required(tmp_path: Path) -> None:
	"""The same absent tool without the flag is a warning and a zero — the local contract."""
	path_script = _materialise_gate_tree(tmp_path, "lint_actions.sh")
	_write(tmp_path / ".github" / "workflows" / "w.yaml", _STR_VALID_WORKFLOW)

	cls_result = _run_sh_gate(
		path_script, {"PATH": _shadow_tool_and_poetry(tmp_path, "actionlint")}
	)

	assert cls_result.returncode == 0
	assert "skip" in cls_result.stdout + cls_result.stderr


def test_lint_actions_a_broken_binary_on_path_resolves_as_absent(tmp_path: Path) -> None:
	"""⚠️ `command -v` answers "is there a file by that name", never "does it run".

	Measured (blueprintx#111): a stub named ``actionlint`` that exits 127 satisfied the bare
	``command -v`` probe, so the wrapper announced ``actionlint [system]: 7 workflow(s)`` and
	then propagated the stub's 127 — blaming the workflows for the tool's failure to start.
	The poetry branch always probed ``--version``; the system branch did not, though the
	function's own comment claimed both did.
	"""
	path_script = _materialise_gate_tree(tmp_path, "lint_actions.sh")
	_write(tmp_path / ".github" / "workflows" / "w.yaml", _STR_VALID_WORKFLOW)

	cls_result = _run_sh_gate(
		path_script, {"PATH": _shadow_tool_and_poetry(tmp_path, "actionlint")}
	)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode == 0, f"the stub's exit leaked out: {str_all}"
	assert "127" not in str_all
	assert "[system]" not in str_all


def test_lint_actions_fails_when_discovery_matches_zero_files(tmp_path: Path) -> None:
	"""⚠️ The witness for the zero-discovery branch: actionlint exits 0 with no arguments.

	So a wrapper whose glob matched nothing reports success forever — green precisely because
	it is checking nothing. The count must be asserted, not the exit code. The required flag
	is set so the run reaches discovery instead of stopping at the absent tool.
	"""
	path_script = _materialise_gate_tree(tmp_path, "lint_actions.sh")
	(tmp_path / ".github" / "workflows").mkdir(parents=True)

	# ⚠️ A HEALTHY actionlint is required for this test to mean anything. With the tool absent
	# the run stops in the required-tool branch and never reaches discovery — so an assertion
	# that also accepts "required" passes even with the vacuous-discovery guard deleted, which
	# is a witness green-lighting without ever reaching the branch it names — the very defect
	# this file exists to prevent. Poetry is shadowed so resolution cannot take the vendored
	# path.
	path_stub_dir = tmp_path / "_stubbin"
	_stub_ok(path_stub_dir, "actionlint")
	_shadow(path_stub_dir, "poetry")

	cls_result = _run_sh_gate(
		path_script, {"PATH": _path_with(path_stub_dir), "LINT_ACTIONS_REQUIRED": "1"}
	)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode != 0
	assert "vacuously" in str_all


def test_lint_docker_required_flag_makes_the_skip_impossible(tmp_path: Path) -> None:
	"""The same required-flag contract as lint_actions, for hadolint."""
	path_script = _materialise_gate_tree(tmp_path, "lint_docker.sh")
	_write(tmp_path / "Dockerfile", "FROM python:3.12-slim\nRUN echo hi\n")

	cls_result = _run_sh_gate(
		path_script,
		{"PATH": _shadow_hadolint_completely(tmp_path), "LINT_DOCKER_REQUIRED": "1"},
	)

	assert cls_result.returncode != 0
	assert "required" in cls_result.stdout + cls_result.stderr


def test_lint_docker_skips_when_the_tier_ships_no_dockerfile(tmp_path: Path) -> None:
	"""No Dockerfile is a legitimate skip — the tier genuinely ships none — but it must say so."""
	path_script = _materialise_gate_tree(tmp_path, "lint_docker.sh")

	cls_result = _run_sh_gate(path_script, {"LINT_DOCKER_REQUIRED": "1"})

	assert cls_result.returncode == 0
	assert "skip" in (cls_result.stdout + cls_result.stderr).lower()


def test_lint_sql_skips_when_no_sql_files_exist(tmp_path: Path) -> None:
	"""A tier with no ``.sql`` is a legitimate skip, and the wrapper must announce it."""
	path_script = _materialise_gate_tree(tmp_path, "lint_sql.sh")

	cls_result = _run_sh_gate(path_script)

	assert cls_result.returncode == 0
	assert "skip" in (cls_result.stdout + cls_result.stderr).lower()


def test_lint_yaml_reports_which_branch_it_took(tmp_path: Path) -> None:
	"""The wrapper must never exit 0 in silence — a silent gate reads as an absent one."""
	path_script = _materialise_gate_tree(tmp_path, "lint_yaml.sh")
	_write(tmp_path / "conf.yaml", "a: 1\n")

	cls_result = _run_sh_gate(path_script)

	assert (cls_result.stdout + cls_result.stderr).strip(), "exited without saying anything"


def test_unix_filenames_gate_fires_on_a_filename_with_a_space(tmp_path: Path) -> None:
	"""The should-fail control for the argv path — the one pre-commit actually uses."""
	path_bad = _write(tmp_path / "bad name.py", "x = 1\n")

	# Constant, trusted argv built from repo-internal paths — no user input reaches it.
	cls_result = subprocess.run(  # noqa: S603
		[_STR_BASH, str(_bin_script("check_unix_filenames.sh")), path_bad.name],
		cwd=tmp_path,
		capture_output=True,
		text=True,
		check=False,
	)
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode != 0
	assert "bad name.py" in str_all


def test_unix_filenames_gate_accepts_a_conventional_filename(tmp_path: Path) -> None:
	"""The positive control, so the test above is proving the rule and not a crash."""
	path_ok = _write(tmp_path / "good_name.py", "x = 1\n")

	# Constant, trusted argv built from repo-internal paths — no user input reaches it.
	cls_result = subprocess.run(  # noqa: S603
		[_STR_BASH, str(_bin_script("check_unix_filenames.sh")), path_ok.name],
		cwd=tmp_path,
		capture_output=True,
		text=True,
		check=False,
	)

	assert cls_result.returncode == 0


# --------------------------
# bin/rerun_stale_gate_runs.sh
# --------------------------


# A scriptable `gh` that records every invocation and answers the three calls the script makes.
# Shadowing rather than mocking is the same technique the tool-absence tests above use: it makes
# the behaviour deterministic on any machine, INCLUDING CI, where the real `gh` is installed and
# a `skipif` would drop the coverage exactly where the contract matters.
#
# It deliberately does NOT evaluate the `--jq` filter. Filtering is GitHub's job, not this
# script's — so the tests assert on the QUERY the script sends, which is the part it owns.
_STR_FAKE_GH = """#!/bin/bash
printf '%s\\n' "$*" >>"$GH_CALL_LOG"
if [[ "$*" == *rerun-failed-jobs* ]]; then
	exit "${FAKE_RERUN_EXIT:-0}"
fi
if [[ "$*" == *--paginate* ]]; then
	printf '%s\\n' ${FAKE_RUN_IDS:-}
	exit "${FAKE_LIST_EXIT:-0}"
fi
printf '%s\\n' "${FAKE_WORKFLOW_ID:-4242}"
exit 0
"""


def _fake_gh(path_root: Path) -> tuple[str, Path]:
	"""Install a scriptable ``gh`` stub first on ``PATH`` and return the PATH and its call log.

	Parameters
	----------
	path_root : pathlib.Path
		Directory to create the stub directory under.

	Returns
	-------
	tuple of (str, pathlib.Path)
		A PATH value with the stub first, and the file every invocation is appended to.
	"""
	path_stub_dir = path_root / "_ghbin"
	path_stub_dir.mkdir(parents=True, exist_ok=True)
	path_stub = path_stub_dir / "gh"
	path_stub.write_text(_STR_FAKE_GH, encoding="utf-8")
	path_stub.chmod(0o755)
	path_log = path_root / "gh_calls.log"
	path_log.write_text("", encoding="utf-8")
	return _path_with(path_stub_dir), path_log


def _run_cleanup(
	path_root: Path,
	str_run_ids: str,
	str_head_sha: str = "deadbee",
	str_rerun_exit: str = "0",
	str_list_exit: str = "0",
) -> tuple[subprocess.CompletedProcess[str], str]:
	"""Run the cleanup script against a scripted ``gh`` and return the result and its call log.

	Parameters
	----------
	path_root : pathlib.Path
		Directory the stub and log live under.
	str_run_ids : str
		Space-separated run ids the listing call should report.
	str_head_sha : str, optional
		The head SHA the workflow would pass in.
	str_rerun_exit : str, optional
		Exit code the stub returns for a re-run request; ``"1"`` simulates a denied
		``actions: write``.
	str_list_exit : str, optional
		Exit code the stub returns for the listing call; ``"1"`` simulates the query failing.

	Returns
	-------
	tuple of (subprocess.CompletedProcess[str], str)
		The finished process, and the recorded ``gh`` invocations as one string.
	"""
	str_path, path_log = _fake_gh(path_root)
	cls_result = _run(
		"rerun_stale_gate_runs.sh",
		dict_env={
			"PATH": str_path,
			"GH_CALL_LOG": str(path_log),
			"GITHUB_REPOSITORY": "acme/widget",
			"GITHUB_RUN_ID": "999",
			"HEAD_SHA": str_head_sha,
			"FAKE_RUN_IDS": str_run_ids,
			"FAKE_WORKFLOW_ID": "4242",
			"FAKE_RERUN_EXIT": str_rerun_exit,
			"FAKE_LIST_EXIT": str_list_exit,
		},
	)
	return cls_result, path_log.read_text(encoding="utf-8")


def test_stale_cleanup_reruns_every_stale_failure_but_never_itself(tmp_path: Path) -> None:
	"""The stale failures are re-run and the CURRENT run is skipped.

	Skipping ``$GITHUB_RUN_ID`` is the loop guard, not tidiness: the step only ever runs from a
	run that PASSED, so re-running itself would re-run a green run forever.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest's per-test temporary directory.
	"""
	cls_result, str_log = _run_cleanup(tmp_path, "111 222 999")

	assert cls_result.returncode == 0
	assert "runs/111/rerun-failed-jobs" in str_log
	assert "runs/222/rerun-failed-jobs" in str_log
	assert "runs/999/rerun-failed-jobs" not in str_log
	assert "Re-ran 2 stale failed run(s)" in cls_result.stdout


def test_stale_cleanup_scopes_its_query_to_this_workflow_and_this_head(tmp_path: Path) -> None:
	"""The listing call is pinned to this head SHA, to failures, and to this workflow id.

	Scoping by ``head_sha`` is what stops the cleanup reaching back and re-running an older
	commit's genuine failures; the workflow id comes from the API rather than from a name,
	because the two shipped copies of this gate disagree on both filename and name.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest's per-test temporary directory.
	"""
	_cls_result, str_log = _run_cleanup(tmp_path, "111")

	assert "head_sha=deadbee" in str_log
	assert "status=failure" in str_log
	assert "select(.workflow_id == 4242)" in str_log


def test_stale_cleanup_does_nothing_off_a_pull_request_event(tmp_path: Path) -> None:
	"""With no HEAD_SHA there is no subject, so the script must not call ``gh`` at all.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest's per-test temporary directory.
	"""
	cls_result, str_log = _run_cleanup(tmp_path, "111", str_head_sha="")

	assert cls_result.returncode == 0
	assert str_log == ""
	assert "not a pull-request event" in cls_result.stdout


def test_stale_cleanup_stays_green_and_warns_when_it_may_not_rerun(tmp_path: Path) -> None:
	"""A denied re-run warns loudly and still exits 0 — and that is not failing open.

	This is a janitor, not a guard. Failing the step would fail the job, which would deposit one
	MORE failed run into the very rollup it came to clean. The PR meanwhile stays BLOCKED behind
	the stale red, which is the status quo and fully visible — nothing is hidden by exiting 0.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest's per-test temporary directory.
	"""
	cls_result, _str_log = _run_cleanup(tmp_path, "111", str_rerun_exit="1")
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode == 0
	assert "::warning::" in str_all
	assert "actions: write" in str_all


def test_stale_cleanup_never_reports_clean_over_a_listing_that_failed(tmp_path: Path) -> None:
	"""A failed listing warns — it must never be reported as "already clean".

	``mapfile -t list < <(producer)`` discards the producer's exit status and reports only
	mapfile's own, so a failing ``gh api`` yields an EMPTY list that is indistinguishable from a
	genuinely clean rollup. That is the false all-clear this gate family exists to prevent, and
	``bin/lint_docker.sh`` documents the same trap at its own discovery call.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest's per-test temporary directory.
	"""
	cls_result, _str_log = _run_cleanup(tmp_path, "", str_list_exit="1")
	str_all = cls_result.stdout + cls_result.stderr

	assert cls_result.returncode == 0
	assert "already clean" not in str_all
	assert "Could not list runs" in str_all
