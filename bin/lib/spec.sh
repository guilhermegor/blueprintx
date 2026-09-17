#!/bin/bash
#
# lib/spec.sh
#
# Named-key answer spec for unattended scaffolds (blueprintx#481).
#
# The problem: every scaffold prompt is answered by STDIN POSITION (`printf
# 'n\n%.0s' {1..12} | bash scaffold.sh ...`). Adding a prompt anywhere in a
# scaffold script silently shifts every answer after it to the wrong
# question — nothing fails loudly, it just answers a different question
# than the one asked.
#
# The fix: a spec file is a shell-sourceable KEY=value list (same convention
# as templates/*/skeleton.meta — grep|cut, no new parser dependency) that
# answers each prompt by NAME. A name does not move when a new prompt is
# inserted; a stdin position does.
#
# bin/scaffold/python_*.sh still read positional stdin at each `read -r -p`
# call site — those scripts are owned by other in-flight PRs (#503/#509)
# and are not edited here. So THIS file is the one seam that knows, per
# skeleton, which named key answers which prompt and in what stdin position
# that prompt currently sits: spec_stdin_for_skeleton() is the translator
# from a stable name to the position it happens to occupy today. When a
# scaffold script gains a new prompt, this is the one place that needs a
# new line — never every stored answer string in every caller.
#
# Two prompts already accept an environment override instead of reading
# stdin (GITHUB_USERNAME in resolve_github_username; MULTI_PIPELINE_OPTIN in
# the MVC tiers' prompt_pipeline_intent) — callers should set those directly
# rather than routing them through stdin.
#
# Scope note (issue #481 comment): publish/registry keys (publish_pypi,
# publish_test_pypi, consume_private) answer the scaffold's EXISTING yes/no
# gate only — they select which release workflow the scaffold already ships.
# Any FUTURE spec key that performs real publishing or registry
# verification must delegate to the `publishprobe` tool (greenfield#26)
# instead of reimplementing credentials or publishing here.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "lib/spec.sh is meant to be sourced, not executed." >&2
    exit 1
fi
if [ -n "${_BX_SPEC_LOADED:-}" ]; then
    return 0
fi
_BX_SPEC_LOADED=1

#
# Usage: spec_get <file> <key> [default]
#
# One KEY=value pair per line, '#' comments and blanks ignored — the same
# shape as skeleton.meta. A missing file or missing key resolves to
# <default> (empty string if omitted), never an error: an absent spec is a
# valid spec (every key takes its documented default).

spec_get() {
    local file="$1" key="$2" default="${3:-}"
    local value=""
    if [ -n "$file" ] && [ -f "$file" ]; then
        value=$(grep "^${key}=" "$file" | tail -n1 | cut -d= -f2-)
    fi
    printf '%s' "${value:-$default}"
}

#
# Usage: spec_yn <file> <key> <default: y|n>
#
# Normalises a spec value to a single lowercase y/n, the alphabet every
# scaffold prompt's `case` statement already matches against.

spec_yn() {
    local file="$1" key="$2" default="${3:-n}"
    local value
    value="$(spec_get "$file" "$key" "$default")"
    case "$value" in
        y | Y | yes | YES | true | TRUE) echo y ;;
        *) echo n ;;
    esac
}

# Per-prompt stdin emitters. Each echoes exactly the line(s) the matching
# `read -r -p` call(s) in bin/scaffold/python_*.sh consume, in order —
# nothing more, since a scaffold script stops reading once a `y` branch's
# own reads are satisfied. Shared verbatim across every tier that has the
# same prompt (DDD + MVC share five of these; only the composition in
# spec_stdin_for_skeleton differs).

_spec_answer_docker_compose() {
    local file="$1" ans
    ans="$(spec_yn "$file" docker_compose n)"
    echo "$ans"
    [ "$ans" = y ] && spec_get "$file" docker_db_backend postgresql
}

_spec_answer_storage() {
    spec_yn "$1" storage n
}

_spec_answer_data_dir() {
    local file="$1" ans
    ans="$(spec_yn "$file" data_dir n)"
    echo "$ans"
    if [ "$ans" = y ]; then
        spec_get "$file" data_dir_base logs
        spec_yn "$file" data_dir_dated n
    fi
}

_spec_answer_webhook() {
    local file="$1" ans
    ans="$(spec_yn "$file" webhook n)"
    echo "$ans"
    [ "$ans" = y ] && spec_get "$file" webhook_platform teams
}

_spec_answer_otel() {
    spec_yn "$1" otel n
}

_spec_answer_email() {
    local file="$1" ans
    ans="$(spec_yn "$file" email n)"
    echo "$ans"
    [ "$ans" = y ] && spec_get "$file" email_backend outlook
}

_spec_answer_pipeline_intent() {
    spec_yn "$1" pipeline_intent n
}

_spec_answer_env_wise() {
    spec_yn "$1" env_wise_config n
}

