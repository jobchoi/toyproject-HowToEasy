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


## 2026-10-26 시험 기능 추가 — 최신 사용법

앞의 '자동 입력·저장 기능 없음' 기록 이후 구현을 추가했다. 현재는 JSON 원고 입력과 임시저장 버튼 클릭 요청이 가능하도록 코드를 작성했다. 네이버 실계정에서 실행한 성공 결과는 아직 없다. 과거 /tmp 설치 파일이 현재 없음을 확인했으므로 새 설치 경로는 프로젝트 .local/browsers로 변경했다.

### 설치 및 실행

```sh
cd /home/mormot/workspace/utilProject/toyproject-HowToEasy/posting-automation
bash scripts/setup_browser.sh
bash scripts/run_browser.sh --blog-id somnium_quest
```

설치는 Python 패키지와 브라우저를 다운로드한다. Chromium 실행에 필요한 OS 라이브러리는 별도이며 설치 명령의 누락 라이브러리 안내를 확인해야 한다. 기존 /tmp 라이브러리를 자동으로 의존하지 않는다. 다른 환경의 패키지·브라우저 설치 성공은 미검증이다. TLS 오류는 신뢰 설정을 해결해야 하며 인증서 검증을 끄지 않는다.

### 시험 순서

1. 전용 브라우저에서 본인이 로그인한다.
2. 터미널에서 Enter를 눌러 글쓰기를 연다. 새 글/이전 글 이어쓰기 팝업은 화면에서 확인한다.
3. `inspect`로 현재 보이는 편집 필드 번호와 메타데이터를 확인한다. 본문/입력값은 출력하지 않는다.
4. 제목·본문 번호를 확인하여 `fill 제목번호 본문번호`를 입력한다. 예를 들어 실제 번호가 0과 1일 때만 `fill 0 1`을 쓴다.
5. 본인 블로그의 빈 새 글임을 확인하고 `INPUT`을 입력한다. 내용이 있는 필드는 덮어쓰지 않는다.
6. 화면에서 예제 원고 내용을 확인하고 `save`, 이어서 `SAVE`를 입력한다. 현재 도구는 정확히 '임시저장'인 버튼 하나만 찾는다. 실제 이름이 다르면 동작하지 않으므로 진단/수정이 필요하다.
7. 저장 버튼 클릭은 성공 확정이 아니다. 네이버에서 직접 임시저장 목록을 열어 제목·본문 일치를 확인한다.
8. 확인했으면 터미널에 `verified`, 이어서 `VERIFIED`를 입력한다. 자동 검증이 아닌 사용자 확인으로 기록한다.
9. `status`로 기록, `quit`으로 종료한다.

기본 원고: examples/naver-trial.json. 다른 원고는 `--draft /절대경로/원고.json` 옵션으로 선택한다. title/body 두 문자열 필드만 허용하며 파일 크기를 제한한다.

저장 요청 전 .local/trials.sqlite3에 원고/블로그 해시와 상태만 기록한다. 응답 유실·프로세스 종료 이후 같은 원고를 자동 재시도하지 않는다. 이 기록을 지우거나 원고를 바꿔 기존 미확인 저장을 우회하지 말고 먼저 네이버 임시저장 목록을 확인한다. 글 전체의 정확히 한 번 저장을 보장하는 범용 중복 방지는 아니며 실험용 동일 원고 요청 차단이다.

검증: unittest 3개 통과 (입력 계약·한글/블로그 경계·동시 요청/재시작 중복 차단), Python 컴파일·셸 문법·git diff --check 통과. 네이버 실제 DOM 입력·사진·서식·저장·재열기 자동 확인은 미검증이다. 공개 발행 코드는 없다.


### OS 라이브러리 누락 해결 (Ubuntu 24.04)

사용자 실행에서 Chromium launch가 libnspr4/libnss3/libasound2t64 부족으로 실패했다. Python 패키지와 브라우저 다운로드만으로 OS 패키지가 설치되지는 않는다. 다음 명령은 사용자가 터미널에서 실행한다 (sudo 비밀번호는 해당 터미널에만 입력).

```sh
sudo apt-get update
sudo apt-get install -y libnspr4 libnss3 libasound2t64
bash scripts/run_browser.sh --blog-id somnium_quest
```

setup 안내와 Python launch 실패 처리를 보완하여 누락 시 위 해결 명령을 표시한다. 이번 변경에서 sudo 설치를 실제 수행하거나 네이버 저장 성공을 검증하지 않았다.

