# Offline-only targets — present only when scaffolded WITHOUT a GitHub remote.
# Included by the project Makefile via `-include make/offline.mk`. These wrap the
# local git workflow that substitutes for GitHub's branch + PR flow, plus the
# git-diff sync helpers for sharing changes without a remote.

.PHONY: new_branch git_merge_to_main git_diff_export git_diff_apply git_diff_check

new_branch:
	@bash bin/new_branch.sh "$(NAME)"

git_merge_to_main:
	@bash bin/git_merge_to_main.sh

git_diff_export:
	@bash bin/git_diff_export.sh

git_diff_apply:
	@bash bin/git_diff_apply.sh $(FILE)

git_diff_check:
	@bash bin/git_diff_check.sh $(FILE)
