#!/bin/bash
# Negative control for the `origin` verification in bin/lib/scaffold_git_remote.sh (#212).
#
# The dangerous direction here is a FALSE PASS: scaffold_add_git_remote returning 0 for a
# remote pointing at someone else's repository, after which `gh repo create --push`, the
# follow-up push and branch protection all write there. So the test that matters is the one
# asserting a MISMATCH fails — a suite that only proves the happy path would have passed
# against the very code this replaced.
#
# Usage:  bash bin/ci/check_git_remote_guard.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=bin/lib/common.sh
source "$REPO_ROOT/bin/lib/common.sh"
# shellcheck source=bin/lib/scaffold_git_remote.sh
source "$REPO_ROOT/bin/lib/scaffold_git_remote.sh"

GITHUB_USERNAME="octocat"
DEFAULT_GITHUB_USERNAME="octocat"
PROJECT_NAME="widget"
int_failures=0

expect_slug() {
    local str_url="$1" str_want="$2" str_got
    str_got="$(scaffold_remote_slug "$str_url")"
    if [ "$str_got" != "$str_want" ]; then
        print_status "error" "scaffold_remote_slug '$str_url' → '$str_got' (expected '$str_want')"
        int_failures=$((int_failures + 1))
    fi
}

make_repo_with_origin() {
    # Prints the path of a fresh repo whose origin is $1 (empty = no origin).
    local str_url="${1:-}" str_path
    str_path="$(mktemp -d)"
    git -C "$str_path" init -q -b main
    if [ -n "$str_url" ]; then
        git -C "$str_path" remote add origin "$str_url"
    fi
    printf '%s' "$str_path"
}

expect_add_remote() {
    # $1 = existing origin URL (empty for none), $2 = expected outcome (pass|fail)
    #
    # ⚠️ The exit status is NOT the whole assertion. A pass that added no remote, or a fail
    # that rewrote the existing one, would both slip past a status-only check — and "the
    # guard refused but retargeted origin anyway" is the failure mode with teeth. So a pass
    # must leave origin resolving to OUR slug, and a fail must leave it untouched.
    local str_url="$1" str_want="$2" str_path str_got="pass" str_after
    str_path="$(make_repo_with_origin "$str_url")"
    scaffold_add_git_remote "$str_path" >/dev/null 2>&1 || str_got="fail"
    str_after="$(git -C "$str_path" remote get-url origin 2>/dev/null || true)"
    rm -rf "$str_path"

    if [ "$str_got" != "$str_want" ]; then
        print_status "error" \
            "scaffold_add_git_remote with origin='${str_url:-<none>}' → $str_got (expected $str_want)"
        int_failures=$((int_failures + 1))
        return 0
    fi
    if [ "$str_want" = "pass" ] && [ "$(scaffold_remote_slug "$str_after")" != "octocat/widget" ]; then
        print_status "error" \
            "passed with origin='${str_url:-<none>}' but origin is now '${str_after:-<none>}'"
        int_failures=$((int_failures + 1))
    fi
    if [ "$str_want" = "fail" ] && [ "$str_after" != "$str_url" ]; then
        print_status "error" \
            "refused origin='${str_url}' but rewrote it to '${str_after:-<none>}'"
        int_failures=$((int_failures + 1))
    fi
}

expect_push_url_mismatch() {
    # A remote whose FETCH url is ours but whose PUSH url is not. `git remote get-url origin`
    # returns only the fetch URL, so a fetch-only check waves this through — and it is the
    # push that writes to the other repository.
    local str_path str_got="pass"
    str_path="$(make_repo_with_origin "git@github.com:octocat/widget.git")"
    git -C "$str_path" remote set-url --push origin "git@github.com:someone-else/widget.git"
    scaffold_add_git_remote "$str_path" >/dev/null 2>&1 || str_got="fail"
    rm -rf "$str_path"
    if [ "$str_got" != "fail" ]; then
        print_status "error" \
            "a matching fetch URL with a MISMATCHED push URL was accepted — pushes would go elsewhere"
        int_failures=$((int_failures + 1))
    fi
}

expect_absent_pat_does_not_abort() {
    # Scaffolding must not die because an OPTIONAL reviewer integration has no credential.
    # The scaffolds run under `set -e`, so a non-zero here would abort a project mid-creation
    # over a secret — trading a red check on a future PR for a broken scaffold today.
    local int_rc=0
    ( unset GH_PAT_REVIEW_TRIGGER; scaffold_set_review_trigger_secret >/dev/null 2>&1 ) || int_rc=$?
    if [ "$int_rc" -ne 0 ]; then
        print_status "error" \
            "scaffold_set_review_trigger_secret returned $int_rc with no PAT — that aborts the scaffold"
        int_failures=$((int_failures + 1))
    fi
}

main() {
    # The same repository, spelled four ways, must reduce to one slug — otherwise the
    # guard would reject a remote the user set up correctly and be disabled by the first
    # person it inconveniences.
    expect_slug "git@github.com:octocat/widget.git" "octocat/widget"
    expect_slug "https://github.com/octocat/widget" "octocat/widget"
    expect_slug "https://github.com/octocat/widget.git" "octocat/widget"
    expect_slug "ssh://git@github.com/octocat/widget.git" "octocat/widget"
    expect_slug "ssh://git@github.com/octocat/widget" "octocat/widget"
    # A non-GitHub remote reduces to itself, so it can never equal an owner/repo slug.
    expect_slug "git@gitlab.com:octocat/widget.git" "git@gitlab.com:octocat/widget"
    # 🔴 HOST CONFUSION — the bypasses the first implementation accepted. `github.com` must be
    # matched as a HOST, not as a substring: cutting at the last occurrence reduced the first
    # of these to `octocat/widget` and the guard waved an arbitrary host through.
    expect_slug "https://evil.example/github.com/octocat/widget.git" \
        "https://evil.example/github.com/octocat/widget"
    expect_slug "https://github.com.evil.com/octocat/widget" \
        "https://github.com.evil.com/octocat/widget"
    expect_slug "https://github.com/octocat/widget/extra" "octocat/widget/extra"

    expect_add_remote "" "pass"                                      # no origin → add it
    expect_add_remote "git@github.com:octocat/widget.git" "pass"     # same repo, ssh
    expect_add_remote "https://github.com/octocat/widget" "pass"     # same repo, https
    expect_add_remote "git@github.com:someone-else/widget.git" "fail"  # ← the one with teeth
    expect_add_remote "git@github.com:octocat/other-project.git" "fail"
    expect_add_remote "git@gitlab.com:octocat/widget.git" "fail"
    expect_add_remote "https://evil.example/github.com/octocat/widget.git" "fail"
    expect_add_remote "https://github.com.evil.com/octocat/widget.git" "fail"
    expect_push_url_mismatch
    expect_absent_pat_does_not_abort

    if [ "$int_failures" -ne 0 ]; then
        print_status "error" "$int_failures git-remote guard assertion(s) failed"
        exit 1
    fi
    print_status "success" "origin verification refuses mismatched remotes and accepts every spelling of the right one"
}

main "$@"
