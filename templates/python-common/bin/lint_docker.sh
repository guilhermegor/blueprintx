#!/usr/bin/env bash
#
# lint_docker.sh — hadolint over the repository's Dockerfiles.
#
# WHY A WRAPPER AND NOT A LINE IN lint.sh: hadolint is the only gate in the set with no Python
# package. pre-commit runs it as `hadolint-docker`, which pulls and runs a DOCKER IMAGE. Calling
# that unconditionally from `poe lint` would break the command on every machine without a
# running Docker daemon — most contributor laptops and some CI runners — turning a lint run into
# an infrastructure requirement. So the same RESOLVE, DON'T INSTALL contract as
# lint_shell.sh / lint_yaml.sh / lint_sql.sh / lint_actions.sh applies here.
#
# ⚠️ WHERE THIS DELIBERATELY DIFFERS FROM lint_actions.sh: that script fails when discovery
# matches zero files, because a repo with a .github/workflows directory and no workflow in it is
# a defect. The analogue here is NOT "zero Dockerfiles is a defect" — measured 2026-08-23, the
# only Dockerfile under templates/ is in react-spa-webpack (a TypeScript tier). NO Python tier
# ships one, and .hadolint.yaml says so in its own header. A blanket zero-file failure would
# make `poe lint` red in every scaffolded Python project on day one.
#
# The shape that DOES transfer is lint_actions.sh's two-tier rule, applied to the right
# subject:
#
#   | situation                          | verdict  | why                                     |
#   |------------------------------------|----------|-----------------------------------------|
#   | no Dockerfile anywhere             | skip     | legitimate — the tier ships none         |
#   | Dockerfile(s) present, tool absent | skip *   | * unless LINT_DOCKER_REQUIRED=1 (CI)     |
#   | Dockerfile(s) present, tool found  | lint     | the only case that can fail              |
#
# The vacuous-success trap the zero-file rule exists to catch is still closed, just one level
# up: the count is asserted before the tool is invoked, so hadolint is never handed an empty
# argument list and never exits 0 for having checked nothing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Pinned so a silent upstream rule change cannot turn a green tree red without a diff. Bump
# deliberately, the way the actionlint pin is bumped.
STR_HADOLINT_IMAGE="hadolint/hadolint:v2.12.0-alpine"

resolve_hadolint_mode() {
	# Print "system" (a binary on PATH), "docker" (the pinned image, daemon reachable), or ""
	# when neither is available. Probes with --version so a real lint exit code is never
	# mistaken for "absent".
	if command -v hadolint >/dev/null 2>&1 && hadolint --version >/dev/null 2>&1; then
		printf 'system'
		return 0
	fi
	# `docker info` and not `command -v docker`: the client binary is present on plenty of
	# machines whose daemon is stopped, and that combination fails at RUN time — which is the
	# hard failure this whole wrapper exists to avoid.
	if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
		printf 'docker'
		return 0
	fi
	printf ''
}

discover_dockerfiles() {
	# ⚠️ GROUP THE FIND EXPRESSION — `-o` binds looser than the implicit `-a`, so an ungrouped
	# `-iname A -o -iname B -type f` applies `-type f` to the second branch only, letting a
	# DIRECTORY named `Dockerfile.d` into the list and failing the gate for an unrelated
	# reason. Same trap documented in lint_actions.sh.
	find . \
		\( -path ./.git -o -path ./.venv -o -path ./node_modules -o -path ./.mypy_cache \) -prune \
		-o \( -iname 'Dockerfile' -o -iname 'Dockerfile.*' -o -iname '*.dockerfile' \) -type f -print |
		sort
}

main() {
	cd "$SCRIPT_DIR/.."

	mapfile -t list_dockerfiles < <(discover_dockerfiles)

	if [ "${#list_dockerfiles[@]}" -eq 0 ]; then
		print_status "info" "skip: no Dockerfile in this project (hadolint has nothing to lint)"
		return 0
	fi

	local str_mode
	str_mode="$(resolve_hadolint_mode)"
	if [ -z "$str_mode" ]; then
		if [ "${LINT_DOCKER_REQUIRED:-0}" = "1" ]; then
			print_status "error" "hadolint is required here but neither the binary nor a running Docker daemon is available — a skipped gate in CI is a gate reporting its own blindness as OK"
			return 1
		fi
		print_status "warning" "skip: hadolint absent (install from https://github.com/hadolint/hadolint, or start Docker)"
		return 0
	fi

	print_status "info" "hadolint [$str_mode]: ${#list_dockerfiles[@]} Dockerfile(s)"
	if [ "$str_mode" = system ]; then
		# hadolint auto-discovers .hadolint.yaml from the current directory.
		hadolint "${list_dockerfiles[@]}"
	else
		# Mount the tree read-only and run from inside it, rather than piping each file in on
		# stdin. Two reasons, both about the report rather than the check: hadolint
		# auto-discovers .hadolint.yaml from the cwd (so the container obeys the same config
		# the binary does), and a file read from stdin is reported as `-`, which makes a
		# multi-Dockerfile project's output unattributable. `--no-fail` is NOT passed: the
		# container's exit status is the gate's verdict.
		docker run --rm -v "$PWD:/repo:ro" -w /repo "$STR_HADOLINT_IMAGE" \
			hadolint "${list_dockerfiles[@]}"
	fi
	print_status "success" "hadolint OK"
}

main "$@"
