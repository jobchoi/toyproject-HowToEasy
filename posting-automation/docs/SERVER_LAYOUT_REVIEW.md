# 라즈서버 구조 분석 및 단계별 정리안

> 정책 갱신(2026-11-02): 아래 apps/services/app-data 분산 배치는 과거 제안이다. 사용자 요청에 따라 ~/web-server/<프로젝트>/{repo,data,backups}와 프로젝트 루트의 운영 진입점으로 통일한다. 기존 서버 경로는 초기 등록에서 이동하지 않는다. 최신 지침은 [서버 관리 기준](../operations/server-workspace/README.md)과 [에이전트 지침](../operations/server-workspace/AGENTS.md)을 따른다.

검토일: 2026-10-30. 근거: 사용자가 제공한 `20261030-121331/report.md` (생성 2026-10-30 03:13:31 UTC, 한국시간 12:13:31). 실서버 변경은 수행하지 않았다. 아래 운영 상태는 조사 시점의 스냅샷이며 이후 상태를 단정하지 않는다. 원본 보고서는 저장소에 복사하지 않는다.

## 결론

기존 `~/my-server`는 운영 디렉터리다. 그 아래 DuctTape Git 저장소의 브랜치는 develop이다. 기존 디렉터리를 통째로 이동하거나 브랜치를 전환할 필요가 없다. 포스팅 저장소는 이미 ~/apps에 분리되어 있어 그대로 유지한다. 먼저 포스팅 앱에 독립 Compose 운영 구성을 추가하고, 기존 서비스 이관은 백업과 의존 경로 확인 후 별도로 진행한다.

## 확인된 서비스와 경로

| 서비스 | 실행/상태 | 코드·운영 위치 | 데이터 위치 | 호스트 포트·외부 연결 |
| --- | --- | --- | --- | --- |
| DuctTape | Docker, running/healthy, unless-stopped | 코드 `~/my-server/duct-tape`, 운영 파일 `~/my-server/compose.duct-tape.yml` | duct-data→/data, duct-temp→/work, duct-uploads→/app/uploads, deployment→/media(읽기 전용) | 127.0.0.1:8000, Tailscale :443 Funnel |
| File Browser | Docker, running/unhealthy, always | `~/my-server/docker-compose.yml` | storage→/srv, settings.json→/config/settings.json, filebrowser.db→/database/filebrowser.db, /config·/database의 익명 볼륨도 존재 | 모든 IPv4/IPv6 인터페이스 :8080; 인터넷 직접 노출 여부는 이 보고서만으로 미확정 |
| Nginx | Docker, running, always | `~/my-server/docker-compose.yml` | html→/usr/share/nginx/html | 모든 IPv4/IPv6 인터페이스 :80; 인터넷 직접 노출 여부는 미확정 |
| 포스팅 자동화 | 사용자 수동 실행/접속 성공 보고, 조사 때 :8010 리스너 없음 | 코드 `~/apps/posting-automation-workspace/posting-automation` | 코드상 기본 저장 위치 `.local/ui/`; 보고서는 숨김 폴더를 탐색하지 않아 서버의 실제 자료 존재·크기 미확인 | Tailscale :8443 tailnet 전용 → 127.0.0.1:8010 라우팅은 유지됨 |

중지된 hello-world 컨테이너도 하나 있지만 현재 정리 대상에 포함하지 않는다. 네트워크·볼륨·이미지 삭제 없이 서비스를 정리할 수 있다.

Git 저장소 두 곳은 조사 시점 모두 develop, 작업 트리 변경 0개다. 포스팅 커밋은 2ae9295, DuctTape 커밋은 7b7c8a4다. 변경 0개는 ignored 데이터/설정이 없다는 뜻이 아니다. 포스팅 저장소의 기존 backend/frontend 디렉터리는 저장소 원래 구성으로 보존하며, 서버 서비스가 실행 중이라는 증거는 없다.

## 먼저 해결할 운영 경계

1. 두 Compose 파일이 모두 project=my-server로 실행되어 있다. 파일 이름이 다르다고 프로젝트가 분리되는 것은 아니다. 기존 서비스를 당장 이름 변경하지 않고, 신규 포스팅에 고유 프로젝트 이름 `posting-automation`을 쓴다. 기존 my-server에서 --remove-orphans 또는 일괄 down으로 정리하지 않는다.
2. 포스팅 라우팅이 있어도 앱 프로세스는 별도로 살아 있어야 한다. 이번 보고서에서 8010이 없다는 사실과 앞선 사용자 접속 성공은 서로 다른 시점의 관찰이다. 현재 가용성은 재확인이 필요하며 Compose 상시 실행/재시작 정책으로 운영을 정리한다.
3. File Browser의 unhealthy는 healthcheck 실패 표시다. 원인이나 실제 화면/기능 장애 여부는 보고서에 없다. healthcheck 정의와 결과를 서버에서 확인하고, 데이터 백업 후 필요한 수정을 개별 적용한다.
4. File Browser는 파일 bind mount와 익명 볼륨을 함께 쓴다. 익명 볼륨이 비어 있다고 가정하지 않는다. DB·설정과 함께 볼륨 내용/사용 여부를 확인한 뒤 향후 명명된 저장소 또는 명시적 데이터 폴더로 이관한다.
5. Nginx/File Browser의 모든 인터페이스 바인딩은 확인됐지만 공유기 포트 포워딩·호스트 방화벽·접근 통제는 미확인이다. DuctTape :443은 Funnel 공개, 포스팅 :8443은 tailnet 전용으로 확인됐다. 이번에는 접근 방식을 바꾸지 않는다.

## 목표 디렉터리 역할

프로젝트마다 다른 규칙을 만들지 않고 아래 역할만 고정한다. 아래 미래 경로는 아직 생성·이동하지 않았다.

