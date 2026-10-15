#!/usr/bin/env bash
set -euo pipefail

str_repo="${GITHUB_REPOSITORY:?}"
int_issue="${ISSUE_NUMBER:?}"
str_context="issue-scope/after-issue-edit"

str_query='query($owner:String!,$name:String!){repository(owner:$owner,name:$name){
  pullRequests(states:OPEN,first:100){nodes{number headRefOid
    closingIssuesReferences(first:20){nodes{number}}}}}}'

mapfile -t arr_prs < <(
  gh api graphql -f query="$str_query" \
    -F owner="${str_repo%/*}" -F name="${str_repo#*/}" \
    --jq ".data.repository.pullRequests.nodes[]
          | select([.closingIssuesReferences.nodes[].number] | index(${int_issue}))
          | \"\(.number) \(.headRefOid)\""
)

if [[ ${#arr_prs[@]} -eq 0 ]]; then
	echo "No open PR closes #${int_issue} — nothing to re-evaluate."
	exit 0
fi

int_failed=0
for str_pr in "${arr_prs[@]}"; do
	int_number="${str_pr%% *}"
	str_sha="${str_pr##* }"
	int_status=0
	PR_NUMBER="$int_number" python3 bin/ci/check_issue_scope.py || int_status=$?

	if [[ $int_status -eq 0 ]]; then
		str_state="success"
		str_desc="Still inside the declared surface of #${int_issue}"
	else
		str_state="failure"
		str_desc="Outside the surface #${int_issue} declares after its edit"
		int_failed=1
	fi

	gh api -X POST "repos/${str_repo}/statuses/${str_sha}" \
		-f state="$str_state" -f context="$str_context" -f description="$str_desc" >/dev/null
	echo "#${int_number} (${str_sha:0:8}): ${str_state} — ${str_desc}"
done

exit "$int_failed"
