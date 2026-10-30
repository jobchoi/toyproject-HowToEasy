# 라즈베리파이 최초 준비와 갱신

기존 서비스·Tailscale 도메인·포트·볼륨을 변경하지 않고 새 저장소와 전용 Python 환경으로 시작한다. 현재 웹 앱은 인증 없는 단일 사용자 loopback 도구이므로 기존 공개/공유 도메인의 루트에 바로 연결하지 않는다.

## 현재 원격 확인 결과

사용자가 제공한 계정/주소를 pi-user@pi-host로 해석해 읽기 전용 SSH pwd를 시도했으나 Permission denied(publickey,password)로 실패했다. 서버 clone/pull/설치/재시작/도메인 변경은 실행하지 않았다. Tailscale 웹 도메인 접속 가능 여부와 SSH 인증은 별개다. 비밀번호는 사용자의 SSH 터미널에만 입력하고 채팅에 전달하지 않는다.

## 최초 clone

사용자 PC에서 SSH로 접속한다 (Tailscale 연결 필요). 비밀번호/추가 인증은 터미널에서 직접 수행한다.

```sh
ssh pi-user@pi-host
```

아래는 서버에서 실행한다. 브랜치는 현재 작업 브랜치 develop을 예로 들었으며 기존 경로가 있다면 덮어쓰지 말고 먼저 내용을 확인한다. 최신 변경이 해당 원격 브랜치에 push되어 있어야 스크립트를 받을 수 있다.

```sh
mkdir -p "$HOME/apps"
git clone --branch develop https://github.com/jobchoi/toyproject-HowToEasy.git "$HOME/apps/toyproject-HowToEasy"
cd "$HOME/apps/toyproject-HowToEasy/posting-automation"
bash scripts/setup_project.sh --profile test
```

OS에 Python/venv/git이 없다면 Debian/Ubuntu/Raspberry Pi OS에서 명시적으로 시스템 설치 옵션을 쓴다. 최초 clone에 git이 없는 경우는 sudo apt-get update 및 sudo apt-get install -y git을 먼저 실행해야 한다.

```sh
bash scripts/setup_project.sh --install-system --profile test
```

옵션을 주면 sudo apt-get으로 git/python3/python3-venv/python3-pip를 설치한다. 현재 스크립트는 Python 3.11 이상이 필요하고 기존 시스템 Python·다른 프로젝트 가상환경을 삭제/교체하지 않는다. 오래된 Pi OS이면 Python/OS 업그레이드는 별도로 계획해야 한다. ARM 기기 설치는 아직 현장 미검증이며 wheel이 없는 의존성의 컴파일 도구가 추가로 필요할 수 있다. 기본 테스트는 계정이나 브라우저 다운로드 없이 실행한다.

## 웹 화면 실행·접속

서버에서:

```sh
bash scripts/run_ui.sh
```

기본 포트 8010이 다른 서비스에서 사용 중이면 그 서비스를 종료하지 말고 다른 포트를 선택한다. 예: .venv-ui/bin/python -m uvicorn posting_tool.web:create_app --factory --host 127.0.0.1 --port 8012

PC의 다른 터미널에서:

```sh
ssh -N -L 8010:127.0.0.1:8010 pi-user@pi-host
```

PC 브라우저에서 http://127.0.0.1:8010 을 연다. 이 방식은 기존 Tailscale 웹 도메인 설정을 바꾸지 않는다. SSH 터널은 닫으면 종료되고 웹 서버도 실행 터미널의 Ctrl+C로 종료된다. 상시 실행/서비스 자동 재시작·도메인 경로 연결은 아직 설치하지 않는다.

## 이후 코드 갱신

서버의 posting-automation 폴더에서:

```sh
bash scripts/update_project.sh --profile test
```

현재 브랜치의 upstream을 git pull --ff-only로 가져온 뒤 의존성과 테스트를 준비한다. 미커밋 변경/분리 HEAD는 중단하며 reset·stash·브랜치 전환·push·기존 서비스 재시작은 하지 않는다. 실행 중 앱에 변경이 반영되려면 사용자가 해당 새 앱의 재시작을 결정해야 한다. .local 원고/템플릿은 Git에서 제외하며 별도 백업해야 한다.

## 다른 Python 프로젝트에서 재사용

scripts/project_setup.py는 project-environment.json의 최소 Python 버전, 가상환경 경로, 프로필별 의존성 파일, 테스트 명령을 읽는다. 해당 스크립트와 자신의 JSON/requirements를 다른 Python 프로젝트에 두어 재사용할 수 있다. 프로젝트별 설정만 바꾸고 전역 환경에 설치하지 않는다. Node/PHP 프로젝트의 설치/테스트 명령은 별도 어댑터가 필요하며 현재 스크립트가 모든 언어를 자동 지원하는 것은 아니다. 요청받지 않은 다른 저장소는 이번에 변경하지 않았다.

## 기존 Funnel 서비스와 분리하여 Tailscale 기기로 접속

2026-10-30 사용자 상태: 기존 HTTPS 기본 포트 443의 `/`가 Funnel 공개 상태로 127.0.0.1:8000에 연결되어 있다. 이 연결은 기존 서비스용으로 유지한다. 아래는 별도 HTTPS 8443을 Serve로 추가하는 방식이다. 기존 8443 설정이 있다면 덮어쓰지 말고 먼저 확인한다.

이 절의 호스트 설정을 지원하는 변경을 작업 PC에서 먼저 커밋/push한 다음 라즈서버에서 update_project.sh로 받아야 한다. 기존 실행 중인 포스팅 앱은 종료한 뒤 다시 실행한다.

```sh
cd ~/apps/posting-automation-workspace/posting-automation
bash scripts/update_project.sh --profile test
POSTING_ALLOWED_HOSTS=raspberry-m5.tail1a38c1.ts.net bash scripts/run_ui.sh
```

별도 라즈서버 터미널에서:

```sh
tailscale serve status
sudo tailscale serve --bg --https=8443 http://127.0.0.1:8010
tailscale serve status
tailscale funnel status
```

접속 PC/휴대폰에서 Tailscale을 켜고 `https://raspberry-m5.tail1a38c1.ts.net:8443/`를 연다. 443의 기존 Funnel은 유지되고 새 8443에는 Funnel on이 없어야 한다. Serve 설정은 유지되지만 Python 앱 자체의 상시 실행은 별도다.

앱은 여전히 127.0.0.1:8010에만 바인딩하며 허용 호스트만 환경변수로 추가한다. `POSTING_ALLOWED_HOSTS`는 쉼표로 구분한 호스트 이름이며 프로토콜/포트/경로/와일드카드는 허용하지 않는다. 실행기는 127.0.0.1 프록시에서 온 forwarded 헤더만 신뢰한다. 토큰/Origin 검사는 유지한다. 앱 로그인은 없으므로 접근이 허용된 tailnet 사용자들은 같은 원고를 볼 수 있다. 권한은 tailnet 접근 정책으로 제한한다.

새 8443 연결만 해제하려면:

```sh
sudo tailscale serve --https=8443 off
```

기존 서비스 보호를 위해 `tailscale serve reset` 또는 기존 443 설정 변경을 실행하지 않는다. 포스팅 앱을 Funnel로 인터넷에 공개하는 설정은 이 안내에 포함하지 않는다. `/posting/` 경로 방식은 현재 절대 경로 API/assets를 사용해 별도 수정 없이 지원하지 않는다.
