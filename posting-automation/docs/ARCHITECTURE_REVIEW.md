# 구현 전 아키텍처 검토안

2026-10-23 / 상태: 사용자 검토용 제안. 확정 설계나 구현 완료 기록이 아님.

## 확인한 사실과 작업 상태

- 기존 backend/frontend는 자습실 관리용 FastAPI·React 프로젝트다. 수정하지 않는다.
- posting-automation에는 빈 디렉터리와 가상환경 준비만 진행했다. 서비스 코드·DB·UI는 없다. 가상환경은 system-site-packages 옵션으로 준비를 시도했으므로 본 구현 때 독립 환경과 잠금 파일로 재구성한다. 의존성 설치 완료 여부는 미확인이다.
- ../duct-tape/editorial/publishing/NEW_PROJECT_HANDOFF.md와 tools/blogger/README.md를 읽었다. 기존 CLI의 실제 계정 검증은 문서상의 과거 기록이며 이번 작업에서 재검증하지 않았다.
- 기존 CLI에는 고정 블로그·라벨·경로와 데스크톱 OAuth가 있다. 필요한 알고리즘과 테스트를 검토해 이식하되 서비스에서 CLI를 subprocess로 실행하지 않는다. 기존 코드·인증 파일·운영 DB를 수정하거나 자동 복사하지 않는다.
- 사용자 요청으로 단계 자동 구현보다 설계 검토를 먼저 한다. 루트의 기존 기획서는 보존한다.

## 제안하는 구성

WSL2 + Python 독립 venv + FastAPI + Jinja2 서버 템플릿 + 작은 JavaScript + SQLAlchemy + Alembic + SQLite로 시작한다. Python 및 패키지 버전은 구현 시작 시 호환성을 확인해 고정한다. 프런트엔드 빌드가 필수인 구조는 만들지 않는다. 편집 UI가 복잡해져 React가 필요하면 View를 교체할 수 있게 한다.

MVC를 기본으로 하되 Controller가 두꺼워지지 않게 Service와 Repository를 나눈다.

- Model: 원고 버전·검토·게시 규칙과 데이터 모델. HTTP 요청이나 템플릿에 의존하지 않는다.
- View: 서버 템플릿, CSS, 편집·미리보기 JavaScript. DB와 플랫폼 API에 직접 접근하지 않는다.
- Controller: 요청 검증·인증·서비스 호출·응답 변환. 웹용과 /api/v1용을 분리한다.
- Service: 원고 저장, 버전 충돌, 검토 무효화, 게시 작업 생성·실행·복구. 웹/API가 함께 사용한다.
- Repository: 조회·트랜잭션·소유권 범위와 DB 제약.
- Adapter: Blogger/모의 플랫폼, 비밀 저장소, 사용자 인증의 외부 경계.

```text
posting-automation/
  app/
    main.py
    config.py
    controllers/{web,api}/
    models/
    schemas/
    services/
    repositories/
    adapters/{publishing,identity,secrets}/
    views/{templates,static}/
  migrations/
  tests/{unit,integration}/
  docs/
  scripts/
```

처음부터 마이크로서비스로 나누지 않는다. 한 프로세스 안에서 모듈을 분리한다. 나중에 게시 실행기를 별도 워커로 옮길 경계를 만든다.

## 개발·서버 환경

- 개발: WSL 내부 파일시스템, 신규 가상환경·설정·DB 사용. 127.0.0.1:8010을 후보로 하며 사용 여부를 먼저 확인한다. 기존 자습실/DuctTape 서버를 재시작하지 않는다.
- 브라우저는 같은 출처의 웹/API에 접속한다. 개발부터 서비스 로그인과 Blogger 권한 연결을 분리한다.
- 초기 실행: 단일 Uvicorn 프로세스, SQLite 로컬 볼륨, 영속 게시 작업. 인프로세스 실행기가 작업을 처리하더라도 요청 종료 후 사라지는 작업만으로 구현하지 않는다.
- 재시작 시 외부 요청을 시작한 작업은 결과 불확실로 전환한다. 원격 확인 없이 생성 요청을 자동 반복하지 않는다. 외부 호출 동안 DB 쓰기 트랜잭션을 유지하지 않는다.
- 지인 테스트: 제한된 네트워크 + 허용 사용자 + 서비스 세션. 실제 OAuth 콜백 주소와 HTTPS 구성은 접속 환경에 맞춰 정한다.
- 선택적 Pi 운영: 별도 컨테이너·볼륨·포트. ARM 실행·메모리·재시작·백업 복원을 실제 확인한 후 지원으로 표시한다. Docker 파일 준비와 실제 배포를 구분한다.
- 사용자/쓰기 동시성 증가 시 PostgreSQL 검토. SQLAlchemy/Alembic을 사용해도 DB 전환이 자동 보장되지는 않으며 제약·타입·동시성 테스트와 데이터 이관이 필요하다.

