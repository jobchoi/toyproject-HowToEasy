# V1-REST 교차 검토 후속 보완 결과

2026-11-21 · `feature/space-utilization-v1`

## 작업 범위

- `frontend/src/App.jsx`: 표 조회 effect 정리 시 AbortController로 fetch를 취소한다. 예약된 요청 시작 전과 응답 본문 해석 후에도 취소 신호를 확인한다. 공통 401 처리는 요청 당시 토큰과 현재 sessionStorage 토큰이 같을 때만 세션을 지운다. request/refresh를 useCallback으로 고정하고 effect 의존성을 명시했다. eslint-disable은 없다.
- `backend/app/backups.py`: 기존 001~004 버전 일치 정책을 유지하고, sqlite_master에서 004 필수 트리거 3개의 존재와 대상 테이블을 검사한다. 누락 시 복구 전 백업 생성이나 현재 DB 변경 전에 HTTP 400으로 거부한다.
- `backend/tests/test_startup.py`: 임시 DB에 001~003만 직접 적용하고 합성 좌석·이용자·배정 이력·기간·시간대·응답을 저장한 뒤 실제 lifespan으로 004 적용 및 재시작을 수행한다. 모든 합성 행 보존, DELETE·동일 ID REPLACE·이력 좌석 DELETE 거부, 종료일 UPDATE·새 ID 이동·좌석 사용 중지 성공을 검증한다. 거부 오류 문구도 확인하여 다른 제약 때문에 실패하는 오탐을 방지한다.
- `backend/tests/test_v1_rest.py`: 알려진 월요일 2026-01-05와 일요일 2026-01-11에 대해 weekday 0/6을 SQL로 직접 저장하여 조회 규약을 독립 검증한다. 미응답 초기화 후 실제 응답 행 0개, 기간 시작일 포함·종료일 미포함, 다른 기간에 실제 저장한 동일 이용자 응답의 비노출, 사용 중지 좌석의 과거 배정 및 종료일 이후 비표시를 확인한다.
- `backend/tests/test_auth_backup.py`: 003 백업 거부, 004 버전은 있으나 각 필수 트리거가 하나씩 없는 백업 거부, 거부 시 현재 DB와 백업 목록 보존을 검증한다. 배정이 있는 정상 백업 복구 후 데이터 복원·삭제/덮어쓰기 거부·종료/이동/사용 중지 허용을 검증한다.

## 확인 사항

- 트리거 이름은 `004_history_protection.sql`과 `backups.py`의 `REQUIRED_HISTORY_TRIGGERS`에서 함께 관리해야 한다. 테스트가 실제 마이그레이션으로 만든 보호 트리거 이름 집합과 상수를 비교하므로 한쪽만 변경하면 실패한다. 복구 검사는 존재와 대상 테이블을 확인하며 SQL 본문의 동일성 검사는 범위에 포함하지 않는다.
- 테스트의 SQLite 연결은 TemporaryDirectory/tmp_path 또는 메모리 DB만 사용한다. 기존 startup 테스트의 `study_room.db`라는 파일명도 임시 디렉터리 안에 생성된다. main의 기본 엔진은 import 시 연결하지 않으며 lifespan 테스트는 임시 엔진으로 교체한다.
- 실제 `backend/study_room.db`는 열거나 수정하지 않았다. TASKS·WORK_HISTORY·HANDOFF는 수정하지 않았다. 커밋·push·브랜치 변경을 하지 않았다.
- 진행 기록은 `/home/jobchoi/project/_progress/PROGRESS.md` 끝에 단계마다 한 줄씩 추가했다.

## 실행 명령과 결과 원문 요약

저장소 루트 기준:

```sh
cd frontend && npx eslint . && npm run build
```

최종 실행: 종료 코드 0. eslint 출력 없음(react-hooks 규칙 포함). 빌드 원문 요약:

```text
> frontend@0.0.0 build
> vite build
vite v8.1.0 building client environment for production...
transforming...✓ 17 modules transformed.
✓ built in 310ms
```

초기 eslint에서 catch 오류의 cause 누락 1건을 발견했고 `{ cause: error }`를 추가한 뒤 재검증했다.

```sh
PYTHONPATH=backend /home/jobchoi/miniforge3/envs/study-room/bin/python -m pytest backend/tests -q
```

최종 실행: 종료 코드 0.

```text
22 passed, 2 warnings, 6 subtests passed in 5.34s
```

경고 원문 요약: anyio pytest 플러그인의 `CallSpec2` 이름 변경 예정 경고(`PytestRemovedIn10Warning`), 기존 `declarative_base()` 위치 변경 경고(`MovedIn20Warning`). 전체 테스트는 포트 바인딩 없이 임시 DB·합성 데이터로 수행했다.

추가 검증: `node --input-type=module`의 인라인 검증에서 App.jsx의 실제 request 콜백 본문을 읽고 fetch/sessionStorage/상태 setter를 모의 구현했다. 이전 토큰 요청의 지연 401은 새 세션을 보존하고, 현재 토큰의 401은 세션을 지우며, 취소된 요청의 응답은 세션을 지우지 않는지 및 fetch에 signal이 전달되는지 assert로 확인했다. 원문:

```text
PASS: stale 401 preserves new session; current 401 clears session; aborted response preserves session; fetch receives abort signal
```

`git diff --check` 통과. 브라우저 UI·실제 네트워크 취소·인쇄·실운영 DB 복구는 실행 검증하지 않았다. Node 검증은 공통 요청 함수의 모의 실행이며 React 브라우저 통합 검증과 구분한다.
