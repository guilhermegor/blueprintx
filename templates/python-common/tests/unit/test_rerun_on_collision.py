"""Should-fail witnesses for the collision selector (blueprintx#1286)."""

import importlib.util
from pathlib import Path
from unittest import mock
import urllib.error

import pytest


cls_spec = importlib.util.spec_from_file_location(
    "rerun_on_collision", Path(__file__).resolve().parents[2] / "bin" / "rerun_on_collision.py"
)
cls_module = importlib.util.module_from_spec(cls_spec)
cls_spec.loader.exec_module(cls_module)


def test_selects_only_the_pr_sharing_a_file() -> None:
    """A merge touching a.py selects the PR touching a.py, not the one touching only b.py."""
    assert cls_module.colliding_prs(
        {"a.py"}, dict_pr_files={1: {"a.py", "c.py"}, 2: {"b.py"}}
    ) == [1]


def test_no_overlap_selects_nothing() -> None:
    """Disjoint files leave every PR alone."""
    assert cls_module.colliding_prs({"a.py"}, dict_pr_files={2: {"b.py"}}) == []


def test_hot_files_are_excluded_on_both_sides() -> None:
    """A lockfile shared by the merge and a PR does not count as a collision."""
    list_prs = {1: {"sub/poetry.lock"}, 2: {"x/poetry.lock", "a.py"}}
    list_hit = cls_module.colliding_prs(
        {"poetry.lock", "a.py"}, dict_pr_files=list_prs, list_excludes=["poetry.lock"]
    )
    assert list_hit == [2]


def test_parse_excludes_splits_commas_and_newlines() -> None:
    """Both separators work and blanks are dropped."""
    assert cls_module.parse_excludes("a, b\n\nc") == ["a", "b", "c"]


def test_paths_of_includes_previous_filename_of_a_rename() -> None:
    """A renamed file contributes both its old and new path."""
    list_files = [{"filename": "b.py", "previous_filename": "a.py"}, {"filename": "c.py"}]
    assert cls_module.paths_of(list_files) == {"a.py", "b.py", "c.py"}


def test_truncated_merge_updates_every_open_pr() -> None:
    """A merge file list at GitHub's cap cannot be intersected, so every PR is selected."""
    assert cls_module._targets(
        None, dict_pr_files={1: {"a.py"}, 2: {"b.py"}}, list_excludes=[]
    ) == [1, 2]


def test_main_skips_without_rerun_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without RERUN_TOKEN the script exits 0 and never calls the API."""
    monkeypatch.delenv("RERUN_TOKEN", raising=False)
    monkeypatch.setattr(cls_module, "_call", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert cls_module.main() == 0


def test_unreadable_pr_is_kept_for_the_full_update_fallback() -> None:
    """A PR with an empty file set is still selected when the merge list was truncated."""
    assert cls_module._targets(None, dict_pr_files={1: set(), 2: {"b.py"}}, list_excludes=[]) == [
        1,
        2,
    ]


def _answers(*bodies: object) -> object:
    """Build a _call stand-in that returns the given bodies in order."""
    iter_bodies = iter(bodies)
    return lambda *args, **kwargs: next(iter_bodies)


def test_a_non_list_page_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A list endpoint answering null raises ValueError instead of corrupting the result."""
    monkeypatch.setattr(cls_module, "_call", lambda *a, **k: None)
    with pytest.raises(ValueError, match="expected a list"):
        cls_module._paged("repos/o/r/pulls", **{"str_token": ""})


def test_merge_files_at_the_cap_is_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    """A compare answer holding exactly 300 files is reported as truncated."""
    list_files = [{"filename": f"f{int_i}.py"} for int_i in range(300)]
    monkeypatch.setattr(cls_module, "_call", _answers({"files": list_files}))
    assert cls_module._merge_files("o/r", str_before="a", str_after="b", str_token="") is None


def test_merge_files_zero_sha_reads_the_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no previous sha the head commit's files are the merge's files."""
    monkeypatch.setattr(cls_module, "_call", _answers({"files": [{"filename": "a.py"}]}))
    assert cls_module._merge_files("o/r", str_before="0" * 40, str_after="b", str_token="") == {
        "a.py"
    }


def test_draft_bot_and_ghost_prs_are_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drafts and bots are skipped; a null user counts as a human."""
    list_prs = [
        {"number": 1, "draft": True, "user": {"type": "User"}},
        {"number": 2, "draft": False, "user": {"type": "Bot"}},
        {"number": 3, "draft": False, "user": None},
    ]
    monkeypatch.setattr(cls_module, "_call", _answers(list_prs, [{"filename": "a.py"}]))
    assert cls_module._open_pr_files("o/r", str_branch="main", str_token="") == (
        {3: {"a.py"}},
        set(),
    )


