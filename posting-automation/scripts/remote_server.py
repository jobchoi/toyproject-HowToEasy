#!/usr/bin/env python3
"""Run a bounded management workflow over SSH and collect local reports."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
PAYLOAD=Path(__file__).with_name('remote_job.py')
WORKFLOWS=('status','diagnose','repair-filebrowser','posting-backup','migrate-filebrowser','rollback-filebrowser','sync-only')


def write_private(path,text):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:stream.write(text)


def ssh_command(host,port,root,job_id,workflow,apply,sync,collect):
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@:\[\]%-]*',host) or host.count('@')>1: raise ValueError('SSH 호스트 또는 별칭을 확인하세요.')
    if not 1<=port<=65535:raise ValueError('SSH 포트는 1~65535입니다.')
    args=['python3','-u','-','--root',root,'--job-id',job_id,'--workflow',workflow]
    if apply:args.append('--apply')
    if sync:args.append('--sync')
    if collect:args.append('--collect')
    return ['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes',
            '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3','-p',str(port),host,shlex.join(args)]


def push(log):
    env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_OPTIONAL_LOCKS':'0'}
    def git(args):
        try:result=subprocess.run(['git','-c','core.fsmonitor=false','-C',str(ROOT),*args],capture_output=True,text=True,timeout=90,env=env)
        except (OSError,subprocess.TimeoutExpired):raise ValueError('PUSH_CONNECTION_FAILED') from None
        if result.returncode:raise ValueError('PUSH_AUTH_OR_COMMAND_FAILED')
        return result.stdout.strip()
    if git(['status','--porcelain']):raise ValueError('LOCAL_REPO_DIRTY')
    if git(['branch','--show-current'])!='develop':raise ValueError('LOCAL_BRANCH_MISMATCH')
    remote=git(['remote','get-url','origin'])
    if remote not in ('https://github.com/jobchoi/toyproject-HowToEasy.git','git@github.com:jobchoi/toyproject-HowToEasy.git'):
        raise ValueError('PUSH_REMOTE_MISMATCH')
    git(['push','origin','develop'])
    log.append({'code':'PUSH_OK','time':datetime.now(timezone.utc).isoformat()})


def ssh_error_summary(stderr):
    known=[('Permission denied','SSH_AUTH_FAILED'),('Host key verification failed','SSH_HOST_KEY_NOT_TRUSTED'),
           ('REMOTE HOST IDENTIFICATION HAS CHANGED','SSH_HOST_KEY_CHANGED'),('Could not resolve hostname','SSH_DNS_FAILED'),
           ('No route to host','SSH_NETWORK_FAILED'),('Connection refused','SSH_CONNECTION_REFUSED'),
           ('Connection timed out','SSH_CONNECTION_TIMEOUT'),('Connection closed','SSH_CONNECTION_CLOSED'),
           ('Connection reset','SSH_CONNECTION_RESET')]
    codes=[code for text,code in known if text in stderr]
    return '\n'.join(codes or (['SSH_DIAGNOSTIC_REDACTED'] if stderr else []))+'\n'


def report(result):
    lines=['# 원격 서버 작업 결과','',f"- 작업 ID: {result['job_id']}",f"- 상태: {result.get('state')}",
           f"- 종료 코드: {result.get('exit_code')}",f"- 원격 결과 위치: {result.get('remote_directory','미확인')}",'']
    if result.get('error'):lines+=['- 오류: '+result['error'],'']
    lines+=['## 실행 단계','']
    for step in result.get('steps',[]):lines.append('- '+step['name']+': '+str(step['exit_code']))
    lines+=['','## 수집된 출력','','```text',result.get('console',''),'```','',
            'unknown/running은 성공/실패로 확정하지 마세요. 동일 작업 ID의 --collect로 조회하고 변경 명령을 새 작업으로 반복하지 마세요.','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description='SSH 서버 관리 실행/결과 수집. 비밀번호 입력·저장 없음.')
    parser.add_argument('--host',required=True,help='사용자@호스트 또는 SSH 별칭')
    parser.add_argument('--port',type=int,default=22);parser.add_argument('--root',default='~/web-server')
    parser.add_argument('--workflow',choices=WORKFLOWS,default='status')
    parser.add_argument('--sync',action='store_true');parser.add_argument('--push',action='store_true')
    parser.add_argument('--apply',action='store_true');parser.add_argument('--collect',metavar='JOB_ID')
    parser.add_argument('--job-id');parser.add_argument('--output',type=Path)
    parser.add_argument('--errors-only',action='store_true');parser.add_argument('--timeout',type=int,default=2100)
    args=parser.parse_args()
    job_id=args.collect or args.job_id or uuid4().hex
    if not re.fullmatch(r'[0-9a-f]{32}',job_id):parser.error('작업 ID는 32자리 소문자 hex입니다.')
    if not 10<=args.timeout<=7200:parser.error('timeout은 10~7200초입니다.')
    if args.collect and (args.push or args.sync or args.apply):parser.error('collect는 조회 전용입니다. push/sync/apply와 함께 사용하지 마세요.')
    if args.workflow=='sync-only' and not args.collect:args.sync=True
    try:command=ssh_command(args.host,args.port,args.root,job_id,args.workflow,args.apply,args.sync,bool(args.collect))
    except ValueError as error:parser.error(str(error))
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:6]
    output=(args.output or ROOT/'.local'/'remote-runs'/(job_id+'-'+stamp)).expanduser().absolute()
    if output.exists() or output.resolve()!=output:parser.error('결과는 새 폴더에 저장합니다. 기존 경로나 심볼릭 링크는 사용할 수 없습니다.')
    output.mkdir(parents=True,mode=0o700)
    events=[]
    write_private(output/'request.json',json.dumps({'job_id':job_id,'host':args.host,'workflow':args.workflow,'apply':args.apply,'sync':args.sync,'collect':bool(args.collect)},ensure_ascii=False,indent=2))
    if not args.errors_only:print('작업 ID: '+job_id+'\n결과 폴더: '+str(output),flush=True)
    result={'job_id':job_id,'state':'failed','exit_code':2}
    try:
        if args.push:
            if args.apply:push(events)
            else:events.append({'code':'PUSH_DRY_RUN'})
        events.append({'code':'SSH_START','time':datetime.now(timezone.utc).isoformat()})
        try:
            transport=subprocess.run(command,input=PAYLOAD.read_text(encoding='utf-8'),capture_output=True,text=True,timeout=args.timeout)
        except subprocess.TimeoutExpired:
            result.update(state='unknown',exit_code=3,error='SSH_TIMEOUT_RESULT_UNCERTAIN');transport=None
        except OSError:
            result.update(error='SSH_NOT_AVAILABLE');transport=None
        if transport is not None:
            events.append({'code':'SSH_FINISHED','returncode':transport.returncode})
            write_private(output/'ssh.stderr.txt',ssh_error_summary(transport.stderr))
            if transport.returncode:
                result.update(state='unknown',exit_code=3,error='SSH_CONNECTION_OR_REMOTE_PROCESS_FAILED')
                for signature,code in (('Permission denied','SSH_AUTH_FAILED'),('Host key verification failed','SSH_HOST_KEY_NOT_TRUSTED'),('Could not resolve hostname','SSH_DNS_FAILED'),('No route to host','SSH_NETWORK_FAILED'),('Connection refused','SSH_CONNECTION_REFUSED'),('Connection timed out','SSH_CONNECTION_TIMEOUT')):
                    if signature in transport.stderr:
                        result.update(state='connection_failed',exit_code=2,error=code)
                        break
            else:
                try:
                    received=json.loads(transport.stdout)
                    if received.get('job_id')!=job_id:raise ValueError()
                    result=received
                except (ValueError,AttributeError):result.update(state='unknown',exit_code=3,error='REMOTE_RESPONSE_INVALID')
    except ValueError as error:result.update(error=str(error))
    result['issues']=[line[:500] for line in result.get('console','').splitlines() if re.match(r'^\[[A-Z_]*(?:ERROR|FAILED|UNHEALTHY|MISSING|CONFLICT|BUSY)[A-Z_]*\]',line)][:8]
    events.append({'code':'RESULT','state':result.get('state'),'exit_code':result.get('exit_code')})
    write_private(output/'result.json',json.dumps(result,ensure_ascii=False,indent=2))
    write_private(output/'report.md',report(result))
    for item in result.get('management_logs',[]):
        if re.fullmatch(r'[A-Za-z0-9_.-]+\.jsonl',item.get('name','')):write_private(output/('remote-'+item['name']),item['text'])
    write_private(output/'events.jsonl',''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in events))
    if result.get('exit_code') or not args.errors_only:
        print('상태: '+str(result.get('state'))+' / 코드: '+str(result.get('exit_code'))+'\n보고서: '+str(output/'report.md'))
        if result.get('error'):print('오류: '+result['error'])
        for issue in result.get('issues',[]):print('문제: '+issue)
        if result.get('state') in {'unknown','running'}:
            print('변경 작업을 반복하지 말고 --collect '+job_id+' 로 결과를 조회하세요.')
    return int(result.get('exit_code',2))


if __name__=='__main__':raise SystemExit(main())
