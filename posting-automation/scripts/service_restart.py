"""Restart exactly one already-managed service; never rebuild or create containers."""
import json
import time
from posting_deploy import run, save_json, history
from server_maintenance import status_rows

SERVICES={'posting-automation':'web','filebrowser':'fileserver'}


def restart(root, project, apply, log):
    from manage_server import safe_path, registry, lock
    if project not in SERVICES:raise ValueError('RESTART_PROJECT: 관리 전환된 posting-automation/filebrowser만 지원합니다.')
    with lock(root):
        records=registry(root);value=records['projects'].get(project)
        if not value or value.get('status') in {'registered_not_migrated','prepared_not_started','recovery_required'}:
            raise ValueError('RESTART_STATE: 관리 전환/복구 상태를 먼저 확인하세요.')
        base=safe_path(root/project);entry=safe_path(base/value.get('compose_file','compose.yaml'))
        if not entry.is_file():raise ValueError('RESTART_COMPOSE: 운영 Compose가 없습니다.')
        service=SERVICES[project]
        command=['docker','--context','default','compose']
        if project=='posting-automation':
            env=safe_path(base/'.env')
            if not env.is_file():raise ValueError('RESTART_ENV: 운영 설정 파일이 없습니다.')
            command+=['--env-file',str(env)]
        command+=['-p',project,'-f',str(entry)]
        def rows():return status_rows(run(command+['ps','--all','--format','json',service],log,'RESTART_STATUS'))
        before=rows()
        if len(before)!=1 or not before[0].get('ID'):raise ValueError('RESTART_CONTAINER: 기존 단일 컨테이너가 없습니다. start/이관 절차를 확인하세요.')
        identifier=before[0]['ID']
        template='{"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}}}'
        info=json.loads(run(['docker','--context','default','inspect','--format',template,identifier],log,'RESTART_OWNER'))
        if info!={'project':project,'service':service,'files':str(entry)}:raise ValueError('RESTART_OWNER: 현재 컨테이너의 소유/운영 경로가 다릅니다.')
        log.event('RESTART_PLAN',project+'의 기존 '+service+'만 재시작합니다. 빌드·재생성·자료 이동은 하지 않습니다.')
        if not apply:
            log.event('DRY_RUN','실제 재시작하려면 --apply를 추가하세요.');return
        try:
            run(command+['restart','--no-deps','--timeout','30',service],log,'SERVICE_RESTART',timeout=60)
            deadline=time.monotonic()+90
            while True:
                after=rows()
                if len(after)!=1 or after[0].get('ID')!=identifier:raise ValueError('RESTART_ID_CHANGED: 컨테이너가 외부에서 변경됐습니다.')
                if after[0].get('State')=='running' and after[0].get('Health')=='healthy':break
                if after[0].get('Health')=='unhealthy' or time.monotonic()>=deadline:raise ValueError('RESTART_NOT_HEALTHY: 상태 점검 실패/시간 초과. 자동 반복하지 않습니다.')
                time.sleep(2)
        except (ValueError,OSError):
            value['restart_state']='check_required';save_json(root/'projects.json',records)
            log.event('RESTART_FAILED','해당 서비스 상태를 확인하세요. 다른 서비스는 재시작하지 않았습니다.');raise
        value['restart_state']='healthy';save_json(root/'projects.json',records)
        history(root,project+' 대상 재시작 후 동일 컨테이너 healthy 확인.',log)
        log.event('RESTART_HEALTHY',project+' 재시작 완료, 기존 컨테이너 ID 유지·healthy 확인.')
