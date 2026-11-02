# 기존 File Browser 상태 검사 수정

## 확인 사실과 수정 범위

2026-11-02 사용자 결과:

- 호스트 127.0.0.1:8080의 GET / 및 /health 모두 HTTP 200.
- 컨테이너 안 wget --spider http://127.0.0.1:80/health 종료 코드 0.
- 기존 /healthcheck.sh 종료 코드 1, 반복 unhealthy.
- 설정에서 address/port를 조회한 결과 모두 null. 키 부재인지 명시적 null인지까지는 확정하지 않음.
- wget/JSON.sh/설정 파일은 사용 가능. jq는 없지만 이미지 구현에 따라 JSON.sh를 사용하므로 이것만으로 장애 원인으로 단정하지 않음.

공식 healthcheck 구현은 설정/환경값에서 주소·포트를 읽어 /health를 요청한다. 위 결과는 앱 응답 자체보다 검사 URL 구성 경로의 문제를 시사한다. 실행 이미지 안의 스크립트 버전/환경 우선순위를 모두 확인한 것은 아니다. 수정은 실제 검증된 고정 주소의 healthcheck로 한정한다. settings.json의 address/port를 임의 변경하면 앱의 실제 바인딩이나 향후 재시작에 영향을 줄 수 있으므로 변경하지 않는다.

## 실행

작업 PC에서 이 변경을 push하고, 서버에서 관리 중인 repo를 갱신한다. 이제 이전 apps 저장소는 업데이트 대상이 아니다.

```bash
# 라즈서버
git -C ~/web-server/posting-automation/repo status --short
# 변경이 있다면 보존하고 아래 갱신을 중단한다.
git -C ~/web-server/posting-automation/repo pull --ff-only origin develop

cd ~/web-server
./manage.sh repair-filebrowser
./manage.sh repair-filebrowser --apply
./manage.sh diagnose-filebrowser
./manage.sh doctor
```

apply 시 기존 file-service가 잠시 중지/재생성되므로 File Browser의 업로드·파일 작업은 멈추고 실행한다. 포스팅/DuctTape/Nginx는 중지하지 않는다. 새 이미지 다운로드/빌드는 하지 않으며 현재 실행 이미지 ID를 고정한다.

## 실행 단계

1. file-service의 실제 Compose 프로젝트/서비스 이름/원본 파일·작업 경로/이미지 ID/마운트만 조회한다.
2. projects.json의 기존 프로젝트와 Compose 파일이 일치하는지 확인한다.
3. 컨테이너 안에서 검증한 wget loopback 요청을 재확인한다.
4. ~/web-server/filebrowser/health.override.json을 생성한다. 서비스 전체 정의를 복사하지 않고 현재 이미지 ID와 healthcheck만 담는 Compose override다.
5. 원본 Compose와 override 적용 결과를 비공개로 비교한다. image/healthcheck 이외의 필드 또는 다른 서비스 변경, bind mount 경로/권한 드리프트가 있으면 중단한다. 병합된 config는 비밀값이 포함될 수 있어 출력/로그 저장하지 않는다.
6. file-service만 정지하고 settings.json, filebrowser.db, 원본 Compose를 backups/health-fix-*에 권한 600으로 복사·해시 검증한다. 원본 파일은 바꾸지 않는다.
7. 원본 Compose + override를 명시하고 --no-deps/--no-build/--pull never로 대상 서비스만 재생성한다. --remove-orphans/down/prune/볼륨 삭제/renew-anon-volumes는 사용하지 않는다.
8. 상태 검사 통과를 기다리고 재생성 전후 모든 마운트가 동일한지 확인한다. 익명 볼륨을 새 것으로 바꾸지 않는다.
9. 등록표에 override/백업/수정 상태를 기록하고 이력을 남긴다. 실제 새 프로젝트 이관 완료로 표시하지 않는다.

동일 override를 사용하는 컨테이너가 이미 healthy면 재생성하지 않는다. 설정 충돌/파일 읽기 권한 부족/예상과 다른 마운트는 자동 해결하지 않고 중단한다. 사용자 설정·DB·공유 파일이 있는 기존 경로는 그대로 유지한다.

## 적용 후 관리 주의

healthcheck 수정은 기존 위치에서 수행한다. File Browser의 새 repo/data 이관이 완료된 것은 아니다. 현재 Compose 프로젝트 이름 my-server도 유지한다. 이후 운영·재생성 때는 projects.json의 legacy_compose_overrides에 기록된 health.override.json을 원본 Compose와 **함께** 사용해야 한다. 원본 docker-compose.yml만으로 다시 생성하면 이미지 기본 검사가 돌아올 수 있다.

현재 이미지 ID 고정은 상태 검사 수정과 이미지 업데이트를 분리하기 위한 것이다. 추후 의도적으로 이미지를 교체할 때 이 고정값도 별도 검토해야 한다. health.override.json을 무조건 덮어쓰지 않는다.

건강 검사 정상화 후 웹 로그인·파일 목록·다운로드를 실제로 확인한다. settings.json/DB 백업에는 민감값이 있을 수 있어 서버 밖에 보관할 때도 접근 권한을 유지하고 채팅이나 Git에 올리지 않는다. 본 수정의 백업은 설정/DB/Compose이며 공유 파일 저장소 전체를 백업하는 기능은 아니다.

## 오류 시

JSONL 로그의 마지막 코드와 projects.json의 health_repair_state를 확인한다. 실패하면 기존/새 이름 file-service 컨테이너 시작만 재시도한다. 자동 자료 복원·파일 덮어쓰기·컨테이너 삭제는 하지 않는다. recovery_required는 실제 앱/상태 검사/마운트를 추가 확인해야 한다는 뜻이다. 생성된 백업과 기존 익명 볼륨을 지우지 않는다. 잘못된 마운트나 데이터가 의심되면 File Browser 사용을 멈추고 백업 경로와 함께 원인을 확인한다.

개발 환경에는 Docker가 없어 명령 선택/설정 변경 범위/백업 보존/실패 경로를 모의 검사했다. 실제 Compose 해석·재생성·익명 볼륨 유지·healthy 판정은 라즈서버 실행 시 검증한다.

참고:
- [공식 이미지 healthcheck](https://github.com/filebrowser/filebrowser/blob/master/docker/alpine/healthcheck.sh)
- [Compose up의 대상 서비스·마운트 보존 옵션](https://docs.docker.com/reference/cli/docker/compose/up/)
