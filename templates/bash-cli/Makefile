.PHONY: lint test install help

# Mirrors BlueprintX's own root Makefile `install` recipe: rsync the tree into a
# location outside the checkout, then stamp the git-tag version into the installed
# entrypoint (no .git there, so it can't `git describe` itself at runtime).
install:
	$(eval VERSION := $(shell git describe --tags --always 2>/dev/null | sed 's/^v//'))
	@sudo mkdir -p /usr/local/lib/${PROJECT_NAME}
	@sudo rsync -a --delete bin/ /usr/local/lib/${PROJECT_NAME}/bin/
	@sudo rsync -a --delete lib/ /usr/local/lib/${PROJECT_NAME}/lib/
	@sudo sed -i "s/^CLI_VERSION=\".*\"/CLI_VERSION=\"$(VERSION)\"/" /usr/local/lib/${PROJECT_NAME}/bin/${PROJECT_NAME}
	@sudo ln -sf /usr/local/lib/${PROJECT_NAME}/bin/${PROJECT_NAME} /usr/local/bin/${PROJECT_NAME}
	@echo "Installed ${PROJECT_NAME} $(VERSION) to /usr/local/bin/${PROJECT_NAME}"

# lib/common.sh is a byte-identical shared file (BlueprintX's templates/common/), so
# shfmt only checks bin/${PROJECT_NAME}, this project's own script; shellcheck still
# covers both.
lint:
	@shellcheck --severity=warning --exclude=SC1091 bin/${PROJECT_NAME} lib/*.sh
	@shfmt -i 4 -ci -d bin/${PROJECT_NAME}

test:
	@bats tests/

help:
	@echo "make lint     - shellcheck + shfmt"
	@echo "make test     - bats tests/"
	@echo "make install  - install to /usr/local/bin/${PROJECT_NAME} (stamps the git-tag version)"
