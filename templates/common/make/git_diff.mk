# Git-diff offline-sync targets — present only when scaffolded without GitHub.
# Included by the project Makefile via `-include make/git_diff.mk`.

.PHONY: git_diff_export git_diff_apply git_diff_check

git_diff_export:
	@bash bin/git_diff_export.sh

git_diff_apply:
	@bash bin/git_diff_apply.sh $(FILE)

git_diff_check:
	@bash bin/git_diff_check.sh $(FILE)
