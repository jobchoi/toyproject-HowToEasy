# 이어서 작업하기

현재: 네이버 계정 보호조치로 로그인/실업로드는 후순위. 기존 backend/frontend를 변경하지 않는다.

신규 코어는 posting_tool 패키지이며 Python 표준 라이브러리만 사용한다. README 명령으로 예제 입력 → 원고 → HTML 미리보기·내보내기를 재현할 수 있다. Publisher 추상 클래스/기능 선언/Registry로 플랫폼을 확장한다. 수동 내보내기와 mock만 구현되어 있다. 네이버/Blogger 실어댑터는 없다.

다음: 가져온 원고·생성 버전 저장소와 편집/검토 화면을 연결한다. 현재는 단일 사용자 CLI와 정적 HTML이다. 이미지/PDF/OCR·URL 참고자료 분리 추출·완전한 Markdown·템플릿 제작 UI·AI 집필은 미완료다. 외부 게시 작업의 영속 큐/서비스 승인·원격 재확인도 별도 구현해야 한다.

사용자 자료/PDF/출력(.local)은 Git에서 제외한다. 커밋/push 성공을 가정하지 말고 Git 상태를 확인한다. 이전 네이버 시험 기록 DB는 삭제하지 않는다.

추가: 로컬 웹 UI가 구현되어 있다. `bash scripts/run_ui.sh`로 127.0.0.1:8010에서 실행한다. Controller(web.py)/Service(web_service.py)/View(views/)로 분리해 기존 코어를 호출한다. 저장은 SQLite 대신 .local/ui/<UUID>의 원고/내보내기 파일이며 편집 시 새 UUID를 만든다. 사용자 인증이 없는 로컬 단일 사용자 도구로 인터넷에 노출하지 않는다. 다음 UI 확장은 원고 목록·버전 비교·편집 경험 개선이다.


요청 1~5 후속 구현: documents.py가 평문/제한 Markdown과 문서 블록을 변환한다. templates.py의 데이터형 템플릿은 버전별 불변 JSON으로 저장하며 임의 코드는 실행하지 않는다. Article에 article_id/parent_id/saved_at를 기본값 있는 필드로 추가해 이전 원고와 호환한다. 목록은 원고별 최신 버전을 묶고 history=true로 이전 버전을 조회한다. 오래된 버전의 저장은 차단한다. UI는 평문/파일 입력, 문서 블록/고급 Markdown 전환, 원고 검색/이어쓰기/이력, 템플릿 제작/미리보기/복제/사본 적용을 제공한다. 기본 템플릿은 상수이며 변경은 별도 사용자 템플릿으로 저장된다. 의미별 AI 분석·부분 글자 서식·이미지·자동 저장은 미구현이다.

검증: 전체 unittest 19개 통과. scripts/check_document_ui.py와 check_ui_browser.py로 새 흐름 및 이전 업로드/편집/다운로드/모바일을 검증했다. 브라우저 스크립트는 별도로 실행 중인 로컬 서버를 필요로 하고 POSTING_UI_TEST_URL로 QA 포트를 선택한다. 외부 플랫폼·네이버 계정에는 접속하지 않았다.

샘플 추가: sample_templates.py의 4종은 불변 기본 템플릿이며 styles.py의 허용된 디자인과 연결한다. Article.style이 저장/로딩/HTML 내보내기/웹 미리보기에 전달된다. 갤러리 GET은 저장 없이 표시하고 샘플 원고 열기는 POST로 명시적으로 저장한다. 사용자 템플릿 복제 시 style도 보존한다. .local/template-samples/에 독립 HTML 샘플이 있으나 Git에서는 제외된다. 원격 블로그 편집기가 CSS를 유지할 것이라고 가정하지 않는다.

최근 변경: 일반 UI의 개발 체크표 제거. 템플릿 선택/제작 입력은 자동 미리보기, 원고 생성은 jobs.py의 단일 워커와 파일 상태로 실제 단계 표시/복구한다. app startup마다 미완료 상태를 interrupted로 표시하므로 다중 워커로 실행하지 않는다. 디자인 조절은 appearance dict allowlist로 관리하고 Article/템플릿 버전에 스냅샷 저장한다.

환경: bash scripts/setup_project.sh --profile dev|test, 이후 update_project.sh는 현재 upstream fast-forward만 수행하며 미커밋 변경을 보존한다. setup_project.sh --install-system은 사용자가 명시할 때만 apt를 실행한다. PI_SETUP.md의 최초 clone/SSH 터널 안내를 따른다. 라즈서버 SSH 인증이 거부되어 실제 서버 배포·ARM 실행은 아직 없다. Git 원격 반영 상태도 별도로 확인한다.

최종 검증: 전체 26개 테스트 및 check_feedback_ui.py/check_document_ui.py/check_ui_browser.py 브라우저 흐름 통과. 다음 기능은 사진·캡션·출처를 갖춘 원고 작성이다.


