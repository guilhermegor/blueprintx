"""Should-fail witnesses for the work-ledger gate's base resolution in a CI-shaped checkout.

A pull-request checkout has no local ``main`` and no ``origin/HEAD``, only ``origin/*``
remote-tracking refs and a detached ``HEAD``. The gate used to read the empty merge-base that
shape produced as "nothing to diff" and exit 0 (blueprintx#1069).
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


ledger = _load("check_backlog_ledger")


def _git_in(path_repo: Path, *args: str) -> str:
    """Run ``git`` inside a throwaway repo and return its stripped stdout.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository to run in.
    *args : str
        Arguments after ``git``.

    Returns
    -------
    str
        Captured stdout, stripped.
    """
    cls_proc = subprocess.run(  # noqa: S603
        ["git", "-C", str(path_repo), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return cls_proc.stdout.strip()


def _init_identity(path_repo: Path) -> None:
    """Give a throwaway repo a committer identity and switch signing off.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository to configure.
    """
    _git_in(path_repo, "config", "user.email", "t@example.com")
    _git_in(path_repo, "config", "user.name", "t")
    _git_in(path_repo, "config", "commit.gpgsign", "false")


def _commit_file(path_repo: Path, str_name: str) -> None:
    """Write one file and commit it.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository to commit in.
    str_name : str
        Repository-relative path of the file to create.
    """
    path_file = path_repo / str_name
    path_file.parent.mkdir(parents=True, exist_ok=True)
    path_file.write_text(str_name, encoding="utf-8")
    _git_in(path_repo, "add", str_name)
    _git_in(path_repo, "commit", "-q", "-m", f"add {str_name}")


@pytest.fixture(autouse=True)
def _neutral_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the CI variables that change the gate's author, and the host's git config.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to clear and set the variables.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_ACTOR", raising=False)
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)


@pytest.fixture
def path_origin(tmp_path: Path) -> Path:
    """Return a bare remote holding ``main``, ``develop`` and a ``feature`` that edits ``src/``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided scratch directory.

    Returns
    -------
    pathlib.Path
        The bare remote.
    """
    path_seed = tmp_path / "seed"
    path_seed.mkdir()
    _git_in(path_seed, "init", "-q", "--initial-branch=main")
    _init_identity(path_seed)
    _commit_file(path_seed, "README.md")
    _git_in(path_seed, "branch", "develop")
    _git_in(path_seed, "checkout", "-q", "-b", "feature")
    _commit_file(path_seed, "src/mod.py")
    path_remote = tmp_path / "origin.git"
    _git_in(tmp_path, "init", "-q", "--bare", str(path_remote))
    _git_in(path_seed, "push", "-q", str(path_remote), "main", "develop", "feature")
    return path_remote


@pytest.fixture
def path_ci(tmp_path: Path, path_origin: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a checkout shaped like ``actions/checkout``: detached, no local branch, no HEAD ref.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided scratch directory.
    path_origin : pathlib.Path
        The bare remote to fetch from.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate inside the checkout.

    Returns
    -------
    pathlib.Path
        The checkout, ``HEAD`` detached at ``origin/feature``.
    """
    path_checkout = tmp_path / "ci"
    path_checkout.mkdir()
    _git_in(path_checkout, "init", "-q")
    _init_identity(path_checkout)
    _git_in(path_checkout, "remote", "add", "origin", str(path_origin))
    _git_in(path_checkout, "fetch", "-q", "origin", "+refs/heads/*:refs/remotes/origin/*")
    _git_in(path_checkout, "checkout", "-q", "--detach", "origin/feature")
    monkeypatch.chdir(path_checkout)
    return path_checkout


@pytest.fixture
def path_ci_merge(path_ci: Path) -> Path:
    """Return the real ``pull_request`` checkout: ``HEAD`` on the merge of the PR into its base.

    Parameters
    ----------
    path_ci : pathlib.Path
        The detached checkout at ``origin/feature``.

    Returns
    -------
    pathlib.Path
        The checkout, ``HEAD`` detached at a merge commit whose parents are ``origin/main``
        and ``origin/feature`` (what ``refs/pull/N/merge`` is).
    """
    _git_in(path_ci, "checkout", "-q", "--detach", "origin/main")
    _git_in(path_ci, "merge", "-q", "--no-ff", "-m", "merge", "origin/feature")
    return path_ci


