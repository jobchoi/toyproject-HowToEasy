# WSL에서 SSH 실행·결과 수집 자동화

## 자동화 범위

scripts/remote_server.py는 현재 PC/WSL에서 실행한다. 고정된 서버 관리 작업만 선택하며 임의 shell 명령을 받지 않는다. 필요하면 로컬 develop push → 서버 managed repo fast-forward → 관리 명령 → 종료 코드 확인 → 서버 결과/관리 로그 회수를 묶는다. 결과는 로컬 `.local/remote-runs/<작업ID>-<시각>/report.md`, result.json, 수집한 JSONL에 저장된다. 매번 scp할 필요 없다.

서버에는 별도 프로그램을 설치하지 않고 Python 표준 라이브러리로 된 실행 코드를 SSH stdin으로 보낸다. Linux 원격 작업자는 분리 세션에서 실행하고 결과를 ~/web-server/remote-runs/<작업ID>/에 기록한다. SSH 연결이 끊겨도 단순히 변경 명령을 다시 실행하지 않는다. OS/세션 정책에 따라 작업자가 종료될 가능성도 있으므로 결과가 불확실하면 unknown으로 남기고 같은 ID로 조회한다. 이 도구는 systemd·정기 스케줄러나 재부팅 후 자동 재개 서비스가 아니다.

## 최초 인증 설정 (WSL 터미널에서)

원격 실행 도구는 비밀번호를 입력받거나 저장하지 않는다. BatchMode=yes와 StrictHostKeyChecking=yes를 사용한다. SSH 키 인증과 호스트 키 확인을 먼저 완료해야 한다.

기존 SSH 키가 있다면 재생성하지 말고 해당 키를 사용한다. 새 전용 키가 필요한 경우 다음은 사용자 터미널에서 직접 실행한다. 동일 이름 파일이 이미 있으면 덮어쓰지 않는다.

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_raspberry
ssh-copy-id -i ~/.ssh/id_ed25519_raspberry.pub jobchoi@100.116.145.77
```

비밀번호/키 암호는 터미널에서만 입력한다. 비밀번호·개인키를 채팅/스크립트/.env/레포에 넣지 않는다. ~/.ssh/config에 기존 내용을 유지하며 별칭을 추가한다.

```sshconfig
Host raspberry-posting
    HostName 100.116.145.77
    User jobchoi
    IdentityFile ~/.ssh/id_ed25519_raspberry
    IdentitiesOnly yes
```

호스트 키 지문을 신뢰할 수 있는 기존 접속 정보와 대조하고, 사용자 터미널에서 최초 접속을 완료한다. 키 암호가 있다면 실행 환경의 ssh-agent에 해당 키를 로드한다. 에이전트/터미널이 서로 다른 SSH_AUTH_SOCK을 사용하면 같은 키 파일이 있어도 비대화형 인증이 실패할 수 있다.

```bash
ssh raspberry-posting 'hostname'
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes raspberry-posting 'hostname'
```

GitHub push 역시 자동 실행 환경에서 사용할 수 있는 인증이 필요하다. 기존 HTTPS credential helper 또는 GitHub에 등록한 SSH 키를 사용하며 인증 토큰은 소스에 저장하지 않는다. 외부 PC/VS Code의 로그인 상태가 도구 실행 환경으로 자동 전달된다고 가정하지 않는다.

이번 에이전트 실행 환경에서 확인된 결과는 Git HTTPS 사용자명 조회 실패, 라즈 SSH Permission denied(publickey,password)이다. 키와 GitHub 인증이 준비되기 전에는 에이전트가 원격 변경을 수행하지 못한다. 코드의 문제나 자동 승인 거부로 간주하지 않는다.

## 읽기 전용 상태·진단

작업 PC의 posting-automation 폴더에서:

```bash
python3 scripts/remote_server.py --host raspberry-posting --workflow status
python3 scripts/remote_server.py --host raspberry-posting --workflow diagnose
```

status는 등록 상태→포스팅 상태→doctor, diagnose는 포스팅 상태→File Browser health 진단→doctor다. doctor가 unhealthy 등의 점검 항목을 발견하면 needs_attention/종료값 1로 기록한다. 앞 단계가 실패하면 다음 단계는 실행하지 않는다. 원본 서버의 관리 도구가 명령을 지원하지 않으면 REMOTE_CAPABILITY_MISSING으로 중단한다.

## 갱신과 실제 수정

기본은 계획 모드다. --apply가 없으면 push/pull/수정/백업을 적용하지 않는다. 관리 도구 자체는 서버에 이미 존재해야 하며 최초 clone/SSH 설치는 자동으로 하지 않는다.

```bash
# 수정 계획 및 진단 조회
python3 scripts/remote_server.py --host raspberry-posting \
  --workflow repair-filebrowser --sync

