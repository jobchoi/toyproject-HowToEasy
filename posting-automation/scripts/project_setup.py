"""Reusable venv bootstrap driven by a project-owned JSON configuration."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import venv


def requirement_inputs(root,path,seen=None):
    seen=set() if seen is None else seen
    path=path.resolve()
    if not path.is_relative_to(root.resolve()) or path in seen:raise ValueError('의존성 경로나 순환 참조를 확인하세요.')
    seen.add(path);data=path.read_text(encoding='utf-8');result=[data]
    for line in data.splitlines():
        if line.startswith('-r '):result.extend(requirement_inputs(root,path.parent/line[3:].strip(),seen))
    return result


def main():
    parser=argparse.ArgumentParser(description='독립 개발/테스트 환경 자동 구성')
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--profile',choices=('ui','dev','test'),default='ui')
    parser.add_argument('--test',action='store_true')
    args=parser.parse_args()
    if args.test and args.profile=='ui':args.profile='test'
    root=args.project.resolve()
    config=json.loads((root/'project-environment.json').read_text(encoding='utf-8'))
    if sys.version_info[:2]<tuple(config['python_minimum']):raise SystemExit('Python 3.11 이상이 필요합니다.')
    target=root/config['environment']
    if target.is_symlink() or target.resolve()==root or not target.resolve().is_relative_to(root):raise SystemExit('가상환경은 프로젝트 내부의 독립 경로를 사용해야 합니다.')
    requirements=root/config['profiles'][args.profile]
    signature=hashlib.sha256(json.dumps([args.profile,sys.version,platform.machine(),*requirement_inputs(root,requirements)]).encode()).hexdigest()
    python=target/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    if not python.exists():
        print('1/3 독립 Python 환경 생성',flush=True);venv.EnvBuilder(with_pip=True).create(target)
    stamp=target/'.project-inputs.json'
    previous=json.loads(stamp.read_text()) if stamp.exists() else {}
    if previous.get('signature')!=signature:
        print('2/3 의존성 설치·갱신',flush=True)
        subprocess.run([str(python),'-m','pip','install','-r',str(requirements)],cwd=root,check=True)
        subprocess.run([str(python),'-m','pip','check'],cwd=root,check=True)
        stamp.write_text(json.dumps({'signature':signature,'profile':args.profile}),encoding='utf-8')
    else:print('2/3 의존성 입력이 동일하여 설치 생략',flush=True)
    if args.test or args.profile=='test':
        print('3/3 테스트 실행 (외부 계정/브라우저 실연결 없음)',flush=True)
        subprocess.run([str(python),*config['test_command']],cwd=root,check=True)
    else:print('3/3 준비 완료. 실행: bash scripts/run_ui.sh',flush=True)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print('환경 구성 실패:',error,file=sys.stderr);raise SystemExit(1)
