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
