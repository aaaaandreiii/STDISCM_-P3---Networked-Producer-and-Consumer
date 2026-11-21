#!/usr/bin/env bash
set -euo pipefail

repo=$(cd -- "$(dirname -- "$0")/../.." && pwd)
approval_dir="$repo/scripts/docker/approval2"
work=$(mktemp -d)
trap 'rm -f -- "$work/fixture.json" "$work/snapshot" "$work/changed" "$work/calls" "$work/snapshot-function.sh"; rmdir -- "$work"' EXIT

python3 - "$work/fixture.json" <<'PY'
import json
import sys
from pathlib import Path

base = {"Status": "running", "Running": True, "StartedAt": "2026-11-21T12:00:00Z"}
fixtures = [
    ("healthy", dict(base, Health={"Status": "healthy", "Log": ["private-probe-output"]}), {}),
    ("no-check", base, {"Env": ["PRIVATE_TEST_VALUE=not-for-output"]}),
    ("unhealthy", dict(base, Health={"Status": "unhealthy"}), {}),
    ("starting", dict(base, Health={"Status": "starting"}), {}),
    ("unreported", base, {"Healthcheck": {"Test": ["CMD", "probe"]}}),
    ("disabled", base, {"Healthcheck": {"Test": ["NONE"]}}),
    ("exited", dict(base, Status="exited", Running=False), {}),
]
Path(sys.argv[1]).write_text(json.dumps([
    {"Id": identifier, "State": state, "RestartCount": 0, "Config": config}
    for identifier, state, config in fixtures
]))
PY

# Load only the runner's snapshot function. The stub accepts one read-only verb.
sed -n '/^snapshot()/,/^}/p' "$approval_dir/run-image-gate.sh" > "$work/snapshot-function.sh"
source "$work/snapshot-function.sh"
baseline_ids=(healthy no-check unhealthy starting unreported disabled exited)
dkr() {
  test "$1 $2" = "container inspect" || return 1
  shift 2
  test "$*" = "${baseline_ids[*]}" || return 1
  printf '%s\n' 'container inspect' >> "$work/calls"
  cat "$work/fixture.json"
}
snapshot > "$work/snapshot"
test "$(cat "$work/calls")" = 'container inspect'

python3 - "$work/snapshot" "$work/fixture.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
states = {row["id"]: row for row in map(json.loads, text.splitlines())}
assert {key: state["classification"] for key, state in states.items()} == {
    "healthy": "running-healthy",
    "no-check": "running-no-healthcheck",
    "unhealthy": "running-unhealthy",
    "starting": "running-starting",
    "unreported": "running-unreported",
    "disabled": "running-no-healthcheck",
    "exited": "stopped",
}
assert "PRIVATE_TEST_VALUE" not in text and "private-probe-output" not in text
fixture = Path(sys.argv[2])
original = json.loads(fixture.read_text())
original[0]["RestartCount"] += 1
fixture.write_text(json.dumps(original))
PY

snapshot > "$work/changed"
if cmp -s "$work/snapshot" "$work/changed"; then
  printf '%s\n' 'A restart-count change must alter the snapshot.' >&2
  exit 1
fi
baseline_ids=(wrong-id)
if snapshot > "$work/changed" 2>/dev/null; then
  printf '%s\n' 'A mismatched inspect response must fail the gate.' >&2
  exit 1
fi
baseline_ids=()
calls=$(cat "$work/calls")
snapshot > "$work/changed"
test ! -s "$work/changed"
test "$(cat "$work/calls")" = "$calls"
printf '%s\n' 'PASS read-only snapshot handles optional health, stopped state, restarts, identity and redaction'
