.PHONY: lint test build drive repo_rules repo_rules_verify help

lint:
	@shellcheck --severity=warning --exclude=SC1091 bin/${PROJECT_NAME} lib/*.sh
	@shfmt -i 4 -ci -d bin/${PROJECT_NAME} $(filter-out lib/common.sh,$(wildcard lib/*.sh))

test:
	@bats tests/

build:
	@bin/${PROJECT_NAME} build

drive:
	@bin/${PROJECT_NAME} drive --device "$(DEVICE)" $(if $(DRY_RUN),--dry-run)

repo_rules:
	@bash bin/enable_repo_rules.sh

repo_rules_verify:
	@bash bin/enable_repo_rules.sh verify

help:
	@echo "make lint                    - shellcheck + shfmt"
	@echo "make test                    - bats tests/ (network stubbed)"
	@echo "make build                   - download, verify and assemble build/drive"
	@echo "make drive DEVICE=/dev/sdX   - write build/drive to a removable drive (add DRY_RUN=1 to preview)"
	@echo "make repo_rules              - provision the pr-quality-gate ruleset + merge settings"
	@echo "make repo_rules_verify       - assert required checks are strict (read-only, fails loud)"
