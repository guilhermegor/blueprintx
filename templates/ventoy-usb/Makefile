.PHONY: all lint test tools build drive repo_rules repo_rules_verify help

all: build

lint:
	@shellcheck --severity=warning --exclude=SC1091 bin/${PROJECT_NAME} lib/*.sh
	@shfmt -i 4 -ci -d bin/${PROJECT_NAME} $(filter-out lib/common.sh,$(wildcard lib/*.sh))
	@bash bin/check_readme_structure.sh README.md

test:
	@bats tests/

tools:
	@bin/${PROJECT_NAME} tools

build:
	@bin/${PROJECT_NAME} build $(if $(KEEP_PERSISTENCE),--keep-persistence)

drive:
	@bin/${PROJECT_NAME} drive $(if $(TARGET),--target "$(TARGET)") $(if $(DRY_RUN),--dry-run) $(if $(YES_DELETE_EXTRAS),--yes-delete-extras) $(if $(KEEP_PERSISTENCE),--keep-persistence)

repo_rules:
	@bash bin/enable_repo_rules.sh

repo_rules_verify:
	@bash bin/enable_repo_rules.sh verify

help:
	@echo "make lint                    - shellcheck + shfmt"
	@echo "make test                    - bats tests/ (network stubbed)"
	@echo "make tools                   - download the latest Ventoy into .tools/"
	@echo "make                         - same as make build"
	@echo "make build                   - download, verify and assemble build/drive"
	@echo "make drive [TARGET=path]     - sync build/drive to the pendrive (asks for the path; DRY_RUN=1 previews)"
	@echo "make repo_rules              - provision the pr-quality-gate ruleset + merge settings"
	@echo "make repo_rules_verify       - assert required checks are strict (read-only, fails loud)"