## UI/UX 제안

초기 화면은 프로젝트·원고 목록, 원고 작업 공간, 연결 계정/대상, 게시 작업 이력 네 가지다. 전체 관리자 대시보드보다 작성 흐름에 집중한다.

PC 작업 공간:

```text
[프로젝트 / 원고 제목]       [저장 상태] [내보내기]
[원고 목록] | [Markdown 편집] | [정제된 미리보기]
            | [일지/매뉴얼 · 대상 블로그 · 라벨]
            | [현재 버전 검토] → [Blogger 초안 저장]
            | [작업 상태 · 오류 · 원격 결과 · 다음 조치]
```

- 먼저 명시적 저장을 제공한다. 미저장 이탈 경고와 저장 오류를 표시한다. 자동 저장은 충돌/실패 UX를 함께 구현할 때 추가한다.
- 검토는 저장된 원고 버전·대상·라벨·변환 결과를 묶은 스냅샷에 적용한다. 어느 하나라도 바뀌면 재검토가 필요하다.
- 모의 플랫폼에는 화면 전체에서 식별 가능한 모의 표시를 둔다. 모의 성공을 실제 Blogger 저장으로 표시하지 않는다.
- 중복 클릭은 UI 비활성화와 서버 DB 제약으로 함께 처리한다.
- 결과 불확실이면 '결과 확인'을 안내한다. 생성 재시도 버튼을 바로 제공하지 않는다.
- 색상 외에 상태 텍스트, 키보드 조작, 입력 레이블, 오류 위치를 제공한다.
- 모바일은 목록·작업 상태 조회를 우선하고 편집/미리보기는 탭으로 전환한다.
- 실제 화면 작성 전에 이 흐름의 간단한 와이어프레임을 검토한다. 아직 브라우저 검증이나 디자인 확정은 없다.

## DB 논리 설계 제안

초기에는 사용자별 개인 프로젝트로 한정한다. 공동 편집이 필요해지면 memberships/역할을 도입하며 소유자 컬럼만으로 협업을 구현하지 않는다. ID는 애플리케이션 생성 UUID, 시각은 UTC 기준으로 저장하고 화면에서 변환한다.

| 테이블 | 주요 데이터·제약 |
| --- | --- |
| users | id, identity_provider, subject, 표시명, 활성 여부; provider+subject 유일 |
| projects | id, owner_id, 이름, 기본 원고 유형 |
| articles | id, project_id, current_revision_id, lock_version; 저장 시 낙관적 충돌 검사 |
| article_revisions | id, article_id, revision_number, title, markdown, kind, content_hash, created_at; article+number 유일, 저장 후 불변 |
| platform_connections | id, owner_id, provider, remote_account_id, secret_ref, 상태; 실제 토큰은 응답/일반 테이블에 넣지 않음 |
| publishing_targets | id, connection_id, remote_blog_id, 이름; connection+remote_blog_id 유일 |
| reviews | id, revision_id, target_id, reviewer_id, snapshot_hash, render_version, 승인 시각; 제목/본문/라벨/대상 포함 |
| publish_jobs | id, review_id, owner_id, target_id, article_id, revision_id, idempotency_key, state, error_code, updated_at; owner+idempotency_key 및 revision+target 유일 |
| job_attempts | id, job_id, attempt_number, 시작/종료 시각, 분류된 결과; 비밀값/원문 응답 제외 |
| remote_posts | id, article_id, target_id, remote_post_id, 원격 비교 메타데이터, 마지막 확인 시각; article+target 및 target+remote_post_id 유일 |
| service_sessions | 세션 해시, 사용자, 만료; 브라우저 로그인용 |
| oauth_flows | state 해시, 세션/사용자 참조, 만료, 사용 여부; 콜백 재사용 방지 |