```text
/home/jobchoi/
├── apps/                              # Git 코드
│   └── posting-automation-workspace/   # 현재 저장소 그대로
│       └── posting-automation/
│           ├── compose.yaml           # 추가할 운영 정의(현재 미구현)
│           └── .local/ui/             # 최초 컨테이너 전환 시 기존 자료 유지
├── services/                          # 프로젝트별 서버 설정·운영 안내(향후)
│   ├── README.md                      # 이름/코드/Compose/데이터/포트/접속주소 목록
│   └── posting-automation/
│       └── .env                       # 서버 전용 설정, Git 제외
├── app-data/                          # 신규/이관 완료 서비스의 영속 데이터(향후)
│   └── posting-automation/ui/
├── backups/                           # 서비스별 백업 묶음(향후)
│   ├── posting-automation/
│   └── duct-tape/
├── server-audits/                      # 현재 조사 결과
└── my-server/                         # 기존 운영을 그대로 유지
    ├── compose.duct-tape.yml
    ├── docker-compose.yml
    ├── duct-tape/
    ├── duct-data/
    ├── duct-temp/
    ├── duct-uploads/
    ├── deployment/
    ├── storage/
    ├── html/
    ├── settings.json
    └── filebrowser.db
```

Compose 정의는 프로젝트 코드와 함께 버전 관리하고 서버별 설정만 services 아래에 둔다. 경로가 두 곳으로 나뉘어도 관리 명령은 명시적인 프로젝트 이름과 Compose 절대 경로를 사용하도록 만들 예정이다. 공통 Compose 파일 하나에 모든 프로젝트를 넣지 않는다.

app-data는 목표 경로다. 최초 Docker 전환은 기존 `.local/ui/`를 bind mount하여 자료 이동 없이 수행하는 것이 우선이다. 이후 쓰기를 중단한 상태에서 백업·복사·파일 수/해시/권한 확인·원고 재열기 검증 후 app-data로 변경한다. 기존 자료를 빈 새 폴더로 덮거나 컨테이너 내부에만 보관하지 않는다.

## 실행 순서와 완료 기준

### 1. 포스팅 앱 독립 운영 준비 — 다음 구현

- Dockerfile, .dockerignore, 고유 프로젝트 이름의 compose.yaml 추가.
- CPU 아키텍처 aarch64 환경에서 빌드·실행 확인. Python/패키지 버전을 코드와 맞춤.
- 단일 앱 프로세스/워커, restart=unless-stopped, 제한된 로그 용량과 상태 점검.
- 기존 :8010 수동 앱을 확인하고 계획된 전환 시에만 종료. 컨테이너는 host 127.0.0.1:8010에 바인딩, 기존 Tailscale :8443 매핑 유지.
- 컨테이너 내부에서 리버스 프록시의 소스 주소가 달라질 수 있다. 기존 run_ui.sh의 127.0.0.1 프록시 신뢰 설정을 그대로 복사하거나 전체 주소를 무조건 신뢰하지 않고, 실제 Docker 프록시 경로를 확인해 HTTPS Origin 검사까지 시험한다.
- 원고·사진·템플릿 저장소를 외부 bind mount, 컨테이너 사용자와 기존 파일 권한 일치 확인.
- 실행/로그/갱신/중지/백업 명령을 해당 프로젝트에만 적용하는 스크립트 추가.
- 자료 생성·사진·저장·재열기·내보내기·컨테이너 재생성 후 데이터 유지·재부팅 후 복구 검증.
- 실패 시 새 컨테이너만 중지하고 동일 데이터 경로로 기존 venv 앱 재실행. 기존 DuctTape/443은 변경 없음.

### 2. 기존 서비스 추가 확인

- compose.duct-tape.yml, docker-compose.yml의 서비스·build context·mount·network·healthcheck·변수 **이름/참조** 확인. 원문에 비밀값이 있을 수 있어 그대로 채팅에 붙이지 않는다.
- File Browser healthcheck 실패 원인과 익명 볼륨 내용/중첩 파일 mount 사용 여부 조사.
- 현재 데이터 크기·소유권·백업 가능 공간 확인. DB는 앱별 정상 백업 또는 쓰기를 멈춘 일관된 백업으로 보관하고 복원 시험.
- storage의 Samba/NFS 공유 여부, deployment를 사용하는 다른 서비스, cron 등 경로 의존성 확인. smbd/nmbd/winbind/rpcbind가 실행 중이므로 Docker mount만 보고 경로를 옮기지 않는다. 실제 공유 설정은 보고서에 없다.

### 3. 기존 서비스 선택적 이관

- 포스팅 운영이 검증된 다음 DuctTape만 별도 Compose 프로젝트/코드 경로로 이관할 필요가 있는지 결정.
- build context·상대 경로·권한·네트워크·포트를 검증하고 앱별 전환/복구 절차 마련.
- 데이터/업로드/공유 파일을 임의로 합치지 않는다. 새 프로젝트를 추가할 때는 apps/services/app-data/backups 규칙을 사용한다.

## 이번에 수행한 범위

보고서 분석과 배치안 문서화, TASKS 현황 갱신만 수행했다. 실서버 파일 이동/컨테이너 중지/데이터 복사/설정 변경은 수행하지 않았다. Docker 운영 구성 및 서비스별 백업/복구 스크립트는 다음 구현 범위다.

## 참고

- [Docker Compose 프로젝트 이름과 격리](https://docs.docker.com/compose/how-tos/project-name/)
- [Compose down의 제거 범위와 익명 볼륨](https://docs.docker.com/reference/cli/docker/compose/down/)
- [Docker 데이터 저장 방식](https://docs.docker.com/engine/storage/)
