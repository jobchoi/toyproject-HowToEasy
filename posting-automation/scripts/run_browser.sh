#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .venv-browser/bin/python ]]; then
    printf '%s\n' '먼저 bash scripts/setup_browser.sh를 실행하세요.' >&2
    exit 1
fi
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$project_dir/.local/browsers}"
exec .venv-browser/bin/python "$project_dir/scripts/naver_browser_probe.py" "$@"
