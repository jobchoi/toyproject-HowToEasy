# 개발 환경 재현과 에이전트 인수인계

환경 구성의 실행 원본은 project-environment.json, scripts/project_setup.py이다. 이 문서에 패키지 버전을 복제하지 않는다. 반복 작업의 수동 해결은 원인을 기록한 뒤 기존 setup 또는 점검 유틸리티로 옮긴다.

## 새 작업 PC

1. Git 저장소를 clone하고 develop을 선택한다. 기존 작업 폴더가 있다면 먼저 git status로 변경을 보존한다.
2. AGENTS.md → posting-automation/HANDOFF.md → TASKS.md → 서버 운영 지침 순서로 읽는다.
3. 프로젝트 폴더에서 `bash scripts/setup_project.sh --profile test`를 실행한다. OS 패키지가 없을 때만 명시적으로 `--install-system`을 사용한다. Docker는 원격 운영에 필요하며 로컬 UI 개발의 필수 조건이 아니다.
4. `python3 scripts/agent_environment.py`로 Python, 도구, 가상환경 import, Git 상태를 확인한다. 종료 1은 점검 필요, 2는 점검 자체 실패다. 네트워크 검사는 기본 실행하지 않는다.
5. `.venv-ui/bin/python -m unittest discover -s tests -v`를 실행한다. 제한 환경의 HTTP 테스트가 멈추면 무한 대기하지 말고 중지·환경 제한 여부를 기록한다. opt-in 브라우저 테스트 제외를 전체 실브라우저 통과로 표현하지 않는다.
6. `bash scripts/run_ui.sh`로 로컬 UI를 실행한다. .local, .env, 원고, PDF, 사진, 인증정보는 Git 대상이 아니다.

Windows PowerShell의 실행 정책을 전역 완화하지 않는다. Naver 시험의 Windows 스크립트는 별도 NAVER_UPLOAD_TRIAL.md 지침을 따르며 실제 계정 시험은 현재 보류다.

## SSH와 Git 인증

인증은 저장소 복사만으로 이전되지 않는다. 기존 개인키/토큰을 저장소에 넣지 않는다. 새 환경에서 공개키 등록과 호스트키 검증을 완료하고 ssh-agent를 필요한 실행 세션에 연결한다. `ssh -o BatchMode=yes raspberry-posting hostname`으로 확인한다. `python3 scripts/agent_environment.py --remote --host raspberry-posting`은 제한 시간 내 읽기 전용 연결만 확인하며 비밀번호나 stderr 원문을 기록하지 않는다.

GitHub push 인증과 라즈 SSH 인증은 별개다. IDE 터미널의 인증이 에이전트 환경에 전달된다고 가정하지 않는다. 인증 실패 시 커밋을 준비하고 미반영 사실을 기록한다. Git bundle 배포는 GitHub push가 아니며 실제 사용한 경우 별도 배포 이력으로 남긴다.

## Git flow

- 새 단계: 깨끗한 develop에서 `git switch -c feature/<단계>`.
- 기능·검증·문서를 해당 feature에 함께 커밋한다. 다른 단계는 별도 feature로 나눈다.
- 검증 후 `git switch develop` → `git merge --no-ff feature/<단계>`로 통합한다. feature 브랜치는 이력 확인용으로 남긴다. 충돌 시 기존 변경을 보존한다.
- develop은 원격 운영의 기존 기준이다. 작업 중인 feature를 운영 develop으로 가장하지 않는다. main 릴리스 승격은 별도다.
- push 성공을 명령 반환값으로 확인한다. 불가하면 커밋 ID·남은 명령·원인을 HANDOFF에 적는다.

## 서버 작업 재개

먼저 agent_environment.py --remote, remote_server.py --workflow status로 실시간 접속/서비스를 확인한다. 실패하면 운영 변경은 하지 않고 독립 작업만 진행한다. 과거 실행 보고서를 최신 상태로 표시하지 않는다.

서버 기준은 `~/web-server/<프로젝트>/{repo,data,backups}`다. projects.json과 각 MIGRATION.md를 읽고 데이터·Compose·컨테이너의 실제 경로를 대조한다. FileBrowser는 운영 제어만 분리됐으며 데이터 이동은 미완료였다. 기존 my-server/apps 원본과 복귀용 컨테이너를 삭제하지 않는다. DuctTape/Nginx는 실시간 조사·백업·복구 검증 전 이전하지 않는다.

443 DuctTape / 8443 포스팅 / 10000 FileBrowser의 역할을 보존한다. 10000은 사용자가 2026-11-02 sudo 설정 후 접속 성공을 보고했고 당시 서버에서도 설정을 확인했다. 이것은 재부팅·로그인·파일 쓰기 검증을 뜻하지 않는다.

unknown/running 원격 작업은 동일 ID collect로 조회한다. 새 ID로 변경 명령을 반복하지 않는다. sudo 권한 부족을 해결하기 위해 비밀번호 파일·sshpass·호스트키 검증 해제를 도입하지 않는다.

## 반복 장애: restart와 보존 컨테이너

구버전 관리기에는 restart가 없고 신버전도 프로젝트 이름이 필수다. `./manage.sh restart posting-automation`은 계획, --apply를 붙이면 해당 서비스만 재시작한다. 전체 Docker 재시작으로 CLI 구문 오류를 해결하지 않는다.

복귀용 컨테이너는 rename/정지만으로 보존하면 always 정책으로 재기동해 포트를 점유할 수 있다. 도구는 원래 정책을 기록하고 해당 대상에만 restart=no를 적용한다. doctor에 PRESERVED_RUNNING 또는 MANAGED_NOT_RUNNING이 나오면 stabilize-filebrowser 계획으로 ID/이미지/마운트부터 확인한다. 데이터 경로가 다르면 자동 전환하지 않는다.

내부 healthy인데 실제 접속이 거부되면 Tailscale 매핑 → 호스트 HTTP → 실제 Docker 공개 포트/endpoint를 순서대로 확인한다. PortBindings 설정이 존재해도 NetworkSettings.Ports/Networks가 비어 있을 수 있다. 이 경우 새 도구 repair-filebrowser-network가 원래 네트워크 연결만 복구한다. 복구 후 호스트뿐 아니라 사용자 HTTPS 주소도 TLS 검증 상태에서 확인한다.
