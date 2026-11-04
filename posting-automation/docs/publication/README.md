# 작업 기록 → 블로그 원고·발표 자료

현재 산출물은 **중간 검토용**이다. 서버 정리가 끝나지 않았고 2026-11-04 SSH 연결이 시간 초과로 실패했다. 실제 Blogger/티스토리 게시와 Google Slides 계정 실행은 하지 않았다.

## 하나의 근거 목록에서 생성

`project-story.json`에 공개 가능한 주장 12개, 상태, 근거 파일을 기록한다. 구현/과거 실행 검증/사용자 보고/현재 차단/계획을 구분하며 각각 원고와 슬라이드에 표시한다. 근거는 저장소 내 파일 존재를 검증하지만 문장의 진위가 자동 보장되는 것은 아니므로 담당자가 원문과 실행 기록을 대조한다. .local·인증정보·자료 원본은 입력하지 않는다.

생성기는 직접 네트워크에 접속하지 않는다. 원고와 발표 자료의 근거를 따로 복사해 수정하지 말고 JSON을 갱신한 뒤 새 출력 폴더로 재생성한다. 기존 폴더가 있으면 덮어쓰지 않는다. 체크하지 않은 미완료 사항을 완료로 바꾸지 않는다.

```bash
cd posting-automation
# 표준 라이브러리만으로 원고·HTML 발표·Apps Script 생성
python3 scripts/build_publication.py --output .local/publication-review-01

# 선택: 별도 가상환경에 PPTX 생성 도구 설치
bash scripts/setup_project.sh --profile publication
.venv-publication/bin/python scripts/build_publication.py \
  --pptx --output .local/publication-review-02

# PPTX를 포함한 해당 기능 검사
.venv-publication/bin/python -m unittest discover -s tests -p test_publication.py -v
```

UI/서버 의존성 환경과 발표 생성 환경을 분리했다. 입력은 requirements-publication.txt, 가상환경 경로는 project-environment.json이 기준이다. 새 환경에서 Python 패키지 설치와 Google OAuth 승인은 각각 필요하다.

## 결과 파일

| 파일 | 용도 | 실제 외부 동작 |
|---|---|---|
| article.md | 근거 ID가 있는 검토 원고 | 없음 |
| blogger.html / tistory.html | 플랫폼 HTML 편집기에 넣을 본문 | 없음 |
| blogger-post.json | Blogger posts.insert 요청 본문 | 전송하지 않음 |
| slides.json / slides.html | 동일 사실의 13장 발표·로컬 보기/인쇄 | 없음 |
| project-story.pptx | --pptx 지정 시 실제 PowerPoint 파일 | 로컬 생성 |
| ProjectStory.gs | 실행 데이터가 포함된 Google Apps Script | Google 계정에서 직접 실행해야 함 |
| manifest.json | 기준일·게시 대기·클라우드 미실행 표시 | 없음 |

PPTX는 재개방·슬라이드 수·ZIP 무결성·모든 XML 파싱을 검사했다. PowerPoint/Google Slides의 실제 글꼴 렌더링과 동일한 모양까지 검증한 것은 아니다. 발표 PC에 Noto Sans KR이 없으면 대체 글꼴이 사용될 수 있다.

## Google Slides 생성과 PPTX 내보내기

