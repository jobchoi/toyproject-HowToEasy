# 프로젝트별 서버 관리 체계

2026-11-02 기준 정책. 이전에 제안한 apps/services/app-data 분산 배치를 대체한다. 기존 서비스와 파일은 초기 등록 때 이동하지 않는다.

## 에이전트가 읽을 지침

- 저장소 루트 [AGENTS.md](../../../AGENTS.md): 기존 프로젝트 보존 및 작업 경계.
- 이 디렉터리 [AGENTS.md](AGENTS.md): 서버 운영 규칙 원본. 초기 구성 스크립트가 ~/web-server/AGENTS.md에 설치한다.
- 서버에서는 ~/web-server/AGENTS.md → projects.json → 프로젝트 README.md → MIGRATION.md 순서로 읽는다.
- 기존 서버 조사 원본과 .env, 사용자 자료를 저장소에 넣지 않는다.

## 서버에 배치할 구조

```text
~/web-server/
├── AGENTS.md                 # 에이전트 공통 운영 규칙
├── README.md                 # 관리 시작점·프로젝트 문서 링크
├── projects.json             # 실제 기존 경로/목표 경로/포트/이관 상태
├── WORK_HISTORY.md           # 관리 작업 이력
├── manage.sh                 # 이곳에서 status/doctor/add 실행
├── logs/                     # manage.sh 실행별 JSONL 로그
├── posting-automation/
│   ├── README.md
│   ├── MIGRATION.md
│   ├── repo/                 # 초기에는 비어 있음
│   ├── data/                 # 초기에는 비어 있음
│   └── backups/
├── duct-tape/                # 위와 같은 구조
├── filebrowser/
└── nginx/
```

등록 직후에는 실제 코드는 기존 ~/apps 또는 ~/my-server에 있다. Compose/.env 생성이나 데이터 복사를 수행하지 않는다. `registered_not_migrated`가 이 상태를 명시한다. 폴더가 생겼다는 이유로 기존 컨테이너를 새 data 경로로 재연결하지 않는다.

## 라즈서버에서 첫 실행

최신 코드를 push/pull한 후 실행한다. Python 3 표준 라이브러리만 사용하며 Linux/WSL 전용이다. sudo·Docker 설치·venv 준비는 필요 없다. 스크립트와 operations/server-workspace/AGENTS.md가 같은 저장소 안에 있어야 한다. 스크립트 파일만 scp하면 적용 시 지침 원본 누락으로 중단된다.

```bash
cd ~/apps/posting-automation-workspace/posting-automation

# 계획 확인: 기본 관리 루트 ~/web-server, 프로젝트 폴더는 만들지 않음
python3 scripts/manage_server.py init

# 실제 디렉터리·MD 지침·등록표 생성, 로그는 관리 루트에 보관
python3 scripts/manage_server.py --log-dir "$HOME/web-server/logs" init --apply

# 이후에는 관리 루트만 찾아가면 됨
cd ~/web-server
./manage.sh status
./manage.sh doctor
```

첫 계획 모드도 실행 기록은 만든다. 기본 로그 경로는 /tmp/web-server-manager/<UID>/이며 재부팅 후 없어질 수 있다. 적용 시 위 명령처럼 --log-dir로 영속 위치를 지정한다. manage.sh를 쓰면 로그는 자동으로 ~/web-server/logs에 저장된다.

기존 파일을 수정해 두었다면 재실행해도 덮어쓰지 않는다. projects.json은 기존 등록값을 유지하면서 새 등록만 추가하고 원자적으로 교체한다. 로그 및 작업 이력은 새로 추가된다. flock으로 관리 작업 중복 실행을 차단한다. 부분 생성 후 실패했다면 원인을 해결하고 동일 명령을 재실행할 수 있다.

## 새 프로젝트 추가

```bash
cd ~/web-server
./manage.sh add my-new-project
./manage.sh add my-new-project --apply

# 기존 코드 위치를 등록하고 싶을 때 (복사·이동하지 않음)
./manage.sh add another-project --source "$HOME/another-project" --apply
```

이름은 소문자로 시작하는 영문 소문자·숫자·하이픈 1~48자다. 기존 프로젝트의 source를 다른 경로로 바꾸려 하면 중단한다. 등록표와 실제 서비스를 대조한 뒤 수동으로 경로를 갱신한다.

## 장애 대응

콘솔 첫 줄에 JSONL 로그 경로를 출력한다. 각 줄에는 UTC 시각, 코드, 메시지, 점검 대상 등 허용된 정보만 기록한다. 콘솔 전체를 복사하기보다 해당 실행 로그를 먼저 확인한다. 경로·서비스 이름은 포함되므로 공유 전 확인한다.

| 코드/종료값 | 의미와 조치 |
| --- | --- |
| DRY_RUN / 0 | 계획만 표시. 폴더 등록 적용은 --apply 필요 |
| REGISTERED / 0 | 폴더와 지침 등록 완료. 실제 서비스 이관 완료와 다름 |
| PRESERVED | 기존 파일 보존. 지침 업데이트는 차이를 검토해 별도로 반영 |
| NOT_DEPLOYED | 새 Compose가 없는 미이관 상태. 기존 운영 위치 사용 |
| SOURCE_MISSING / 1 | 기존 코드 경로 미발견. 해당 서버 사용자/경로/마운트 확인 |
| COMPOSE_MISSING / 1 | 이관 완료로 표시했는데 운영 정의 없음. 등록표와 배치 상태 확인 |
| COMMAND_MISSING / 1 | Docker 또는 의존 명령 없음. 자동 설치하지 않음 |
| COMMAND_FAILED / 1 | Docker/Compose 확인 실패. 설치/접속 권한 확인 |
| COMMAND_TIMEOUT / 1 | 명령 시간 초과. Docker 데몬 상태 점검 후 필요한 진단만 재실행 |
| DOCKER_UNAVAILABLE / 1 | 컨테이너 조회 불가. 데몬/접속 권한 확인; 권한 확대 자동 실행 없음 |
| UNHEALTHY / 1 | healthcheck 실패. 대상 서비스의 원인 확인; 일괄 재시작하지 않음 |
| ERROR / 2 | 경로·지침 원본·등록표·권한 충돌 등. message/error_type을 확인 |
| INTERRUPTED / 130 | 사용자 중단. 로그의 마지막 단계와 생성된 파일 확인 |

로그를 읽으려면 첫 줄에 나온 경로를 사용한다.

```bash
cat /실제로/출력된/로그.jsonl
```

.env/인증정보/원고 본문/컨테이너 환경변수/프로세스 인자/명령의 원시 stderr는 수집하지 않는다. doctor는 Docker 버전과 컨테이너 상태를 조회하며 파일을 수정하거나 서비스를 재시작하지 않는다. 전체 서버 의존성 조사는 audit_server.py를 사용한다. 로그 자동 삭제는 없으므로 보관 주기를 따로 정한다.

## 실제 이관은 다음 단계

현재 도구는 관리 디렉터리와 정책/등록 체계를 구성한다. Dockerfile/운영 Compose·자료 백업/복원·실제 파일 이동·컨테이너 전환은 구현하거나 실행하지 않았다.

1. 포스팅 앱부터 기존 자료 보존·백업 확인.
2. 단일 운영 Compose 정의와 ARM/프록시/데이터 권한 검증.
3. 기존 경로를 먼저 그대로 마운트해 서비스만 전환 가능.
4. 원고 재열기·저장·재시작·복원 시험 후 프로젝트 경로 이관.
5. manager_script/manage.sh 참조도 새 코드 위치로 갱신.
6. 성공한 프로젝트만 등록표 status를 migrated로 바꾸고 실제 코드·데이터·Compose 위치를 기록.
7. 기존 DuctTape/File Browser/Nginx는 별도 검증 뒤 하나씩 이관.

포스팅 실제 이관 전에는 기존 run_ui.sh와 원래 경로를 계속 사용한다. status/doctor는 앱 HTTP 접속·데이터 복원 검증을 대신하지 않는다. 기존 루트 /client 리다이렉트와 서버 디렉터리 구조는 별개이며 Tailscale 443/8443은 유지한다.

## 포스팅 실제 이관 지원 추가

2026-11-02 후속: prepare-posting과 posting start/stop/status/confirm 명령을 추가했다. 기존 초기 등록 명령은 그대로이며, 실제 이관 명령은 명시적으로 실행해야 한다. 위 문서의 초기 도구 미지원 설명은 초기 등록 범위에 해당한다. 최신 상세 절차는 [포스팅 Docker 이관](../../docs/POSTING_DOCKER_MIGRATION.md)을 따른다. 기존 폴더를 임의로 이동하지 않는다.

## 이관 완료 후

사용자 서버에서 포스팅 실행/재시작/confirm 로그를 확인했다. [이관 후 운영](../../docs/POST_MIGRATION_OPERATIONS.md)에 따라 posting backup, use-managed, diagnose-filebrowser를 사용할 수 있다. backup은 잠시 대상 앱만 중지한 뒤 복원 검증·재개하며 명시적 --apply가 필요하다. 관리 코드 전환 후에는 원래 apps 폴더가 아닌 web-server 아래 repo를 갱신한다. File Browser 원시 health 오류/명령 인자는 로그에 노출하지 않는다.
