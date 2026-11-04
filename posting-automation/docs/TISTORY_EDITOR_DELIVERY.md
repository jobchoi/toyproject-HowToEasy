# 티스토리·Blogger 편집기 전달

## 현재 제공 범위

네이버 로그인은 계속 보류한다. 티스토리 공식 [Open API 종료 공지](https://notice.tistory.com/2664)를 확인했으며 종료된 API를 호출하지 않는다. TistoryEditorPublisher / BloggerEditorPublisher는 공통 EditorPublisher → Publisher를 상속하고 PREPARE_EDITOR/EXPORT 기능을 선언한다. CREATE_DRAFT는 선언하지 않으며 원격 저장 성공으로 위장하지 않는다.

웹 UI에서 원고 검토 → 티스토리 선택 → 편집기 전달 준비 → 제목/서식 본문/HTML 소스 복사 → 편집기 열기를 제공한다. 티스토리는 사용자 블로그의 /manage/newpost, Blogger는 관리 화면을 연다. 대상 블로그는 전달 패널에 표시한다. 실제 로그인·붙여넣기·임시저장·발행은 플랫폼 편집기에서 수행한다. 사진은 로컬 참조를 깨진 원격 이미지로 전달하지 않고 명시적인 별도 첨부 안내로 바꾸며 캡션/출처를 유지한다. 플랫폼의 CSS와 이미지 첨부 호환성은 실제 편집기에서 확인한다.

클립보드 권한이 없거나 서식 복사가 지원되지 않으면 읽기 전용 원고를 펼쳐 직접 선택하도록 한다. 원고 수정/버전 변경/재검토/플랫폼 변경 시 이전 전달 자료는 무효화한다. UI의 '복사 완료'를 '게시 완료'로 표시하지 않는다.

## API

- GET /api/platforms: 대상/편집기/전달 방식. 인증 토큰은 포함하지 않는다.
- POST /api/previews/<버전>/editor-package: `{provider: "tistory-editor", reviewed: true}`. 기존 요청 토큰과 Origin 검사를 유지하며 명시적 검토만 인정한다.
- 결과는 `prepared_for_editor`, `remote_saved: false`다. 플랫폼 계정에 접속하거나 외부 네트워크를 사용하지 않는다.

## 실제 업로드의 현재 제약

사용자가 실제 업로드 시험을 요청했지만 이 실행 환경에 로그인된 Blogger/티스토리 연결은 확인되지 않았다. 기존 Google Apps Script의 실제 테스트 위치를 사용자에게 확인 요청했다. 브라우저 작업을 지원하는 TinyFish도 발견했지만 현재 설치/계정 연결은 확인되지 않았다. 비밀번호·쿠키를 채팅이나 소스에 요청하지 않는다. 연결이 준비되면 실제 편집기 저장/게시 결과와 글 ID/URL을 확인한 후에만 업로드 성공으로 기록한다.

최종 프로젝트 기록은 아직 서버 전체 정리가 미완료여서 검토용이다. 기능 시험용 짧은 원고를 새로 작성하는 것과 최종 개발기를 게시하는 것을 구분한다.

## 검증

```bash
.venv-ui/bin/python -m unittest discover -s tests -p test_editor_delivery.py -v
.venv-ui/bin/python scripts/check_editor_delivery_ui.py
```

브라우저 QA는 임시 로컬 원고 저장소만 사용하며 외부 HTTPS 요청과 실제 클립보드를 차단/모의 처리한다. 검토 게이트·티스토리/Blogger 전환·서식 HTML·클립보드 거부 대응·수정 시 무효화·모바일을 확인한다. 실제 티스토리 계정·편집기 동작 검증이 아니다.
