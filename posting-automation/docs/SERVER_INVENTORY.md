# 라즈서버 구조 조사와 정리 준비

기존 DuctTape/my-server 및 포스팅 자동화를 유지한 채 서버의 현재 배치를 확인한다. `scripts/audit_server.py`는 Python 표준 라이브러리만 사용하며 가상환경 설치나 sudo가 필요 없다. 조사 대상에는 조회 명령만 사용하고, 지정한 결과 폴더에 보고서 두 개를 새로 쓴다. 파일 이동·서비스 중지/재시작·Docker 변경·Tailscale 설정 변경·Git fetch/pull을 실행하지 않는다.

## 1. 스크립트 전달

스크립트가 GitHub에 반영됐다면 서버에서 최신 코드를 받은 뒤 프로젝트의 scripts/audit_server.py를 사용한다. 아직 push하지 않았다면 작업 PC의 저장소 루트에서 파일 하나만 별도로 보낼 수 있다.

```sh
scp posting-automation/scripts/audit_server.py jobchoi@100.116.145.77:/tmp/posting-audit-server.py
```

## 2. 라즈서버에서 실행

위 scp 방식으로 보냈다면 서버에서:

```sh
python3 /tmp/posting-audit-server.py
```

저장소의 스크립트를 사용한다면:

```sh
cd ~/apps/posting-automation-workspace/posting-automation
python3 scripts/audit_server.py
```

기본 조사 루트는 사용자 홈, /opt, /srv, /var/www이며 깊이 4, 최대 디렉터리 1,500개다. Git 저장소가 더 깊은 곳이나 다른 디스크에 있다면 해당 상위 경로를 명시한다. --roots는 기본 목록을 대체한다.

```sh
python3 /tmp/posting-audit-server.py --roots "$HOME" /opt /srv /var/www /mnt/projects --depth 5
```

디렉터리당 최대 500개 항목만 열거하며 숨김 디렉터리, venv/node_modules, 캐시, data/uploads/logs 등은 하위 탐색에서 제외한다. 심볼릭 링크 디렉터리는 탐색하지 않는다. 누락·권한 부족·명령 부재·제한을 결과에 기록한다. 전체 서버를 완전히 조사했다는 뜻은 아니다. 저장소 자체가 제외된 경로에 있다면 조사 루트로 명시한다.

## 3. 결과 확인과 공유

완료 시 다음 결과 경로가 표시된다.

```text
~/server-audits/날짜-시각/
├── report.md
└── report.json
```

report.md를 먼저 검토하고 분석을 위해 공유한다. 필요하면 report.json도 함께 제공한다. 폴더는 700, 보고서는 600 권한으로 생성하며 기존 결과 폴더는 덮어쓰지 않는다. 보고서는 Git 저장소 밖에 보관한다.

수집 내용:

- 프로젝트 디렉터리와 Compose/Dockerfile/언어 manifest/systemd 파일의 **위치**
- Git 브랜치·커밋·변경 항목 수 (변경 파일명/본문, 원격 인증 URL 제외)
- Docker 컨테이너 이름·이미지·상태·포트·Compose 위치·재시작 정책·데이터 마운트
- 실행 중 시스템/사용자 서비스의 이름·실행 디렉터리·사용자·unit 파일 위치
- TCP 수신 포트·보이는 프로세스 이름/PID·작업 디렉터리·실행 파일 경로 (프로세스 명령 인자 제외)
- Tailscale Serve 라우팅과 Funnel 상태 (프록시 URL 인증정보/쿼리/본문 제외)

.env·인증키·파일 본문·컨테이너 환경변수·전체 docker inspect·서비스 ExecStart는 수집하지 않는다. 다만 경로·사용자명·호스트명·프로젝트/서비스/이미지 이름은 포함되므로 공유 전 확인한다. URL·경로에 사람이 비밀정보를 이름으로 넣은 경우까지 자동 제거하지는 못한다.

Docker 권한이 없거나 명령이 없으면 error가 기록된다. 이 스크립트 때문에 sudo로 전체 조사를 다시 실행하거나 Docker 그룹 권한을 변경할 필요는 없다. 결과를 먼저 확인한 뒤 꼭 필요한 항목만 추가 조사한다. 포트가 없는 백그라운드 작업이나 중지된 systemd 서비스 등은 이 결과만으로 완전히 파악되지 않을 수 있다.

## 4. 결과 분석 후 정리 순서

1. 현재 서비스 → 실행 방식 → 코드 경로 → 데이터 경로 → 포트 → 외부 연결을 대조한다.
2. 프로젝트별 코드/데이터/운영 설정 배치안과 유지할 기존 경로를 정한다.
3. 백업 대상·복구 방법·중단 필요 여부를 확인한다.
4. 새 포스팅 앱부터 독립 Compose 또는 systemd 관리로 전환한다.
5. 기존 DuctTape는 확인된 의존 경로·볼륨·설정을 기준으로 별도 이관한다.

폴더를 먼저 이동하면 Compose 상대 경로·마운트·systemd WorkingDirectory가 깨질 수 있다. 이 스크립트는 조사만 수행하며 정리를 자동 실행하지 않는다.

2026-10-30 보고서 분석 및 실제 경로 기준 정리안은 [서버 배치 검토](SERVER_LAYOUT_REVIEW.md)를 참고한다.
