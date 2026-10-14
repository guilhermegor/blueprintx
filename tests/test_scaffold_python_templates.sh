#!/bin/bash

set -uo pipefail
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
int_failures=0

pass() { echo "ok: $1"; }
fail() {
	echo "FAIL ($1): $2"
	int_failures=$((int_failures + 1))
}

make_root() {
	local path_root="$1"
	mkdir -p "$path_root/bin/lib"
	cp "$REPO_ROOT/bin/lib/scaffold_provenance.sh" "$path_root/bin/lib/"
	echo 'BLUEPRINTX_VERSION="9.9.9"' >"$path_root/bin/blueprintx.sh"
}

stamp() {
	local path_root="$1" path_project="$2" str_tier="$3"
	mkdir -p "$path_project"
	BLUEPRINTX_ROOT="$path_root" bash -c 'source "$BLUEPRINTX_ROOT/bin/lib/scaffold_provenance.sh"; scaffold_stamp_provenance "$1" "$2"' _ "$str_tier" "$path_project"
}

seed_repo() {
	git -C "$1" init -q -b main
	git -C "$1" add -A
	git -C "$1" -c user.email=t@example.com -c user.name=T commit -q -m "chore: seed"
	git -C "$1" tag "$2"
}

test_packaged_install_nested_in_a_foreign_repo_uses_the_literal() {
	local path_outer="$WORK_DIR/outer"
	make_root "$path_outer/pkg"
	seed_repo "$path_outer" v1.2.3
	stamp "$path_outer/pkg" "$WORK_DIR/p1" mvc-service-native-db
	if grep -qx 'blueprintx_version: 9.9.9' "$WORK_DIR/p1/.blueprintx-provenance.yaml" \
		&& grep -qx 'blueprintx_commit: unknown' "$WORK_DIR/p1/.blueprintx-provenance.yaml"; then
		pass "a root without its own .git never stamps the enclosing repo"
	else
		fail "nested install" "$(tr '\n' '|' <"$WORK_DIR/p1/.blueprintx-provenance.yaml")"
	fi
}

test_a_checkout_stamps_its_own_tag_and_commit() {
	local path_root="$WORK_DIR/checkout" str_head
	make_root "$path_root"
	seed_repo "$path_root" v0.1.0
	str_head="$(git -C "$path_root" rev-parse HEAD)"
	stamp "$path_root" "$WORK_DIR/p2" lib-minimal
	if grep -qx 'blueprintx_version: 0.1.0' "$WORK_DIR/p2/.blueprintx-provenance.yaml" \
		&& grep -qx "blueprintx_commit: $str_head" "$WORK_DIR/p2/.blueprintx-provenance.yaml" \
		&& grep -qx 'tier: lib-minimal' "$WORK_DIR/p2/.blueprintx-provenance.yaml"; then
		pass "a git checkout stamps its own tag and HEAD"
	else
		fail "checkout" "$(tr '\n' '|' <"$WORK_DIR/p2/.blueprintx-provenance.yaml")"
	fi
}

test_lib_minimal_has_no_stamp_function_of_its_own() {
	if grep -q 'blueprintx-provenance\|lib_minimal_stamp_provenance' "$REPO_ROOT/bin/scaffold/python_lib_minimal.sh"; then
		fail "collapse" "python_lib_minimal.sh grew its own provenance logic again"
	else
		pass "python_lib_minimal.sh calls the shared stamp, no copy"
	fi
}

GATE="$REPO_ROOT/templates/python-common/bin/check_template_drift.py"
TIER=mvc-service-native-db

make_checkout() {
	local path_root="$1"
	mkdir -p "$path_root/bin/lib"
	cp "$REPO_ROOT"/bin/lib/{scaffold_python_templates,scaffold_provenance,common}.sh "$path_root/bin/lib/"
	cp -r "$REPO_ROOT/templates" "$path_root/templates"
}

copies() {
	bash "$1/bin/lib/scaffold_python_templates.sh" --list-copies --tier "$TIER" --roster "${2:-false}"
}

make_project() {
	local path_root="$1" path_project="$2" str_kind str_src str_dst
	mkdir -p "$path_project"
	printf 'tier: %s\nreview_bot_roster: false\n' "$TIER" >"$path_project/.blueprintx-provenance.yaml"
	while IFS=$'\t' read -r _ str_kind str_src str_dst; do
		if [[ "$str_kind" == dir ]]; then
			mkdir -p "$path_project/$str_dst"
			cp -r "$path_root/$str_src/." "$path_project/$str_dst"
		elif [[ -n "$str_kind" ]]; then
			mkdir -p "$(dirname "$path_project/$str_dst")"
			: >"$path_project/$str_dst"
		fi
	done < <(copies "$path_root" | grep '^COPY')
}

