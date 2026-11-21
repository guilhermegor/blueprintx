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
`poe new_branch feat/minha-mudanca`, faça commits (Conventional Commits) e
integre com `poe git_merge_to_main`.
EOF
	else
		cat >>"$str_project_path/CONTRIBUTING.md" <<'EOF'

## Offline workflow (no GitHub remote)

Without a remote, `main` stays protected locally. Branch with
`poe new_branch feat/my-change`, commit (Conventional Commits), then merge
with `poe git_merge_to_main`.
EOF
	fi

	path_doc="$str_project_path/docs/contributing.md"
	[ -f "$path_doc" ] && [ "${DOCS_LOCALE:-en}" = "en" ] || return 0
	cat >>"$path_doc" <<'EOF'

## Without a GitHub remote (offline)

1. `poe new_branch feat/my-change` — branch off the default branch.
2. Do the work and commit (Conventional Commits). Pre-flight the message first with
   `poe check_commit_msg <file>`.
3. `poe bump_version` — runs `cz bump`: computes the next version from your commits, updates
   `pyproject.toml`, regenerates `CHANGELOG.md`, and creates the `vX.Y.Z` tag.
4. `poe git_merge_to_main` — merges the branch into the protected default branch locally.
5. Preview the Changelog any time with `poe changelog`.
EOF
}
