#!/bin/bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "lib/spec.sh is meant to be sourced, not executed." >&2
    exit 1
fi
if [ -n "${_BX_SPEC_LOADED:-}" ]; then
    return 0
fi
_BX_SPEC_LOADED=1

spec_get() {
    local file="$1" key="$2" default="${3:-}"
    local value=""
    if [ -n "$file" ] && [ -f "$file" ]; then
        value=$(grep "^${key}=" "$file" | tail -n1 | cut -d= -f2-) || true
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"
    fi
    printf '%s' "${value:-$default}"
}

spec_yn() {
    local file="$1" key="$2" default="${3:-n}"
    local value
    value="$(spec_get "$file" "$key" "$default")"
    case "$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')" in
        y | yes | true) echo y ;;
        n | no | false) echo n ;;
        *)
            echo "spec: '$key' must be y/yes/true or n/no/false, got '$value'" >&2
            return 1
            ;;
    esac
}

_spec_answer_docker_compose() {
    local file="$1" ans
    ans="$(spec_yn "$file" docker_compose n)"
    echo "$ans"
    [ "$ans" = y ] && echo "$(spec_get "$file" docker_db_backend postgresql)" || true
}

_spec_answer_storage() {
    spec_yn "$1" storage n
}

_spec_answer_data_dir() {
    local file="$1" ans
    ans="$(spec_yn "$file" data_dir n)"
    echo "$ans"
    if [ "$ans" = y ]; then
        echo "$(spec_get "$file" data_dir_base logs)"
        spec_yn "$file" data_dir_dated n
    fi
}

_spec_answer_webhook() {
    local file="$1" ans
    ans="$(spec_yn "$file" webhook n)"
    echo "$ans"
    [ "$ans" = y ] && echo "$(spec_get "$file" webhook_platform teams)" || true
}

_spec_answer_otel() {
    spec_yn "$1" otel n
}

_spec_answer_email() {
    local file="$1" ans
    ans="$(spec_yn "$file" email n)"
    echo "$ans"
    [ "$ans" = y ] && echo "$(spec_get "$file" email_backend outlook)" || true
}

_spec_answer_pipeline_intent() {
    spec_yn "$1" pipeline_intent n
}

_spec_answer_env_wise() {
    spec_yn "$1" env_wise_config n
}

_spec_answer_review_bot() {
    spec_yn "$1" review_bot_roster n
}

_spec_answer_git_remote() {
    spec_yn "$1" git_remote n
}

_spec_answer_ventoy_options() {
    local file="$1"
    spec_yn "$file" include_windows y
    spec_yn "$file" include_android y
    spec_get "$file" persistence_size_mb 4096
    echo
}

_spec_validate_ventoy() {
    local skeleton="$1" file="$2" str_size
    [ "$skeleton" = ventoy-usb ] || return 0
    str_size="$(spec_get "$file" persistence_size_mb 4096)"
    if ! [[ "$str_size" =~ ^[0-9]+$ ]] || [ "$str_size" -lt 1024 ] || [ $((str_size % 1024)) -ne 0 ]; then
        echo "spec: 'persistence_size_mb' must be a multiple of 1024 (>= 1024), got '$str_size'" >&2
        return 1
    fi
}

_spec_visibility_choice() {
    case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
        public) echo 1 ;;
        private) echo 2 ;;
        *) return 1 ;;
    esac
}

_spec_answer_create_repo() {
    local file="$1" ans
    [ "$(spec_yn "$file" git_remote n)" = y ] || return 0
    ans="$(spec_yn "$file" create_repo n)"
    echo "$ans"
    [ "$ans" = y ] || return 0
    _spec_visibility_choice "$(spec_get "$file" repo_visibility private)"
    spec_yn "$file" kanban n
    ans="$(spec_yn "$file" protect_branch n)"
    echo "$ans"
    [ "$ans" = y ] && spec_yn "$file" human_reviewers n || true
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

_SPEC_SUPPORTED_SKELETONS="ddd-service-native-db ddd-service-orm-db api-service-native-db mvc-service-native-db mvc-service-orm-db lib-minimal ts-lib ventoy-usb"

spec_skeleton_supported() {
    local str_name
    for str_name in $_SPEC_SUPPORTED_SKELETONS; do
        [ "$1" = "$str_name" ] && return 0
    done
    return 1
}

spec_supported_skeletons() {
    printf '%s' "${_SPEC_SUPPORTED_SKELETONS// /, }"
}

spec_stdin_for_skeleton() {
    local skeleton="$1" file="$2"
    spec_validate_answers "$skeleton" "$file" || return 1
    case "$skeleton" in
        ddd-service-native-db | ddd-service-orm-db | api-service-native-db)
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
            _spec_answer_otel "$file"
            _spec_answer_docker_compose "$file"
            _spec_answer_publish_targets "$file"
            _spec_answer_review_bot "$file"
            _spec_answer_git_remote "$file"
            ;;
        ts-lib)
            _spec_answer_review_bot "$file"
            _spec_answer_otel "$file"
            _spec_answer_git_remote "$file"
            _spec_answer_create_repo "$file"
            ;;
        ventoy-usb)
            _spec_answer_ventoy_options "$file"
            _spec_answer_review_bot "$file"
            _spec_answer_git_remote "$file"
            _spec_answer_create_repo "$file"
            ;;
        *)
            return 1
            ;;
    esac
}

