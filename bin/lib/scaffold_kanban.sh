#!/usr/bin/env bash

SCAFFOLD_KANBAN_STATUS_OPTIONS="Blocked|RED|Cannot start: a named blocker is unfinished
Backlog|GREEN|This item hasn't been started
Ready|BLUE|This is ready to be picked up
In progress|YELLOW|This is actively being worked on
In review|PURPLE|This item is in review
Done|ORANGE|This has been completed"

SCAFFOLD_HOUSE_LABELS="type:task|0E8A16|A unit of work
type:research|1D76DB|A question to answer, not code to ship
type:grilling|5319E7|A design interview before any code
hitl|FBCA04|Needs a human in the loop
afk|C2E0C6|Safe to run unattended
oracle:strong|0052CC|Verifiable by a strong oracle (tests, types, gates)
oracle:weak|BFD4F2|No strong oracle; needs review
do-not-merge|B60205|Hold: must not be merged yet
state:blocked|D93F0B|Cannot start: see the Blocked by line"

scaffold_kanban_scope_hint() {
	if grep -qiE 'scope|403|insufficient|read:project' <<<"$1"; then
		print_status "warning" "The gh token lacks the 'project' scope — run: gh auth refresh -s project" >&2
	else
		print_status "warning" "Could not create the kanban board: $1" >&2
	fi
}

scaffold_create_house_labels() {
	local str_slug="$1" str_name str_colour str_desc str_line int_failed=0
	while IFS='|' read -r str_name str_colour str_desc; do
		gh label create "$str_name" --repo "$str_slug" --color "$str_colour" \
			--description "$str_desc" --force >/dev/null 2>&1 ||
			{ int_failed=$((int_failed + 1)); str_line="$str_name"; }
	done <<<"$SCAFFOLD_HOUSE_LABELS"
	if [ "$int_failed" -eq 0 ]; then
		print_status "success" "House labels created on ${str_slug}"
	else
		print_status "warning" "${int_failed} house label(s) could not be created on ${str_slug} (last: ${str_line})"
	fi
}

scaffold_kanban_visibility() {
	local str_slug="$1" str_choice str_private
	prompt_read str_choice "$(prompt_sub "Project visibility [1] same as repo (default)  [2] public  [3] private: ")"
	case "$str_choice" in
	2) printf 'PUBLIC' ;;
	3) printf 'PRIVATE' ;;
	*)
		str_private="$(gh repo view "$str_slug" --json isPrivate --jq '.isPrivate' 2>/dev/null)" || str_private=""
		[ "$str_private" = "true" ] && printf 'PRIVATE' || printf 'PUBLIC'
		;;
	esac
}

scaffold_kanban_find() {
	local str_owner="$1" str_title="$2" str_numbers int_count str_err
	str_title="${str_title//\\/\\\\}"
	str_title="${str_title//\"/\\\"}"
	str_err="$(mktemp)"
	str_numbers="$(gh project list --owner "$str_owner" --format json \
		--jq ".projects[] | select(.title==\"${str_title}\") | .number" 2>"$str_err")" || {
		scaffold_kanban_scope_hint "$(cat "$str_err")"
		rm -f "$str_err"
		return 1
	}
	rm -f "$str_err"
	int_count="$(grep -c . <<<"$str_numbers" || true)"
	[ "$int_count" -le 1 ] || return 2
	printf '%s' "$str_numbers"
}

scaffold_kanban_option_id() {
	local str_existing="$1" str_want="$2" str_id str_name
	while IFS='|' read -r str_id str_name; do
		[ "$str_name" = "$str_want" ] && { printf '%s' "$str_id"; return 0; }
	done <<<"$str_existing"
	return 0
}

scaffold_kanban_status_options() {
	local str_owner="$1" str_number="$2" str_field str_existing str_json str_name str_colour str_desc str_id str_idjson str_sep=""
	str_field="$(gh project field-list "$str_number" --owner "$str_owner" --format json \
		--jq '.fields[] | select(.name=="Status") | .id' 2>/dev/null | head -n1)"
	[ -n "$str_field" ] || return 1
	str_existing="$(gh project field-list "$str_number" --owner "$str_owner" --format json \
		--jq '.fields[] | select(.name=="Status") | .options[]? | "\(.id)|\(.name)"' 2>/dev/null)" || str_existing=""
	while IFS='|' read -r str_name str_colour str_desc; do
		str_id="$(scaffold_kanban_option_id "$str_existing" "$str_name")"
		str_idjson=""
		[ -z "$str_id" ] || str_idjson="\"id\":\"${str_id}\","
		str_json+="${str_sep}{${str_idjson}\"name\":\"${str_name}\",\"color\":\"${str_colour}\",\"description\":\"${str_desc}\"}"
		str_sep=","
	done <<<"$SCAFFOLD_KANBAN_STATUS_OPTIONS"
	printf '{"query":"mutation($f:ID!,$o:[ProjectV2SingleSelectFieldOptionInput!]!){updateProjectV2Field(input:{fieldId:$f,singleSelectOptions:$o}){clientMutationId}}","variables":{"f":"%s","o":[%s]}}' \
		"$str_field" "$str_json" | gh api graphql --input - >/dev/null 2>&1
}

