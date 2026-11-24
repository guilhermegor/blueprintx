"""Should-fail witnesses for the collision selector (blueprintx#1286)."""

import importlib.util
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "rerun_on_collision", Path(__file__).resolve().parents[2] / "bin" / "rerun_on_collision.py"
)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)


def test_selects_only_the_pr_sharing_a_file() -> None:
    """A merge touching a.py selects the PR touching a.py, not the one touching only b.py."""
    assert _MOD.colliding_prs({"a.py"}, pr_files={1: {"a.py", "c.py"}, 2: {"b.py"}}) == [1]


def test_no_overlap_selects_nothing() -> None:
    """Disjoint files leave every PR alone."""
    assert _MOD.colliding_prs({"a.py"}, pr_files={2: {"b.py"}}) == []


def test_hot_files_are_excluded_on_both_sides() -> None:
    """A lockfile shared by the merge and a PR does not count as a collision."""
    prs = {1: {"sub/poetry.lock"}, 2: {"x/poetry.lock", "a.py"}}
    list_hit = _MOD.colliding_prs({"poetry.lock", "a.py"}, pr_files=prs, excludes=["poetry.lock"])
    assert list_hit == [2]


def test_parse_excludes_splits_commas_and_newlines() -> None:
    """Both separators work and blanks are dropped."""
    assert _MOD.parse_excludes("a, b\n\nc") == ["a", "b", "c"]


def test_paths_of_includes_previous_filename_of_a_rename() -> None:
    """A renamed file contributes both its old and new path."""
    files = [{"filename": "b.py", "previous_filename": "a.py"}, {"filename": "c.py"}]
    assert _MOD.paths_of(files) == {"a.py", "b.py", "c.py"}


def test_truncated_merge_updates_every_open_pr() -> None:
    """A merge file list at GitHub's cap cannot be intersected, so every PR is selected."""
    assert _MOD._targets(None, pr_files={1: {"a.py"}, 2: {"b.py"}}, excludes=[]) == [1, 2]


def test_main_skips_without_rerun_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without RERUN_TOKEN the script exits 0 and never calls the API."""
    monkeypatch.delenv("RERUN_TOKEN", raising=False)
    monkeypatch.setattr(_MOD, "_call", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert _MOD.main() == 0


def test_unreadable_pr_is_kept_for_the_full_update_fallback() -> None:
    """A PR with an empty file set is still selected when the merge list was truncated."""
    assert _MOD._targets(None, pr_files={1: set(), 2: {"b.py"}}, excludes=[]) == [1, 2]


def test_a_non_list_page_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A list endpoint answering null raises ValueError instead of corrupting the result."""
    monkeypatch.setattr(_MOD, "_call", lambda *a, **k: None)
    with pytest.raises(ValueError, match="expected a list"):
        _MOD._paged("repos/o/r/pulls", str_token="t")
