#!/usr/bin/env python3
"""Portable, read-only environment preflight. Network checks are explicit opt-in."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def check_command(args, timeout=10):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 'timeout', ''
    except OSError:
        return 'unavailable', ''
    return ('ok' if result.returncode == 0 else 'failed'), result.stdout.strip() if result.returncode == 0 else ''


def inspect_environment(remote=False, host='raspberry-posting'):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@:\[\]%-]*', host) or host.count('@') > 1:
        raise ValueError('INVALID_SSH_HOST')
    records = []
    def add(name, state, detail):
        records.append({'check':name, 'state':state, 'detail':detail})
    spec = json.loads((ROOT/'project-environment.json').read_text())
    minimum = tuple(spec['python_minimum'])
    add('python', 'ok' if sys.version_info[:2] >= minimum else 'failed', platform.python_version())
    add('platform', 'info', platform.system()+'/'+platform.machine())
    for executable in ('git','ssh','scp','docker'):
        add(executable, 'ok' if shutil.which(executable) else 'optional_missing' if executable == 'docker' else 'missing', 'executable presence only')
    git = ['git','-c','core.fsmonitor=false','-C',str(ROOT)]
    status, branch = check_command(git+['branch','--show-current'])
    add('git_branch', status, branch if re.fullmatch(r'[A-Za-z0-9_./-]+',branch) else 'unavailable')
    status, dirty = check_command(git+['status','--porcelain'])
    add('git_worktree', status if status != 'ok' else 'needs_attention' if dirty else 'ok', 'modified files present' if dirty else 'no changes reported')
    interpreter = ROOT/spec['environment']/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if interpreter.exists():
        state, _ = check_command([str(interpreter),'-c','import fastapi,uvicorn,httpx'],15)
        add('ui_environment',state,'import fastapi/uvicorn/httpx')
    else:
        add('ui_environment','missing','run bash scripts/setup_project.sh --profile test')
    # Only presence booleans, never credential values or configuration contents.
    add('auth_environment','info',{name:bool(os.environ.get(name)) for name in ('SSH_AUTH_SOCK','GIT_ASKPASS','VSCODE_GIT_IPC_HANDLE')})
    if remote:
        state, _ = check_command(['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8',host,'true'],12)
        add('remote_ssh',state,'read-only connection probe; raw SSH output omitted')
    else:
        add('remote_ssh','not_checked','opt in with --remote')
    return {'schema_version':1,'checks':records,'needs_attention':any(r['state'] in {'failed','missing','needs_attention','unavailable','timeout'} for r in records)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote',action='store_true'); parser.add_argument('--host',default='raspberry-posting')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try: result=inspect_environment(args.remote,args.host)
    except (ValueError,OSError): print('ENVIRONMENT_CHECK_FAILED');return 2
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        # Exclusive creation avoids overwriting another agent's diagnostics or following a symlink.
        fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:stream.write(text)
    print(text,end='')
    return 1 if result['needs_attention'] else 0


if __name__=='__main__': raise SystemExit(main())