scaffold_kanban_fields() {
	local str_owner="$1" str_number="$2" int_failed=0 str_spec str_name str_type str_opts
	while IFS='|' read -r str_name str_type str_opts; do
		if [ -n "$str_opts" ]; then
			gh project field-create "$str_number" --owner "$str_owner" --name "$str_name" \
				--data-type "$str_type" --single-select-options "$str_opts" >/dev/null 2>&1 ||
				{ int_failed=1; str_spec="$str_name"; }
		else
			gh project field-create "$str_number" --owner "$str_owner" --name "$str_name" \
				--data-type "$str_type" >/dev/null 2>&1 || { int_failed=1; str_spec="$str_name"; }
		fi
	done <<<"Priority|SINGLE_SELECT|P0,P1,P2
Size|SINGLE_SELECT|XS,S,M,L,XL
Estimate|NUMBER|
Start date|DATE|
Target date|DATE|
Points|NUMBER|
Blocker|SINGLE_SELECT|Internal,External,Decision"
	[ "$int_failed" -eq 0 ] || print_status "warning" "A project field could not be created (last failure: ${str_spec})"
}

scaffold_kanban_url() {
	local str_owner="$1" str_number="$2" str_kind str_path="users"
	str_kind="$(gh api "users/${str_owner}" --jq '.type' 2>/dev/null)" || str_kind=""
	[ "$str_kind" = "Organization" ] && str_path="orgs"
	printf 'https://github.com/%s/%s/projects/%s' "$str_path" "$str_owner" "$str_number"
}

scaffold_kanban_create() {
	local str_slug="$1" str_owner="$2" str_title="$3" str_vis="$4" str_number str_err
	str_err="$(mktemp)"
	str_number="$(gh project create --owner "$str_owner" --title "$str_title" --format json \
		--jq '.number' 2>"$str_err")" || {
		scaffold_kanban_scope_hint "$(cat "$str_err")"
		rm -f "$str_err"
		return 1
	}
	rm -f "$str_err"
	gh project edit "$str_number" --owner "$str_owner" --visibility "$str_vis" >/dev/null 2>&1 ||
		print_status "warning" "Could not set the board's visibility to ${str_vis}"
	gh project link "$str_number" --owner "$str_owner" --repo "$str_slug" >/dev/null 2>&1 ||
		print_status "warning" "Could not link the board to ${str_slug}"
	scaffold_kanban_status_options "$str_owner" "$str_number" ||
		print_status "warning" "Could not set the Status options (Blocked / Backlog / Ready / In progress / In review / Done)"
	scaffold_kanban_fields "$str_owner" "$str_number"
	print_status "success" "Created '${str_title}' (${str_vis}), linked to ${str_slug}"
	print_status "info" "No public API for views or built-in workflows — enable auto-add and item-closed -> Done at: $(scaffold_kanban_url "$str_owner" "$str_number")/workflows"
}

scaffold_kanban_setup() {
	local str_slug str_owner str_title str_answer str_vis str_found int_rc=0
	str_slug="$(scaffold_repo_slug)"
	str_owner="${str_slug%%/*}"
	str_title="${PROJECT_NAME} kanban"
	command -v gh >/dev/null 2>&1 || return 0

	scaffold_create_house_labels "$str_slug"

	str_answer=n
	if prompt_can_read; then
		read -r -p "$(prompt_main "Create a '${str_title}' GitHub Project linked to this repo? [Y/n]: ")" str_answer || str_answer=n
	else
		prompt_warn_default "$(prompt_main "Create a '${str_title}' GitHub Project linked to this repo? [Y/n]: ")" "'n'"
	fi
	case "$str_answer" in
	n | N)
		print_status "info" "Skipped the kanban board"
		return 0
		;;
	esac

	str_found="$(scaffold_kanban_find "$str_owner" "$str_title")" || int_rc=$?
	if [ "$int_rc" -eq 2 ]; then
		print_status "warning" "More than one '${str_title}' project exists — not guessing which; resolve it by hand"
		return 0
	fi
	[ "$int_rc" -eq 0 ] || return 0
	if [ -n "$str_found" ]; then
		print_status "info" "'${str_title}' already exists (#${str_found}) — skipping"
		return 0
	fi

	str_vis="$(scaffold_kanban_visibility "$str_slug")"
	scaffold_kanban_create "$str_slug" "$str_owner" "$str_title" "$str_vis" || true
	return 0
}