_spec_key_map() {
    local skeleton="$1"
    local -a keys=()
    case "$skeleton" in
        ddd-service-native-db | ddd-service-orm-db | api-service-native-db)
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
            keys=(logs:n otel:n docker_compose:n docker_db_backend:postgresql \
                publish_pypi:y publish_test_pypi:y consume_private:n \
                review_bot_roster:n git_remote:n)
            ;;
        ts-lib)
            keys=(review_bot_roster:n otel:n git_remote:n create_repo:n \
                repo_visibility:private kanban:n protect_branch:n human_reviewers:n)
            ;;
        ventoy-usb)
            keys=(include_windows:y include_android:y persistence_size_mb:4096 \
                review_bot_roster:n git_remote:n create_repo:n repo_visibility:private \
                kanban:n protect_branch:n)
            ;;
        *)
            echo "no named-key prompt map for '$skeleton' yet" >&2
            return 1
            ;;
    esac
    printf '%s\n' "${keys[@]}"
}

spec_validate_answers() {
    local skeleton="$1" file="$2"
    local map entry key default int_bad=0
    map="$(_spec_key_map "$skeleton")" || return 1
    while IFS= read -r entry; do
        key="${entry%%:*}"
        default="${entry#*:}"
        case "$default" in
            y | n) spec_yn "$file" "$key" "$default" >/dev/null || int_bad=1 ;;
        esac
    done <<<"$map"
    _spec_validate_remote "$skeleton" "$file" || int_bad=1
    _spec_validate_ventoy "$skeleton" "$file" || int_bad=1
    return "$int_bad"
}

spec_creates_repo() {
    grep -q '^create_repo:' <<<"$(_spec_key_map "$1" 2>/dev/null)" || return 1
    [ "$(spec_yn "$2" git_remote n 2>/dev/null)" = y ] \
        && [ "$(spec_yn "$2" create_repo n 2>/dev/null)" = y ]
}

_spec_validate_remote() {
    local skeleton="$1" file="$2" str_vis int_bad=0
    grep -q '^create_repo:' <<<"$(_spec_key_map "$skeleton")" || return 0
    str_vis="$(spec_get "$file" repo_visibility private)"
    if ! _spec_visibility_choice "$str_vis" >/dev/null; then
        echo "spec: 'repo_visibility' must be public or private, got '$str_vis'" >&2
        int_bad=1
    fi
    if [ "$(spec_yn "$file" create_repo n 2>/dev/null)" = y ] \
        && [ "$(spec_yn "$file" git_remote n 2>/dev/null)" != y ]; then
        echo "spec: 'create_repo' is y but 'git_remote' is not: set git_remote=y too" >&2
        int_bad=1
    fi
    return "$int_bad"
}

spec_repo_slug() {
    printf '%s/%s' "$(spec_get "$1" github_username "${GITHUB_USERNAME:-<gh-user>}")" "$2"
}

spec_preflight_create_repo() {
    local skeleton="$1" file="$2" str_owner str_slug str_err
    spec_creates_repo "$skeleton" "$file" || return 0
    if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
        echo "spec: create_repo=y needs an authenticated gh CLI (gh auth login)" >&2
        return 1
    fi
    str_owner="$(spec_get "$file" github_username "${GITHUB_USERNAME:-}")"
    [ -n "$str_owner" ] || str_owner="$(gh api user -q .login 2>/dev/null)" || true
    if [ -z "$str_owner" ]; then
        echo "spec: create_repo=y needs 'github_username' (gh could not tell who you are)" >&2
        return 1
    fi
    str_slug="$str_owner/$3"
    if str_err="$(gh repo view "$str_slug" 2>&1 >/dev/null)"; then
        echo "spec: create_repo=y but GitHub repo '$str_slug' already exists" >&2
        return 1
    fi
    if [[ "$str_err" != *"Could not resolve to a Repository"* ]]; then
        echo "spec: could not check whether '$str_slug' exists (not a not-found error): $str_err" >&2
        return 1
    fi
    GITHUB_USERNAME="$str_owner"
}

spec_describe_skeleton() {
    local skeleton="$1" file="$2"
    local str_map str_entry
    str_map="$(_spec_key_map "$skeleton")" || return 1
    while IFS= read -r str_entry; do
        printf '%s=%s\n' "${str_entry%%:*}" "$(spec_get "$file" "${str_entry%%:*}" "${str_entry#*:}")"
    done <<<"$str_map"
}
