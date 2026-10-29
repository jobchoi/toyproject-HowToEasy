#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
python3 -m venv .venv-browser
.venv-browser/bin/python -m pip install -r requirements-browser.txt
export PLAYWRIGHT_BROWSERS_PATH="$project_dir/.local/browsers"
.venv-browser/bin/python -m playwright install chromium --no-shell
printf '%s\n' '브라우저 파일 다운로드 완료. OS 라이브러리 설치 여부는 별도입니다.' 'Ubuntu 24.04에서 libnspr4/libnss3/libasound2t64 누락 시:' '  sudo apt-get update' '  sudo apt-get install -y libnspr4 libnss3 libasound2t64' '실행: bash scripts/run_browser.sh'
