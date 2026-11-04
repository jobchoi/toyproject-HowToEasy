"""List usernames from a private consistent snapshot; never print password hashes."""
import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime
from uuid import uuid4
from filebrowser_migrate import container
from filebrowser_network import local_health
from posting_deploy import run, history


def usernames(output):
    lines=output.splitlines()
    index=next((i for i,line in enumerate(lines) if 'Username' in line and 'ID' in line),None)
    if index is None:raise ValueError('ACCOUNT_FORMAT: 계정 조회 형식이 다릅니다.')
    names=[]
    for line in lines[index+1:]:
        fields=line.split()
        if len(fields)>=2 and fields[0].isdigit():names.append(fields[1])
    if not names:raise ValueError('ACCOUNT_EMPTY: 확인된 계정이 없습니다.')
    return names


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.digest()


def inspect_accounts(root,apply,log):
    from manage_server import safe_path,lock
    with lock(root):
        current=container(log,'file-service')
        if current['project']!='filebrowser' or not re.fullmatch(r'sha256:[0-9a-f]{64}',current['image']):raise ValueError('ACCOUNT_OWNER: 관리 중인 FileBrowser를 확인하세요.')
        matches=[m for m in current['mounts'] if m['Type']=='bind' and m['Destination']=='/database/filebrowser.db']
        if len(matches)!=1:raise ValueError('ACCOUNT_DATABASE: 등록된 DB 마운트를 확인하세요.')
        source=safe_path(matches[0]['Source'])
        if not source.is_file():raise ValueError('ACCOUNT_DATABASE: DB 파일이 없습니다.')
        log.event('ACCOUNT_PLAN','필요 시 FileBrowser만 잠시 정지해 DB 사본을 만들고 재개합니다. 네트워크 없는 임시 조회 컨테이너에서 계정명만 읽으며 비밀번호는 변경하지 않습니다.')
        if not apply:return []
        folder=safe_path(root/'filebrowser/backups'/('account-query-'+datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:6]));folder.mkdir(mode=0o700)
        snapshot=folder/'users.db'
        try:
            if current['running']:run(['docker','--context','default','stop','--time','30',current['id']],log,'ACCOUNT_PAUSE',timeout=60)
            shutil.copyfile(source,snapshot);snapshot.chmod(0o600)
            if digest(source)!=digest(snapshot):raise ValueError('ACCOUNT_SNAPSHOT: DB 사본 검증 실패.')
        finally:
            if current['running']:
                run(['docker','--context','default','start',current['id']],log,'ACCOUNT_RESUME')
                deadline=time.monotonic()+60
                while not local_health():
                    if time.monotonic()>=deadline:raise ValueError('ACCOUNT_RESUME: 실제 HTTP 재개를 확인하지 못했습니다.')
                    time.sleep(2)
        output=run(['docker','--context','default','run','--rm','--pull','never','--network','none','--read-only','--user',str(os.getuid())+':'+str(os.getgid()),'--mount','type=bind,source='+str(folder)+',target=/query','--entrypoint','filebrowser',current['image'],'users','ls','--database','/query/users.db'],log,'ACCOUNT_QUERY',timeout=20)
        result=usernames(output)
        history(root,'FileBrowser 일관된 DB 사본 검증·계정명 조회. 원본 비밀번호/권한 변경 없음.',log)
        log.event('ACCOUNT_COUNT',str(len(result))+'개 계정 확인. 비밀번호는 조회/변경하지 않았습니다.')
        return result