2026-10-30: 사진 우선 단계 구현 완료. media.py가 해시 기반 로컬 래스터 업로드/참조/인라인화를 담당한다. documents.py image 블록은 text(alt), src, caption, source를 사용하며 Markdown은 표준 상대 경로 이미지 + `사진 설명: ...`/`사진 출처: ...` 연속 두 줄로 직렬화한다. 본문/메타데이터는 HTML 이스케이프하고 출처는 http(s)만 허용한다. Workspace.save가 전역 assets 저장소를 사용해 HTML에 data 이미지를 포함하고 버전 폴더에 참조 파일을 복사한다. ZIP에도 사진을 포함한다. 삭제한 사진 자동 GC는 없으며 이전 버전/백업을 보존한다. 외부 이미지 URL 가져오기·SVG·자동 압축·사진 편집·ZIP 재가져오기는 미구현. 전체 28개 테스트와 check_media_ui.py 로컬 브라우저 검증 통과. 다음은 TASKS.md 마지막 기능 순서 참고. 이전 develop eb1e573은 사용자 push 후 원격 일치가 확인됐으며 이번 변경은 아직 커밋/push하지 않았다.

메뉴 UX 보완: index.html의 workspace-nav 순서는 writing-room → library → template-gallery → template-studio로 실제 DOM과 일치한다. writing-room은 자료 입력부터 편집/검토를 포함한다. app.js updateNavigation이 viewport 위치 기준 강조·aria-current·상단 current-location을 갱신한다. 네이티브 앵커/해시/브라우저 이력을 유지하며 모바일 sticky 높이를 scroll-margin에 반영한다. 메뉴 확장 시 본문 구역 및 check_navigation_ui.py도 함께 검토한다.


2026-11-02 운영 정책 변경: 사용자가 관리 경로 분산을 피하고 ~/web-server/<프로젝트>/{repo,data,backups}에 모으도록 요청했다. operations/server-workspace/AGENTS.md가 서버 에이전트 지침 원본이며 루트 AGENTS.md도 이를 참조한다. scripts/manage_server.py는 init/add 계획 및 명시적 --apply로 프로젝트 폴더·README·MIGRATION·projects.json·WORK_HISTORY·manage.sh를 생성한다. 기존 코드/자료를 옮기지 않고 registered_not_migrated 상태로 실제 기존 경로를 등록한다. manage.sh는 원본 스크립트 경로를 호출하므로 실제 저장소 이동 때 참조를 갱신해야 한다. status/doctor는 읽기 전용 상태 점검, 코드별 JSONL 로그를 기록한다. 적용 로그는 --log-dir "$HOME/web-server/logs"로 영속 보관한다. 기존 폴더는 초기 등록만으로 이동/삭제하지 않는다. Docker 운영 구성·실제 서비스 이관은 여전히 후속 작업이다. 과거 분산 배치안에는 대체됨 표시를 추가했다.


포스팅 이관 지원 추가: Dockerfile/.dockerignore와 deploy/compose.yaml을 canonical 정의로 추가. 관리 루트 compose는 extends 진입점, .env에 UID/GID/호스트/절대 코드·데이터 경로 저장. Linux host networking + Uvicorn 127.0.0.1:8010으로 Tailscale loopback proxy 신뢰를 유지한다. prepare-posting은 기존앱 정지·원본 Git 청결·충돌을 확인하고 로컬 clone, .local/ui 복사, tar 백업의 실제 임시 복원·해시 검증 후 prepared_not_started로 등록한다. posting start/stop/confirm은 --apply 필요, start는 healthcheck 후 running_pending_review, confirm은 사용자의 외부 검토 기록 후 migrated. 실제 Docker/ARM 실행은 아직 검증되지 않았다. 상세는 docs/POSTING_DOCKER_MIGRATION.md. 원본 ignored resources/브라우저 기록은 이전 위치에 남으므로 기존 폴더를 삭제하지 않는다.

사용자 라즈서버 2026-11-02 로그에서 포스팅 prepare/start running healthy/stop/start/confirm 성공을 확인했다. 실제 화면/사진 및 재부팅·서버 밖 백업 확인은 별도다. 이관 후 운영을 위해 posting backup --apply(현재 data/ui를 정지·백업 복원 검증·원래 실행상태 재개), use-managed --apply(기존 manage.sh 백업 후 새 repo 스크립트로 연결), diagnose-filebrowser(허용된 health 메타데이터만 조회)를 추가했다. 상세 docs/POST_MIGRATION_OPERATIONS.md 참조. 관리 실행기 전환 전에는 기존 apps 저장소와 새 web-server repo를 모두 최신 코드로 받고, 이후에는 managed repo가 운영 코드 기준이다. 백업은 실행 중인 포스팅만 잠시 멈추며 실패 시 재개를 시도하고 재개 실패는 recovery_required로 기록한다. 실제 신규 명령 서버 실행은 아직 미확인이다.

File Browser 사용자 추가 진단: 호스트 / 및 /health HTTP200, 컨테이너 loopback wget 검사 0, 기존 스크립트 1, 설정 address/port 조회 null. 앱 설정을 바꾸지 않고 repair-filebrowser 계획/apply로 검증된 wget 검사만 override하는 기능 추가. 실제 Compose label/원본 경로·마운트 확인, 설정/DB/Compose 정지 백업, 현재 이미지 ID 고정, 다른 서비스 필드 변경 거부, --no-deps/--no-build/--pull never 대상 서비스 재생성, 마운트 동일 확인. 이 기능은 기존 위치의 health 수정이며 File Browser 이관 완료와 구분한다. 적용 후 legacy_compose_overrides를 모든 후속 재생성 명령에 포함해야 한다. docs/FILEBROWSER_HEALTH_REPAIR.md 참조. 실제 서버 apply는 아직 미실행이다.
