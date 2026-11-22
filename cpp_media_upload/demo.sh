#!/usr/bin/env bash
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
command -v python3 >/dev/null || { printf 'MediaDock requires Python 3.11 or later.\n' >&2; exit 1; }
exec python3 -B "$root/scripts/demo/controller.py" "$@"
