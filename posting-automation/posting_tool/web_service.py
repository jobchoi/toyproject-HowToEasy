"""Local preparation use cases shared by HTTP controllers and UI."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from threading import RLock
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from .models import Article, Source
from .documents import from_plain, from_markdown, to_markdown
from .templates import TemplateStore
from .service import prepare_article
from .exporting import export_article
from .providers import ManualExportPublisher
from .rendering import preview_document


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.templates = TemplateStore(self.root / 'templates')
        self.lock = RLock()

    def save(self, article: Article):
        key = uuid4().hex
        article = replace(article, article_id=article.article_id or key, saved_at=datetime.now(timezone.utc).isoformat())
        export_article(article, self.root / key, ManualExportPublisher())
        return self.response(key, article)

    def response(self, key, article):
        return {'id': key, 'title': article.title, 'markdown': article.markdown,
                'warnings': list(article.warnings), 'source_count': len(article.sources),
                'blocks':from_markdown(article.markdown), 'style':article.style,'appearance':article.appearance, 'template_id':article.template_version,
                'article_id':article.article_id or key,'parent_id':article.parent_id,'saved_at':article.saved_at,
                'html': preview_document(article.title, article.markdown, article.warnings, show_notices=False,style=article.style,appearance=article.appearance)}

    def load(self, key):
        if len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
            raise FileNotFoundError('원고를 찾을 수 없습니다.')
        data = json.loads((self.root / key / 'article.json').read_text(encoding='utf-8'))
        return Article(data['title'], data['markdown'], tuple(Source(**s) for s in data['sources']), tuple(data['warnings']), data['template_version'],data.get('article_id',key),data.get('parent_id',''),data.get('saved_at',''),data.get('style','plain'),data.get('appearance',{}))

    def prepare(self, data, progress=lambda stage: None):
        progress("자료 확인")
        template=self.templates.get(data.get('template_id') or 'information-v1')
        if 'text' in data:
            progress('문단·구조 정리')
            blocks=from_plain(data['text'])
            title=data.get('title') or '붙여넣은 원고'
            if not isinstance(title,str) or not title.strip() or len(title)>200 or '\n' in title or '\r' in title: raise ValueError('제목은 줄바꿈 없이 1~200자로 입력하세요.')
            source=Source('붙여넣은 자료.txt',hashlib.sha256(data['text'].encode()).hexdigest(),data['text'])
            blocks=[{'type':'title','text':title},*blocks]
            progress('템플릿 적용')
            blocks,warnings=self.templates.apply(blocks,template)
            article=Article(title,to_markdown(blocks),(source,),tuple(['규칙으로 문단과 번호를 정리했습니다. 소제목 분류·출처를 직접 확인하세요.','AI 집필이나 사실 검증을 수행하지 않았습니다.',*warnings]),template['id'],style=template.get('style','plain'),appearance=template.get('appearance',{}))
            progress('미리보기·파일 저장')
            return self.save(article)
        files = data.get('files')
        title = data.get('title') or None
        if title is not None and not isinstance(title, str):
            raise ValueError('제목은 문자열이어야 합니다.')
        if not isinstance(files, list) or not 1 <= len(files) <= 20:
            raise ValueError('Markdown/TXT 파일을 1~20개 선택하세요.')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / 'upload'
            folder.mkdir()
            names = set()
            for file in files:
                if not isinstance(file, dict):
                    raise ValueError('파일 형식을 확인하세요.')
                name, content = file.get('name'), file.get('content')
                if not isinstance(name, str) or not name or '/' in name or '\\' in name or '\x00' in name or len(name) > 150:
                    raise ValueError('파일 이름에 경로를 포함할 수 없습니다.')
                if Path(name).suffix.lower() not in {'.md', '.txt'} or name.casefold() in names:
                    raise ValueError('파일 확장자 또는 중복 이름을 확인하세요.')
                if not isinstance(content, str):
                    raise ValueError('UTF-8 텍스트가 필요합니다.')
                names.add(name.casefold())
                (folder / name).write_text(content, encoding='utf-8')
            progress('문단·구조 정리')
            article = prepare_article(root, 'upload', title)
            # Export source paths as display names, never temporary server paths.
            article = replace(article, sources=tuple(replace(s, name=Path(s.name).name) for s in article.sources))
        progress('템플릿 적용')
        if template['id']!='information-v1':
            blocks,warnings=self.templates.apply(from_markdown(article.markdown),template)
            article=replace(article,markdown=to_markdown(blocks),warnings=(*article.warnings,*warnings),template_version=template['id'],style=template.get('style','plain'),appearance=template.get('appearance',{}))
        progress('미리보기·파일 저장')
        return self.save(article)

    def edit(self, key, data):
        article = self.load(key)
        title = data.get('title')
        markdown = to_markdown(data['blocks']) if 'blocks' in data else data.get('markdown')
        if not isinstance(title, str) or not title.strip() or len(title) > 200 or '\n' in title or '\r' in title:
            raise ValueError('제목은 줄바꿈 없이 1~200자로 입력하세요.')
        if not isinstance(markdown, str) or not markdown.strip() or len(markdown) > 100_000:
            raise ValueError('원고는 1~100,000자로 입력하세요.')
        warnings = tuple(dict.fromkeys((*article.warnings, '편집한 내용과 원본 자료의 일치 여부를 다시 검토하세요.')))
        with self.lock:
            latest=[entry for entry in self.list_articles() if entry['article_id']==(article.article_id or key)]
            if latest and latest[0]['id']!=key:
                raise ValueError('다른 버전이 이미 저장됐습니다. 원고 목록에서 최신 원고를 열어 주세요. 현재 내용은 복사해 보관하세요.')
            return self.save(replace(article, title=title.strip(), markdown=markdown, warnings=warnings,parent_id=key))


    def list_articles(self, history=False):
        records=[]
        for path in self.root.iterdir():
            if not path.is_dir() or len(path.name)!=32 or any(c not in '0123456789abcdef' for c in path.name): continue
            try:
                article=self.load(path.name)
            except (OSError,ValueError,KeyError): continue
            records.append({'id':path.name,'article_id':article.article_id or path.name,'title':article.title,'saved_at':article.saved_at or datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),'parent_id':article.parent_id,'template_id':article.template_version})
        records.sort(key=lambda r:r['saved_at'],reverse=True)
        if history: return records
        latest={}
        for record in records:
            latest.setdefault(record['article_id'],record)
        return list(latest.values())

    def apply_template(self,key,template_id):
        article=self.load(key)
        template=self.templates.get(template_id)
        blocks,warnings=self.templates.apply(from_markdown(article.markdown),template)
        # Applying a template creates an independent copy, preserving the original.
        return self.save(replace(article,markdown=to_markdown(blocks),template_version=template['id'],style=template.get('style','plain'),appearance=template.get('appearance',{}),warnings=tuple(dict.fromkeys((*article.warnings,*warnings))),article_id='',parent_id=''))


    def sample_article(self, template_id):
        from .sample_templates import SAMPLES,sample_blocks
        if not any(t['id']==template_id for t in SAMPLES): raise FileNotFoundError('샘플 템플릿이 없습니다.')
        template=self.templates.get(template_id)
        return Article('작은 도서관에서 시작하는 독서 모임',to_markdown(sample_blocks(template)),(),('가상 예제 자료입니다. 실제 기관·일정·성과에 대한 정보가 아닙니다.',),template_id,style=template['style'])