## 2026-10-28 후속 검증

로그인 없이 실행 가능한 접속 진단을 추가했다.

```sh
bash scripts/run_browser.sh --diagnose
```

DNS, Python HTTPS, 화면 없는 Chromium HTTPS를 순서대로 검사한다. 프록시/인증서 환경변수는 설정 유무만 출력하고 URL·비밀번호·쿠키·본문은 출력하지 않는다. 화면 없는 진단 결과는 실제 로그인/추가 인증 성공을 보장하지 않는다.

현재 에이전트 일반 네트워크 실행에서 DNS OK, Python HTTPS HTTP 200, Chromium HTTPS net::ERR_CERT_AUTHORITY_INVALID를 재현했다. 제한된 샌드박스에서는 DNS/브라우저 프로세스 실행도 제한되어 이 결과와 구분했다. Python과 Chromium의 인증서 처리 차이가 있음을 확인했으나, 잘못된 인증서 체인의 구체 원인이나 신뢰해야 할 CA는 확정하지 않았다. 인증서 검증을 끄거나 임의 인증서를 신뢰시키지 않았다.

이미 Linux 환경에 Google Chrome 또는 Edge가 설치되어 있다면 다음과 같이 비교할 수 있다. Windows에만 설치된 Chrome이 WSL 채널 옵션으로 자동 선택되는 것은 아니다. 이 작업 환경에는 해당 Linux 실행 파일이 확인되지 않아 아래 대체 채널 실행은 미검증이다.

```sh
bash scripts/run_browser.sh --diagnose --channel chrome
bash scripts/run_browser.sh --channel chrome --blog-id somnium_quest
```

인증서 오류가 계속되면 정상 브라우저에서 확인한 인증서 발급기관과 네트워크의 보안 프록시 여부를 확인하고 해당 환경에서 관리하는 정식 CA 신뢰 설정을 해결해야 한다. 아직 해결 완료로 표시하지 않는다.

로컬 모의 편집기 통합 테스트를 추가했다. 네이버/로그인 요청을 모두 로컬 HTML 응답으로 대체한 Chromium에서 한글 JSON 입력, 저장 요청, 두 번째 저장 차단을 확인했다. 네이버 실편집기와 동일하다는 뜻은 아니다. 브라우저의 빈 줄 표현 차이는 내용 비교에서 제외하되 비어 있지 않은 줄 순서/문자 변경은 검사한다. 실제 최종 레이아웃은 화면에서 확인해야 한다. SQLite 연결을 트랜잭션 종료 후 명시적으로 닫도록 수정했다.

검증: 단위 테스트 4개 + 로컬 Chromium 통합 테스트 1개 = 5개 통과.

```sh
RUN_BROWSER_TESTS=1 .venv-browser/bin/python -m unittest discover -s tests -v
```

## 2026-10-29 접속 재검사

사용자 진단은 Python HTTP 200 / Chromium ERR_CERT_AUTHORITY_INVALID였다. 이후 에이전트 일반 네트워크에서 TLS 검증을 유지한 Python 직접 연결로 NAVER Corporation의 *.naver.com 인증서, DigiCert Global G2 TLS RSA SHA256 2020 CA1 발급기관과 유효기간(2026-10-01~2027-03-09)을 확인했다. Chromium 진단 재검사에서는 HTTP 200이 나왔다. CA 추가·검증 비활성화·브라우저 업데이트는 수행하지 않았다. 이전 오류의 구체적인 원인은 아직 확정하지 않으며 일시적인 네트워크/인증서 경로 변화 가능성도 남아 있다. 사용자 터미널 재검사와 실제 로그인은 별도 확인이 필요하다.

오류 재발 시 비교할 수 있도록 Chromium 진단에 CDP Security 이벤트의 공개 발급기관·주체·인증서 네트워크 오류 코드 출력만 추가했다. 인증서 전체/로그인/세션 값은 출력하지 않는다.

## 2026-10-29 Windows/WSL 분리 시험

사용자는 Windows Chrome 정상, WSL 시험 Chromium만 인증서 오류라고 확인했다. 진단 대상을 login(nid), home(www), blog(blog) 세 호스트로 확대했다. 에이전트 재검사에서는 Python 세 호스트 HTTP 200, Chromium login/home HTTP 200, blog ERR_CERT_AUTHORITY_INVALID였다. 사용자의 www 오류 보고와 실패 호스트가 달라 현재 TLS/네트워크 경로는 안정적으로 정상이라고 판단하지 않는다.

