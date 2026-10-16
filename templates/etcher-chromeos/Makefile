.PHONY: lint test tools tools_etcher install repo_rules repo_rules_verify help

tools:
	@bash bin/fetch_tools.sh bmaptool

tools_etcher:
	@bash bin/fetch_tools.sh etcher

install:
	$(eval VERSION := $(shell git describe --tags --always 2>/dev/null | sed 's/^v//'))
	@sudo mkdir -p /usr/local/lib/${PROJECT_NAME}
	@sudo rsync -a --delete bin/ /usr/local/lib/${PROJECT_NAME}/bin/
	@sudo rsync -a --delete lib/ /usr/local/lib/${PROJECT_NAME}/lib/
	@sudo sed -i "s/^CLI_VERSION=\".*\"/CLI_VERSION=\"$(VERSION)\"/" /usr/local/lib/${PROJECT_NAME}/bin/${PROJECT_NAME}
	@sudo ln -sf /usr/local/lib/${PROJECT_NAME}/bin/${PROJECT_NAME} /usr/local/bin/${PROJECT_NAME}
	@echo "Installed ${PROJECT_NAME} $(VERSION) to /usr/local/bin/${PROJECT_NAME}"

lint:
	@shellcheck --severity=warning --exclude=SC1091 bin/${PROJECT_NAME} bin/fetch_tools.sh lib/*.sh
	@shfmt -i 4 -ci -d bin/${PROJECT_NAME} bin/fetch_tools.sh $(filter-out lib/common.sh,$(wildcard lib/*.sh))

test:
	@bats tests/

repo_rules:
	@bash bin/enable_repo_rules.sh

repo_rules_verify:
	@bash bin/enable_repo_rules.sh verify

help:
	@echo "make tools              - check for the distro bmaptool (never downloads)"
	@echo "make tools_etcher       - balenaEtcher GUI into .tools/ (needs ALLOW_UNSIGNED_DOWNLOAD=1)"
	@echo "make lint               - shellcheck + shfmt"
	@echo "make test               - bats tests/ (network and devices stubbed)"
	@echo "make install            - install to /usr/local/bin/${PROJECT_NAME} (stamps the git-tag version)"
	@echo "make repo_rules         - provision the pr-quality-gate ruleset + merge settings"
	@echo "make repo_rules_verify  - assert required checks are strict (read-only, fails loud)"
