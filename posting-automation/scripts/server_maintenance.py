"""Post-migration backups, manager handoff, and redacted legacy diagnostics."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
from uuid import uuid4
from posting_deploy import run, manifest, backup_and_verify, save_json, ensure_stopped, history


def status_rows(output):
    try:
        rows = json.loads(output) if output.startswith('[') else [json.loads(line) for line in output.splitlines() if line]
        if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows): raise ValueError()
        return rows
    except ValueError: raise ValueError('COMPOSE_FORMAT: 컨테이너 상태 형식을 확인하세요.') from None


def backup_locked(root, base, command, records, log):
    from manage_server import safe_path
    data = safe_path(base/'data'/'ui'); backups = safe_path(base/'backups')
    if not backups.is_dir(): raise ValueError('BACKUP_PATH: 등록된 백업 폴더가 없습니다.')
    rows = status_rows(run(command+['ps','--all','--format','json','web'],log,'BACKUP_STATUS'))
    was_running = any(row.get('State')=='running' for row in rows)
    value = records['projects']['posting-automation']
    original_state = value['status']
    # Capture code identity before interrupting a live service.
    commit = run(['git','-C',str(base/'repo'),'rev-parse','HEAD'],log,'BACKUP_CODE')
    archive = backups/('posting-'+datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:6]+'.tar.gz')
    try:
        if was_running: run(command+['stop','web'],log,'BACKUP_STOP')
        ensure_stopped()
        before = manifest(data)
        size = sum((data/name).stat().st_size for name in before)
        if shutil.disk_usage(backups).free < size*3+10_000_000: raise ValueError('DISK_SPACE: 백업·복원 시험 공간이 부족합니다.')
        backup_and_verify(data,archive,before,log)
        if manifest(data)!=before: raise ValueError('DATA_CHANGED: 백업 중 자료가 변경됐습니다.')
        save_json(archive.with_suffix(archive.suffix+'.json'),{'verified_at':datetime.now(timezone.utc).isoformat(),
                  'repository_commit':commit,'file_count':len(before),'archive':str(archive),'scope':'saved_ui_only'})
        value['last_backup']=str(archive)
        save_json(root/'projects.json',records)
        history(root,'현재 포스팅 자료 백업 및 실제 복원 해시 검증: '+str(archive),log)
    except (ValueError,OSError):
        log.event('BACKUP_FAILED','백업 완료로 기록하지 않았습니다. 원본 자료는 유지됩니다.')
        raise
    finally:
        if was_running:
            try:
                run(command+['up','-d','--no-build','--wait','--wait-timeout','90','web'],log,'BACKUP_RESUME',timeout=180)
                value['status']=original_state; save_json(root/'projects.json',records)
                log.event('RESUMED','백업 전 실행 중이던 포스팅 앱을 재개했습니다.')
            except ValueError:
                value['status']='recovery_required'; save_json(root/'projects.json',records)
                log.event('RESUME_FAILED','포스팅 재개 실패. posting status와 대상 컨테이너 로그를 확인하세요. 다른 서비스는 변경하지 않았습니다.')
                raise
    log.event('BACKUP_COMPLETE','현재 원고·사진·템플릿 백업 완료. 서버 밖으로도 사본을 보관하세요.',archive=str(archive))


def use_managed(root, apply, log):
    from manage_server import safe_path, registry, lock
    repo = safe_path(root/'posting-automation'/'repo')
    manager = safe_path(repo/'posting-automation'/'scripts'/'manage_server.py')
    launcher = safe_path(root/'manage.sh')
    safe_path(root/'WORK_HISTORY.md')
    log.event('HANDOFF_PLAN','관리 실행기를 이관된 repo의 스크립트로 연결합니다.',script=str(manager))
    if not apply:
        log.event('DRY_RUN','계획만 표시했습니다. --apply가 있어야 관리 실행기 경로를 변경합니다.'); return
    with lock(root):
        records = registry(root)
        if records['projects']['posting-automation']['status'] != 'migrated':
            raise ValueError('HANDOFF_STATE: 먼저 포스팅 이관 검토/confirm을 완료하세요.')
        if not manager.is_file() or not (manager.parent/'posting_deploy.py').is_file() or not (manager.parent/'server_maintenance.py').is_file():
            raise ValueError('MANAGER_MISSING: 이관된 repo에 최신 관리 코드가 없습니다. 먼저 해당 repo를 갱신하세요.')
        if run(['git','-c','core.fsmonitor=false','-C',str(repo),'status','--porcelain'],log,'HANDOFF_GIT'):
            raise ValueError('TARGET_DIRTY: 이관된 repo에 미커밋 변경이 있습니다.')
        if not launcher.is_file(): raise ValueError('MANAGER_MISSING: 기존 manage.sh를 찾지 못했습니다.')
        backup = root/('manage.sh.before-'+uuid4().hex[:8])
        with backup.open('x',encoding='utf-8') as stream: stream.write(launcher.read_text())
        backup.chmod(0o700)
        text = ('#!/usr/bin/env bash\nset -euo pipefail\n'
                'management_root="$(cd -- "$(dirname -- "$0")" && pwd -P)"\n'
                'exec python3 '+shlex.quote(str(manager))+' --root "$management_root" --log-dir "$management_root/logs" "$@"\n')
        temporary = root/('.manager-'+uuid4().hex+'.tmp')
        try:
            with temporary.open('x',encoding='utf-8') as stream: stream.write(text)
            temporary.chmod(0o700); temporary.replace(launcher)
        finally: temporary.unlink(missing_ok=True)
        records['manager_script']=str(manager); save_json(root/'projects.json',records)
        history(root,'관리 실행기를 이관된 repo로 변경. 이전 실행기 보관: '+str(backup),log)
        log.event('HANDOFF_COMPLETE','이제 관리 코드는 web-server 아래 repo를 사용합니다. 기존 원본 폴더는 아직 보관하세요.')


def diagnose_filebrowser(log):
    # Docker returns only selected fields; Env, full inspect, raw health output are never requested.
    template = '{"image":{{json .Config.Image}},"test":{{with .Config.Healthcheck}}{{json .Test}}{{else}}[]{{end}},{{with .State.Health}}"health":{{json .Status}},"streak":{{json .FailingStreak}},"checks":[{{range $i,$v := .Log}}{{if $i}},{{end}}{"start":{{json $v.Start}},"end":{{json $v.End}},"exit_code":{{$v.ExitCode}}}{{end}}]{{else}}"health":null,"streak":0,"checks":[]{{end}}}'
    output = run(['docker','--context','default','inspect','--format',template,'file-service'],log,'FILEBROWSER_INSPECT')
    try: data = json.loads(output)
    except ValueError: raise ValueError('DIAGNOSE_FORMAT: 컨테이너 진단 형식을 확인하세요.') from None
    test = data.get('test') or []
    kind = test[0] if test and test[0] in {'CMD','CMD-SHELL','NONE'} else 'unknown'
    program = 'unknown'
    try:
        parts = shlex.split(test[1]) if kind=='CMD-SHELL' and len(test)>1 else test[1:]
        if parts and re.fullmatch(r'[A-Za-z0-9_./-]+',parts[0]): program=Path(parts[0]).name
    except ValueError: pass
    summary = {'container':'file-service','image':data.get('image'),'health':data.get('health'),
               'failing_streak':data.get('streak'),'check_kind':kind,'check_program':program,
               'recent_checks':data.get('checks',[])}
    log.event('FILEBROWSER_HEALTH','파일브라우저 상태: '+str(summary['health'])+' / 검사 실행 파일: '+program,**summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    log.event('READ_ONLY','검사 결과만 조회했습니다. 컨테이너 실행/설정/자료를 변경하지 않았습니다.')
