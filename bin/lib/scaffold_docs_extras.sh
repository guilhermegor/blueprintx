#!/usr/bin/env bash

scaffold_copy_docs_extras() {
	local str_project_path="$1"

	cp "$COMMON_TEMPLATE_ROOT/docs/incidents.md" \
		"$str_project_path/docs/incidents.md"
}

scaffold_append_offline_contributing() {
	local str_project_path="$1" path_doc

	if [ "${DOCS_LOCALE:-en}" = "pt-BR" ]; then
		cat >>"$str_project_path/CONTRIBUTING.md" <<'EOF'

## Fluxo offline (sem remoto GitHub)

Sem remoto, a `main` continua protegida localmente. Crie a branch com
`poe new_branch feat/minha-mudanca`, faça commits (Conventional Commits; teste a
mensagem antes com `poe check_commit_msg <arquivo>`), gere a versão com
`poe bump_version` e integre com `poe git_merge_to_main`.
EOF
	else
		cat >>"$str_project_path/CONTRIBUTING.md" <<'EOF'

## Offline workflow (no GitHub remote)

Without a remote, `main` stays protected locally. Branch with
`poe new_branch feat/my-change`, commit (Conventional Commits; pre-flight the
message with `poe check_commit_msg <file>`), cut the version with
`poe bump_version`, then merge with `poe git_merge_to_main`.
EOF
	fi

	path_doc="$str_project_path/docs/contributing.md"
	[ -f "$path_doc" ] && [ "${DOCS_LOCALE:-en}" = "en" ] || return 0
	local path_tmp
	path_tmp="$(mktemp)"
	awk '
		function emit() {
			print "**Without a GitHub remote (offline)** — the pull-request steps above need a remote;"
			print "here `main` is protected locally instead:"
			print ""
			print "1. `poe new_branch feat/my-change` — branch off the default branch."
			print "2. Do the work and commit (Conventional Commits). Pre-flight the message first with"
			print "   `poe check_commit_msg <file>` — it runs the same gitlint + commitizen `commit-msg` checks"
			print "   in seconds, instead of a rejected title costing a full pre-commit gate run."
			print "3. `poe bump_version` — runs `cz bump`: computes the next version from your commits, updates"
			print "   `pyproject.toml`, regenerates `CHANGELOG.md`, and creates the `vX.Y.Z` tag."
			print "4. `poe git_merge_to_main` — merges the branch into the protected default branch locally."
			print "5. Preview the Changelog any time with `poe changelog`."
			print ""
			done = 1
		}
		/^## / { if (in_rel && !done) emit(); in_rel = ($0 == "## Releasing") }
		{ print }
		END { if (!done) { print ""; emit() } }
	' "$path_doc" >"$path_tmp"
	cat "$path_tmp" >"$path_doc"
	rm -f "$path_tmp"
}