_spec_answer_review_bot() {
    # scaffold_prompt_review_bot_roster (bin/lib/scaffold_git_remote.sh) asks
    # "do you have a review bot" as [Y/n] — "n" is the one that turns the
    # roster OFF, so the emitted line is the raw y/n answer, not a polarity
    # flip on review_bot_roster's own y=include/n=exclude meaning.
    spec_yn "$1" review_bot_roster n
}

_spec_answer_git_remote() {
    # "n" here (no GitHub remote) is what every unattended/CI run wants:
    # the scaffold falls back to the offline git workflow and skips branch
    # protection entirely. A spec asking for "y" would need a real gh CLI
    # session and is out of scope for this seam.
    spec_yn "$1" git_remote n
}

_spec_answer_logs() {
    spec_yn "$1" logs n
}

_spec_answer_publish_targets() {
    local file="$1"
    spec_yn "$file" publish_pypi y
    spec_yn "$file" publish_test_pypi y
    spec_yn "$file" consume_private n
}

#
# Usage: spec_skeleton_supported <skeleton>
#
# True only for a skeleton with a named-key prompt map below. Named-key
# support ships incrementally, tier by tier — see docs/spec-answers.md for
# what is mapped and what remains a follow-up.

spec_skeleton_supported() {
    case "$1" in
        ddd-service-native-db | ddd-service-orm-db | \
            mvc-service-native-db | mvc-service-orm-db | lib-minimal)
            return 0
            ;;
        *) return 1 ;;
    esac
}

#
# Usage: spec_stdin_for_skeleton <skeleton> <file>
#
# Emits, in the exact order the scaffold script's `read` calls consume them,
# the full stdin stream a named-key spec resolves to for one skeleton. Pipe
# straight into the scaffold script:
#   spec_stdin_for_skeleton "$skeleton" "$spec_file" | bash "$scaffold_script" ...

spec_stdin_for_skeleton() {
    local skeleton="$1" file="$2"
    case "$skeleton" in
        ddd-service-native-db | ddd-service-orm-db)
            _spec_answer_docker_compose "$file"
            _spec_answer_storage "$file"
            _spec_answer_data_dir "$file"
            _spec_answer_webhook "$file"
            _spec_answer_otel "$file"
            _spec_answer_email "$file"
            _spec_answer_env_wise "$file"
            _spec_answer_review_bot "$file"
            _spec_answer_git_remote "$file"
            ;;
        mvc-service-native-db | mvc-service-orm-db)
            _spec_answer_docker_compose "$file"
            _spec_answer_data_dir "$file"
            _spec_answer_webhook "$file"
            _spec_answer_otel "$file"
            _spec_answer_email "$file"
            _spec_answer_pipeline_intent "$file"
            _spec_answer_env_wise "$file"
            _spec_answer_review_bot "$file"
            _spec_answer_git_remote "$file"
            ;;
        lib-minimal)
            _spec_answer_logs "$file"
            _spec_answer_docker_compose "$file"
            _spec_answer_publish_targets "$file"
            _spec_answer_review_bot "$file"
            _spec_answer_git_remote "$file"
            ;;
        *)
            return 1
            ;;
    esac
}

#
# Usage: spec_describe_skeleton <skeleton> <file>
#
# Prints "key=resolved_value" for every named key that skeleton reads — the
# --spec --dry-run report (issue #481: "print resolved answers"). Prints
# every key a tier CAN read, not only the ones a sub-branch would reach, so
# a spec author can see exactly what changing any one key would resolve to.

spec_describe_skeleton() {
    local skeleton="$1" file="$2"
    local -a keys=()
    case "$skeleton" in
        ddd-service-native-db | ddd-service-orm-db)
            keys=(docker_compose:n docker_db_backend:postgresql storage:n \
                data_dir:n data_dir_base:logs data_dir_dated:n \
                webhook:n webhook_platform:teams otel:n \
                email:n email_backend:outlook env_wise_config:n \
                review_bot_roster:n git_remote:n)
            ;;
        mvc-service-native-db | mvc-service-orm-db)
            keys=(docker_compose:n docker_db_backend:postgresql \
                data_dir:n data_dir_base:logs data_dir_dated:n \
                webhook:n webhook_platform:teams otel:n \
                email:n email_backend:outlook pipeline_intent:n \
                env_wise_config:n review_bot_roster:n git_remote:n)
            ;;
        lib-minimal)
            keys=(logs:n docker_compose:n docker_db_backend:postgresql \
                publish_pypi:y publish_test_pypi:y consume_private:n \
                review_bot_roster:n git_remote:n)
            ;;
        *)
            echo "no named-key prompt map for '$skeleton' yet" >&2
            return 1
            ;;
    esac
    local entry key default
    for entry in "${keys[@]}"; do
        key="${entry%%:*}"
        default="${entry#*:}"
        printf '%s=%s\n' "$key" "$(spec_get "$file" "$key" "$default")"
    done
}
