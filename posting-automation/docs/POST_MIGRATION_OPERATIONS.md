# 포스팅 이관 후 운영 및 기존 서비스 진단

2026-11-02 사용자 로그에서 prepare→백업 복원 검증→Docker running/healthy→stop/start→confirm 완료를 확인했다. 이 사실은 사용자 서버 로그 기반이며 개발 환경에서 직접 실행한 Docker 검증과 구분한다. 화면/사진/편집·내보내기, 재부팅 자동 복구, 서버 밖 백업은 별도 확인 항목이다.

## 현재 상태

- 포스팅 코드: ~/web-server/posting-automation/repo
- 저장 원고/사진/템플릿: ~/web-server/posting-automation/data/ui
- 백업: ~/web-server/posting-automation/backups
- 서버 설정/운영 진입점: 프로젝트 루트 .env / compose.yaml
- 관리 명령: ~/web-server/manage.sh
- 이전 ~/apps 및 ~/my-server는 아직 삭제하지 않는다. File Browser는 원인 확인 전 유지한다.

## 이번 기능을 서버에 반영

먼저 작업 PC의 커밋을 push한 뒤, 아직 관리 실행기가 참조하는 기존 저장소에서 최신 관리 코드를 받는다. 이후 관리 실행기 자체를 이관된 repo로 바꾸면 앞으로는 web-server에서만 관리할 수 있다.

```bash
# 라즈서버
cd ~/apps/posting-automation-workspace/posting-automation
bash scripts/update_project.sh --profile test

cd ~/web-server
# 원고 수정은 잠시 멈추고, 백업이 끝날 때까지 터미널을 유지한다.
./manage.sh posting backup --apply

# 이관된 repo도 최신 코드로 갱신 (미커밋 변경이 있다면 중단하고 보존)
git -C ~/web-server/posting-automation/repo status --short
git -C ~/web-server/posting-automation/repo pull --ff-only origin develop

./manage.sh use-managed
./manage.sh use-managed --apply
./manage.sh posting status
```

use-managed는 migrated 상태와 완전한 관리 코드, 깨끗한 Git 상태를 요구한다. 기존 manage.sh를 manage.sh.before-* 파일로 보관하고 원자적으로 교체하며 projects.json의 manager_script도 갱신한다. 코드/원고/컨테이너를 이동하거나 재시작하지 않는다. 실행기를 바꿔도 ignored 원문/PDF/시험 자료가 이전 경로에 남아 있을 수 있으므로 이전 저장소를 삭제하지 않는다.

이번 변경은 호스트에서 실행하는 관리 스크립트·문서 중심이므로 앱 이미지 재빌드 없이 백업/관리 전환 명령을 사용할 수 있다. 이후 앱 코드 또는 의존성이 변경됐다면 아래 업데이트 절차로 이미지를 교체한다.

## 일상 관리와 업데이트

```bash
cd ~/web-server
./manage.sh posting status
./manage.sh posting backup                # 계획만
./manage.sh posting backup --apply        # 실제 백업
```

백업은 현재 data/ui를 대상으로 한다. 실행 중인 포스팅 컨테이너만 잠시 중지하고 tar 생성→임시 경로 실제 복원→해시 검증 후 기존 이미지로 다시 켠다. 처음부터 중지돼 있던 서비스는 켜지 않는다. 백업이 실패해도 실행 중이던 앱은 재개를 시도한다. 재개까지 실패하면 recovery_required로 기록한다. 다른 서비스와 Tailscale은 변경하지 않는다.

BACKUP_COMPLETE 로그와 .tar.gz.json 검증 메타데이터가 있는 백업을 확인한다. 데이터/DB/원고를 쓰는 다른 프로세스가 있다면 먼저 중지해야 한다. 백업 중 앱은 잠시 응답하지 않으므로 유지보수 가능한 시간에 실행한다. 자동 정기 백업과 백업 자동 삭제는 아직 없다.

앱 업데이트 순서:

```bash
cd ~/web-server
./manage.sh posting backup --apply
git -C ~/web-server/posting-automation/repo status --short
# 변경이 있으면 위 출력 확인 후 중단하고 보존한다.
git -C ~/web-server/posting-automation/repo pull --ff-only origin develop
./manage.sh posting start --apply
# 실제 화면/원고 저장을 검토한 뒤
./manage.sh posting confirm --apply
```

pull은 코드만 갱신하며 Docker 실행 코드는 이미지 재빌드 전까지 유지된다. managed repo 내부 .local/ui는 Docker의 운영 데이터가 아니다. 초기 prepare-posting을 다시 실행하지 않는다. 서버별 .env/data/backups는 Git pull 대상 밖에 둔다. 업데이트 실패 시 코드/데이터 백업을 보존하고 대상 컨테이너 상태를 확인한다. 자동 reset/자료 덮어쓰기/이미지 태그 되돌리기는 수행하지 않는다.

## File Browser 원인 조사

```bash
cd ~/web-server
./manage.sh diagnose-filebrowser
```

진단은 기존 이름 file-service를 대상으로 현재 image/health/failing streak, 검사 프로그램의 이름과 최근 검사 종료 코드·시각만 출력한다. 원시 healthcheck Output, 명령 인자/URL/인증정보, 환경값은 출력하지 않는다. 이 결과로 명령 미존재/검사 실패를 추가 조사할 수 있으며 이것만으로 원인을 단정하지 않는다. 컨테이너 실행·설정·자료는 변경하지 않는다. 결과 JSON 또는 해당 실행 JSONL 로그를 공유하면 다음 수정 범위를 정할 수 있다.

## 남은 현장 확인

1. 실제 원고·사진 표시/수정/저장·내보내기 확인.
2. 백업 tar.gz와 검증 메타데이터를 WSL 또는 외장 저장소로 복사. 서버 .env와 자료 원본의 별도 보관도 점검.
3. 가능한 유지보수 시간에 서버 재부팅 후 기존 DuctTape/포스팅/8443 접속 재확인. 임의로 지금 재부팅하지 않는다.
4. File Browser 진단 후 설정/DB·볼륨을 확인하고 백업한 뒤 개별 수정/이관.
5. Nginx 및 기존 Compose 프로젝트 분리는 그 다음 진행. my-server를 통째로 이동하거나 down/prune/볼륨 삭제하지 않는다.
