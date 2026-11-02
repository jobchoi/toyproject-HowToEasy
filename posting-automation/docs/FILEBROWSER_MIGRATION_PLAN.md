# FileBrowser 개별 이관 계획

2026-11-02 실제 SSH 조사 기준. 기존 서비스는 변경하지 않았다.

## 확인된 현재 구조

- 컨테이너: `file-service`, 서비스: `fileserver`, Compose 프로젝트: `my-server`.
- 현재 운영 파일: `~/my-server/docker-compose.yml` + `~/web-server/filebrowser/health.override.json`. 두 파일을 함께 사용해야 수정한 상태 점검이 유지된다.
- 호스트 포트: 8080 → 컨테이너 80. 네트워크: `my-server_default`.
- `~/my-server/storage` → `/srv`, `settings.json` → `/config/settings.json`, `filebrowser.db` → `/database/filebrowser.db`.
- `/config`, `/database`에 각각 익명 볼륨이 추가로 연결되어 있다. 루트 항목 및 일반 파일 조회 결과 각각 위의 bind 파일 한 개였다. 이 결과만으로 볼륨 내부 전체 백업을 대체하지 않는다.
- 다른 컨테이너와 겹치는 마운트 없음. 동일 Compose 프로젝트에 DuctTape와 Nginx가 있으므로 전체 down은 금지한다.
- Nginx의 실제 `nginx -T` 출력에서 `file-service`, `fileserver`, `8080`, `my-server` 참조 없음. 설정 원문은 로그에 보관하지 않았다.
- 공유 폴더 일반 파일 0개, 심볼릭 링크 0개, 조사 당시 가용 공간 약 19GB. 호스트 프로세스·사용자 cron·NFS·외부 클라이언트는 아직 전체 확인하지 않았다.

## 1차: 운영 제어 분리 (아직 미실행)

1. 최신 컨테이너/등록표/원본+override의 합성 Compose를 다시 대조한다. 원시 Compose는 비밀값이 있을 수 있으므로 출력하지 않는다.
2. 합성된 `fileserver`만 독립 운영 정의로 준비한다. 이미지 ID·포트·명령·사용자·재시작 정책을 보존하고 필요 외부 리소스를 검증한다. `depends_on`, secrets/configs 또는 예상하지 않은 리소스가 있으면 자동 전환을 중단한다.
3. 초기 전환에서는 기존 bind 경로와 익명 볼륨을 그대로 유지한다. 익명 볼륨은 실제 이름으로 external 선언하고, 네트워크도 기존 `my-server_default`를 external로 연결한다. 데이터 폴더 이동과 네트워크 교체를 한 번에 하지 않는다.
4. FileBrowser만 중지하고 설정·DB·필요 볼륨·공유 자료를 일관된 상태로 백업한다. 별도 경로에 복원하고 파일 목록/해시/권한을 검증한다.
5. 기존 컨테이너를 제거해야 새 Compose 프로젝트가 같은 이름·포트를 사용할 수 있다. 제거 전 원본 Compose+override 복귀 명령과 백업을 기록한다. 볼륨 삭제 플래그는 사용하지 않는다.
6. 고유 프로젝트 `filebrowser`로 대상 서비스만 시작한다. mount/이미지/포트/네트워크 일치, HTTP `/health` 및 Docker healthy, 다른 서비스 상태를 검사한다.
7. 실패하면 신규 대상만 정지하고 기존 Compose+override로 `fileserver`만 복귀한다. 다른 프로젝트를 재시작하지 않는다.
8. 웹 로그인·파일 목록/열기·저장 확인 후 운영 경로와 상태를 등록한다. 현재 단계에서는 `registered_not_migrated`를 유지한다.

## 2차: 데이터 위치 정리 (1차 검증 후)

- 호스트 프로세스·공유 서비스·외부 접근 경로 의존성을 확인한다.
- 정지 상태에서 `~/web-server/filebrowser/data/`로 복사하고 소유자/권한/해시를 검증한다. 원본은 보존한다.
- bind 경로만 바꿔 대상 서비스를 재생성한 뒤 읽기/쓰기 및 이전 자료 보존을 확인한다.
- 서버 밖 백업과 복귀 절차를 확인하기 전 원본을 삭제하거나 심볼릭 링크로 바꾸지 않는다.

## 재조사

작업 PC에서 아래 스크립트를 SSH stdin으로 실행할 수 있다. 서비스 변경은 없다.

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes raspberry-posting \
  python3 - < scripts/filebrowser_inventory.py > .local/filebrowser-inventory.json
```

출력은 마운트/포트/Compose/공유 경로 등 운영 메타데이터다. 공개 저장소에 추가하지 않는다. 환경값·설정 내용·DB 내용은 출력하지 않는다.