Windows Python + Windows 설치 Chrome으로 분리 시험할 실행기를 추가했다. Windows에 Python의 py 런처 및 Chrome이 필요하다. 전용 가상환경은 LOCALAPPDATA/HowToEasyPosting에 준비하고 기존 브라우저 프로필/쿠키는 사용하지 않는다. 프로젝트 자체는 WSL 경로에 남겨 Windows에서 해당 파일을 읽는다. Windows 글꼴 설정은 변경하지 않는다. 패키지 최초 설치에는 다운로드가 필요하다.

posting-automation 디렉터리의 WSL 터미널에서:

```sh
powershell.exe -NoProfile -File "$(wslpath -w scripts/run_browser_windows.ps1)" -Diagnose
```

세 호스트가 모두 HTTP 200이면:

```sh
powershell.exe -NoProfile -File "$(wslpath -w scripts/run_browser_windows.ps1)"
```

새 창에서 직접 로그인한 뒤 터미널 Enter, inspect 순서로 진행한다. Windows Python/py 런처가 없거나 PowerShell 실행 정책에 의해 차단되면 해당 오류를 확인해야 한다. 이 스크립트는 실행 정책을 변경하지 않는다. 에이전트 환경에서 Windows 실행은 미검증이며, Windows 평소 Chrome의 정상 접속이 자동화 전용 Chrome에서도 반드시 같다는 보장은 없다.

## 2026-10-29 Windows SQLite 잠김 수정

사용자 Windows 실행에서 Python HTTPS 검사는 세 호스트 모두 200이었지만 공유 경로의 .local/trials.sqlite3 생성/접근 중 database is locked로 종료됐다. 패키지 설치는 성공했다. 진단이 원고와 작업 DB를 불필요하게 열던 결함을 수정하여 --diagnose는 둘 다 접근하지 않는다.

Windows 일반 실행 DB는 %LOCALAPPDATA%/HowToEasyPosting/state/trials.sqlite3로 분리했다. WSL에서는 기존 프로젝트 .local/trials.sqlite3를 유지한다. 기존 DB를 지우거나 자동으로 이동하지 않는다. 두 환경의 기록은 별개이므로 이미 요청했던 원고는 네이버 임시저장 목록을 확인한 뒤 작업한다. Windows 로컬 경로 누락/UNC 경로와 DB 잠김은 안내 후 중단한다.

회귀 검사: 진단에서 DB/원고 접근 금지, Windows 로컬 경로 선택과 UNC 거부, Linux 기존 경로 보존 테스트 추가. Windows 네이티브 실행 결과는 사용자가 같은 명령으로 재확인해야 한다.

## 로그인 후 글쓰기 재인증 대응

Windows 로그인 후 기존 Redirect=Write 바로가기에서 다시 로그인 폼으로 이동했다는 사용자 보고가 있었다. 인증 성공/세션 유지/블로그 소유권/새 탭 중 원인은 미확정이다. Enter/editor를 본인 블로그 홈 열기로 변경했다. 브라우저에서 직접 글쓰기를 누른 뒤 같은 탭이면 inspect, 새 탭이면 tabs → use 번호 → inspect 순서로 진행한다. tabs 출력은 호스트/경로만 표시하며 URL 쿼리·쿠키는 출력하지 않는다. 작업 탭 변경 시 이전 입력 필드/저장 선택을 무효화한다. 로그인 폼에서 inspect 시 반복 로그인 대신 탭 확인을 안내한다. 블로그 홈에서도 재인증이 계속되면 별도 세션/계정 확인이 필요하며 해결 완료로 기록하지 않는다.

## 계정 보호조치 보고 — 실계정 시험 중단

사용자가 네이버 아이디 보호조치 화면을 보고했다. 보호 사유·실제 로그인 기록은 확인하지 못했으며 자동화 시험이 원인이라고 확정하지 않는다. 추가 실계정 로그인/업로드 시험은 중단한다. 사용자가 평소 사용하는 Windows Chrome 또는 네이버 앱에서 공식 본인확인/보호조치 해제를 수행해야 한다. 비밀번호·인증코드를 수집하지 않는다. 해제 자체를 자동화 재개 승인으로 취급하지 않는다.

공식 안내: https://help.naver.com/service/5640/bookmark/1117

후속 개발은 실제 계정에 접속하지 않는 원고 분석·템플릿·미리보기·내보내기·모의 편집기 검증으로 진행할 수 있다. 실제 네이버 저장은 계속 미검증이다.
