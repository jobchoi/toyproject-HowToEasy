# 포스팅 앱 실제 이관 실행 순서

이 문서는 ~/web-server 초기 등록을 마친 라즈서버용이다. DuctTape/Nginx/File Browser 및 Tailscale 443/8443 연결은 변경하지 않는다. 이번 코드가 커밋/push되어 서버에서 최신 버전을 받은 뒤 실행한다. 아직 Docker 빌드/ARM 실실행을 검증한 배포가 아니므로 첫 실행 로그와 화면 결과를 확인한다.

## 1. 최신 코드 받기

기존 포스팅 원본 저장소에서:

```bash
cd ~/apps/posting-automation-workspace/posting-automation
bash scripts/update_project.sh --profile test
```

업데이트에는 manage_server.py, posting_deploy.py, Dockerfile, deploy/compose.yaml이 포함되어야 한다. 생성된 ~/web-server/manage.sh는 기존 스크립트를 호출하므로 최신 기능을 그대로 사용할 수 있다.

## 2. 계획 확인 후 기존 포스팅 앱만 종료

```bash
cd ~/web-server
./manage.sh prepare-posting --hostname raspberry-m5.tail1a38c1.ts.net
```

기존 run_ui.sh 실행 터미널에서 Ctrl+C로 종료하고 프롬프트가 돌아올 때까지 기다린다. DuctTape나 다른 Docker 서비스를 종료하지 않는다. 터미널을 찾기 어려우면 `ss -ltnp 'sport = :8010'`로 프로세스를 확인한 뒤 포스팅 앱만 정상 종료한다. 스크립트는 8010이 사용 중이면 PORT_BUSY로 중단한다.

이후 복사가 끝날 때까지 기존 앱을 다시 시작하거나 원고 폴더를 수정하지 않는다. 원본 저장소에 미커밋 변경이 있으면 SOURCE_DIRTY로 중단한다. ignored 파일은 코드 복사에 포함하지 않으며 저장 원고는 별도로 복사한다.

## 3. 코드·자료 복사와 백업 검증

```bash
./manage.sh prepare-posting \
  --hostname raspberry-m5.tail1a38c1.ts.net --apply
```

이 단계가 수행하는 일:

1. 등록된 기존 코드와 .local/ui 경로, 포트, Git 상태를 점검한다.
2. 기존 저장소의 커밋을 새 posting-automation/repo로 로컬 clone하고 origin을 프로젝트 GitHub 주소로 설정한다. 원본을 이동/삭제하지 않는다.
3. 기존 .local/ui를 새 data/ui로 복사하고 원본/복사본의 SHA-256을 대조한다.
4. backups/before-docker-*.tar.gz를 생성한다. 임시 경로에 실제로 풀어 복사본과 해시를 대조한다.
5. 프로젝트 루트 .env와 compose.yaml 진입점을 생성하고 prepared_not_started를 기록한다. 컨테이너는 시작하지 않는다.

Docker 이미지에는 허용한 앱 코드·의존성 목록·예제·TASKS만 보낸다. .env·실제 원고·사진·venv·Git 메타데이터는 빌드 컨텍스트에서 제외한다.

새 데이터와 원본이 다르면 DATA_CONFLICT로 중단하며 덮어쓰지 않는다. 코드/설정이 다르면 TARGET_CONFLICT 또는 CONFIG_CONFLICT로 중단한다. 심볼릭 링크/특수 파일도 자동 복사하지 않는다. 실패 시 이미 생성된 코드·자료·백업은 보존하므로 로그를 확인한 뒤 재시도한다. 빈 저장소 경로는 DATA_MISSING이며 자동으로 새 빈 원고를 만들지 않는다.

복사 범위는 저장 원고·사진·사용자 템플릿·작업 상태가 있는 `.local/ui`다. resources의 원문/PDF 및 브라우저 시험 기록 등 다른 ignored 자료는 기존 위치에 남는다. 기존 저장소는 삭제하지 않는다. 생성 백업을 서버 밖으로도 별도 복사한다.

## 4. 컨테이너 시작

```bash
./manage.sh posting start --apply
./manage.sh posting status
```

