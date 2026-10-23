# 네이버 업로드 시험 현황

2026-10-23. 사용자 지정 시험 대상: https://blog.naver.com/somnium_quest

## 실행한 작업

- 별도 .venv-browser에 Playwright 1.55.0 설치, Chromium v1187 다운로드.
- 시스템 라이브러리 부족을 확인하여 libnspr4/libnss3/libasound2t64를 /tmp/posting-browser-libs에 다운로드·추출. OS 패키지는 변경하지 않음.
- 화면 있는 Chromium 실행 후 네이버 로그인 URL 접근을 실제 시도.
- 결과: Page.goto에서 net::ERR_CERT_AUTHORITY_INVALID. 로그인·편집기 입력·임시저장·공개 발행은 수행하지 못함. 인증서 검증을 끄지 않음.
- 기존 프로젝트와 사용자의 기존 브라우저 프로필/쿠키는 사용하거나 변경하지 않음.
- 브라우저 도구 후보를 Plugin Management로 검색했으나 연결하지 않음. 현재는 로컬 시험 방식으로 준비.

## 준비된 진단 스크립트

scripts/naver_browser_probe.py: 사용자가 직접 로그인한 뒤 editor 명령으로 글쓰기 화면을 열고 inspect로 편집 필드의 태그/클래스/placeholder만 확인한다. 입력값·본문·토큰은 출력하지 않으며 쿠키/프로필/트레이스 파일을 저장하지 않는다. 공개 버튼을 누르는 코드도 없다. 실제 제목/본문 자동 입력 및 저장 코드는 아직 없으며 편집기 구조 확인 후 구현한다.

현재 설치 위치에서 네트워크·인증서 신뢰 구성이 해결된 뒤 다음 명령으로 재시도한다. /tmp 경로는 환경 재시작 시 사라질 수 있다.

```sh
cd posting-automation
LD_LIBRARY_PATH=/tmp/posting-browser-libs/root/usr/lib/x86_64-linux-gnu .venv-browser/bin/python scripts/naver_browser_probe.py --blog-id somnium_quest
```

다음 조건: 네이버 로그인이 가능한 사용자 브라우저 실행 환경. 이 환경에서 사용자가 로그인/추가 인증을 수행한 뒤 시험용 원고 입력 → 임시저장 → 목록과 재열기로 보존 확인. 공개 발행은 검토한 시험 원고에 대한 별도 의사 확인 후 한다.

공식 도구 안내: https://playwright.dev/python/docs/browsers

## 로그인 이후 사용 안내 보완

사용자가 로그인 완료를 알려 왔다. 이번 대화에서 편집기·저장 결과는 직접 확인하지 않았다. 기존 실행 중인 도구에서는 터미널 `probe>`에 `editor`를 입력하면 된다. 수정한 스크립트는 재실행 후 Enter로도 글쓰기 화면을 연다. 실행 중 프로세스에 코드 변경이 자동 적용되지는 않는다. 현재 도구는 화면 열기/필드 진단만 제공하며 자동 입력·저장 기능은 아직 없다.

## 한글 글꼴 표시 보완

시스템의 `fc-list :lang=ko` 결과가 비어 있어 한글 글꼴 부재를 확인했다. Windows의 맑은 고딕 파일이 존재하여 진단 도구 전용 `.local/fonts`에서 심볼릭 링크로 참조하고, 해당 Chromium 프로세스에만 FONTCONFIG_FILE을 지정하도록 수정했다. 시스템 글꼴 설정과 Windows 파일은 변경하지 않았다. `fc-match :lang=ko`가 Malgun Gothic 및 해당 파일을 선택함을 검증했다. 네이버 화면의 실제 표시 개선은 브라우저 재실행 후 확인해야 한다. 임시 브라우저이므로 종료하면 도구의 로그인 세션이 유지되지 않아 다시 로그인해야 한다.