article의 current_revision 포인터는 같은 article 소속인지 DB 제약 또는 트랜잭션 검증을 한다. 프로젝트·원고·연결 계정·대상의 소유자가 같은지 서버에서 확인한다. 외부 호출자는 임의 owner_id를 지정할 수 없다.

publish_jobs의 키 재사용 시 동일 요청이면 기존 작업을 돌려주고 다른 payload이면 409를 반환한다. 실패 후 재시도는 기존 job의 명시적 상태 전이와 attempt 추가로 처리한다. 원고 버전이 달라도 article+target에 remote_posts 또는 미해결 작업이 있으면 신규 생성은 막는다. 새 버전으로 초안을 반복 생성해 중복되는 일을 방지하며 기존 원격 글 자동 덮어쓰기는 초기 기능에서 제외한다.

게시 작업 상태: queued → sending → succeeded / failed / needs_reconciliation. 원고 작성·검토 필요 상태와 업로드 실행 상태는 별개로 관리한다. 원격 결과가 없다고 즉시 실패/재시도로 확정하지 않는다. API 전체에 걸친 정확히 한 번 실행을 보장한다고 주장하지 않는다.

## API 확장 및 DuctTape 연동

서버는 처음부터 내부 /api/v1 JSON 경계를 두고 UI와 같은 Service를 사용한다. 외부 이용을 허용하기 전 인증·권한·오류 규격·호환성 테스트를 추가한다.

초기 계약 후보:

- POST /api/v1/projects/{project_id}/articles: 원고 등록
- POST /api/v1/articles/{article_id}/revisions: 충돌 검사를 포함한 버전 저장
- POST /api/v1/articles/{article_id}/reviews: 현재 스냅샷 검토
- POST /api/v1/publish-jobs: 검토 ID와 Idempotency-Key로 초안 작업 생성, 202 + 작업 ID 반환
- GET /api/v1/publish-jobs/{job_id}: 영속 상태 조회
- POST /api/v1/publish-jobs/{job_id}/reconcile: 원격 확인 요청

DuctTape 1차 연동은 원고 Markdown+메타데이터 내보내기/가져오기와 별도 화면 링크로 한다. 2차는 DuctTape 서버가 최소 범위의 서비스 자격 증명으로 원고를 제출하고 작업을 조회한다. 외부 프로젝트/원고 ID 매핑 테이블에 호출자 범위를 포함한 유일 제약을 두어 가져오기 중복을 막는다. 임의 서버 파일 경로나 실행 명령을 입력으로 받지 않는다.

기본 서비스 자격 증명은 원고 제출·상태 조회만 허용하고 사람의 검토를 대신하지 않는다. 공동 로그인이나 자동 검토는 별도 요구로 설계한다. DuctTape 브라우저에 Blogger 토큰/서비스 비밀키를 주지 않는다. DB 직접 참조, Python 런타임 import 의존, 기존 관리자 쿠키 공유는 도입하지 않는다. 웹훅은 실제 필요가 확인되면 서명·재전송 정책과 함께 추가한다.

## 검증과 구현 순서

1. 사용자와 기술/화면/DB 방향 검토, 와이어프레임과 ER 관계 확정.
2. 독립 실행 골격·마이그레이션·모의 사용자·원고 저장/미리보기/내보내기.
3. 검토 스냅샷·영속 작업·중복·응답 유실·재시작 복구. 동시 저장/클릭, XSS, 파일 크기, 다른 사용자 접근 실패 테스트.
4. 최소 로그인과 웹 OAuth, 실제 계정은 사용자 설정/동의 후 시험 초안으로 검증.
5. DuctTape 입력 계약 및 계약 테스트. 원본 프로젝트 변경은 별도 범위로 검토.
6. 지인 사용성 및 선택적 Pi 검증.

## 확인한 공식 자료

- FastAPI 모듈/APIRouter 구성: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- SQLAlchemy 버전 충돌 검사와 일괄 갱신 시 제한: https://docs.sqlalchemy.org/en/20/orm/versioning.html
- Blogger API와 OAuth: https://developers.google.com/blogger/docs/3.0/using

위 자료는 사용 가능한 기술을 확인하기 위한 근거다. MVC 계층 배치와 UI/DB 구조는 이 프로젝트에 대한 설계 제안이다.

## 추가 요구: 자료 폴더와 재사용 템플릿

2026-10-23 사용자 추가 요구. 실제 초기 게시 대상은 Blogger가 아니라 네이버 블로그다. 앞의 Blogger 중심 구현 순서는 이 요구를 반영해 재검토한다. MVC·서비스·어댑터 경계는 유지한다.

### 목표 흐름

지정 폴더 자료 → 가져오기 → 자료 분석/누락 정보 표시 → 템플릿 적용 초안 → 편집·검토 → 네이버 전달/업로드 → 결과 확인.

- resources/inbox/<자료묶음>/에 원고를 넣고 UI에서 '자료 가져오기'를 실행하는 방식부터 시작한다. 폴더 감시는 나중에 선택 기능으로 추가한다. 파일 배치 자체가 외부 AI 호출이나 공개 발행을 실행하지 않는다.
- 초기 입력은 UTF-8 Markdown/TXT로 제안한다. 이미지·PDF·DOCX·OCR은 실제 자료 형식을 확인한 뒤 추가한다.
- 서버에서 읽는 폴더다. 다른 PC의 브라우저 사용자는 파일 업로드로 같은 가져오기 서비스를 이용하도록 한다.
- 원본을 보존하고 파일 해시·가져오기 이력으로 중복을 확인한다. 기록 중인 파일, 심볼릭 링크, 루트 밖 경로, 과대 파일을 거부한다. 폴더와 프로젝트/사용자 매핑을 서버 설정으로 제한한다.
- 구조 추출과 AI 요약/작성은 구분한다. AI 공급자·비용·전송 자료 범위는 아직 미정이며 유료 호출이나 원문 전송을 자동 실행하지 않는다. 자료에 없는 사실은 채워 넣지 않고 확인 필요로 표시한다.

### 템플릿 요구

사용자가 제공한 https://blog.naver.com/iiew237- 의 게시글을 참고한다. 이번 웹 도구에서는 robots 접근 제한으로 본문을 읽지 못했고 검색에서도 해당 글을 확보하지 못했다. 글의 구조·문체를 분석했다고 기록하지 않는다. 대표 글 본문이나 화면 자료를 확보한 뒤 제목, 도입, 소제목, 문단 길이, 이미지/캡션, 마무리, 태그의 공통 패턴을 추출한다. 구체 문장을 그대로 재사용하는 대신 사용자가 원하는 구성 규칙을 만든다.

업로드 경로 검증을 먼저 하고 템플릿 제작 UI를 후속 구현한다. 초기에는 코드/설정으로 관리하는 고정 템플릿을 적용하고, 이후 사용자가 생성·수정·복제·미리보기·기본 지정할 수 있게 확장한다. 템플릿은 버전별 불변 스냅샷으로 저장하며 기존 생성 원고를 새 템플릿으로 자동 변경하지 않는다.

DB 추가 후보:

- source_batches/source_files: 소유 프로젝트, 허용 상대 경로, 파일 해시, 추출 상태, 원본 참조.
- content_templates/template_versions: 소유자, 이름, 섹션·필드·배치·문체 규칙, 버전.
- generation_runs: 입력 자료/버전, 템플릿 버전, 분석/생성 방식, 결과 원고 버전, 오류·확인 필요 항목. 실제 AI 사용 시 모델/프롬프트 버전 기록.

UI 템플릿(Jinja2)과 포스팅 콘텐츠 템플릿은 별개다. 콘텐츠 템플릿은 허용된 데이터 규칙으로 처리하며 사용자 입력 Python/Jinja 코드를 실행하지 않는다. 내부 미리보기와 네이버 편집기 결과의 일치 여부는 실계정 시험으로 확인해야 한다.

### 네이버 업로드 검토 결과와 남은 결정

공식 현재 API 목록 https://developers.naver.com/products/intro/plan/plan.md 에 블로그 검색·공유는 있으나 블로그 글쓰기 항목을 확인하지 못했다. 검색 API https://developers.naver.com/docs/serviceapi/search/blog/blog.md 는 게시용이 아니다. 옛 글쓰기 API 자료를 현행 지원으로 간주하지 않는다.

