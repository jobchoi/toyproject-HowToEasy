# 작업 지시서 V1-REST — 첫 버전 남은 기능(실제 DB 무관)

- 지시: Claude Code · 구현: Codex · 검증: Claude Code(격리 DB로 서버·브라우저 실행)
- 브랜치: `feature/space-utilization-v1` (변경·커밋·push 금지)
- 먼저 읽을 것: AGENTS.md, docs/space-utilization/README.md → V1_SCOPE.md → TASKS.md → HANDOFF.md → WORK_HISTORY.md, backend/

## 범위(V1_SCOPE 확정 범위 안에서 TASKS의 남은 항목)

1. 요일별 주간 반복 사전 응답과 미응답 처리(현재 시간대 등록만 구현됨)
2. 운영표·좌석표 화면과 인쇄용 보기(브라우저 인쇄 CSS)
3. 이력 직접 삭제 방지, 동시 배정 충돌(같은 좌석·같은 시간대 중복) 검증과 테스트
4. 운영 기간·시간대·사전 응답 화면이 기존 공간·좌석 화면과 연결되는 흐름

## 절대 조건
- `backend/study_room.db`(실제 데이터, Git 추적)를 열거나 수정·마이그레이션하지 않음. 테스트·개발은 임시 경로 DB와 합성 데이터만.
- 실제 출결은 V1 제외(V1_SCOPE). 범위 밖 기능 추가 금지.
- 기존 테스트 유지, 새 기능마다 pytest 추가. 의존성 추가 금지.
- 커밋·push·브랜치 변경 금지. 이 폴더의 TASKS.md·WORK_HISTORY.md·HANDOFF.md는 수정하지 말고 보고에만 적음(Claude가 검증 후 기록).
- 서버 포트를 열 수 없으면 브라우저 검증은 미검증으로 보고(Claude가 실행).

## 보고
1. 수정 파일 2. 범위 1~4 충족/미충족/미검증 + 근거 3. 실행한 명령과 결과(pytest 수) 4. Claude가 브라우저로 확인할 화면 경로와 합성 데이터 준비 방법