# 로컬 push + 원격 repo 갱신 + 수정 + 진단 + 전체 상태 확인
python3 scripts/remote_server.py --host raspberry-posting \
  --workflow repair-filebrowser --push --sync --apply

# 현재 자료 백업 후 상태 확인 (대상 앱만 잠시 중지/재개)
python3 scripts/remote_server.py --host raspberry-posting \
  --workflow posting-backup --apply
```

--push는 로컬 작업 트리 청결/develop/지정 origin을 확인한다. GitHub 인증 실패 시 SSH 작업으로 넘어가지 않는다. --sync는 서버 managed repo 청결/develop을 확인하고 pull --ff-only origin develop만 실행한다. reset/stash/force push를 실행하지 않는다. 본 도구는 원격 수정/백업의 기존 점검·중단·복구 절차를 그대로 사용하며 전체 서비스를 재시작하지 않는다.

## 결과와 장애 처리

- 로컬 결과: posting-automation/.local/remote-runs/...
- 서버 결과: ~/web-server/remote-runs/<작업ID>/
- 서버 기존 관리 로그: ~/web-server/logs/
- request.json/result.json/report.md/events.jsonl 및 수집한 관리 JSONL은 공유 전 확인한다. 경로·호스트·서비스 이름이 포함된다.
- ssh.stderr.txt는 인증/호스트키/네트워크 오류 분류만 선별 기록하며 SSH stderr 원문은 저장하지 않는다. 원시 Git 출력/환경변수/비밀번호도 보고서에 포함하지 않는다.
- --errors-only를 추가하면 정상 실행 때 콘솔은 조용히 유지하고 문제가 있을 때 요약과 보고서 경로만 출력한다. 파일은 계속 기록한다.
- 기본 연결 대기는 8초, 결과 대기는 2100초다. --timeout으로 결과 대기를 조절할 수 있으며 시간 초과는 원격 작업 취소나 실패 확정을 의미하지 않는다.
- 동일 작업 ID는 한 번만 제출한다. 이미 제출된 ID로 변경 명령을 반복 실행하지 않으며 다른 workflow/apply/sync로 재사용하면 충돌로 거부한다.

연결이 끊겼거나 unknown/running이면 출력된 ID로 조회한다.

```bash
python3 scripts/remote_server.py --host raspberry-posting --collect 실제_32자리_작업ID
```

--collect는 push/sync/apply와 함께 쓰지 않는다. 완료 후 결과를 다시 받을 수 있고, 작업자가 살아 있으면 running, 완료 여부를 확정할 수 없으면 unknown을 반환한다. 새 작업 ID를 만들어 같은 변경을 즉시 반복하지 않는다. 로그/실제 서비스 상태를 확인한 뒤 후속 조치를 정한다.

환경에 따라 에이전트의 네트워크 실행 승인 절차는 별도로 적용될 수 있다. SSH 키 등록이 플랫폼 권한 절차를 우회하지는 않는다. Slack/메일 통보나 자동 스케줄 등록은 포함하지 않는다. 출력과 보고서를 에이전트가 읽고 분석하는 흐름까지 제공한다.

## FileBrowser 독립 운영 제어 전환

```bash
python3 scripts/remote_server.py --host raspberry-posting --workflow migrate-filebrowser
python3 scripts/remote_server.py --host raspberry-posting --workflow migrate-filebrowser --sync --apply
# 실제 전환 후 문제 발생 시에만
python3 scripts/remote_server.py --host raspberry-posting --workflow rollback-filebrowser --apply
```

기존 데이터 경로·익명 볼륨·공유 네트워크를 보존한다. 중지된 기존 컨테이너는 이름을 바꿔 보관하며 자동 삭제하지 않는다. 컨테이너 rename 후 새 서비스로 전환하기 전에 설정/DB/공유 폴더 tar를 실제 임시 복원해 파일 내용과 파일 모드를 검증한다. UID/GID는 tar 메타데이터에 보존하며 현재 데이터 소유자를 변경하지 않는다. 운영 제어 전환은 데이터 디렉터리 이동이나 실제 웹 로그인 검토 완료를 뜻하지 않는다. pending_review 중에는 기존 my-server Compose로 fileserver를 재생성하거나 down하지 않는다. 복귀도 대상 FileBrowser만 수행하며 볼륨을 삭제하지 않는다.
