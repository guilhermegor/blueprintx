# -------------------
# VIRTUAL ENVIRONMENT
# -------------------
.PHONY: init-venv update-venv

init-venv:
	@bash scripts/init_venv.sh

update-venv:
	@poetry update
	@echo "Poetry project updated"

# -------------------
# VSCODE CONFIG
# -------------------
.PHONY: vscode_init export_deps

vscode_init:
	@bash scripts/vscode_keybindings.sh
	@bash scripts/vscode_extensions.sh

export_deps:
	@bash scripts/export_deps.sh
