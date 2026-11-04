# 에이전트 인수인계 — 2026-11-04

## 재개 순서

1. 루트 AGENTS.md → docs/agent/ENVIRONMENT_RUNBOOK.md → TASKS.md → 운영 지침을 읽는다.
2. git status / git branch -vv로 사용자의 변경과 현재 feature를 확인한다. 과거 답변의 push 완료를 가정하지 않는다.
3. 프로젝트 폴더에서 bash scripts/setup_project.sh --profile test 및 python3 scripts/agent_environment.py를 사용한다.
4. 서버 변경 전 python3 scripts/agent_environment.py --remote로 연결을 점검하고 remote_server.py --workflow status로 현재 상태를 다시 수집한다.
5. 새 단계는 feature/<단계>에서 구현·검증 후 develop에 --no-ff 통합한다. main 승격은 별도다.

## 구현된 제품

posting_tool은 자료 가져오기·규칙 기반 원고 구성·파일 버전 저장·미리보기/내보내기 코어다. web.py Controller / 서비스 / views 구조를 사용한다. 로컬 UI는 평문/제한 Markdown 입력, 블록 편집, 원고 목록/이전 버전 열기, 샘플 디자인 4종, 사용자 템플릿/색상·글꼴·여백 조절, 사진·캡션·출처, 실제 생성 진행 상태를 제공한다. 네이버 로그인/실게시, AI 집필, 다중 사용자 인증, 버전 차이 비교는 미완료다. 이전 backend/frontend/DB는 보존한다.

환경 입력은 project-environment.json, setup/update 도구가 원본이다. 가상환경은 .venv-ui, 단일 워커 UI 포트는 8010이다. 사용자 자료/.env/.local/키는 Git에 넣지 않는다. 네이버 계정 보호조치 이후 실계정 시험은 계속 보류다.

## 서버: 확인된 과거 사실과 현재 확인 제한

2026-11-02 실제 보고서 및 SSH 확인:

- 포스팅: ~/web-server/posting-automation/repo와 data/ui, Docker healthy. 백업 실제 임시 복원·해시 검증 및 WSL 사본 검증 완료.
- FileBrowser: c2e64e9의 migrate-filebrowser로 운영 제어만 독립 프로젝트로 분리. 작업 7bdee1d412f64fd695eab8fed09439b8 성공, /config·/database·/srv 백업 복원 검증, 원본 이미지/마운트 유지, doctor 0.
- FileBrowser 복귀 컨테이너는 정지 보존. 프로젝트 compose.yaml은 새 경로, 데이터는 여전히 기존 my-server의 bind/익명 볼륨이다. control_migrated_pending_review와 데이터 이전 완료를 혼동하지 않는다.
- DuctTape/Nginx는 아직 기존 my-server 운영이다. Nginx mount 겹침은 당시 없었다. DuctTape의 읽기 전용 /media에는 약 1.1GB 입력 자료가 있어 외부 의존성 확인 없이 이동하지 않는다.
- Tailscale은 443→8000(DuctTape, 기존 Funnel), 8443→8010(포스팅), 10000→8080(FileBrowser, tailnet 전용). 사용자는 sudo 설정 후 FileBrowser 페이지 접속 성공을 보고했다. 로그인/파일 쓰기/재부팅 검증은 따로 남는다.

2026-11-04 재개: SSH ConnectTimeout=8로 접속 시간 초과. 서버 상태/자료/라우팅은 변경하지 않았다. 이는 현재 서버가 정상이라는 증거도, 서버 고장 원인 확정도 아니다. 연결 복구 후 현재 지침/등록표/Compose/mount/백업/복구를 다시 읽는다. 미접속 중에 모의 테스트를 실서버 완료로 기록하지 않는다.

## 남은 운영 작업

1. SSH 연결 회복 및 읽기 전용 최신 진단.
2. FileBrowser 로그인/파일 열기·쓰기 확인 후 데이터 경로 복사·권한/소유자/백업·복귀 도구 구현 및 검증. 오래된 원본 DB로 복귀해 새 변경을 잃지 않도록 별도 데이터 복구 설계가 필요하다.
3. Nginx, DuctTape를 한 프로젝트씩 분리. 원본 경로·공유 Compose/네트워크를 유지하며 외부 마운트 의존성을 확인한다.
4. 최종 서비스/접속/백업/인수인계 확인. 원본 및 복귀 컨테이너의 삭제는 별도 승인 전 하지 않는다.

remote_server.py는 migrate/rollback-filebrowser, repair, posting-backup, status/diagnose/sync-only를 제공한다. unknown/running이면 동일 ID collect로 조회하고 새 ID로 작업을 반복하지 않는다. 기존 FileBrowser rollback은 이전 bind 경로를 전제로 하므로 데이터 이동 후 그대로 호출해서는 안 된다.

## 게시/발표 산출물

사용자 대상은 https://lealnspire.blogspot.com 및 https://rt-jobchoi.tistory.com 이다. 최종 작업 완료 후 게시할 목적이며 지금은 초안 준비다. 공개 글·슬라이드는 공개 가능한 증거 목록만 사용한다. 서버 주소/사용자 경로/원시 보고서/원고/키는 넣지 않는다. Blogger OAuth와 Google Apps Script 실행은 계정 연결·동의가 필요하다. 티스토리 공식 Open API는 종료됐으므로 API 업로드 완료를 주장하지 않는다.

블로그·발표 결과의 생성/로컬 검증/Google 실행/게시를 구분해 기록한다. 현재 단계와 feature 통합 커밋은 WORK_HISTORY와 Git 이력을 확인한다.