@pytest.fixture
def path_no_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a repo with commits on ``feature`` and no branch the gate can call the default.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided scratch directory.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate inside the repo.

    Returns
    -------
    pathlib.Path
        The repository.
    """
    path_repo = tmp_path / "nodefault"
    path_repo.mkdir()
    _git_in(path_repo, "init", "-q", "--initial-branch=feature")
    _init_identity(path_repo)
    _commit_file(path_repo, "README.md")
    _commit_file(path_repo, "src/mod.py")
    monkeypatch.chdir(path_repo)
    return path_repo


def test_main_ci_checkout_without_local_main_demands_a_ledger(path_ci: Path) -> None:
    """The CI shape is where the gate matters, so src/ changes there must still be refused."""
    assert ledger.main() == 1


def test_main_ci_checkout_names_the_missing_ledger(
    path_ci: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The refusal in a CI checkout is the ledger message, not silence."""
    ledger.main()
    assert "adds no work ledger" in capsys.readouterr().out


def test_default_branch_ci_checkout_resolves_the_remote_tracking_ref(path_ci: Path) -> None:
    """With no local ``main`` and no ``origin/HEAD``, the usable ref is ``origin/main``."""
    assert ledger.default_branch() == "origin/main"


def test_default_branch_prefers_the_pull_request_base_ref(
    path_ci: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A PR targeting ``develop`` is diffed against ``origin/develop``, not ``origin/main``."""
    monkeypatch.setenv("GITHUB_BASE_REF", "develop")
    assert ledger.default_branch() == "origin/develop"


def test_default_branch_refuses_to_fall_back_from_an_unresolvable_base_ref(
    path_ci: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A known PR base that was not fetched must not be swapped for another branch."""
    monkeypatch.setenv("GITHUB_BASE_REF", "does-not-exist")
    assert ledger.default_branch() == ""


def test_main_unresolvable_pull_request_base_fails(
    path_ci: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A narrow fetch that lacks the PR base is reported, never judged against ``origin/main``.

    HEAD sits at ``origin/main`` so a silent fallback would read "HEAD is the base" and pass.
    """
    _git_in(path_ci, "checkout", "-q", "--detach", "origin/main")
    monkeypatch.setenv("GITHUB_BASE_REF", "does-not-exist")
    assert ledger.main() == 1


def test_main_unresolvable_base_on_a_feature_branch_fails(path_no_default: Path) -> None:
    """No resolvable base on a branch with commits is a failure, never a silent pass."""
    assert ledger.main() == 1


def test_main_unresolvable_base_says_it_could_not_resolve(
    path_no_default: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The failure names the cause so the reader is not left guessing."""
    ledger.main()
    assert "could not resolve a base" in capsys.readouterr().out


def test_main_pull_request_merge_commit_demands_a_ledger(path_ci_merge: Path) -> None:
    """The ``refs/pull/N/merge`` shape is the one the workflow really checks out."""
    assert ledger.main() == 1


def test_main_unresolvable_base_names_a_local_remedy(
    path_no_default: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A developer with no CI to reconfigure is told to fetch or create the default branch."""
    ledger.main()
    assert "git fetch origin" in capsys.readouterr().out


def test_fixture_repos_ignore_the_host_global_git_config(path_ci: Path) -> None:
    """A developer's global ``core.hooksPath`` or templates must not reach the fixture repos."""
    assert _git_in(path_ci, "config", "--global", "--list") == ""


def test_main_on_the_default_branch_is_still_a_no_op(path_ci: Path) -> None:
    """The control: HEAD at ``origin/main`` has nothing to diff and passes."""
    _git_in(path_ci, "checkout", "-q", "--detach", "origin/main")
    assert ledger.main() == 0


def test_main_repository_without_commits_is_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first commit of a new repo has no HEAD to compare, and must not be refused."""
    path_empty = tmp_path / "empty"
    path_empty.mkdir()
    _git_in(path_empty, "init", "-q")
    monkeypatch.chdir(path_empty)
    assert ledger.main() == 0
