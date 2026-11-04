"""Recover a missing Docker endpoint without recreating containers or moving data."""
import http.client
import json
import time
from filebrowser_migrate import container
from filebrowser_repair import mount_set
from posting_deploy import run,save_json,history

NETWORK='my-server_default'


def endpoint_ready(info):
    networks=info.get('networks',{})
    if set(networks)!={NETWORK} or not networks[NETWORK].get('EndpointID'):return False
    bindings=info.get('actual_ports',{}).get('80/tcp') or []
    return any(str(b.get('HostPort'))=='8080' and b.get('HostIp','') in ('','0.0.0.0','127.0.0.1') for b in bindings)


def local_health():
    connection=http.client.HTTPConnection('127.0.0.1',8080,timeout=5)
    try:
        connection.request('GET','/health');response=connection.getresponse()
        return response.status==200
    except (OSError,http.client.HTTPException):return False
    finally:connection.close()


def repair(root,apply,log):
    from manage_server import registry,safe_path,lock
    with lock(root):
        records=registry(root);value=records['projects']['filebrowser']
        journal=safe_path(root/'filebrowser/migration.json');state=json.loads(journal.read_text())
        if state.get('state')!='switched_pending_review':raise ValueError('ENDPOINT_STATE: 이관 기록이 예상과 다릅니다.')
        current=container(log,'file-service');old=container(log,state['old_name'])
        if current['id']!=state['new_id'] or old['id']!=state['old_id'] or current['project']!='filebrowser' or old['project']!=value['legacy_compose_project']:
            raise ValueError('ENDPOINT_ID: 등록된 대상과 실제 컨테이너가 다릅니다.')
        if current['image']!=old['image'] or mount_set(current)!=mount_set(old):raise ValueError('ENDPOINT_DATA: 데이터/이미지가 달라 자동 복구하지 않습니다.')
        if old['running'] or old.get('restart',{}).get('Name')!='no':raise ValueError('ENDPOINT_PRESERVED: 먼저 복귀용 컨테이너 정지/자동 기동 해제를 확인하세요.')
        if not current['running'] or current['health']!='healthy':raise ValueError('ENDPOINT_SERVICE: 내부 서비스 상태를 먼저 확인하세요.')
        configured=current.get('ports',{})
        if set(configured)!={'80/tcp'} or len(configured['80/tcp'])!=1 or str(configured['80/tcp'][0].get('HostPort'))!='8080' or configured['80/tcp'][0].get('HostIp','') not in ('','0.0.0.0','127.0.0.1'):
            raise ValueError('ENDPOINT_PORT_CONFIG: 예상하지 않은 공개 포트입니다.')
        if endpoint_ready(current):
            if not local_health():raise ValueError('ENDPOINT_HTTP: 포트/네트워크는 있으나 실제 HTTP 응답이 비정상입니다.')
            log.event('ENDPOINT_ALREADY_OK','네트워크/8080 바인딩 및 호스트 HTTP 200 확인. 변경하지 않습니다.');return
        if current.get('networks') or current.get('actual_ports') or current.get('network_mode')!=NETWORK:
            raise ValueError('ENDPOINT_LAYOUT: 완전히 누락된 예상 네트워크가 아닙니다. 자동 변경하지 않습니다.')
        meta=json.loads(run(['docker','--context','default','network','inspect','--format','{"name":{{json .Name}},"driver":{{json .Driver}},"internal":{{json .Internal}}}',NETWORK],log,'ENDPOINT_NETWORK'))
        if meta!={'name':NETWORK,'driver':'bridge','internal':False}:raise ValueError('ENDPOINT_NETWORK: 기존 공유 네트워크 성격이 다릅니다.')
        log.event('ENDPOINT_PLAN','기존 독립 FileBrowser에 원래 네트워크 endpoint만 연결합니다. 컨테이너·자료·Tailscale은 재생성/변경하지 않습니다.')
        if not apply:return
        state['endpoint_state']='repairing';save_json(journal,state)
        try:
            run(['docker','--context','default','network','connect','--alias','fileserver','--alias','file-service',NETWORK,current['id']],log,'ENDPOINT_CONNECT')
            deadline=time.monotonic()+15
            while True:
                after=container(log,'file-service')
                if after['id']!=current['id'] or after['image']!=current['image'] or mount_set(after)!=mount_set(current):raise ValueError('ENDPOINT_DRIFT: 외부 변경이 감지됐습니다.')
                if endpoint_ready(after) and after['running'] and after['health']=='healthy' and local_health():break
                if time.monotonic()>=deadline:raise ValueError('ENDPOINT_VERIFY: 실제 네트워크/8080/HTTP 검증 실패. 반복 연결하지 않습니다.')
                time.sleep(1)
        except (ValueError,OSError):
            state['endpoint_state']='check_required';save_json(journal,state)
            log.event('ENDPOINT_FAILED','현재 상태와 데이터는 보존합니다. 자동 반복/다른 서비스 재시작은 하지 않습니다.');raise
        state['endpoint_state']='verified';save_json(journal,state)
        value['endpoint_state']='verified';save_json(root/'projects.json',records)
        history(root,'FileBrowser 원래 네트워크 endpoint 복구. 동일 컨테이너/데이터 유지, 실제 8080 HTTP 200 확인.',log)
        log.event('ENDPOINT_VERIFIED','동일 컨테이너·마운트 유지, 네트워크 endpoint·8080 공개·호스트 HTTP 200 확인.')


def check(log):
    info=container(log,'file-service')
    good=info['running'] and info['health']=='healthy' and endpoint_ready(info) and local_health()
    log.event('ENDPOINT_OK' if good else 'ENDPOINT_MISSING','FileBrowser 네트워크/호스트 8080/HTTP 응답 '+('정상' if good else '비정상. 내부 healthy만으로 접속 정상이라 판단하지 마세요.'))
    return good