1. Google Apps Script에서 독립 프로젝트를 만든다. 생성된 출력 폴더의 `ProjectStory.gs`를 붙여넣는다. `operations/google/ProjectStory.gs`는 치환 전 템플릿이므로 그대로 실행하지 않는다.
2. 프로젝트 설정에서 manifest 표시 후 `operations/google/appsscript.json`을 사용한다. 필요한 OAuth 동의는 본인 계정에서 진행하고 토큰·비밀번호를 저장소/채팅에 넣지 않는다. 본 스크립트는 웹 앱으로 배포하지 않아도 편집기에서 실행할 수 있다.
3. `createProjectSlides`를 실행한다. 실행 로그의 링크와 13장 내용을 확인한다. 스크립트 속성의 PROJECT_DECK_ID / PROJECT_DECK_STATE로 중복 생성을 막는다. building 상태라면 먼저 해당 자료를 확인한다. 일부 생성된 자료를 숨기고 반복 생성하지 않는다.
4. `exportProjectPptx`를 실행하면 Drive API로 PPTX를 내보내고 Drive에 새 파일을 저장한다. 스크립트가 생성한 파일을 사용하는 drive.file 권한과 Drive API 사용 가능 상태가 필요하다. Cloud 프로젝트에서 API 비활성 오류가 나오면 해당 Google 프로젝트의 Drive API 설정을 확인한다. 로컬 PPTX는 이 절차 없이도 사용할 수 있다.
5. Google 실행/내보내기 성공 여부는 별도 WORK_HISTORY에 실제 결과로 기록한다. 현재 JavaScript 모의 검증 성공을 Google 실실행으로 적지 않는다.

Google의 공식 [Slides 서비스](https://developers.google.com/apps-script/reference/slides/slide), [발표자 노트](https://developers.google.com/apps-script/reference/slides/notes-page), [Drive 내보내기](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/export)를 사용한다. Drive export는 문서상 10MB 제한이 있으므로 큰 이미지 자료를 추가하면 확인해야 한다.

## Blogger: 최종 검토 후 초안 전달

대상: https://lealnspire.blogspot.com

현재 `publication_ready=false`라 createBloggerDraft는 네트워크 요청 전에 차단된다. 서버 운영 정리 및 사실 검토를 마친 후 근거 목록·차단 상태를 갱신하고 승인 상태로 재생성한다. 현재 차단 주장이 남은 채 ready만 true로 바꾸면 빌드가 실패한다.

본인 Google 계정이 블로그 작성 권한을 가져야 하며 연결된 Google Cloud 프로젝트에서 Blogger API 사용 설정 및 Blogger OAuth 동의가 필요하다. 이는 Google Slides 실행 권한과 별개다. 준비된 생성 스크립트의 createBloggerDraft는 공식 API의 isDraft=true만 사용한다. 응답 유실/실패/중복 실행에서는 BLOGGER_DRAFT_STATE를 확인하고 관리 화면에서 실제 결과를 먼저 대조한다. 서버/계정 상태를 확인하지 않고 속성을 지워 재시도하지 않는다. 공개 발행은 Blogger 편집기에서 최종 검토 후 진행한다.

공식 [블로그 URL 조회](https://developers.google.com/blogger/docs/3.0/reference/blogs/getByUrl)와 [글 생성 API](https://developers.google.com/blogger/docs/3.0/reference/posts/insert)를 참고했다. 이 스크립트는 코어 Publisher의 실어댑터 구현/계정 실행 검증과 별개다.

## 티스토리: HTML 편집기에 원고 전달

대상: https://rt-jobchoi.tistory.com

공식 [Open API 종료 공지](https://notice.tistory.com/2664)에 따라 종료된 글쓰기 API를 구현하지 않았다. 최종 검토 후 티스토리 관리자에서 새 글을 열고 HTML 모드에 tistory.html의 본문을 붙여넣어 제목·표시·링크를 확인한다. 먼저 임시저장으로 확인하고 발행한다. 블로그 스킨에 따른 표시 차이는 실제 편집기에서 확인해야 한다. 쿠키나 비밀번호를 가져오는 자동화는 추가하지 않았다.

## 다음 에이전트의 사실 확인

- 현재 feature/merge와 테스트 결과는 Git/WORK_HISTORY에서 확인한다.
- 서버 정리 미완료 상태를 최종 완료 글로 발행하지 않는다.
- 날짜가 지난 healthy·SSH 결과를 현재 정상으로 표현하지 않는다.
- Apps Script는 모의 API 검사만 수행했으며 실제 Google 계정 검증은 남아 있다.
- 최종 서버 정리 후 바뀐 사실을 먼저 JSON에 반영하고 모든 산출물을 재생성한다.
