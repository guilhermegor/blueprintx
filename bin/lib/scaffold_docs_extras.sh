#!/usr/bin/env bash

scaffold_copy_docs_extras() {
	local str_project_path="$1"

	cp "$COMMON_TEMPLATE_ROOT/docs/incidents.md" \
		"$str_project_path/docs/incidents.md"
}
