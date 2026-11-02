"""Posting-only staged deployment. Never delete sources or change other services."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tarfile
import tempfile
from uuid import uuid4

COMPOSE_ENTRY = 'services:\n  web:\n    extends:\n      file: ./repo/posting-automation/deploy/compose.yaml\n      service: web\n'


def run(args, log, code, timeout=120):
    log.event(code, '명령 실행: ' + ' '.join(args[:2]))
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    for key in ('COMPOSE_FILE','COMPOSE_PROJECT_NAME','COMPOSE_REMOVE_ORPHANS','COMPOSE_PROFILES','DOCKER_HOST','DOCKER_CONTEXT'):
        env.pop(key, None)
    for key in list(env):
        if key.startswith('POSTING_'): env.pop(key)
    try: result = subprocess.run(args,capture_output=True,text=True,timeout=timeout,env=env)
    except (OSError,subprocess.TimeoutExpired):
        raise ValueError(code+': 실행 불가/시간 초과. 원본과 생성 파일은 보존됩니다.') from None
    if result.returncode:
        log.event(code+'_FAILED', '실행 실패. 대상 프로젝트의 설치/권한/경로를 확인하세요.',exit_code=result.returncode)
        raise ValueError(code+': 명령 실패 (원시 출력은 비밀값 노출 방지를 위해 로그에 복사하지 않습니다).')
    return result.stdout.strip()


def ensure_stopped():
    with socket.socket() as connection:
        connection.settimeout(1)
        if connection.connect_ex(('127.0.0.1',8010)) == 0:
            raise ValueError('PORT_BUSY: 8010 앱이 실행 중입니다. 해당 포스팅 앱만 정상 종료한 뒤 재시도하세요.')


def manifest(root):
    result = {}
    if not root.is_dir(): raise ValueError('DATA_MISSING: 기존 원고 저장소를 찾을 수 없습니다: '+str(root))
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise ValueError('DATA_TYPE: 심볼릭 링크/특수 파일이 있어 자동 복사를 중단합니다.')
        if path.is_file():
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''): digest.update(chunk)
            result[path.relative_to(root).as_posix()] = digest.hexdigest()
    return result


def save_json(path, data):
    if path.is_symlink(): raise ValueError('심볼릭 링크에 기록하지 않습니다: '+str(path))
    temporary = path.with_name('.'+path.name+'-'+uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as stream: json.dump(data,stream,ensure_ascii=False,indent=2)
        temporary.chmod(0o600); temporary.replace(path)
    finally: temporary.unlink(missing_ok=True)


def backup_and_verify(data, archive, expected, log):
    with tarfile.open(archive,'x:gz') as tar: tar.add(data,arcname='ui')
    archive.chmod(0o600)
    with tempfile.TemporaryDirectory(prefix='posting-restore-',dir=archive.parent) as temporary:
        restored = Path(temporary)
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar.getmembers():
                path = restored/member.name
                if not path.resolve().is_relative_to(restored.resolve()) or not (member.isfile() or member.isdir()):
                    raise ValueError('BACKUP_FORMAT: 복원할 수 없는 백업 항목입니다.')
                if member.isdir(): path.mkdir(parents=True,exist_ok=True)
                else:
                    path.parent.mkdir(parents=True,exist_ok=True)
                    with tar.extractfile(member) as source, path.open('xb') as target: shutil.copyfileobj(source,target)
        if manifest(restored/'ui') != expected: raise ValueError('BACKUP_VERIFY: 복원 해시가 일치하지 않습니다.')
    log.event('BACKUP_VERIFIED','백업 복원·해시 검증 완료.',archive=str(archive),file_count=len(expected))


def history(root, message, log):
    from manage_server import safe_path
    path = safe_path(root/'WORK_HISTORY.md')
    fd = os.open(path,os.O_CREAT | os.O_APPEND | os.O_WRONLY,0o600)
    with os.fdopen(fd,'a',encoding='utf-8') as stream:
        stream.write('\n- '+datetime.now(timezone.utc).isoformat()+' '+message+' / 로그: '+str(log.path)+'\n')


def prepare(root, hostname, apply, log):
    from manage_server import registry, safe_path, lock, write_new
    if len(hostname)>253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in hostname.split('.')):
        raise ValueError('호스트 이름만 입력하세요. https://·포트·경로는 제외합니다.')
    records = registry(root)
    value = records['projects'].get('posting-automation')
    if not value: raise ValueError('포스팅 프로젝트를 먼저 init으로 등록하세요.')
    source = safe_path(value['legacy_code']); old_data = safe_path(value['legacy_data'])
    base = safe_path(root/'posting-automation')
    safe_path(base/'MIGRATION.md'); safe_path(root/'WORK_HISTORY.md')
    repo = safe_path(base/'repo'); data = safe_path(base/'data'/'ui')
    backups = safe_path(base/'backups')
    if source == repo or old_data == data or old_data.is_relative_to(base):
        raise ValueError('SOURCE_CONFLICT: 기존 원본과 새 배치 경로가 겹칩니다.')
    for path in (source,repo,data,backups):
        if any(c in str(path) for c in '\r\n"$\\'): raise ValueError('자동 구성에서 지원하지 않는 경로 문자입니다.')
    log.event('PREPARE_PLAN','포스팅만 코드 복사·원고 백업/복원 검증·Compose 준비.',source=str(source),target=str(base))
    if not apply:
        log.event('DRY_RUN','계획만 표시합니다. 기존 포스팅 앱 종료 후 --apply로 준비하세요.'); return
    if os.getuid() == 0: raise ValueError('sudo 없이 실제 운영 사용자로 실행하세요.')
    with lock(root):
        records = registry(root); value = records['projects']['posting-automation']
        if value['status'] not in {'registered_not_migrated','prepared_not_started'}:
            raise ValueError('이미 준비 이후 상태입니다. 기존 배포를 덮어쓰지 않습니다.')
        ensure_stopped()
        if run(['git','-c','core.fsmonitor=false','-C',str(source),'status','--porcelain'],log,'GIT_STATUS'):
            raise ValueError('SOURCE_DIRTY: 기존 코드에 미커밋 변경이 있습니다. 먼저 보존/커밋하세요.')
        commit = run(['git','-C',str(source),'rev-parse','HEAD'],log,'GIT_HEAD')
        required = ['posting-automation/Dockerfile','posting-automation/deploy/compose.yaml']
        for name in required:
            run(['git','-C',str(source),'cat-file','-e','HEAD:'+name],log,'SOURCE_CHECK')
        for path in (repo,base/'data',backups):
            if not path.is_dir(): raise ValueError('초기 프로젝트 디렉터리가 없습니다. init부터 확인하세요.')
        for path in (base/'compose.yaml',base/'.env',base/'.prepared.json'):
            safe_path(path)
        before = manifest(old_data)
        required_space = sum((old_data/name).stat().st_size for name in before) * 4 + 100_000_000
        if shutil.disk_usage(base).free < required_space:
            raise ValueError('DISK_SPACE: 복사·백업·복원 시험에 필요한 여유 공간이 부족합니다.')
        if any(repo.iterdir()):
            if run(['git','-C',str(repo),'rev-parse','HEAD'],log,'TARGET_HEAD') != commit:
                raise ValueError('TARGET_CONFLICT: repo에 다른 코드가 있습니다. 덮어쓰지 않습니다.')
            if run(['git','-c','core.fsmonitor=false','-C',str(repo),'status','--porcelain'],log,'TARGET_STATUS'):
                raise ValueError('TARGET_DIRTY: 새 repo에 변경이 있습니다.')
        else:
            with tempfile.TemporaryDirectory(prefix='.posting-code-',dir=base) as temporary:
                staged = Path(temporary)/'repo'
                run(['git','clone','--no-hardlinks','--',str(source),str(staged)],log,'CLONE',timeout=300)
                run(['git','-C',str(staged),'remote','set-url','origin','https://github.com/jobchoi/toyproject-HowToEasy.git'],log,'ORIGIN')
                if run(['git','-C',str(staged),'rev-parse','HEAD'],log,'CLONE_VERIFY') != commit:
                    raise ValueError('CLONE_CHANGED: 복사 중 원본 커밋이 변경됐습니다.')
                repo.rmdir(); staged.rename(repo)
        if not data.exists():
            with tempfile.TemporaryDirectory(prefix='.posting-data-',dir=base) as temporary:
                staged = Path(temporary)/'ui'; shutil.copytree(old_data,staged)
                if manifest(staged) != before or manifest(old_data) != before:
                    raise ValueError('DATA_CHANGED: 복사 중 원고가 변경됐습니다. 쓰기 작업을 확인하세요.')
                staged.rename(data)
        elif manifest(data) != before:
            raise ValueError('DATA_CONFLICT: 새 data와 원본 내용이 다릅니다. 덮어쓰지 않습니다.')
        archive = backups/('before-docker-'+datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:6]+'.tar.gz')
        backup_and_verify(data,archive,before,log)
        ensure_stopped()
        if manifest(old_data) != before: raise ValueError('DATA_CHANGED: 원본에 쓰기가 재개됐습니다. 전환을 중단합니다.')
        env_text = '\n'.join(['POSTING_UID='+str(os.getuid()),'POSTING_GID='+str(os.getgid()),
                             'POSTING_ALLOWED_HOSTS='+hostname,'POSTING_CODE_DIR="'+str(repo/'posting-automation')+'"',
                             'POSTING_DATA_DIR="'+str(data)+'"',''])
        for path,text in ((base/'.env',env_text),(base/'compose.yaml',COMPOSE_ENTRY)):
            if path.exists() and path.read_text()!=text: raise ValueError('CONFIG_CONFLICT: 기존 운영 설정과 다릅니다: '+str(path))
            write_new(path,text,log)
        save_json(base/'.prepared.json',{'commit':commit,'archive':str(archive),'file_count':len(before),'hostname':hostname})
        value.update(status='prepared_not_started',actual_code=str(repo),actual_data=str(data),backup=str(archive),prepared_commit=commit)
        save_json(root/'projects.json',records)
        with (base/'MIGRATION.md').open('a',encoding='utf-8') as stream:
            stream.write('\n- '+datetime.now(timezone.utc).isoformat()+' 코드/자료 복사·백업 복원 해시 확인 완료. 서비스 시작/8443 검토 전. 백업: '+str(archive)+'\n')
        history(root,'포스팅 코드/자료 복사 및 백업 복원 검증, 컨테이너 시작 전.',log)
        log.event('PREPARED','준비 완료. 기존 원본은 유지했으며 컨테이너는 아직 시작하지 않았습니다.')


def operate(root, action, log):
    from manage_server import registry, safe_path, lock
    base = safe_path(root/'posting-automation')
    safe_path(base/'MIGRATION.md'); safe_path(root/'WORK_HISTORY.md')
    for name in ('.env','compose.yaml','.prepared.json'):
        if not safe_path(base/name).is_file(): raise ValueError('PREPARE_REQUIRED: prepare-posting을 먼저 적용하세요.')
    command = ['docker','--context','default','compose','--env-file',str(base/'.env'),'-p','posting-automation','-f',str(base/'compose.yaml')]
    with lock(root):
        records = registry(root); value = records['projects']['posting-automation']
        if action == 'start':
            if value['status'] == 'prepared_not_started': ensure_stopped()
            run(command+['config','--quiet'],log,'COMPOSE_CONFIG')
            run(command+['up','-d','--build','--wait','--wait-timeout','90','web'],log,'COMPOSE_START',timeout=1800)
            value['status'] = 'running_pending_review'; save_json(root/'projects.json',records)
            history(root,'포스팅 컨테이너 상태 점검 통과, 사용자 화면 검토 대기.',log)
            log.event('RUNNING','컨테이너 상태 점검 통과. 8443 접속·원고/사진·저장 확인 후 confirm을 실행하세요.')
        elif action == 'stop':
            run(command+['stop','web'],log,'COMPOSE_STOP')
            value['status']='stopped'; save_json(root/'projects.json',records)
            history(root,'포스팅 컨테이너만 중지, 원본/자료 보존.',log)
            log.event('STOPPED','포스팅 컨테이너만 중지했습니다. 데이터·볼륨·다른 서비스는 유지합니다.')
        elif action in {'status','confirm'}:
            output = run(command+['ps','--all','--format','json','web'],log,'COMPOSE_STATUS')
            try:
                rows = json.loads(output) if output.startswith('[') else [json.loads(line) for line in output.splitlines() if line]
            except ValueError: raise ValueError('COMPOSE_FORMAT: 상태 출력 형식을 확인하세요.') from None
            healthy = False
            for row in rows:
                log.event('POSTING_STATUS',str(row.get('State'))+' / '+str(row.get('Health')))
                healthy = healthy or (row.get('State')=='running' and row.get('Health')=='healthy')
            if action=='confirm':
                if not healthy: raise ValueError('NOT_HEALTHY: 컨테이너가 정상 상태가 아닙니다.')
                value['status']='migrated'; save_json(root/'projects.json',records)
                with (base/'MIGRATION.md').open('a',encoding='utf-8') as stream:
                    stream.write('\n- '+datetime.now(timezone.utc).isoformat()+' 사용자가 외부 접속/원고 저장을 확인하고 confirm 실행. 재부팅/서버 밖 백업 검증은 별도 기록 필요.\n')
                history(root,'사용자가 포스팅 화면/저장 검토 후 이관 확인 명령 실행.',log)
                log.event('CONFIRMED','사용자 검토 완료를 기록했습니다. 기존 원본은 삭제하지 않습니다.')
