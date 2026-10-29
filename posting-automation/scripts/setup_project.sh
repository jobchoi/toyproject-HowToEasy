#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "${1:-}" == '--install-system' ]]; then
    shift
    if ! command -v apt-get >/dev/null; then
        printf '%s\n' '자동 OS 설치는 Debian/Ubuntu/Raspberry Pi OS의 apt 환경만 지원합니다.' >&2
        exit 1
    fi
    sudo apt-get update
    sudo apt-get install -y git python3 python3-venv python3-pip
fi
if ! command -v python3 >/dev/null; then
    printf '%s\n' 'Python3가 없습니다. Debian 계열에서는 --install-system 옵션으로 다시 실행하세요.' >&2
    exit 1
fi
exec python3 "$project_dir/scripts/project_setup.py" --project "$project_dir" "$@"
