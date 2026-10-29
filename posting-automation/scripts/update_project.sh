#!/usr/bin/env bash
# Run in the target checkout; never resets changes, switches branches, pushes, or restarts services.
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
repository_dir="$(git -C "$project_dir" rev-parse --show-toplevel)"
if [[ -n "$(git -C "$repository_dir" status --porcelain)" ]]; then
    printf '%s\n' '미커밋 변경이 있어 중단합니다. 변경을 보존한 뒤 다시 실행하세요.' >&2
    exit 1
fi
branch="$(git -C "$repository_dir" branch --show-current)"
if [[ -z "$branch" ]]; then
    printf '%s\n' '브랜치가 선택되지 않았습니다. 사용할 브랜치를 먼저 확인하세요.' >&2
    exit 1
fi
printf '현재 브랜치 %s를 fast-forward로 갱신합니다.\n' "$branch"
git -C "$repository_dir" pull --ff-only
exec bash "$project_dir/scripts/setup_project.sh" "$@"