고유 Compose 프로젝트 posting-automation의 web 서비스만 config 점검 → 빌드 → 시작 → 상태 점검한다. 첫 빌드에는 이미지/패키지 다운로드 시간이 필요하며 진행 중 상태는 시작/실패/완료 코드로 기록한다. 빌드 원시 출력은 JSONL에 복사하지 않아 잠시 출력이 없는 구간이 있을 수 있다. 실패하면 자동 삭제하지 않는다.

이 서비스는 Linux host 네트워크를 사용하고 앱은 127.0.0.1:8010에만 바인딩한다. Docker port 매핑은 없다. 기존 Tailscale loopback 프록시와 신뢰 IP를 유지하기 위한 선택이며 네트워크 네임스페이스는 호스트와 공유한다. 컨테이너는 운영 사용자 UID/GID, 쓰기 가능한 data/ui 마운트, 읽기 전용 코드, 권한 제거, 로그 회전, 단일 워커로 실행한다. 기존 프로세스를 새 앱과 동시에 실행하지 않는다.

서비스 정의 원본은 repo/posting-automation/deploy/compose.yaml 하나이며 프로젝트 루트 compose.yaml은 extends 진입점이다. 서버 값은 .env만 수정한다. 다른 Docker context가 선택돼 있더라도 이 관리 작업은 로컬 default context를 사용한다.

## 5. 브라우저 검토와 기록

Tailscale이 켜진 기기에서 다음 주소를 연다.

https://raspberry-m5.tail1a38c1.ts.net:8443/

- 기존 원고와 사진이 열리는지 확인한다.
- 테스트 원고 편집·저장·재열기·HTML/ZIP 내보내기를 확인한다.
- 컨테이너 중지/재시작 후 원고가 유지되는지 확인한다.

```bash
./manage.sh posting stop --apply
./manage.sh posting start --apply
```

접속·저장·재시작을 직접 검토한 뒤:

```bash
./manage.sh posting confirm --apply
./manage.sh status
```

confirm은 사용자가 검토했다는 기록을 남기고 migrated로 변경한다. 단순 healthcheck 통과와 외부 접속·복원 검증은 다르다. 서버 재부팅 자동 복구와 서버 밖 백업은 별도로 확인/기록한다. 기존 루트 README/AGENTS는 재초기화로 덮어쓰지 않으므로 최신 운영 방식은 프로젝트 MIGRATION.md와 등록표를 함께 읽는다.

## 오류 확인과 복구

관리 명령의 JSONL 로그는 ~/web-server/logs에 기록된다. 명령 원시 stdout/stderr와 환경값은 저장하지 않는다. PORT_BUSY/SOURCE_DIRTY/DATA_CONFLICT/CONFIG_CONFLICT/BACKUP_VERIFY/DISK_SPACE 등 실패 코드를 기준으로 확인한다.

Docker 빌드 상세 오류가 필요할 때는 해당 프로젝트에서 직접 확인한다. 출력에 서버 설정/경로가 포함될 수 있으니 공유 전에 확인한다.

```bash
cd ~/web-server/posting-automation
docker --context default compose --env-file .env -p posting-automation -f compose.yaml build web
docker --context default compose --env-file .env -p posting-automation -f compose.yaml logs --tail 100 web
```

실패 후 다른 서비스를 내리거나 prune/down -v를 실행하지 않는다. 새 앱만 중지하려면 `~/web-server/manage.sh posting stop --apply`를 사용한다. 원본 코드와 원본 .local/ui는 그대로 남아 있다.

새 앱에서 아직 자료를 수정하지 않았다면 기존 원본 폴더에서 이전 POSTING_ALLOWED_HOSTS 설정으로 run_ui.sh를 실행해 되돌릴 수 있다. 새 앱에서 이미 저장한 글이 있다면 원본 데이터는 그 변경을 포함하지 않는다. 새 data/ui와 최신 백업을 먼저 보존하고 일관된 복구 계획을 세운 뒤 원본으로 복원한다. 자동 데이터 덮어쓰기/역복사는 제공하지 않는다.

현재 Docker 엔진이 없는 개발 환경에서는 준비/복사/백업 복원·상태 전이의 자동 검사를 수행했다. Docker Compose config·실제 이미지 빌드·라즈 ARM 실행·Tailscale HTTPS·재부팅은 서버 현장 검증 항목이다.
