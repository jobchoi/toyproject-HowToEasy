# 플랫폼 전송과 별도 서비스 재사용

2026-10-29. 검토 내용이며 외부 전송/배포/계정 접속을 수행한 기록이 아니다.

## 예전 PHP/그누보드 연동과 현재 네이버

과거 코드가 없으므로 사용한 방식은 확정하지 못한다. 신문사 기사에서 블로그로 보냈던 기능은 원문 URL 공유, 당시 글쓰기 API, XML-RPC 등 중 하나였을 가능성이 있다. 언어가 PHP라서 허용되거나 Python이라서 차단되는 문제가 아니라 대상 플랫폼의 인터페이스 지원 여부다.

네이버는 로그인 방식 블로그 글쓰기 Open API를 2020-05-06 종료했다. 한편 현재 공식 문서에는 네이버 공유하기(url/title)와 블로그 공유 버튼이 별도로 안내된다. 원문 페이지 공유와 본문/이미지 전체 복제는 다른 기능이다. 일반 공유 가이드는 로컬 URL을 서버에서 파싱할 수 없어 공유할 수 없다고 안내한다. 현재 127.0.0.1 UI 원고를 그대로 네이버 공유 기능에 넘겨 게시할 수 있다고 가정하지 않는다. 외부에 접근 가능한 기사 URL을 마련하는 것은 별도 공개 범위/호스팅 작업이다. 계정 보호조치 상태이므로 실제 공유 창 실행도 이번에는 보류한다.

- 종료 공지: https://developers.naver.com/notice/article/7527
- 공유(url/title): https://developers.naver.com/docs/share/navershare/
- 블로그 공유 버튼: https://developers.naver.com/docs/share/share/

## 기능을 별도 서비스로 개발할 수 있는가

가능하다. 다만 모듈 분리와 서비스 분리, 화면 임베드는 다른 선택이다.

| 방식 | 목적 | 현재 프로젝트 적용 방향 |
| --- | --- | --- |
| 같은 Python 패키지 | 실행 환경 안에서 로직 재사용 | 현재 원고 준비·렌더링·Publisher 구조 유지 |
| 별도 HTTP API | 다른 언어/서버에서 기능 재사용 | DuctTape 등 실제 소비자가 필요할 때 인증된 API 경계 추가 |
| iframe 화면 임베드 | 이미 완성한 기능 화면을 다른 서비스 안에서 사용 | 우리 소유 UI 또는 임베드를 공식 허용한 서비스에 한정 |
| 별도 창/링크 | 독립 로그인/화면 유지 | iframe 불가한 서비스에 우선 고려 |

권장 경로: 현재 UI → 기존 Service/Publisher → 필요 시 RemotePublisher/API Adapter → 별도 서비스. 사용자에게는 하나의 작업 흐름을 보여 주고 배포 위치에 따라 게시 로직을 중복 작성하지 않는다.

iframe은 대상 서버의 CSP frame-ancestors/X-Frame-Options 설정에 따라 차단될 수 있다. 화면을 넣었다고 다른 서비스의 DOM/쿠키/로그인을 제어할 수 있는 것은 아니다. 우리가 만든 iframe끼리 메시지를 교환한다면 postMessage의 정확한 origin/source/메시지 스키마 검증과 세션 소유권 경계가 필요하다. 플랫폼 비밀번호나 토큰을 iframe 부모로 넘기는 방식은 사용하지 않는다.

현재 로컬 UI는 의도적으로 frame-ancestors 'none'이며 외부 서비스 내 임베드는 아직 허용하지 않는다. DuctTape 임베드가 실제 요구되면 HTTPS·사용자 인증·명시적인 부모 origin 허용과 요청 위조 검사를 함께 구성한다. 임베드하더라도 네이버의 종료된 글쓰기 API를 복구하는 것은 아니다.

공식 웹 플랫폼 참고: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors
