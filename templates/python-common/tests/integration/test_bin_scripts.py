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
	if cls_result.returncode != 0:
		pytest.skip("Poetry could not be resolved -- offline/CI integration guard only")

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
	str_git = shutil.which("git")
	if str_git is None:
		pytest.skip("git not available -- integration guard only")

	path_repo = tmp_path / "repo"
	path_repo.mkdir()
	path_home = tmp_path / "home"
	path_home.mkdir()
	path_global_cfg = path_home / ".gitconfig"
	# A real work tree; the throwaway HOME/config isolates the global safe.directory write.
	subprocess.run(  # noqa: S603
		[str_git, "init", "-q", str(path_repo)], check=True
	)

	dict_env = {
		"GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
		"GIT_CONFIG_GLOBAL": str(path_global_cfg),
		"HOME": str(path_home),
	}
	cls_result = _run("precommit.sh", cwd=path_repo, dict_env=dict_env)
	str_output = cls_result.stdout + cls_result.stderr
	if "dubious ownership" not in str_output and not path_global_cfg.exists():
		pytest.skip("git build does not honour GIT_TEST_ASSUME_DIFFERENT_OWNER -- guard only")

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
	str_bash = shutil.which("bash") or "bash"
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
	(path_bin / "lib").mkdir(parents=True)
	for path_lib in (Path(__file__).resolve().parents[2] / "bin" / "lib").glob("*.sh"):
		shutil.copy(path_lib, path_bin / "lib" / path_lib.name)

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
	(path_bin / "lib").mkdir(parents=True)
	for path_lib in (Path(__file__).resolve().parents[2] / "bin" / "lib").glob("*.sh"):
		shutil.copy(path_lib, path_bin / "lib" / path_lib.name)
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


def test_get_corporate_ca_refuses_with_guidance_off_windows(tmp_path: Path) -> None:
	"""On a non-Windows host the script refuses and names the system trust store.

	The rewrite deliberately removed the old behaviour of opening a TLS connection with
	verification disabled and saving whatever certificate the network presented — that
	captured the LEAF, not the CA, and trusted whatever a hostile network offered. There is
	no automatic substitute off Windows, so refusing with the path to the OS bundle is the
	feature, and this pins it: a future edit that silently "restores" extraction would fail
	here rather than in production behind a proxy.
	"""
	if os.name == "nt":  # pragma: no cover - the guard under test is the POSIX branch
		pytest.skip("this asserts the non-Windows refusal path")

	cls_result = _run("get_corporate_ca.sh", cwd=tmp_path)

	assert cls_result.returncode != 0, "the script must not report success without a pem"
	str_output = cls_result.stdout + cls_result.stderr
	assert "Windows only" in str_output
	# The refusal carries the remedy, not just the verdict.
	assert "ca-certificates.crt" in str_output or "ca-bundle.crt" in str_output
	# Nothing is written on the refusal path.
	assert not (tmp_path / "bin" / "corporate_ca.pem").exists()


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
