# 저장소 작업 지침

- 작업 분야를 먼저 확인한다. 공간활용(자습실·작업실 등) 작업은 `docs/space-utilization/README.md`부터 읽고 해당 폴더의 기획·작업 현황·인수인계를 따른다. 포스팅 문서를 공간활용 요구사항으로 적용하지 않는다.
- 포스팅 자동화 작업 범위는 posting-automation/이다. 아래 포스팅 경로·검증·서버 운영 지침은 해당 작업에 적용한다. 공간활용 문서 정리만으로 기존 backend/, frontend/, DB 변경이 승인된 것은 아니다.
- 커밋과 push는 각각 사용자 별도 승인 후 진행한다.
- 사용자 자료·.env·인증정보·.local·원고/사진·서버 조사 원본은 Git에 추가하지 않는다.
- 라즈서버 운영 기준은 posting-automation/operations/server-workspace/AGENTS.md를 따른다. 이 문서는 manage_server.py가 서버의 관리 루트에도 설치하는 원본이다.
- 서버 디렉터리 표준은 ~/web-server/<프로젝트>/{repo,data,backups}이며 Compose 정의는 한 곳에서 관리한다. 이전 apps/services/app-data 제안은 이 표준으로 대체한다. 기존 경로를 자동으로 옮기지는 않는다.
- 원격 보고서와 실제 실행 검증을 구분한다. 새 스크립트는 기본 계획 모드, 명시적 apply, 기존 파일 보존, 프로젝트 단위 동작, 진단 로그를 제공한다.
- 기존 서비스 변경 전 실제 Compose·mount·작업 경로·백업/복구를 확인한다. 전체 down/prune/볼륨 삭제/기존 Tailscale 라우팅 변경을 기본 동작으로 넣지 않는다.
- 검증: posting-automation/.venv-ui/bin/python -m unittest discover -s posting-automation/tests -v. 네이버 실계정 시험은 보류 상태이며 테스트에서 외부 게시하지 않는다.
- 2026-11-04 이후 새 단계는 feature/<단계>에서 구현·검증·문서화하고 develop에 --no-ff로 통합해 이력을 남긴다. 운영 기준 develop과 작업 feature를 구분한다.
- 반복 환경 작업은 기존 setup/점검 유틸리티로 재현 가능하게 만들고 posting-automation/docs/agent/ENVIRONMENT_RUNBOOK.md에 기록한다.
- 공개 글·발표 자료는 확인된 증거와 연결한다. 구현/모의 테스트/실서버/사용자 보고/계획을 구분하고 인증정보·원고·서버 조사 원문을 공개 산출물에 포함하지 않는다.