def _capped_listing(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[int, set[str]], set[int]]:
    """List two open PRs where PR 1 hit the (patched) file-list cap and PR 2 did not."""
    monkeypatch.setattr(cls_module, "PR_FILE_CAP", 2)
    list_prs = [{"number": int_pr, "draft": False, "user": {"type": "User"}} for int_pr in (1, 2)]
    list_files = {1: [{"filename": "x.py"}, {"filename": "y.py"}], 2: [{"filename": "z.py"}]}
    monkeypatch.setattr(cls_module, "PAGE_SIZE", 100)
    monkeypatch.setattr(cls_module, "_call", _answers(list_prs, list_files[1], list_files[2]))
    return cls_module._open_pr_files("o/r", str_branch="main", str_token="")


def test_pr_at_file_cap_is_reported_as_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the PR whose file list reached the cap is flagged as capped."""
    _, set_capped = _capped_listing(monkeypatch)
    assert set_capped == {1}


def test_capped_pr_file_list_is_updated_despite_no_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PR whose file list hit GitHub's 3000 cap may overlap via an omitted file."""
    dict_pr_files, set_capped = _capped_listing(monkeypatch)
    assert cls_module._targets(
        {"a.py"}, dict_pr_files=dict_pr_files, list_excludes=[], set_capped=set_capped
    ) == [1]


def test_main_exits_1_when_the_merge_cannot_be_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreadable merge file list ends the run with exit code 1."""
    monkeypatch.setenv("RERUN_TOKEN", "x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("AFTER_SHA", "b")
    monkeypatch.delenv("BEFORE_SHA", raising=False)
    monkeypatch.delenv("BASE_BRANCH", raising=False)
    monkeypatch.delenv("RERUN_EXCLUDE_FILES", raising=False)
    monkeypatch.setattr(cls_module, "_call", _answers(None))
    assert cls_module.main() == 1


def test_update_failures_are_logged_and_the_run_still_exits_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An HTTP error on one update and a dropped connection on the next both leave exit 0."""
    monkeypatch.setenv("RERUN_TOKEN", "x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("AFTER_SHA", "b")
    monkeypatch.delenv("BEFORE_SHA", raising=False)
    monkeypatch.delenv("BASE_BRANCH", raising=False)
    monkeypatch.delenv("RERUN_EXCLUDE_FILES", raising=False)
    list_prs = [{"number": int_pr, "draft": False, "user": {"type": "User"}} for int_pr in (1, 2)]
    exc_err = urllib.error.HTTPError("u", 422, "m", None, None)
    list_side = [
        {"files": [{"filename": "a.py"}]},
        list_prs,
        [{"filename": "a.py"}],
        [{"filename": "a.py"}],
    ]
    mock_call = mock.Mock(side_effect=[*list_side, exc_err, ConnectionResetError()])
    monkeypatch.setattr(cls_module, "_call", mock_call)
    assert (cls_module.main(), mock_call.call_count) == (0, 6)


def test_empty_exclude_variable_uses_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty RERUN_EXCLUDE_FILES falls back to the default globs, as the workflow does."""
    mock_parse = mock.Mock(return_value=[])
    monkeypatch.setattr(cls_module, "parse_excludes", mock_parse)
    monkeypatch.setenv("RERUN_TOKEN", "x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("AFTER_SHA", "b")
    monkeypatch.setenv("RERUN_EXCLUDE_FILES", "")
    monkeypatch.delenv("BEFORE_SHA", raising=False)
    monkeypatch.setattr(cls_module, "_call", _answers(None))
    cls_module.main()
    assert mock_parse.call_args.args == (cls_module.DEFAULT_EXCLUDES,)


def test_empty_base_branch_defaults_to_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty BASE_BRANCH lists PRs against main, never against an empty base."""
    mock_call = mock.Mock(side_effect=[{"files": [{"filename": "a.py"}]}, []])
    monkeypatch.setenv("RERUN_TOKEN", "x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("AFTER_SHA", "b")
    monkeypatch.setenv("BASE_BRANCH", "")
    monkeypatch.delenv("BEFORE_SHA", raising=False)
    monkeypatch.setattr(cls_module, "_call", mock_call)
    cls_module.main()
    assert "base=main" in mock_call.call_args_list[1].kwargs["str_path"]
