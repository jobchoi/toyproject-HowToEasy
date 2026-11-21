# V1-REST 구현 결과 — 2026-11-21

현재 `feature/space-utilization-v1` 유지. 브랜치 변경·커밋·push 없음.
실제 `backend/study_room.db`를 열거나 수정하지 않았다. TASKS·HANDOFF·WORK_HISTORY도 수정하지 않았다.

## 수정 파일

- `backend/app/space_api.py`: 운영 기간·날짜로 필터링한 표 API(`/api/reports`). 주간 반복 응답, 미응답, 해당 날짜의 배정과 빈 좌석을 동일한 조회 결과로 제공.
- `backend/migrations/004_history_protection.sql`: 배정 직접 삭제·동일 ID 덮어쓰기 방지, 배정 이력이 있는 좌석 삭제 방지. 실제 DB 적용 없음.
- `backend/app/backups.py`: 신규 스키마 백업의 복구 검사 목록 갱신. 이전 스키마 백업 복구는 기존 정책대로 거부한다.
- `backend/tests/test_startup.py`: 시작 시 적용되는 마이그레이션 목록 갱신.
- `backend/tests/test_v1_rest.py`: pytest 5개 추가(매개변수 포함). 임시 DB만 사용.
- `frontend/src/App.jsx`: 표 API 연결, 빈 좌석 표시, 사전 응답 기간 필터·기존 응답 수정, 작업 순서 앵커, 계정·백업 영역 인쇄 제외.
- 본 보고서. 별도로 지정된 `_progress/PROGRESS.md`에 단계별 기록을 추가했다.

## 범위별 결과

| 범위 | 결과 | 근거·한계 |
| --- | --- | --- |
| 1 주간 응답·미응답 | 충족(자동 검증), UI 미검증 | 기존 저장 기능 유지. 같은 요일 다음 주 반복, 다른 요일 미응답, 응답 초기화, 시간대·기간 격리 테스트 |
| 2 운영표·좌석표·인쇄 | 구현 충족, 브라우저 미검증 | 두 표가 `/api/reports` 결과 공유. 빈 좌석·공간 단위 배정·이동 전후 조회. 기존 인쇄 CSS에 맞춰 편집 영역 숨김 |
| 3 이력 보호·동시 충돌 | 충족(자동 검증) | DELETE·REPLACE 거부, 별도 SQLite 연결 2개의 동시 쓰기에서 동일 좌석 또는 동일 이용자 경쟁 시 한 건만 저장. 날짜 구간은 시작 포함·종료 제외이며 날짜 배정이 모든 시간대에 적용됨 |
| 4 화면 흐름 | 구현 충족, 브라우저 미검증 | 공간→기간→시간대→좌석·배정→사전 응답→표 앵커. 응답의 공간/기간 선택에 따라 시간대 필터 |

## 실행 검증

- `PYTHONPATH=backend python3 -m pytest backend/tests -q`: 최종 **17 passed**, 기존 SQLAlchemy declarative_base 경고 1개. 기존 12개 유지 + 신규 5개.
- 최초 실행: 16 passed / 1 failed. 백업 복구의 고정 스키마 목록에 004가 누락되어 수정 후 전체 재실행 통과.
- `git diff --check`: 통과.
- `cd frontend && npm run lint && npm run build`: eslint 설치 부재로 lint에서 중단. build 미실행.
- `npm ci --offline --no-audit --no-fund`: 캐시 누락(ENOTCACHED).
- `npm ci --no-audit --no-fund --cache /tmp/v1-rest-npm-cache --fetch-retries=0 --fetch-timeout=15000`: npm 자체 오류(Exit handler never called). 의존성 선언·lockfile 변경 없음.
- 서버 실행·HTTP·브라우저·인쇄 미검증. 아래 단계는 Claude의 후속 실행 절차이며 실행 성공 보고가 아니다.

## Claude 격리 실행 및 합성 데이터 준비

저장소 backend 디렉터리에서 서버나 계정 CLI를 실행하지 않는다. 실행 작업 디렉터리가 DB 경로이므로 반드시 새 임시 디렉터리를 사용한다.

```sh
repo=/home/jobchoi/project/toyproject-HowToEasy
sandbox=$(mktemp -d /tmp/space-v1-rest.XXXXXX)
cd "$sandbox"
python3 "$repo/backend/scripts/create_operator.py"
PYTHONPATH="$repo/backend" python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

계정은 대화형으로 새 합성 계정을 생성한다. 다른 터미널에서 `cd /home/jobchoi/project/toyproject-HowToEasy/frontend`, 기존 lockfile 기준 `npm ci`, `npm run lint`, `npm run build`, `npm run dev -- --host 127.0.0.1` 실행. `http://localhost:5173/`에서 로그인한다.

합성 데이터는 화면으로 등록한다:

1. `/#spaces`: 합성 자습실(좌석 사용)과 합성 작업실(좌석 없음) 생성.
2. `/#periods`: 두 공간에 각각 2090-01-01~2090-02-01 기간 생성(종료일 미포함).
3. `/#slots`: 각 기간에 오전 09:00~10:00, 자습실에 오후 13:00~14:00 추가. 같은 기간명이 있어도 공간명으로 구별되는지 확인.
4. 이용자 등록 영역에서 합성 가·나 생성. `/#assignments`에서 자습실 A·B·C 좌석을 만들고 합성 가를 A에 2090-01-01부터 배정, 2090-01-15에 B로 이동. 합성 나는 작업실에 공간 단위 배정.
5. `/#responses`: 자습실 기간·오전·월요일에 합성 가의 참여 예정을 저장. 목록의 수정 버튼으로 불참 예정과 합성 사유로 수정. 미응답 저장 시 응답이 사라지는지 확인.
6. `/#reports`: 2090-01-02와 2090-01-09(둘 다 월요일)의 응답 반복, 오후 미응답, 01-14/01-15의 A→B 이동, 빈 좌석 C 확인. 작업실에는 가짜 좌석 없이 공간 단위 배정 표시. 02-01은 표 조회·인쇄 불가 확인.
7. 인쇄 미리보기에서 표와 공간·기간·날짜만 남고 로그인 정보·계정·백업·입력 양식은 숨겨지는지 확인. 저장·수정 후 표가 갱신되는지 확인.
8. 네트워크 또는 콘솔 오류와 브라우저 인쇄 결과를 기록한다. 실행 환경에서 포트가 열리지 않으면 미검증으로 유지한다.

자동 테스트 합성 데이터는 `backend/tests/test_v1_rest.py`의 임시 DB fixture에 정의되어 있으며 실제 DB와 무관하다. 실제 출결·날짜별 예외는 추가하지 않았다.
