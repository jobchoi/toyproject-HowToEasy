"""Immutable, data-only content templates; never execute user code."""
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
import tempfile
from .sample_templates import SAMPLES
from .styles import STYLES, normalize_appearance

DEFAULT = {'id':'information-v1','family':'information-v1','version':1,'name':'정보형 · 기본 템플릿', 'intro':'','sections':[], 'outro':'', 'builtin':True}


class TemplateStore:
    def __init__(self, root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)

    def get(self,key):
        if not isinstance(key,str): raise FileNotFoundError('템플릿이 없습니다.')
        if key=='information-v1': return dict(DEFAULT)
        for sample in SAMPLES:
            if sample['id']==key: return {**sample,'sections':list(sample['sections'])}
        if len(key)!=32 or any(c not in '0123456789abcdef' for c in key): raise FileNotFoundError('템플릿이 없습니다.')
        return json.loads((self.root/(key+'.json')).read_text(encoding='utf-8'))

    def list(self):
        latest={}
        for path in self.root.glob('*.json'):
            data=json.loads(path.read_text(encoding='utf-8'))
            if data['family'] not in latest or data['created_at']>latest[data['family']]['created_at']: latest[data['family']]=data
        return [dict(DEFAULT),*[{**sample,'sections':list(sample['sections'])} for sample in SAMPLES],*sorted(latest.values(),key=lambda d:d['created_at'],reverse=True)]

    @staticmethod
    def validate(data):
        name,intro,outro,sections=(data.get(k) for k in ('name','intro','outro','sections'))
        if not isinstance(name,str) or not name.strip() or len(name)>80: raise ValueError('템플릿 이름은 1~80자여야 합니다.')
        if not all(isinstance(s,str) and len(s)<=3000 for s in (intro,outro)): raise ValueError('도입/마무리는 각각 3,000자 이하로 입력하세요.')
        if not isinstance(sections,list) or len(sections)>12 or any(not isinstance(s,str) or not s.strip() or len(s)>100 or '\n' in s or '\r' in s for s in sections): raise ValueError('소제목은 줄마다 하나씩 최대 12개, 각각 100자 이하로 입력하세요.')
        if 'style' in data and (not isinstance(data['style'],str) or data['style'] not in STYLES): raise ValueError('지원하지 않는 디자인 스타일입니다.')
        normalize_appearance(data.get("appearance"))
        return name,intro,outro,sections

    def save(self,data,parent=None,clone=False):
        name,intro,outro,sections=self.validate(data)
        previous=self.get(parent) if parent else None
        style=data.get('style',previous.get('style','plain') if previous else 'plain')
        if not isinstance(style,str) or style not in STYLES: raise ValueError('지원하지 않는 디자인 스타일입니다.')
        key=uuid4().hex
        value={'id':key,'family':previous['family'] if previous and not clone and not previous.get('builtin') else key,
               'version':previous['version']+1 if previous and not clone and not previous.get('builtin') else 1,
               'name':name.strip(),'style':style,'appearance':normalize_appearance(data.get('appearance',previous.get('appearance',{}) if previous else {})),'intro':intro.strip(),'sections':[s.strip() for s in sections],'outro':outro.strip(),'builtin':False,
               'created_at':datetime.now(timezone.utc).isoformat(),'parent':parent}
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.root,suffix='.tmp',delete=False) as file:
                temporary=Path(file.name)
                json.dump(value,file,ensure_ascii=False,indent=2)
            temporary.replace(self.root/(key+'.json'))
        finally:
            if temporary is not None: temporary.unlink(missing_ok=True)

        return value

    def apply(self,blocks,template):
        if template.get('id')=='information-v1' or (template.get('builtin') and not template.get('sections')): return blocks,[]
        title=[b for b in blocks if b['type']=='title']
        body=[b for b in blocks if b['type']!='title']
        output=list(title); warnings=[]
        if template['intro']: output.append({'type':'paragraph','text':template['intro']})
        if template['sections']:
            output.append({'type':'heading','text':template['sections'][0]})
        output.extend(body)
        for section in template['sections'][1:]:
            output.append({'type':'heading','text':section})
            warnings.append(f'템플릿의 「{section}」 단락은 생성 당시 비어 있었습니다. 문서 편집에서 확인하세요.')
        if template['outro']: output.append({'type':'paragraph','text':template['outro']})
        return output,warnings