run_gate() {
	python3 "$GATE" --root "$1" --blueprintx-root "$2" 2>&1
}

expect_gate_output() {
	local str_name="$1" str_want="$2" str_got="$3"
	if grep -qF -- "$str_want" <<<"$str_got"; then
		pass "$str_name"
	else
		fail "$str_name" "wanted '$str_want' in: $(head -c 400 <<<"$str_got" | tr '\n' '|')"
	fi
}

expect_gate_silent() {
	local str_name="$1" str_unwanted="$2" str_got="$3"
	if grep -qF -- "$str_unwanted" <<<"$str_got"; then
		fail "$str_name" "did not want '$str_unwanted' in: $(head -c 400 <<<"$str_got" | tr '\n' '|')"
	else
		pass "$str_name"
	fi
}

test_the_roster_choice_decides_whether_its_file_is_listed() {
	make_checkout "$WORK_DIR/c1"
	expect_gate_output "roster opted in lists .review-bots.yaml" $'file\ttemplates/python-common/.review-bots.yaml' "$(copies "$WORK_DIR/c1" true)"
	expect_gate_silent "roster declined omits .review-bots.yaml" '.review-bots.yaml' "$(copies "$WORK_DIR/c1" false)"
}

test_a_complete_project_is_clean_and_a_missing_file_is_named() {
	make_checkout "$WORK_DIR/c2"
	make_project "$WORK_DIR/c2" "$WORK_DIR/p3"
	expect_gate_output "a project holding every copy is clean" "No template drift detected" "$(run_gate "$WORK_DIR/p3" "$WORK_DIR/c2")"
	rm "$WORK_DIR/p3/pytest.ini"
	expect_gate_output "a dropped file is flagged" "➖ pytest.ini" "$(run_gate "$WORK_DIR/p3" "$WORK_DIR/c2")"
}

test_dropping_a_copy_from_the_lib_stops_requiring_it() {
	make_checkout "$WORK_DIR/c3"
	make_project "$WORK_DIR/c3" "$WORK_DIR/p4"
	rm "$WORK_DIR/p4/pytest.ini"
	local path_lib="$WORK_DIR/c3/bin/lib/scaffold_python_templates.sh" int_hits
	int_hits="$(grep -c 'pytest.ini"' "$path_lib")"
	grep -v 'pytest.ini"' "$path_lib" >"$path_lib.new" && mv "$path_lib.new" "$path_lib"
	echo "mutation applied: removed $int_hits line(s) naming pytest.ini"
	expect_gate_silent "the lib no longer copies pytest.ini, so it is not required" "pytest.ini" "$(run_gate "$WORK_DIR/p4" "$WORK_DIR/c3")"
}

test_a_copy_in_a_form_a_regex_cannot_read_is_still_required() {
	make_checkout "$WORK_DIR/c4"
	make_project "$WORK_DIR/c4" "$WORK_DIR/p5"
	local path_lib="$WORK_DIR/c4/bin/lib/scaffold_python_templates.sh"
	awk '{ print } /^scaffold_copy_tooling_configs\(\) \{/ { print "\tlocal str_n; for str_n in .gitlint; do cp \"$COMMON_TEMPLATE_ROOT/$str_n\" \"$1/copy-of-$str_n\"; done" }' "$path_lib" >"$path_lib.new" && mv "$path_lib.new" "$path_lib"
	echo "mutation applied: $(grep -c 'copy-of-' "$path_lib") loop copy added"
	expect_gate_output "a looped copy is flagged" "➖ copy-of-.gitlint" "$(run_gate "$WORK_DIR/p5" "$WORK_DIR/c4")"
}

test_packaged_install_nested_in_a_foreign_repo_uses_the_literal
test_a_checkout_stamps_its_own_tag_and_commit
test_lib_minimal_has_no_stamp_function_of_its_own
test_the_roster_choice_decides_whether_its_file_is_listed
test_a_complete_project_is_clean_and_a_missing_file_is_named
test_dropping_a_copy_from_the_lib_stops_requiring_it
test_a_copy_in_a_form_a_regex_cannot_read_is_still_required

exit "$int_failures"
