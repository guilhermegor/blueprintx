"""Should-fail witnesses for the collision selector (blueprintx#1286)."""

import importlib.util
from pathlib import Path
import sys
from unittest import mock
import urllib.error

import pytest


path_here = Path(__file__).resolve()
path_gate = next(
    (
        path_candidate
        for path_candidate in (
            path_here.parents[2] / "bin" / "check_review_threads.py",
            path_here.parents[3] / "common" / "bin" / "check_review_threads.py",
        )
        if path_candidate.is_file()
    ),
    path_here.parents[2] / "bin" / "check_review_threads.py",
)
cls_gate_spec = importlib.util.spec_from_file_location("check_review_threads", path_gate)
cls_gate = importlib.util.module_from_spec(cls_gate_spec)
sys.modules["check_review_threads"] = cls_gate
cls_gate_spec.loader.exec_module(cls_gate)

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
    dict_prs = {1: {"sub/poetry.lock"}, 2: {"x/poetry.lock", "a.py"}}
    list_hit = cls_module.colliding_prs(
        {"poetry.lock", "a.py"}, dict_pr_files=dict_prs, list_excludes=["poetry.lock"]
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
    dict_files = {1: [{"filename": "x.py"}, {"filename": "y.py"}], 2: [{"filename": "z.py"}]}
    monkeypatch.setattr(cls_module, "PAGE_SIZE", 100)
    monkeypatch.setattr(cls_module, "_call", _answers(list_prs, dict_files[1], dict_files[2]))
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
    dict_pull = {"head": {"sha": "old"}}
    list_side = [
        {"files": [{"filename": "a.py"}]},
        list_prs,
        [{"filename": "a.py"}],
        [{"filename": "a.py"}],
    ]
    mock_call = mock.Mock(
        side_effect=[*list_side, dict_pull, exc_err, dict_pull, ConnectionResetError()]
    )
    monkeypatch.setattr(cls_module, "_call", mock_call)
    monkeypatch.setattr(cls_module, "_roster_commands", lambda: [])
    assert (cls_module.main(), mock_call.call_count) == (0, 8)


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


def test_review_commands_asks_coderabbit_when_it_is_a_threads_reviewer() -> None:
    """A roster naming coderabbitai as a threads reviewer yields its full-review request."""
    assert cls_module.review_commands({"coderabbitai": "threads"}) == ["@coderabbitai full review"]


def test_review_commands_skips_a_reviewer_with_no_known_command() -> None:
    """A threads reviewer this script has no request for is never asked."""
    assert cls_module.review_commands({"greptile-apps": "threads"}) == []


def test_review_commands_skips_a_status_only_member() -> None:
    """A status-only member cannot review, so it is never asked even with a known command."""
    dict_roster = {"coderabbitai": "status", "greptile-apps": "threads"}
    assert cls_module.review_commands(dict_roster) == []


def test_patch_unchanged_is_true_for_equal_fingerprints() -> None:
    """Equal fingerprints at both heads mean the carried-forward review stands."""
    assert cls_module.patch_unchanged(lambda str_oid: "same", str_old="a", str_new="b")


def test_patch_unchanged_is_false_for_different_fingerprints() -> None:
    """Different fingerprints mean the review no longer covers the head."""
    dict_digests = {"a": "x", "b": "y"}
    assert not cls_module.patch_unchanged(dict_digests.__getitem__, str_old="a", str_new="b")


def _raise_runtime(str_oid: str) -> str:
    """Stand in for a fingerprint that cannot be computed."""
    raise RuntimeError(str_oid)


def test_patch_unchanged_fails_closed_when_the_fingerprint_is_unavailable() -> None:
    """A fingerprint that cannot be computed counts as changed, as in the review gate."""
    assert not cls_module.patch_unchanged(_raise_runtime, str_old="a", str_new="b")


def _follow_up_posts(monkeypatch: pytest.MonkeyPatch, *, fn_fingerprint: object) -> mock.Mock:
    """Run one follow-up for a PR whose head moved old to new; return the POST mock."""
    dict_pull = {"head": {"sha": "new"}, "base": {"sha": "base"}}
    mock_post = mock.Mock(return_value={})
    dict_routes = {"GET": lambda **kwargs: dict_pull, "POST": mock_post}
    monkeypatch.setattr(
        cls_module, "_call", lambda str_method, **kwargs: dict_routes[str_method](**kwargs)
    )
    monkeypatch.setattr(
        cls_module.check_review_threads,
        "fetch_patch_fingerprint",
        lambda str_owner, *, str_repo, str_base, str_oid: fn_fingerprint(str_oid),
    )
    cls_module._follow_up(
        "o/r",
        int_num=7,
        str_old="old",
        str_token="",
        list_commands=["@coderabbitai full review"],
    )
    return mock_post


def test_follow_up_requests_exactly_one_review_when_the_patch_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should-fail witness: a changed fingerprint posts the review request once."""
    dict_digests = {"old": "x", "new": "y"}
    mock_post = _follow_up_posts(monkeypatch, fn_fingerprint=dict_digests.__getitem__)
    assert mock_post.call_count == 1


def test_follow_up_posts_the_roster_command_as_the_comment_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The comment carries the exact command a user would type."""
    dict_digests = {"old": "x", "new": "y"}
    mock_post = _follow_up_posts(monkeypatch, fn_fingerprint=dict_digests.__getitem__)
    assert mock_post.call_args.kwargs["dict_body"] == {"body": "@coderabbitai full review"}


def test_follow_up_requests_nothing_when_the_patch_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Should-fail witness: an unchanged fingerprint keeps the review and posts nothing."""
    mock_post = _follow_up_posts(monkeypatch, fn_fingerprint=lambda str_oid: "same")
    assert mock_post.call_count == 0


def test_follow_up_requests_a_review_when_the_fingerprint_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An uncomputable fingerprint is read as changed, so the red gate gets its request."""
    mock_post = _follow_up_posts(monkeypatch, fn_fingerprint=_raise_runtime)
    assert mock_post.call_count == 1


def test_await_new_head_gives_up_when_the_head_never_moves() -> None:
    """A PR whose head stays put after every poll yields None, so no review is requested."""
    dict_pull = {"head": {"sha": "old"}}
    assert (
        cls_module._await_new_head(lambda: dict_pull, str_old="old", fn_sleep=lambda s: None)
        is None
    )


def test_await_new_head_returns_the_pull_once_the_head_moves() -> None:
    """The first poll showing a different head sha is returned."""
    dict_pull = {"head": {"sha": "new"}}
    assert (
        cls_module._await_new_head(lambda: dict_pull, str_old="old", fn_sleep=lambda s: None)
        == dict_pull
    )


def test_a_failed_review_request_does_not_stop_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """A follow-up that raises is logged; the update stays done and the run goes on."""
    monkeypatch.setattr(cls_module, "_call", lambda *a, **k: {"head": {"sha": "old"}})
    monkeypatch.setattr(cls_module, "_follow_up", mock.Mock(side_effect=ValueError("boom")))
    assert cls_module._update_one("o/r", int_num=1, str_token="", list_commands=["x"]) is None


def test_an_unusable_roster_requests_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A roster that cannot be loaded reads as nobody to ask, never as a crash."""
    monkeypatch.setattr(
        cls_module.check_review_threads, "load_roster", mock.Mock(side_effect=RuntimeError("x"))
    )
    assert cls_module._roster_commands() == []
