"""Read-only File Browser migration inventory; never emit settings or environment values."""
import json
import os
from pathlib import Path
import subprocess


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('INVENTORY_COMMAND_FAILED')
    return result.stdout


def overlap(left, right):
    a, b = Path(left), Path(right)
    return a == b or a in b.parents or b in a.parents


def inventory(target_name="file-service"):
    template = '{"name":{{json .Name}},"image":{{json .Image}},"state":{{json .State.Status}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},"files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},"working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},"mounts":{{json .Mounts}},"ports":{{json .HostConfig.PortBindings}},"networks":{{json .NetworkSettings.Networks}}}'
    ids = command(['docker', '--context', 'default', 'ps', '-aq']).split()
    containers = []
    for cid in ids:
        data = json.loads(command(['docker', '--context', 'default', 'inspect', '--format', template, cid]))
        data['name'] = data['name'].lstrip('/')
        # Network inspect contains more fields than required; retain names only.
        data['networks'] = sorted(data['networks'])
        data['mounts'] = [{key: m.get(key) for key in ('Type', 'Name', 'Source', 'Destination', 'RW')} for m in data['mounts']]
        containers.append(data)
    target = next((c for c in containers if c['name'] == target_name), None)
    if target is None:
        raise RuntimeError('TARGET_NOT_FOUND')
    shared = []
    for mount in target['mounts']:
        for other in containers:
            if other is target:
                continue
            for peer in other['mounts']:
                if overlap(mount['Source'], peer['Source']):
                    shared.append({'target': mount['Destination'], 'other_container': other['name'], 'other_target': peer['Destination'], 'other_state': other['state']})
    sources = [m['Source'] for m in target['mounts']]
    # Only report filenames referring to legacy paths, never their content.
    references, unreadable = [], []
    for base in (Path('/etc/systemd/system'), Path.home()/'.config/systemd/user', Path('/etc/cron.d'), Path('/etc/samba')):
        if not base.exists():
            continue
        for folder, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(folder)/d).is_symlink()]
            for name in files:
                path = Path(folder)/name
                if path.is_symlink():
                    continue
                try:
                    if path.stat().st_size > 1_000_000:
                        continue
                    text = path.read_text(errors='replace')
                    if any(source in text for source in sources):
                        references.append(str(path))
                except OSError:
                    unreadable.append(str(path))
    return {'target': target, 'shared_mounts': shared,
            'same_compose_project': [{'name':c['name'], 'service':c['service'], 'state':c['state']} for c in containers if c['project'] == target['project'] and c is not target],
            'legacy_path_reference_files': references, 'unreadable_reference_files': unreadable,
            'limitations': ['No settings, DB contents, environment or command arguments emitted.', 'Host processes, user crontabs, NFS exports and external clients require separate checks.', 'No services stopped; no data copied.']}


if __name__ == '__main__':
    try:
        import argparse
        parser=argparse.ArgumentParser(description='읽기 전용 서비스 이관 의존성 조사')
        parser.add_argument('--container',choices=('file-service','web-service','my-server-duct-tape-1'),default='file-service')
        args=parser.parse_args()
        print(json.dumps(inventory(args.container), ensure_ascii=False, indent=2))
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired):
        print(json.dumps({'error':'INVENTORY_FAILED'}))
        raise SystemExit(2)
