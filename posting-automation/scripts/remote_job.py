"""SSH stdin payload: execute allowlisted management workflows and retain results."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

WORKFLOWS = {
    'status': [('status',),('posting','status'),('doctor',)],
    'diagnose': [('posting','status'),('diagnose-filebrowser',),('doctor',)],
    'repair-filebrowser': [('repair-filebrowser',),('diagnose-filebrowser',),('doctor',)],
    'posting-backup': [('posting','backup'),('posting','status')],
    'sync-only': [],
}
MUTATING = {'repair-filebrowser', 'posting-backup'}


def write_json(path, data):
    temp=path.with_name('.'+path.name+'-'+uuid4().hex)
    try:
        with temp.open('x',encoding='utf-8') as stream: json.dump(data,stream,ensure_ascii=False,indent=2)
        temp.chmod(0o600); temp.replace(path)
    finally: temp.unlink(missing_ok=True)


def safe_path(path):
    path=Path(os.path.abspath(Path(path).expanduser()))
    if path.resolve()!=path or path in (Path('/'),Path.home().resolve()):
        raise ValueError('UNSAFE_PATH')
    return path


def process_marker(pid):
    try:
        fields=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()
        return None if fields[0] in {'Z','X'} else fields[19]
    except (OSError,IndexError): return None


def collected(folder):
    for name in ('result.json','request.json'):
        if (folder/name).is_symlink(): raise ValueError('UNSAFE_RESULT_PATH')
    result=json.loads((folder/'result.json').read_text()) if (folder/'result.json').exists() else None
    if result is None:
        if not (folder/'request.json').exists(): return {'state':'unknown' if folder.exists() else 'not_found','job_id':folder.name,'exit_code':3 if folder.exists() else 2}
        request=json.loads((folder/'request.json').read_text())
        alive=bool(request.get('process_marker')) and process_marker(request['pid'])==request['process_marker']
        result={'state':'running' if alive else 'unknown','job_id':folder.name,'exit_code':3}
    result={**result,'remote_directory':str(folder),'console':'','management_logs':[]}
    console=folder/'console.txt'
    if console.is_file() and not console.is_symlink(): result['console']=console.read_text(errors='replace')[-160_000:]
    # Manager logs are selected from their printed path, confined to this workspace.
    log_root=folder.parent.parent/'logs'
    seen=set()
    for line in result['console'].splitlines():
        if not line.startswith('로그: '): continue
        path=Path(line[4:].strip())
        if str(path) in seen:continue
        seen.add(str(path))
        if path.is_symlink() or path.parent!=log_root or path.suffix!='.jsonl' or not path.is_file(): continue
        if len(result['management_logs'])>=8: break
        result['management_logs'].append({'name':path.name,'text':path.read_text(errors='replace')[-80_000:]})
    return result


def git(repo,args):
    try:
        result=subprocess.run(['git','-c','core.fsmonitor=false','-C',str(repo),*args],
            capture_output=True,text=True,timeout=90,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0'})
    except (OSError,subprocess.TimeoutExpired): raise ValueError('REMOTE_GIT_TIMEOUT') from None
    if result.returncode: raise ValueError('REMOTE_GIT_FAILED')
    return result.stdout.strip()


def run(root,job_id,workflow,apply=False,sync=False,collect=False):
    root=safe_path(root)
    if not re.fullmatch(r'[0-9a-f]{32}',job_id): raise ValueError('INVALID_JOB_ID')
    folder=root/'remote-runs'/job_id
    safe_path(folder)
    if collect: return collected(folder)
    if (folder/'request.json').exists():
        previous=json.loads((folder/'request.json').read_text())
        if any(previous.get(k)!=v for k,v in {'workflow':workflow,'apply':apply,'sync':sync}.items()):
            raise ValueError('JOB_ID_CONFLICT')
        return collected(folder)  # Never repeat a submitted mutation.
    if (folder/'result.json').exists():return collected(folder)
    repo=safe_path(root/'posting-automation'/'repo')
    manager=repo/'posting-automation'/'scripts'/'manage_server.py'
    if not (root/'projects.json').is_file() or not manager.is_file(): raise ValueError('MANAGED_WORKSPACE_MISSING')
    run_root=root/'remote-runs'; run_root.mkdir(mode=0o700,exist_ok=True)
    folder.mkdir(mode=0o700,exist_ok=False)
    guard=safe_path(root/'.remote-operation.lock')
    with guard.open('a') as stream:
        try: fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            write_json(folder/'result.json',{'job_id':job_id,'state':'busy','exit_code':4,'error':'ANOTHER_REMOTE_JOB'})
            return collected(folder)
        request={'job_id':job_id,'workflow':workflow,'apply':apply,'sync':sync,'pid':os.getpid(),
                 'process_marker':process_marker(os.getpid()),'started_at':datetime.now(timezone.utc).isoformat()}
        write_json(folder/'request.json',request)
        result={'job_id':job_id,'workflow':workflow,'apply':apply,'sync':sync,'state':'succeeded','exit_code':0,'steps':[]}
        fd=os.open(folder/'console.txt',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as console:
            try:
                if apply and (sync or workflow in MUTATING):
                    if git(repo,['status','--porcelain']): raise ValueError('REMOTE_REPO_DIRTY')
                    if git(repo,['branch','--show-current'])!='develop': raise ValueError('REMOTE_BRANCH_MISMATCH')
                if sync:
                    if apply:
                        old=git(repo,['rev-parse','HEAD'])
                        git(repo,['pull','--ff-only','origin','develop'])
                        new=git(repo,['rev-parse','HEAD'])
                        result['steps'].append({'name':'sync','exit_code':0,'before':old,'after':new})
                        console.write('[SYNC_OK] managed repo fast-forward 완료\n');console.flush()
                    else: console.write('[DRY_RUN] repo 갱신은 --apply 필요\n');console.flush()
                if WORKFLOWS[workflow]:
                    help_result=subprocess.run([sys.executable,str(manager),'--help'],capture_output=True,text=True,timeout=15)
                    if help_result.returncode or any(operation[0] not in help_result.stdout for operation in WORKFLOWS[workflow]):
                        raise ValueError('REMOTE_CAPABILITY_MISSING')
                for operation in WORKFLOWS[workflow]:
                    arguments=list(operation)
                    if apply and workflow in MUTATING and arguments in (['repair-filebrowser'],['posting','backup']): arguments.append('--apply')
                    command=[sys.executable,str(manager),'--root',str(root),'--log-dir',str(root/'logs'),*arguments]
                    console.write('[REMOTE_STEP] '+' '.join(operation)+'\n');console.flush()
                    step=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=console,stderr=subprocess.DEVNULL,start_new_session=True)
                    result['steps'].append({'name':' '.join(operation),'exit_code':step.returncode})
                    if step.returncode:
                        result.update(state='needs_attention' if step.returncode==1 else 'failed',exit_code=step.returncode)
                        break
            except (ValueError,OSError) as error:
                # Never include raw command output, remote URLs or credentials.
                code=str(error) if isinstance(error,ValueError) else 'REMOTE_OS_ERROR'
                if not re.fullmatch(r'[A-Z_]+',code):code='REMOTE_ERROR'
                result.update(state='unknown' if 'UNCERTAIN' in code else 'failed',exit_code=3 if 'UNCERTAIN' in code else 2,error=code)
                console.write('[REMOTE_ERROR] '+code+'\n')
        result['finished_at']=datetime.now(timezone.utc).isoformat()
        write_json(folder/'result.json',result)
        return collected(folder)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',default='~/web-server')
    parser.add_argument('--job-id',required=True)
    parser.add_argument('--workflow',choices=WORKFLOWS,default='status')
    parser.add_argument('--apply',action='store_true');parser.add_argument('--sync',action='store_true');parser.add_argument('--collect',action='store_true')
    args=parser.parse_args()
    try:
        root=safe_path(args.root)
        if not re.fullmatch(r'[0-9a-f]{32}',args.job_id): raise ValueError('INVALID_JOB_ID')
        folder=root/'remote-runs'/args.job_id
        safe_path(folder)
        if args.collect or (folder/'request.json').exists() or (folder/'result.json').exists():
            result=run(root,args.job_id,args.workflow,args.apply,args.sync,args.collect)
        else:
            # A detached worker owns execution/result files; an SSH disconnect must not
            # interrupt a backup between stop and resume, or trigger a second repair.
            pid=os.fork()
            if pid==0:
                os.setsid()
                fd=os.open(os.devnull,os.O_RDWR)
                for target in (0,1,2):os.dup2(fd,target)
                if fd>2:os.close(fd)
                try:run(root,args.job_id,args.workflow,args.apply,args.sync,False)
                except Exception:pass  # Incomplete jobs remain unknown; never overwrite another worker's result.
                finally:os._exit(0)
            while True:
                finished,_=os.waitpid(pid,os.WNOHANG)
                if finished:
                    result=collected(folder)
                    break
                time.sleep(0.5)
    except (ValueError,OSError) as error:
        code=str(error) if isinstance(error,ValueError) and re.fullmatch(r'[A-Z_]+',str(error)) else 'REMOTE_SETUP_FAILED'
        result={'job_id':args.job_id,'state':'failed','exit_code':2,'error':code}

    print(json.dumps(result,ensure_ascii=False))
    return 0  # Transport success is distinct from workflow exit_code.


if __name__=='__main__':raise SystemExit(main())