따라서 공식 API 기반 직접 업로드는 지원 확인 전 구현 가능으로 확정하지 않는다. 우선 완성 원고·이미지 순서·태그를 내보내거나 복사하는 수동 전달 경로는 구현 가능하다. 이는 업로드 완료와 구분한다. 브라우저 자동화는 별도 가능성 검증 대상으로 두며 본인 로그인, 편집기 입력/서식/이미지, 임시저장, 중복·응답 유실, 플랫폼 정책을 확인해야 한다. 로그인/CAPTCHA를 우회하지 않고 최종 공개는 작성자 확인 후 수행한다.

다음 검토 순서: 참고 글 확보 → 네이버 업로드 방식의 소규모 기술 검증 → 고정 템플릿+자료 가져오기 → 사용자 편집·검토 → 재사용 템플릿 제작 UI. 업로드 경로가 미확정인 상태에서 Blogger를 대체 목표로 진행하지 않는다.

### 참고 PDF 확인 결과 (2026-10-23)

사용자가 reference-posts에 제공한 PDF 8페이지를 모두 시각적으로 확인했다. 제목은 '세계의 나라들(서아시아) #12. 이스라엘'이다. 번호형 정보 단락·사진/출처·구분선·마무리·참고자료/태그가 확인되어 docs/templates/INFORMATION_ARTICLE_V1.md에 관찰 결과와 재사용 템플릿 초안을 남겼다. 원래 요청 URL과 PDF의 글 대응, 전체 사실 검증, 정확한 CSS, 네이버 편집기 결과는 미확인이다. 서비스 코드는 작성하지 않았다.

### 2026-10-26 진행표·환경/자동화 검토 추가

현재 상태와 다음 작업의 체크박스는 [TASKS.md](../TASKS.md)에서 관리한다. [개발 환경과 자동화 방향](DEVELOPMENT_DIRECTION.md)에 실제 기존 JavaScript/React 구성, venv 개발·Docker 후속 배포 추천, Python 코드 재사용 학습 과제, API가 없는 네이버에 대한 로컬 브라우저/도우미/파일 전달 경계를 정리했다. 새 구조 채택이나 실제 기능 구현 완료를 의미하지 않는다.

### 구현된 플랫폼 경계와 오프라인 코어

posting_tool/providers의 Publisher ABC를 플랫폼별로 상속하고 Capability와 Registry로 지원 작업을 구분한다. 현재 ManualExportPublisher/MockPublisher만 구현했으며 네이버/Blogger 실모듈은 없다. 원고 준비(Service)·입력(Source)·표현(rendering)·파일 전달(exporting)을 분리했다. CLI가 같은 코어를 호출하며 향후 MVC Controller에서도 재사용한다. 외부 호출의 재시도/멱등성/사용자 소유권은 실제 저장소 서비스와 함께 확장해야 한다. 구체 사용법과 현재 제한은 README.md에 기록했다.

### 로컬 웹 View 구현

사용자 CLI 대신 UI 요청에 따라 FastAPI web.py Controller, web_service.py Workspace Service, views/ HTML/CSS/JS로 구성했다. 기존 prepare_article/export_article/Publisher 경계를 그대로 재사용한다. 초기 서버 템플릿 대신 고정 HTML View와 작은 JavaScript를 사용했고 별도 Node 빌드는 도입하지 않았다. 원고 버전은 UUID 파일 묶음으로 보존하며 정식 DB·사용자 모델 도입은 후속 범위다. 로컬 loopback 전용으로 실행하고 외부 호스팅은 하지 않는다.

### 문서 블록·원고 버전·콘텐츠 템플릿 구현

documents.py가 평문/제한 Markdown ↔ 블록 데이터 계약을 처리하고 View는 블록 유형 선택/텍스트/순서를 편집한다. Article의 선택 필드 article_id/parent_id/saved_at로 기존 원고 호환성을 유지하면서 목록과 이력을 제공한다. templates.py는 데이터형 템플릿 저장/버전/복제/미리보기/적용을 담당한다. 기존 core Publisher 경계는 유지하며 외부 호출과 분리했다. 저장은 현재 파일 기반 단일 프로세스/단일 사용자 설계이며 다중 사용자 DB 제약을 구현했다고 간주하지 않는다.
