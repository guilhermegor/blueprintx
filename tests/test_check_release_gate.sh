#!/usr/bin/env bash
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GATE="${GATE_PATH:-$REPO_ROOT/templates/common/bin/check_release_gate.py}"
WORK_DIR="$(mktemp -d)"
int_failures=0
int_server_pid=0

cleanup() {
	[ "$int_server_pid" -gt 0 ] && kill "$int_server_pid" 2>/dev/null
	rm -rf "$WORK_DIR"
}
trap cleanup EXIT

write_server() {
	cat >"$WORK_DIR/server.py" <<'PY'
import http.server
import pathlib
import sys

int_status = int(sys.argv[1])
bytes_body = pathlib.Path(sys.argv[2]).read_bytes()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(int_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(bytes_body)

    def log_message(self, *args):
        pass


cls_server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
print(cls_server.server_address[1], flush=True)
cls_server.serve_forever()
PY
}

start_server() {
	local int_status="$1" str_body="$2"
	printf '%s' "$str_body" >"$WORK_DIR/body.json"
	python3 "$WORK_DIR/server.py" "$int_status" "$WORK_DIR/body.json" >"$WORK_DIR/port" &
	int_server_pid=$!
	until [ -s "$WORK_DIR/port" ]; do sleep 0.05; done
}

stop_server() {
	kill "$int_server_pid" 2>/dev/null
	wait "$int_server_pid" 2>/dev/null
	int_server_pid=0
	rm -f "$WORK_DIR/port"
}

run_gate() {
	local str_previous="$1" str_new="$2" str_api="${3:-}"
	GITHUB_API_URL="$str_api" GITHUB_REPOSITORY="owner/repo" GITHUB_TOKEN="t" \
		python3 "$GATE" --previous-version "$str_previous" --new-version "$str_new" \
		>"$WORK_DIR/out" 2>&1
}

expect() {
	local str_name="$1" int_want="$2" int_got="$3" str_needle="${4:-}"
	if [ "$int_got" -ne "$int_want" ]; then
		echo "FAIL: $str_name (exit $int_got, wanted $int_want)"
		cat "$WORK_DIR/out"
		int_failures=$((int_failures + 1))
		return
	fi
	if [ -n "$str_needle" ] && ! grep -qF -- "$str_needle" "$WORK_DIR/out"; then
		echo "FAIL: $str_name (output lacks '$str_needle')"
		cat "$WORK_DIR/out"
		int_failures=$((int_failures + 1))
		return
	fi
	echo "ok: $str_name"
}

case_with_issues() {
	local str_name="$1" str_body="$2" int_want="$3" str_needle="$4"
	start_server 200 "$str_body"
	run_gate "0.9.0" "1.0.0" "http://127.0.0.1:$(cat "$WORK_DIR/port")"
	expect "$str_name" "$int_want" "$?" "$str_needle"
	stop_server
}

main() {
	write_server
	local str_open='[{"number":7,"title":"Fix parser","labels":[]},{"number":8,"title":"Later","labels":[{"name":"post-1.0"}]}]'
	local str_deferred='[{"number":8,"title":"Later","labels":[{"name":"post-1.0"}]},{"number":9,"title":"PR","pull_request":{},"labels":[]},{"number":10,"title":"Cut 1.0.0","labels":[{"name":"state:blocked"}]}]'

	case_with_issues "0.x to 1.0.0 with an unlabelled open issue fails and names it" "$str_open" 1 "#7"
	case_with_issues "0.x to 1.0.0 with only post-1.0 issues passes" "$str_deferred" 0 "gate passed"
	case_with_issues "a look-alike Cut 1.0.0 title still blocks" '[{"number":11,"title":"Cut 1.0.0 docs rewrite","labels":[]}]' 1 "#11"
	case_with_issues "0.x to 1.0.0 with no open issues passes" "[]" 0 "gate passed"

	run_gate "1.0.0" "1.0.1"
	expect "1.0.0 to 1.0.1 is unaffected (no API call)" 0 "$?" "not applicable"
	run_gate "0.4.0" "0.5.0"
	expect "0.4.0 to 0.5.0 is unaffected (no API call)" 0 "$?" "not applicable"
	run_gate "1.4.0" "2.0.0"
	expect "1.x to 2.0.0 is unaffected (no API call)" 0 "$?" "not applicable"

	start_server 500 '{"message":"boom"}'
	run_gate "0.9.0" "1.0.0" "http://127.0.0.1:$(cat "$WORK_DIR/port")"
	expect "API read error fails closed" 1 "$?" "failed closed"
	stop_server

	start_server 200 '{"message":"not a list"}'
	run_gate "0.9.0" "1.0.0" "http://127.0.0.1:$(cat "$WORK_DIR/port")"
	expect "unexpected API payload fails closed" 1 "$?" "failed closed"
	stop_server

	run_gate "0.9.0" "1.0.0" "http://127.0.0.1:1"
	expect "unreachable API fails closed" 1 "$?" "failed closed"

	run_gate "0.0.0" "1.0.0" "http://127.0.0.1:1"
	expect "first publish at 1.0.0 is gated" 1 "$?" "failed closed"

	[ "$int_failures" -eq 0 ] || { echo "$int_failures case(s) failed"; return 1; }
	echo "all cases passed"
}

main "$@"
