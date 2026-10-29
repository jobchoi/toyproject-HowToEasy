"""Single-process preparation jobs with persistent status, no external posting."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from uuid import uuid4
import tempfile

STAGES=['자료 확인','문단·구조 정리','템플릿 적용','미리보기·파일 저장']


class Jobs:
    def __init__(self, workspace):
        self.workspace=workspace;self.root=workspace.root/'jobs';self.root.mkdir(exist_ok=True)
        self.lock=RLock();self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='prepare')
        for path in self.root.glob('*.json'):
            data=json.loads(path.read_text(encoding='utf-8'))
            if data['state'] in {'queued','running'}:
                data['state']='interrupted';data['error']='서버가 재시작되어 작업이 중단됐습니다. 저장한 원고 목록을 먼저 확인하세요.';self.write(data)

    def write(self,data):
        data['updated_at']=datetime.now(timezone.utc).isoformat()
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.root,suffix='.tmp',delete=False) as file:
            json.dump(data,file,ensure_ascii=False);path=Path(file.name)
        path.replace(self.root/(data['id']+'.json'))

    def get(self,key):
        if not isinstance(key,str) or len(key)!=32 or any(c not in '0123456789abcdef' for c in key):raise FileNotFoundError()
        with self.lock:return json.loads((self.root/(key+'.json')).read_text(encoding='utf-8'))

    def submit(self,payload):
        with self.lock:
            # Bound the in-memory queue and avoid duplicate UI retries while a job runs.
            if any(json.loads(p.read_text(encoding='utf-8'))['state'] in {'queued','running'} for p in self.root.glob('*.json')):
                raise ValueError('다른 원고를 처리 중입니다. 완료를 기다려 주세요.')
            data={'id':uuid4().hex,'state':'queued','stages':[{'name':name,'state':'pending'} for name in STAGES]}
            self.write(data)
        self.executor.submit(self.run,data['id'],payload)
        return data['id']

    def run(self,key,payload):
        def progress(name):
            with self.lock:
                data=self.get(key);data['state']='running'
                for item in data['stages']:
                    if item['state']=='running':item['state']='done'
                    if item['name']==name:item['state']='running'
                self.write(data)
        try:
            result=self.workspace.prepare(payload,progress=progress)
            with self.lock:
                data=self.get(key);data.update(state='succeeded',result_id=result['id'])
                for item in data['stages']:item['state']='done'
                self.write(data)
        except Exception as error:
            with self.lock:
                data=self.get(key);data['state']='failed';data['error']=str(error) if isinstance(error,ValueError) else '원고 처리에 실패했습니다. 자료 형식과 저장 경로를 확인하세요.'
                for item in data['stages']:
                    if item['state']=='running':item['state']='failed'
                self.write(data)

    def close(self):self.executor.shutdown(wait=True,cancel_futures=True)
