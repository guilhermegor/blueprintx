#!/usr/bin/env bash

scaffold_stamp_provenance() {
	local str_tier="$1"
	local str_project_path="$2"

	local str_version=""
	local str_commit=unknown
	if [[ -e "$BLUEPRINTX_ROOT/.git" ]]; then
		str_version="$(git -C "$BLUEPRINTX_ROOT" describe --tags --always 2>/dev/null || true)"
		str_commit="$(git -C "$BLUEPRINTX_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
	fi
	[[ -n "$str_version" ]] || str_version="$(sed -n 's/^BLUEPRINTX_VERSION="\(.*\)"$/\1/p' "$BLUEPRINTX_ROOT/bin/blueprintx.sh" 2>/dev/null || true)"
	[[ -n "$str_version" ]] || str_version=unknown
	local str_scaffolded_at
	str_scaffolded_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

	cat >"$str_project_path/.blueprintx-provenance.yaml" <<-EOF
	tier: ${str_tier}
	review_bot_roster: $([[ "${INCLUDE_REVIEW_BOT_ROSTER:-true}" == "true" ]] && echo true || echo false)
	blueprintx_version: ${str_version#v}
	blueprintx_commit: ${str_commit}
	scaffolded_at: ${str_scaffolded_at}
	EOF
}

scaffold_dry_cp() {
	local str_project_path="$1"
	shift
	while [[ "${1:-}" == -* ]]; do shift; done
	local str_dst="${!#}" str_src str_kind str_rel_dst
	for str_src in "${@:1:$#-1}"; do
		str_rel_dst="${str_dst#"$str_project_path"}"
		if [[ $# -gt 2 || "$str_dst" == */ ]]; then
			str_rel_dst="${str_rel_dst%/}/${str_src##*/}"
		fi
		str_kind="file"
		[[ -d "$str_src" ]] && str_kind=dir
		str_src="${str_src%/.}"
		printf 'COPY\t%s\t%s\t%s\n' "$str_kind" "${str_src#"$BLUEPRINTX_ROOT"/}" "${str_rel_dst#/}"
	done
}

scaffold_dry_rm() {
	local str_project_path="$1" str_arg
	shift
	for str_arg in "$@"; do
		[[ "$str_arg" == -* ]] && continue
		printf 'RM\t%s\n' "${str_arg#"$str_project_path"/}"
	done
}

scaffold_dry_run() {
	local str_fn="$1" str_project_path int_status
	str_project_path="$(mktemp -d)"
	(
		set -e
		print_status() { :; }
		envsubst() { :; }
		mkdir() { :; }
		touch() { :; }
		chmod() { :; }
		cp() { scaffold_dry_cp "$str_project_path" "$@"; }
		rm() { scaffold_dry_rm "$str_project_path" "$@"; }
		"$str_fn" "$str_project_path"
	)
	int_status=$?
	rm -rf "$str_project_path"
	return "$int_status"
}
