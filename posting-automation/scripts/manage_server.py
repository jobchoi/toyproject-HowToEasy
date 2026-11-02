#!/usr/bin/env python3
"""Bootstrap a project-oriented server workspace; no service mutations or moves."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import tempfile
from uuid import uuid4

TEMPLATE = Path(__file__).resolve().parents[1] / 'operations/server-workspace/AGENTS.md'
DEFAULTS = {
    'posting-automation': ('apps/posting-automation-workspace', 'posting-automation/.local/ui', 'manual', 8010),
    'duct-tape': ('my-server/duct-tape', 'my-server/duct-data', 'my-server', 8000),
    'filebrowser': ('my-server', 'my-server/storage', 'my-server', 8080),
    'nginx': ('my-server', 'my-server/html', 'my-server', 80),
}


def safe_path(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    if path.resolve() != path or path == Path('/') or path == Path.home().resolve():
        raise ValueError('관리 경로는 홈/루트 자체가 아닌 독립 폴더여야 하며 심볼릭 링크를 포함하면 안 됩니다.')
    return path


def slug(value):
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,47}', value):
        raise ValueError('프로젝트 이름은 영문 소문자로 시작하는 소문자·숫자·하이픈 1~48자입니다.')
    return value


class Log:
    def __init__(self, folder):
        folder = safe_path(folder)
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = folder / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:8] + '.jsonl')
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        self.stream = os.fdopen(fd, 'w', encoding='utf-8')

    def event(self, code, message, **details):
        row = {'time':datetime.now(timezone.utc).isoformat(), 'code':code, 'message':message, **details}
        self.stream.write(json.dumps(row, ensure_ascii=False) + '\n'); self.stream.flush()
        print('[' + code + '] ' + message, flush=True)

    def close(self):
        self.stream.close()


def registry(root):
    path = root / 'projects.json'
    if path.is_symlink(): raise ValueError('등록 파일의 심볼릭 링크는 허용하지 않습니다.')
    if not path.exists(): return {'schema_version':1, 'projects':{}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data,dict) or data.get('schema_version') != 1 or not isinstance(data.get('projects'),dict):
        raise ValueError('지원하지 않는 projects.json 형식입니다.')
    for name, value in data['projects'].items():
        slug(name)
        if not isinstance(value,dict): raise ValueError('프로젝트 등록 형식이 잘못됐습니다.')
    return data


def entry(name, home, source=None):
    code, data, old_project, port = DEFAULTS.get(name, ('','','',None))
    original_code = str(source) if source else (str(home/code) if code else '')
    if name == 'posting-automation': original_data = str(home/code/data)
    else: original_data = str(home/data) if data else ''
    compose = 'compose.duct-tape.yml' if name == 'duct-tape' else 'docker-compose.yml'
    return {'status':'registered_not_migrated', 'code':'repo', 'data':'data', 'backups':'backups',
            'compose_file':'compose.yaml', 'compose_project':name,
            'legacy_code':original_code, 'legacy_data':original_data,
            'legacy_compose':str(home/'my-server'/compose) if name in {'duct-tape','filebrowser','nginx'} else '',
            'legacy_compose_project':old_project, 'host_port':port}


def write_new(path, text, log, mode=0o600):
    if path.is_symlink(): raise ValueError('심볼릭 링크에는 쓰지 않습니다: ' + str(path))
    if path.exists():
        if not path.is_file(): raise ValueError('일반 파일이 아닌 경로입니다: ' + str(path))
        log.event('PRESERVED', '기존 파일 유지: ' + str(path)); return
    with path.open('x', encoding='utf-8') as stream: stream.write(text)
    path.chmod(mode)
    log.event('CREATED', '파일 생성: ' + str(path))


@contextmanager
def lock(root):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / '.management.lock'
    if path.is_symlink(): raise ValueError('잠금 파일이 심볼릭 링크입니다.')
    with path.open('a') as stream:
        try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('다른 관리 작업이 실행 중입니다. 종료 후 재시도하세요.') from None
        try: yield
        finally: fcntl.flock(stream, fcntl.LOCK_UN)


def apply(root, names, source, log):
    if not TEMPLATE.is_file():
        raise ValueError('AGENTS 원본이 없습니다. scripts 파일만 옮기지 말고 최신 저장소에서 실행하세요.')
    with lock(root):
        records = registry(root)
        records.setdefault('manager_script', str(Path(__file__).resolve()))
        for filename in ('AGENTS.md','README.md','.gitignore','WORK_HISTORY.md','manage.sh'):
            target = root/filename
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError('관리 파일 경로 충돌: '+str(target))
        # Preflight all paths before creating project skeletons.
        for name in names:
            if source and name in records['projects'] and records['projects'][name].get('legacy_code') != str(source):
                raise ValueError('기존 등록 경로와 다릅니다. projects.json을 검토하세요: '+name)
            base = safe_path(root/name)
            for target in [base,base/'repo',base/'data',base/'backups']:
                safe_path(target)
                if target.exists() and not target.is_dir(): raise ValueError('디렉터리가 아닌 경로: '+str(target))
            for filename in ('README.md','MIGRATION.md'):
                target = base/filename
                if target.is_symlink() or (target.exists() and not target.is_file()):
                    raise ValueError('문서 경로 충돌: '+str(target))
        write_new(root/'AGENTS.md', TEMPLATE.read_text(encoding='utf-8'), log)
        write_new(root/'README.md', '''# 서버 프로젝트 관리

이 디렉터리가 운영 관리의 시작점입니다. AGENTS.md → projects.json → 프로젝트 README/MIGRATION 순서로 확인하세요.

- 프로젝트/<repo,data,backups>에 코드·데이터·백업을 구분합니다.
- projects.json은 프로젝트 목록과 실제 운영 중인 기존 경로를 기록합니다.
- registered_not_migrated는 폴더 등록만 됐다는 뜻이며 기존 서비스는 이전 경로에서 운영됩니다.
- 빈 repo/data를 실제 운영 경로로 사용하지 마세요. Compose나 .env는 자동 생성하지 않습니다.
- 기존 서비스 이동·중지·Tailscale 변경·볼륨 삭제는 이 초기화 작업에서 수행하지 않습니다.
- 프로젝트별 Compose 정의는 단일 원본으로 유지하고 환경값은 서버 전용 .env로 분리합니다.
- `./manage.sh status`로 등록 상태, `./manage.sh doctor`로 Docker 상태를 점검합니다.
- `./manage.sh add 새-프로젝트`로 계획을 보고 --apply를 붙여 등록합니다.
- 등록 목록: [포스팅](posting-automation/README.md), [DuctTape](duct-tape/README.md), [File Browser](filebrowser/README.md), [Nginx](nginx/README.md). 실제 등록 여부는 projects.json이 기준입니다.
- manage.sh는 원래 포스팅 저장소의 scripts/manage_server.py를 호출합니다. 저장소를 이동할 때 이 참조 경로도 함께 갱신합니다.
- 실행 기록은 WORK_HISTORY.md와 명령 실행 시 출력되는 JSONL 로그를 확인하세요.
- 실제 데이터 백업은 서버 밖에도 보관하고 복원 검증합니다.
''', log)
        launcher = ('#!/usr/bin/env bash\nset -euo pipefail\n'
                    'management_root="$(cd -- "$(dirname -- "$0")" && pwd -P)"\n'
                    'exec python3 ' + shlex.quote(str(Path(__file__).resolve())) +
                    ' --root "$management_root" --log-dir "$management_root/logs" "$@"\n')
        write_new(root/'manage.sh', launcher, log, mode=0o700)
        write_new(root/'.gitignore', '*/repo/\n*/data/\n*/backups/\n**/.env*\nlogs/\n.management.lock\n',log)
        for name in names:
            base = root/name
            for target in (base,base/'repo',base/'data',base/'backups'):
                target.mkdir(exist_ok=True,mode=0o700)
            value = records['projects'].setdefault(name,entry(name,Path.home(),source))
            write_new(base/'README.md', '# '+name+'\n\n상태: 등록 완료·미이관\n' + '\n기존 운영 위치: `'+value.get('legacy_code','')+'`\n\n등록값은 ../projects.json, 절차는 MIGRATION.md를 확인하세요.\nrepo/data/backups는 향후 배치 위치입니다. 운영 코드나 자료를 복사한 상태가 아닙니다.\n',log)
            write_new(base/'MIGRATION.md', '''# 이관·운영 체크리스트

- [ ] 현재 코드/Compose/build/mount/공유 경로 의존성 확인
- [ ] 기존 데이터/DB/필요 볼륨을 일관된 방법으로 백업
- [ ] 복원 시험과 되돌리기 절차 기록
- [ ] 단일 Compose 정의와 고유 프로젝트 이름/포트 준비
- [ ] repo 코드 배치와 data 권한·소유자 확인
- [ ] 대상 프로젝트에만 계획한 전환 실행
- [ ] 접속/저장/재생성/재시작/백업·복원 확인
- [ ] projects.json의 status와 실제 운영 경로 갱신

초기화는 이동·복사·운영 설정 변경을 수행하지 않습니다.
''',log)
        temporary = root / ('.projects-' + uuid4().hex + '.tmp')
        try:
            with temporary.open('x',encoding='utf-8') as stream: json.dump(records,stream,ensure_ascii=False,indent=2)
            temporary.chmod(0o600); temporary.replace(root/'projects.json')
        finally: temporary.unlink(missing_ok=True)
        history = root/'WORK_HISTORY.md'
        if history.is_symlink(): raise ValueError('이력 경로가 심볼릭 링크입니다.')
        fd = os.open(history, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd,'a',encoding='utf-8') as stream:
            stream.write('\n- '+datetime.now(timezone.utc).isoformat()+' 등록: '+', '.join(names)+' / 이관·서비스 변경 없음. 로그: '+str(log.path)+'\n')
        log.event('REGISTERED', '관리 디렉터리 등록 완료. 기존 서비스 배치는 유지했습니다.')


def check(root, log, doctor=False):
    records = registry(root)
    if not records['projects']: raise ValueError('등록된 프로젝트가 없습니다. init 계획을 확인하세요.')
    problems = 0
    for name, value in records['projects'].items():
        exists = (root/name/value.get('compose_file','compose.yaml')).is_file()
        log.event('PROJECT',name+' / '+value.get('status','unknown'), legacy_code=value.get('legacy_code',''), compose_exists=exists)
        source = value.get('legacy_code')
        if value.get('status') == 'registered_not_migrated' and source and not Path(source).exists():
            log.event('SOURCE_MISSING',name+': 등록한 기존 코드 위치를 찾을 수 없습니다.',path=source); problems += 1
        if not exists:
            if value.get('status') == 'registered_not_migrated':
                log.event('NOT_DEPLOYED',name+': 신규 운영 Compose는 미배치 상태입니다. 기존 운영 위치를 계속 사용하세요.')
            else:
                log.event('COMPOSE_MISSING',name+': 이관 상태와 다르게 운영 Compose 파일이 없습니다.'); problems += 1
    if doctor:
        for args in (['docker','--version'],['docker','compose','version']):
            if not shutil.which(args[0]):
                log.event('COMMAND_MISSING','docker를 찾을 수 없습니다. 설치는 실행하지 않습니다.'); problems += 1; break
            try: result = subprocess.run(args,capture_output=True,text=True,timeout=12)
            except (OSError,subprocess.TimeoutExpired):
                log.event('COMMAND_TIMEOUT','Docker 명령 실행 불가/시간 초과.'); problems += 1; continue
            if result.returncode:
                log.event('COMMAND_FAILED','Docker/Compose 버전 확인 실패. 권한과 설치 상태를 확인하세요.'); problems += 1
            else: log.event('VERSION_OK',' '.join(args)+' 확인 완료.')
        if shutil.which('docker'):
            try: result = subprocess.run(['docker','ps','-a','--format','{{json .}}'],capture_output=True,text=True,timeout=12)
            except (OSError,subprocess.TimeoutExpired): result = None
            if result is None or result.returncode:
                log.event('DOCKER_UNAVAILABLE','컨테이너 목록 조회 불가. Docker 실행/접속 권한을 확인하세요.'); problems += 1
            else:
                for line in result.stdout.splitlines()[:100]:
                    try: data = json.loads(line)
                    except ValueError: continue
                    details = {key:data.get(key) for key in ('Names','Image','State','Status','Ports')}
                    log.event('CONTAINER',str(details.get('Names'))+' / '+str(details.get('State'))+' / '+str(details.get('Status')),**details)
                    if 'unhealthy' in str(details.get('Status')):
                        log.event('UNHEALTHY','상태 점검 실패: '+str(details.get('Names'))+' / 자동 재시작하지 않습니다.'); problems += 1
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser(description='프로젝트별 서버 관리 초기 구성 (이동·서비스 변경 없음)')
    parser.add_argument('--root',type=Path,default=Path.home()/'web-server')
    parser.add_argument('--log-dir',type=Path,default=Path(tempfile.gettempdir())/'web-server-manager'/str(os.getuid()))
    sub = parser.add_subparsers(dest='action',required=True)
    init = sub.add_parser('init'); init.add_argument('--apply',action='store_true')
    add = sub.add_parser('add'); add.add_argument('name'); add.add_argument('--source',type=Path); add.add_argument('--apply',action='store_true')
    sub.add_parser('status'); sub.add_parser('doctor')
    prepare = sub.add_parser('prepare-posting')
    prepare.add_argument('--hostname',required=True)
    prepare.add_argument('--apply',action='store_true')
    posting = sub.add_parser('posting')
    posting.add_argument('operation',choices=('start','stop','status','confirm','backup'))
    posting.add_argument('--apply',action='store_true')
    handoff = sub.add_parser('use-managed'); handoff.add_argument('--apply',action='store_true')
    sub.add_parser('diagnose-filebrowser')
    for action in ('migrate-filebrowser','rollback-filebrowser'):
        migration = sub.add_parser(action); migration.add_argument('--apply',action='store_true')
    fix = sub.add_parser('repair-filebrowser'); fix.add_argument('--apply',action='store_true')
    args = parser.parse_args(); log = None
    try:
        root = safe_path(args.root)
        log = Log(args.log_dir); print('로그: '+str(log.path),flush=True)
        log.event('START',args.action+' / '+str(root))
        if args.action in ('migrate-filebrowser','rollback-filebrowser'):
            from filebrowser_migrate import operate
            operate(root,args.apply,log,rollback=args.action=='rollback-filebrowser'); result = 0
        elif args.action == 'repair-filebrowser':
            from filebrowser_repair import repair
            repair(root,args.apply,log); result = 0
        elif args.action == 'use-managed':
            from server_maintenance import use_managed
            use_managed(root,args.apply,log); result = 0
        elif args.action == 'diagnose-filebrowser':
            from server_maintenance import diagnose_filebrowser
            diagnose_filebrowser(log); result = 0
        elif args.action == 'prepare-posting':
            from posting_deploy import prepare
            prepare(root,args.hostname,args.apply,log); result = 0
        elif args.action == 'posting':
            if args.operation != 'status' and not args.apply:
                log.event('DRY_RUN','포스팅 '+args.operation+' 계획만 표시합니다. 실제 적용은 --apply가 필요합니다.')
            else:
                from posting_deploy import operate
                operate(root,args.operation,log)
            result = 0
        elif args.action in {'init','add'}:
            names = list(DEFAULTS) if args.action=='init' else [slug(args.name)]
            source = args.source.expanduser().absolute() if args.action=='add' and args.source else None
            for name in names: log.event('PLAN',str(root/name)+' → repo / data / backups (기존 파일 유지)')
            if args.apply: apply(root,names,source,log)
            else: log.event('DRY_RUN','계획만 표시했습니다. 적용하려면 같은 명령에 --apply를 추가하세요. 로그 외에는 생성하지 않습니다.')
            result = 0
        else: result = check(root,log,doctor=args.action=='doctor')
        log.event('END','완료' if result==0 else '확인이 필요한 항목이 있습니다. 로그의 에러 코드를 확인하세요.',exit_code=result)
        return result
    except (ValueError,OSError,KeyError,TypeError) as exc:
        if log: log.event('ERROR',str(exc),error_type=type(exc).__name__)
        else: print('ERROR: '+str(exc))
        return 2
    except KeyboardInterrupt:
        if log: log.event('INTERRUPTED','중단했습니다. 일부 생성된 항목이 있으면 로그를 확인하고 다시 실행하세요.')
        return 130
    finally:
        if log: log.close()


if __name__=='__main__': raise SystemExit(main())
