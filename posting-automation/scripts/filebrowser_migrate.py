"""Isolate FileBrowser control plane while retaining all original mounts and rollback container."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from uuid import uuid4

from filebrowser_repair import inspect, mount_set
from posting_deploy import run, save_json, history


def compose_model(info, model):
    """Build only one service; pin existing external volumes and network resources."""
    service = info['service']
    spec = deepcopy(model['services'][service])
    if any(spec.get(k) for k in ('depends_on','secrets','configs','build','links','volumes_from','network_mode','extends','develop','post_start','pre_stop','profiles')):
        raise ValueError('DEPENDENCY_UNSUPPORTED: 독립 이관 전에 추가 서비스 의존성을 확인하세요.')
    if set(spec.get('networks',{})) != {'default'}:
        raise ValueError('NETWORK_LAYOUT: 예상한 default 네트워크 구성이 아닙니다.')
    spec['image'] = info['image']
    spec['container_name'] = 'file-service'
    spec['volumes'] = []
    volumes = {}
    for index, mount in enumerate(info['mounts']):
        if mount['Type'] == 'bind':
            source = mount['Source']
            kind = 'bind'
        elif mount['Type'] == 'volume' and mount.get('Name'):
            source = 'preserved_'+str(index)
            kind = 'volume'
            volumes[source] = {'external':True,'name':mount['Name']}
        else:
            raise ValueError('MOUNT_UNSUPPORTED: 예상하지 않은 마운트 종류입니다.')
        spec['volumes'].append({'type':kind,'source':source,'target':mount['Destination'],'read_only':not mount['RW']})
    return {'name':'filebrowser','services':{service:spec},'volumes':volumes,
            'networks':{'default':{'external':True,'name':'my-server_default'}}}


def verify_archive(archive):
    """Actually restore in a private directory and compare content and mode with tar metadata."""
    with tempfile.TemporaryDirectory(prefix='restore-',dir=archive.parent) as folder:
        root = Path(folder)
        with tarfile.open(archive, 'r:') as stream:
            seen = set()
            for member in stream:
                path = root/member.name
                if not path.resolve().is_relative_to(root) or member.name in seen or not (member.isdir() or member.isfile()):
                    raise ValueError('BACKUP_TYPE: 링크/특수 파일/중복 항목이 있어 자동 이관을 중단합니다.')
                seen.add(member.name)
                if member.isdir():
                    path.mkdir(parents=True,exist_ok=True)
                else:
                    path.parent.mkdir(parents=True,exist_ok=True)
                    source = stream.extractfile(member)
                    expected = hashlib.sha256()
                    with path.open('xb') as target:
                        for chunk in iter(lambda:source.read(1024*1024),b''):
                            expected.update(chunk); target.write(chunk)
                    path.chmod(member.mode & 0o777)
                    actual = hashlib.sha256(path.read_bytes()).digest()
                    if actual != expected.digest() or path.stat().st_size != member.size or path.stat().st_mode & 0o777 != member.mode & 0o777:
                        raise ValueError('BACKUP_VERIFY: 복원 검증 실패.')
    digest=hashlib.sha256()
    with archive.open('rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def copy_archive(container, destination, archive, log):
    # Stream binary tar, never settings/DB contents to logs. No shell and no new image pull.
    log.event('MIGRATION_BACKUP','정지된 컨테이너의 마운트 백업 및 임시 복원 검증.',destination=destination)
    fd = os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as output:
        try:
            result=subprocess.run(['docker','--context','default','cp',container+':'+destination,'-'],stdout=output,stderr=subprocess.DEVNULL,timeout=300)
        except (OSError,subprocess.TimeoutExpired): raise ValueError('BACKUP_COPY: 백업 복사 실패/시간 초과.') from None
    if result.returncode: raise ValueError('BACKUP_COPY: 백업 복사 실패.')
    return verify_archive(archive)


def container(log, name):
    template='{"id":{{json .Id}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"running":{{json .State.Running}},"health":{{with .State.Health}}{{json .Status}}{{else}}null{{end}},"image":{{json .Image}},"config":{{json .Config}},"ports":{{json .HostConfig.PortBindings}},"restart":{{json .HostConfig.RestartPolicy}},"mounts":{{json .Mounts}},"networks":{{json .NetworkSettings.Networks}}}'
    return json.loads(run(['docker','--context','default','inspect','--format',template,name],log,'MIGRATION_INSPECT'))


def operate(root, apply, log, rollback=False):
    from manage_server import registry, safe_path, lock
    with lock(root):
        records=registry(root); value=records['projects']['filebrowser']
        base=safe_path(root/'filebrowser'); journal=safe_path(base/'migration.json')
        entry=safe_path(base/'compose.yaml')
        compose=['docker','--context','default','compose','--project-directory',str(base),'-p','filebrowser','-f',str(entry)]
        if journal.exists():
            state=json.loads(journal.read_text())
            if rollback:
                if state['state']!='switched_pending_review': raise ValueError('ROLLBACK_STATE: 전환 완료 상태가 아닙니다.')
                current=container(log,'file-service')
                if current['id']!=state['new_id'] or current['project']!='filebrowser': raise ValueError('ROLLBACK_ID: 복귀 대상이 변경됐습니다.')
                log.event('ROLLBACK_PLAN','신규 FileBrowser만 제거하고 보존한 기존 컨테이너를 재개합니다. 볼륨은 삭제하지 않습니다.')
                if not apply:return
                run(['docker','--context','default','stop','file-service'],log,'NEW_STOP')
                run(['docker','--context','default','rm',state['new_id']],log,'NEW_REMOVE')
                run(['docker','--context','default','rename',state['old_name'],'file-service'],log,'OLD_RENAME')
                run(['docker','--context','default','start','file-service'],log,'OLD_START')
                state['state']='rolled_back'; save_json(journal,state)
                value['status']='registered_not_migrated'; value['control_state']='rolled_back'; save_json(root/'projects.json',records)
                history(root,'FileBrowser 기존 컨테이너 복귀. 원본/백업/볼륨 유지.',log);return
            if state['state']=='switched_pending_review':
                current=container(log,'file-service')
                if current['id']!=state['new_id'] or current['health']!='healthy': raise ValueError('MIGRATION_DRIFT: 전환 후 상태가 변경됐습니다.')
                log.event('ALREADY_SWITCHED','이미 제어 분리 완료. 웹 기능 확인은 별도입니다.');return
            raise ValueError('MIGRATION_EXISTS: 이전 실행 기록이 있습니다. 자동 반복하지 않습니다.')
        if rollback:raise ValueError('ROLLBACK_MISSING: 이관 기록이 없습니다.')
        info=inspect(log); runtime=container(log,'file-service')
        if info['project']!=value['legacy_compose_project'] or info['health']!='healthy' or not runtime['running']:
            raise ValueError('SOURCE_STATE: 기존 FileBrowser 정상 상태를 먼저 확인하세요.')
        if set(runtime['networks'])!={'my-server_default'}:raise ValueError('NETWORK_DRIFT: 현재 네트워크가 예상과 다릅니다.')
        files=[safe_path(p) for p in info['files'].split(',')]
        expected=[safe_path(value['legacy_compose']),*[safe_path(p) for p in value.get('legacy_compose_overrides',[])]]
        if files!=expected:raise ValueError('COMPOSE_DRIFT: 등록표와 실제 운영 파일이 다릅니다.')
        legacy=['docker','--context','default','compose','--project-directory',info['working_dir'],'-p',info['project']]
        for path in files:legacy+=['-f',str(path)]
        model=json.loads(run(legacy+['config','--format','json'],log,'SOURCE_CONFIG'))
        candidate=compose_model({**info,'mounts':runtime['mounts']},model)
        # Refuse ignored bind options, relative paths or current config/runtime discrepancies.
        configured={(v['source'],v['target'],not v.get('read_only',False)) for v in model['services'][info['service']].get('volumes',[]) if v['type']=='bind'}
        live={(m['Source'],m['Destination'],m['RW']) for m in runtime['mounts'] if m['Type']=='bind'}
        if configured!=live:raise ValueError('MOUNT_DRIFT: Compose와 실제 bind mount가 다릅니다.')
        destinations={m['Destination'] for m in runtime['mounts']}
        if destinations!={'/config','/database','/srv','/config/settings.json','/database/filebrowser.db'}:
            raise ValueError('MOUNT_LAYOUT: 백업 범위를 초과한 마운트입니다.')
        log.event('MIGRATION_PLAN','FileBrowser 운영 제어만 분리합니다. 기존 데이터·볼륨·네트워크 유지, 기존 컨테이너는 정지 상태로 보존합니다.')
        if not apply:return
        if entry.exists():raise ValueError('COMPOSE_EXISTS: 기존 독립 Compose를 덮어쓰지 않습니다.')
        for m in runtime['mounts']:
            if m['Type']=='bind':safe_path(m['Source'])
        backup=safe_path(base/'backups'/('control-'+datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:6]))
        backup.mkdir(mode=0o700)
        # Current known source is small; require at least 1 GB and reject an unexpectedly large /srv.
        srv=next(Path(m['Source']) for m in runtime['mounts'] if m['Destination']=='/srv')
        size=sum(p.stat().st_size for p in srv.rglob('*') if p.is_file())
        if shutil.disk_usage(backup).free < max(1_000_000_000, size*3):raise ValueError('DISK_SPACE: 백업/복원 여유 공간 부족.')
        save_json(entry,candidate)
        normalized=json.loads(run(compose+['config','--format','json'],log,'TARGET_CONFIG'))
        if set(normalized['services'])!={info['service']}:raise ValueError('TARGET_SCOPE: 독립 서비스 범위 오류.')
        old_name='file-service-before-'+uuid4().hex[:10]
        state={'state':'prepared','old_name':old_name,'old_id':runtime['id'],'source_mounts':list(mount_set(runtime)), 'backup':str(backup),'created':datetime.now(timezone.utc).isoformat()}
        save_json(journal,state)
        renamed=False; new_id=None
        try:
            run(['docker','--context','default','stop','file-service'],log,'SOURCE_STOP')
            hashes={d:copy_archive('file-service',d,backup/(d.lstrip('/')+'.tar'),log) for d in ('/config','/database','/srv')}
            save_json(backup/'verified.json',{'archives':hashes,'source_id':runtime['id']})
            for index,path in enumerate(files):shutil.copyfile(path,backup/('compose-'+str(index)));(backup/('compose-'+str(index))).chmod(0o600)
            state['state']='backup_verified';save_json(journal,state)
            run(['docker','--context','default','rename','file-service',old_name],log,'SOURCE_PRESERVE');renamed=True
            run(compose+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','90',info['service']],log,'TARGET_START',timeout=180)
            current=container(log,'file-service');new_id=current['id']
            config_keys=('Cmd','Entrypoint','Env','User','WorkingDir')
            config_same=all(current.get('config',{}).get(k)==runtime.get('config',{}).get(k) for k in config_keys)
            if not config_same or current.get('ports')!=runtime.get('ports') or current.get('restart')!=runtime.get('restart') or set(current['networks'])!=set(runtime['networks']) or current['project']!='filebrowser' or current['image']!=runtime['image'] or current['health']!='healthy' or mount_set(current)!=mount_set(runtime):
                raise ValueError('TARGET_VERIFY: 이미지/마운트/healthy 검증 실패.')
        except (ValueError,OSError,tarfile.TarError):
            state['state']='recovery_required';save_json(journal,state)
            if renamed:
                # A failing compose up may have created the new container; scope removal by project and ID.
                found=run(['docker','--context','default','ps','-aq','--filter','name=^/file-service$'],log,'RECOVERY_LOOKUP')
                if found:
                    current=container(log,'file-service')
                    if current['project']!='filebrowser':raise ValueError('RECOVERY_ID: 예상하지 않은 컨테이너. 자동 제거하지 않습니다.') from None
                    run(['docker','--context','default','stop',current['id']],log,'RECOVERY_STOP')
                    run(['docker','--context','default','rm',current['id']],log,'RECOVERY_REMOVE')
                run(['docker','--context','default','rename',old_name,'file-service'],log,'RECOVERY_RENAME')
            run(['docker','--context','default','start','file-service'],log,'RECOVERY_START')
            state['state']='rolled_back';save_json(journal,state)
            raise
        state.update(state='switched_pending_review',new_id=new_id);save_json(journal,state)
        value.update(control_state='switched_pending_review',control_backup=str(backup),preserved_container=old_name,status='control_migrated_pending_review')
        save_json(root/'projects.json',records)
        with (base/'MIGRATION.md').open('a') as stream:stream.write('\n- '+state['created']+' 운영 제어 분리'+' 완료, 웹 검토 대기. 기존 데이터 경로 유지. 복귀 컨테이너: '+old_name+' / 백업: '+str(backup)+'\n')
        history(root,'FileBrowser 운영 제어 분리: healthy·원본 마운트/이미지 유지, 기존 컨테이너 정지 보존. 데이터 이동/웹 기능 검토는 별도.',log)
        log.event('MIGRATION_HEALTHY','독립 FileBrowser healthy. 원본 마운트·이미지 유지, 웹 검토 대기.')
