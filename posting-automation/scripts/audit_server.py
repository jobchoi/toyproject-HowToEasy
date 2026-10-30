#!/usr/bin/env python3
"""Bounded, read-only Linux project inventory. Standard library only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from urllib.parse import urlsplit

SKIP = {'.git', '.local', '.cache', '.config', '.ssh', '.aws', '.codex', '.agents',
        '.venv', '.venv-ui', '.venv-browser', 'venv', 'node_modules', '__pycache__',
        'site-packages', '.npm', '.vscode-server', '.rustup', '.cargo', '.conda',
        'miniconda3', 'anaconda3', 'dist', 'build', 'vendor', 'data', 'uploads', 'logs'}
MARKERS = {'compose.yml', 'compose.yaml', 'docker-compose.yml', 'docker-compose.yaml',
           'Dockerfile', 'package.json', 'pyproject.toml', 'requirements.txt',
           'requirements-ui.txt', 'project-environment.json', 'manage.py',
           'Cargo.toml', 'go.mod', 'composer.json'}


def command(args):
    """Do not include stderr or failed command output in a shareable report."""
    if not shutil.which(args[0]): return None, 'command_missing'
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=12,
                                env={**os.environ, 'GIT_OPTIONAL_LOCKS':'0', 'LC_ALL':'C'})
    except (OSError, subprocess.TimeoutExpired): return None, 'unavailable_or_timeout'
    if result.returncode: return None, 'permission_denied_or_command_failed'
    if len(result.stdout) > 2_000_000: return None, 'output_limit'
    return result.stdout, None


def safe_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname: return '[non-http target]'
        host = parsed.hostname
        if ':' in host: host = '[' + host + ']'
        return parsed.scheme + '://' + host + (':' + str(parsed.port) if parsed.port else '')
    except (ValueError, TypeError): return '[invalid target]'


def git_info(folder):
    prefix = ['git', '-c', 'core.fsmonitor=false', '-C', str(folder)]
    head, error = command(prefix + ['symbolic-ref', '--short', '-q', 'HEAD'])
    commit, commit_error = command(prefix + ['rev-parse', '--short', 'HEAD'])
    status, status_error = command(prefix + ['status', '--porcelain', '--untracked-files=normal'])
    return {'path':str(folder), 'branch':head.strip() if head else None,
            'commit':commit.strip() if commit else None,
            'changed_entry_count':len(status.splitlines()) if status is not None else None,
            'status_error':status_error, 'git_error':commit_error}


def scan(roots, depth, limit):
    directories, repos, notes = [], [], []
    seen = set()
    def visit(folder, level):
        if len(directories) >= limit:
            return
        if folder.is_symlink(): return
        name = str(folder.absolute())
        if name in seen: return
        seen.add(name)
        try:
            # Bound enumeration even for directories containing many user files.
            entries = []
            with os.scandir(folder) as iterator:
                for entry in iterator:
                    entries.append(entry)
                    if len(entries) >= 500:
                        notes.append({'path':name,'reason':'entry_limit_500'}); break
        except OSError:
            notes.append({'path':name,'reason':'missing_or_not_readable'}); return
        markers = sorted(e.name for e in entries if e.name in MARKERS or e.name.endswith('.service')
                         or (e.name.startswith(('compose.', 'docker-compose.')) and e.name.endswith(('.yaml', '.yml'))))
        directories.append({'path':name,'depth':level,'markers':markers})
        if any(e.name == '.git' for e in entries): repos.append(git_info(folder))
        children = sorted((e for e in entries if not e.name.startswith('.') and e.name not in SKIP), key=lambda e:e.name)
        for entry in children:
            if entry.is_symlink(): continue
            try: is_dir = entry.is_dir(follow_symlinks=False)
            except OSError: continue
            if is_dir and level < depth: visit(Path(entry.path),level+1)
    for root in roots: visit(root,0)
    if len(directories) >= limit: notes.append({'reason':'directory_limit','limit':limit})
    return {'roots':[str(p) for p in roots], 'directories':directories,'repositories':repos,'notes':notes}


def docker_inventory():
    listing, error = command(['docker','ps','-a','--format','{{json .}}'])
    if error: return {'error':error,'containers':[]}
    containers = []
    for line in listing.splitlines()[:100]:
        try: item = json.loads(line)
        except ValueError: continue
        record = {key:item.get(key) for key in ('ID','Names','Image','State','Status','Ports')}
        # Never request Config.Env, command arguments, or full inspect output.
        template = '{"mounts":{{json .Mounts}},"restart":{{json .HostConfig.RestartPolicy.Name}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},"config_files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}}}'
        detail, detail_error = command(['docker','inspect','--format',template,item['ID']])
        if detail_error: record['detail_error'] = detail_error
        else:
            try:
                data = json.loads(detail)
                data['mounts'] = [{k:m.get(k) for k in ('Type','Source','Destination','RW')} for m in data.get('mounts',[])]
                record.update(data)
            except ValueError: record['detail_error'] = 'invalid_json'
        containers.append(record)
    return {'containers':containers,'truncated':len(listing.splitlines())>100}


def services(user=False):
    prefix = ['systemctl'] + (['--user'] if user else [])
    listing, error = command(prefix + ['list-units','--type=service','--state=running','--no-legend','--plain','--no-pager'])
    if error: return {'error':error,'services':[]}
    records = []
    units = [line.split()[0] for line in listing.splitlines() if line.strip()][:100]
    for unit in units:
        data, error = command(prefix + ['show',unit,'--no-pager','--property=Id,FragmentPath,WorkingDirectory,User,ActiveState,SubState'])
        if not error:
            records.append(dict(line.split('=',1) for line in data.splitlines() if '=' in line))
    return {'services':records,'limit':100}


def listeners():
    output, error = command(['ss','-ltnpH'])
    if error: return {'error':error,'tcp':[]}
    rows = []
    for line in output.splitlines()[:200]:
        parts = line.split()
        if len(parts)<5: continue
        processes = []
        for name, pid in re.findall(r'\("([^"\n]+)",pid=(\d+)',line):
            process = {'name':name, 'pid':int(pid)}
            for key in ('cwd', 'exe'):
                try: process[key] = os.readlink('/proc/' + pid + '/' + key)
                except OSError: process[key] = None
            processes.append(process)
        rows.append({'listen':parts[3], 'processes':processes})
    return {'tcp':rows,'note':'Process names/PIDs may be absent without elevated permissions; UDP not collected.'}


def tailscale():
    output, error = command(['tailscale','serve','status','--json'])
    if error: return {'error':error}
    try: data = json.loads(output)
    except ValueError: return {'error':'invalid_json'}
    routes = []
    for host, web in (data.get('Web') or {}).items():
        for path, handler in (web.get('Handlers') or {}).items():
            routes.append({'host':host, 'path':path, 'proxy':safe_url(handler['Proxy']) if handler.get('Proxy') else None,
                           'kind':'proxy' if handler.get('Proxy') else 'file_or_text'})
    return {'routes':routes,'funnel':data.get('AllowFunnel',{}),
            'tcp':{port:{k:value.get(k) for k in ('HTTPS','HTTP')} for port,value in (data.get('TCP') or {}).items()}}


def markdown_report(report):
    lines = ['# 서버 구조 조사 결과', '', '읽기 전용 조사이며 서비스/파일 이동·설정 변경을 실행하지 않았습니다.',
             '경로·계정·호스트·서비스 이름은 포함됩니다. 공유 전 내용을 확인하세요.', '',
             f"- 생성 시각(UTC): {report['created_at']}",f"- 플랫폼: {report['system']}", '', '## 프로젝트 저장소', '']
    for repo in report['filesystem']['repositories']:
        lines.append('- ' + json.dumps(repo,ensure_ascii=False))
    lines += ['', '## 디렉터리와 구성 파일 위치', '', '```text']
    for row in report['filesystem']['directories']:
        lines.append('  '*row['depth'] + row['path'] + ('  ['+', '.join(row['markers'])+']' if row['markers'] else ''))
    lines += ['```']
    for title,key in [('조사 누락/제한','filesystem'),('Docker','docker'),('시스템 서비스','system_services'),('사용자 서비스','user_services'),('TCP 포트','listeners'),('Tailscale 연결','tailscale')]:
        value = report[key]['notes'] if key=='filesystem' else report[key]
        lines += ['', '## '+title, '', '```json',json.dumps(value,ensure_ascii=False,indent=2),'```']
    lines += ['', '## 다음 검토', '', '- 저장소/Compose 경로와 실행 프로세스·포트·데이터 마운트 대조',
              '- 기존 서비스 유지 및 프로젝트별 코드·데이터·운영 설정 위치 제안',
              '- 백업·이관·복구 절차 확정 후 개별 프로젝트부터 변경',
              '- 프로젝트 탐색은 깊이/개수 제한이 있으므로 누락 경로를 추가하여 재실행', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='서버 구조 읽기 전용 조사 (Python 표준 라이브러리, sudo 불필요)')
    parser.add_argument('--roots', nargs='+', type=Path, help='조사할 프로젝트 상위 경로')
    parser.add_argument('--depth',type=int,default=4)
    parser.add_argument('--max-dirs',type=int,default=1500)
    parser.add_argument('--output',type=Path, help='새 보고서 폴더 (기존 경로 덮어쓰지 않음)')
    args = parser.parse_args()
    if not 0 <= args.depth <= 8 or not 1 <= args.max_dirs <= 10000: parser.error('depth: 0~8, max-dirs: 1~10000')
    output = (args.output or Path.home()/'server-audits'/datetime.now().strftime('%Y%m%d-%H%M%S')).absolute()
    if output.exists() or output.is_symlink(): parser.error('새 output 폴더를 지정하세요. 기존 결과는 보존합니다.')
    roots = [p.expanduser().absolute() for p in (args.roots or [Path.home(),Path('/opt'),Path('/srv'),Path('/var/www')])]
    print('디렉터리/Git → Docker → 서비스 → 포트/Tailscale 순으로 조사합니다.',flush=True)
    report = {'schema_version':1,'created_at':datetime.now(timezone.utc).isoformat(),
              'system':{'os':platform.system(),'release':platform.release(),'architecture':platform.machine()},
              'filesystem':scan(roots,args.depth,args.max_dirs)}
    for key,collector in [('docker',docker_inventory),('system_services',services),('user_services',lambda:services(True)),('listeners',listeners),('tailscale',tailscale)]:
        print(key+' 조사 중…',flush=True)
        report[key] = collector()
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    for name,content in [('report.json',json.dumps(report,ensure_ascii=False,indent=2)),('report.md',markdown_report(report))]:
        path = output/name
        with path.open('x',encoding='utf-8') as stream: stream.write(content)
        path.chmod(0o600)
    print('완료: '+str(output/'report.md'))
    print('보고서만 생성했습니다. 정리·중지·재시작·설치·파일 이동은 실행하지 않았습니다.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
