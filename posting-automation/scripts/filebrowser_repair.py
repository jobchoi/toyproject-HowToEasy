"""Scoped repair for the already-tested File Browser health endpoint."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4
from posting_deploy import run, save_json, history

TEST = ['CMD','wget','-q','--spider','http://127.0.0.1:80/health']


def inspect(log):
    template = '{"image":{{json .Image}},"health":{{with .State.Health}}{{json .Status}}{{else}}null{{end}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},"mounts":{{json .Mounts}}}'
    try: return json.loads(run(['docker','--context','default','inspect','--format',template,'file-service'],log,'REPAIR_INSPECT'))
    except ValueError: raise ValueError('REPAIR_INSPECT: 필요한 컨테이너 메타데이터를 읽을 수 없습니다.') from None


def mount_set(data):
    return {(m['Type'],m['Source'],m['Destination'],m['RW']) for m in data['mounts']}


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): digest.update(chunk)
    return digest.digest()


def repair(root, apply, log):
    from manage_server import safe_path, registry, lock
    with lock(root):
        records = registry(root); value = records['projects'].get('filebrowser')
        if not value: raise ValueError('File Browser 등록이 없습니다. init부터 확인하세요.')
        info = inspect(log)
        if info.get('project')!=value.get('legacy_compose_project'):
            raise ValueError('PROJECT_MISMATCH: 조사한 기존 Compose 프로젝트와 다릅니다.')
        service = info.get('service','')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',service): raise ValueError('SERVICE_MISSING: Compose 서비스 이름이 없습니다.')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',info.get('image','')): raise ValueError('IMAGE_MISSING: 현재 이미지 식별자를 확인하세요.')
        original = safe_path(value['legacy_compose']); working = safe_path(info['working_dir'])
        base = safe_path(root/'filebrowser'); override = safe_path(base/'health.override.json')
        safe_path(root/'WORK_HISTORY.md'); safe_path(base/'MIGRATION.md')
        files = [safe_path(Path(name)) for name in info.get('files','').split(',') if name]
        if not original.is_file() or original not in files or any(path not in (original,override) for path in files):
            raise ValueError('COMPOSE_MISMATCH: 예상하지 않은 Compose 파일 구성이므로 자동 적용하지 않습니다.')
        log.event('REPAIR_PLAN','File Browser의 건강 검사만 고정 주소로 변경합니다. 적용 시 해당 컨테이너가 잠시 재생성됩니다.',service=service,project=info['project'],override=str(override))
        if not apply:
            log.event('DRY_RUN','기존 설정/컨테이너를 변경하지 않았습니다. 적용하려면 --apply를 추가하세요.'); return
        # Revalidate the known-good target before any stop/recreate operation.
        run(['docker','--context','default','exec','file-service',*TEST[1:]],log,'HEALTH_PROBE')
        sources = []
        for destination in ('/config/settings.json','/database/filebrowser.db'):
            matches=[m for m in info['mounts'] if m.get('Type')=='bind' and m.get('Destination')==destination]
            if len(matches)!=1: raise ValueError('BACKUP_LAYOUT: 예상한 설정/DB bind mount와 다릅니다.')
            source=safe_path(matches[0]['Source'])
            if not source.is_file() or not os.access(source,os.R_OK): raise ValueError('BACKUP_ACCESS: 설정/DB 파일을 읽을 수 없습니다. 권한을 임의 변경하지 마세요.')
            sources.append(source)
        text=json.dumps({'services':{service:{'image':info['image'],'healthcheck':{
            'test':TEST,'interval':'15s','timeout':'5s','retries':3,'start_period':'10s'}}}},indent=2)+'\n'
        if override.exists() and override.read_text()!=text:
            raise ValueError('OVERRIDE_CONFLICT: 기존 health.override.json과 다릅니다. 덮어쓰지 않습니다.')
        if override.exists() and override in files and info.get('health')=='healthy':
            log.event('ALREADY_HEALTHY','동일한 검사 설정으로 정상 실행 중입니다. 재생성하지 않습니다.'); return
        if not override.exists():
            with override.open('x',encoding='utf-8') as stream: stream.write(text)
            override.chmod(0o600)
        command=['docker','--context','default','compose','--project-directory',str(working),'-p',info['project'],'-f',str(original)]
        combined=command+['-f',str(override)]
        # Evaluate privately; never log the merged config, which may contain secret values.
        before=json.loads(run(command+['config','--format','json'],log,'BASE_CONFIG'))
        after=json.loads(run(combined+['config','--format','json'],log,'OVERRIDE_CONFIG'))
        for model in (before,after):
            if service not in model.get('services',{}): raise ValueError('SERVICE_MISSING: Compose 정의에 대상 서비스가 없습니다.')
            model['services'][service].pop('image',None)
            model['services'][service].pop('healthcheck',None)
        if before!=after: raise ValueError('UNEXPECTED_CONFIG: 이미지 고정·healthcheck 외의 설정 변경이 감지됐습니다.')
        configured_binds={(v['source'],v['target'],not v.get('read_only',False)) for v in after['services'][service].get('volumes',[]) if v.get('type')=='bind'}
        runtime_binds={(m['Source'],m['Destination'],m['RW']) for m in info['mounts'] if m['Type']=='bind'}
        if configured_binds!=runtime_binds: raise ValueError('MOUNT_DRIFT: 현재 Compose와 실제 마운트가 다릅니다. 먼저 경로를 확인하세요.')
        backups=safe_path(base/'backups'); backups.mkdir(exist_ok=True)
        backup=backups/('health-fix-'+datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:6]); backup.mkdir(mode=0o700)
        if shutil.disk_usage(backups).free < sum(source.stat().st_size for source in [*sources,original])+10_000_000:
            raise ValueError('DISK_SPACE: 설정/DB 백업 공간이 부족합니다.')
        try:
            run(['docker','--context','default','stop','file-service'],log,'FILEBROWSER_STOP')
            for source in [*sources,original]:
                target=backup/source.name
                shutil.copyfile(source,target); target.chmod(0o600)
                if file_hash(source)!=file_hash(target):
                    raise ValueError('BACKUP_VERIFY: 백업 파일 해시가 다릅니다.')
            log.event('FILEBROWSER_BACKUP','중지 상태에서 설정/DB/Compose 백업·해시 검증 완료.',backup=str(backup))
            value.update(health_override=str(override),health_repair_state='pending',health_backup=str(backup),legacy_compose_overrides=[str(override)])
            save_json(root/'projects.json',records)
            run(combined+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','90',service],log,'FILEBROWSER_RECREATE',timeout=180)
            if mount_set(inspect(log))!=mount_set(info): raise ValueError('MOUNT_CHANGED: 재생성 후 마운트가 달라졌습니다. 보존된 원본/볼륨을 먼저 확인하세요.')
        except (ValueError,OSError):
            value['health_repair_state']='recovery_required'; save_json(root/'projects.json',records)
            log.event('REPAIR_FAILED','수정 미완료. 원본/백업/볼륨을 유지합니다. 해당 컨테이너 시작만 재시도합니다.')
            run(['docker','--context','default','start','file-service'],log,'FILEBROWSER_RESUME')
            raise
        value['health_repair_state']='healthy'; save_json(root/'projects.json',records)
        with (base/'MIGRATION.md').open('a',encoding='utf-8') as stream:
            stream.write('\n- '+datetime.now(timezone.utc).isoformat()+' 기존 위치에서 healthcheck 고정 주소 적용, 현재 이미지 고정·마운트 동일 확인. 이관 완료가 아님. 운영 시 원본 Compose와 '+str(override)+'를 함께 사용. 백업: '+str(backup)+'\n')
        history(root,'File Browser 건강 검사 수정. 이미지/마운트 유지, override: '+str(override),log)
        log.event('FILEBROWSER_HEALTHY','File Browser 상태 검사 통과. 기존 사용자 설정/DB/저장 자료는 유지했습니다.')
