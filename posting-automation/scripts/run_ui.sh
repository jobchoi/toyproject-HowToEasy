#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
bash scripts/setup_project.sh --profile ui
printf '%s\n' '포스트룸 열기: http://127.0.0.1:8010' '종료: Ctrl+C'
exec .venv-ui/bin/python -m uvicorn posting_tool.web:create_app --factory --host 127.0.0.1 --port 8010 --proxy-headers --forwarded-allow-ips 127.0.0.1
