"""Loopback-only HTTP controllers. No platform logins or external calls."""
from io import BytesIO
from contextlib import asynccontextmanager
import json
from pathlib import Path
import secrets
from zipfile import ZipFile, ZIP_DEFLATED
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .web_service import Workspace

MAX_REQUEST = 1_600_000
DOWNLOADS = {'article.md', 'article.html', 'article.json', 'preview.html', 'browser-draft.json'}
ROOT = Path(__file__).resolve().parents[1]


def create_app(workspace=None):
    store = Workspace(workspace or ROOT / '.local/ui')
    from .jobs import Jobs
    jobs=Jobs(store)
    @asynccontextmanager
    async def lifespan(app):
        yield
        jobs.close()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None,lifespan=lifespan)
    token = secrets.token_urlsafe(32)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.middleware('http')
    async def local_requests(request, call_next):
        if request.method not in {'GET', 'HEAD'}:
            if not secrets.compare_digest(request.headers.get('x-workspace-token', ''), token):
                return Response('로컬 화면을 새로고침한 뒤 다시 시도하세요.', status_code=403)
            origin = request.headers.get('origin')
            if origin and origin != f'{request.url.scheme}://{request.headers.get("host")}':
                return Response('허용되지 않은 요청입니다.', status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; frame-src 'self' about:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    async def body(request):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > MAX_REQUEST:
                raise HTTPException(413, '자료 전체 크기가 너무 큽니다. 1MB 이하로 묶어 주세요.')
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, '요청 형식을 확인하세요.') from None
        if not isinstance(data, dict):
            raise HTTPException(400, '요청 형식을 확인하세요.')
        return data

    @app.get('/')
    def home():
        return FileResponse(ROOT / 'posting_tool/views/index.html')

    @app.get('/api/config')
    def config():
        return {'token': token}

    @app.get('/api/roadmap')
    def roadmap():
        from .progress import read_roadmap
        return read_roadmap(ROOT / 'TASKS.md')

    @app.get('/api/example')
    def example():
        return {'files': [{'name': p.name, 'content': p.read_text(encoding='utf-8')} for p in sorted((ROOT / 'examples/source-bundle').iterdir()) if p.suffix in {'.md', '.txt'}]}

    @app.post('/api/jobs',status_code=202)
    async def start_job(request: Request):
        data=await body(request)
        try:return {'id':jobs.submit(data)}
        except ValueError as exc:raise HTTPException(409,str(exc)) from None

    @app.get('/api/jobs/{key}')
    def job_status(key: str):
        try:return jobs.get(key)
        except FileNotFoundError:raise HTTPException(404,'작업을 찾을 수 없습니다.') from None

    @app.post('/api/template-choice-preview')
    async def choice_preview(request: Request):
        data=await body(request)
        try:
            from .documents import from_plain,to_markdown,from_markdown
            from .rendering import preview_document
            template=store.templates.get(data.get('template_id'))
            if isinstance(data.get('text'),str) and data['text'].strip():blocks=from_plain(data['text'])
            elif isinstance(data.get('markdown'),str) and data['markdown'].strip():
                if len(data['markdown'])>100_000:raise ValueError('원고는 100,000자 이하로 입력하세요.')
                blocks=from_markdown(data['markdown'])
            else:blocks=from_plain('여기에 작성한 자료가 배치됩니다. 선택한 디자인과 단락 구성을 확인하세요.')
            blocks,warnings=store.templates.apply(blocks,template)
            return {'html':preview_document(template['name'],to_markdown(blocks),tuple(warnings),show_notices=False,style=template.get('style','plain'),appearance=template.get('appearance',{})),'name':template['name']}
        except FileNotFoundError:raise HTTPException(404,'템플릿을 찾을 수 없습니다.') from None
        except ValueError as exc:raise HTTPException(400,str(exc)) from None

    @app.post('/api/previews')
    async def prepare(request: Request):
        data = await body(request)
        try:
            return store.prepare(data)
        except FileNotFoundError:
            raise HTTPException(404, '템플릿을 찾을 수 없습니다.') from None
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(400, str(exc)) from None

    @app.post('/api/document-blocks')
    async def document_blocks(request: Request):
        data=await body(request)
        from .documents import from_markdown, validate_blocks
        text=data.get('markdown')
        if not isinstance(text,str) or not text.strip() or len(text)>100_000:
            raise HTTPException(400,'원고는 1~100,000자로 입력하세요.')
        try:
            return {'blocks':validate_blocks(from_markdown(text))}
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from None

    @app.get('/api/previews')
    def list_previews(history: bool = False):
        return {'articles':store.list_articles(history=history)}

    @app.get('/api/template-samples')
    def template_samples():
        from .sample_templates import SAMPLES
        from .rendering import preview_document
        return {'samples':[{**t,'html':preview_document(store.sample_article(t['id']).title,store.sample_article(t['id']).markdown,(),show_notices=False,style=t['style'])} for t in SAMPLES]}

    @app.post('/api/template-samples/{key}')
    def open_sample(key: str):
        try:
            return store.save(store.sample_article(key))
        except FileNotFoundError:
            raise HTTPException(404,'샘플을 찾을 수 없습니다.') from None

    @app.get('/api/templates')
    def list_templates():
        return {'templates':store.templates.list()}

    @app.get('/api/templates/{key}')
    def get_template(key: str):
        try:
            return store.templates.get(key)
        except FileNotFoundError:
            raise HTTPException(404,'템플릿을 찾을 수 없습니다.') from None

    @app.post('/api/template-preview')
    async def preview_template(request: Request):
        data=await body(request)
        try:
            from .documents import from_plain, to_markdown
            from .rendering import preview_document
            spec=data.get('template')
            if not isinstance(spec,dict): raise ValueError('템플릿 내용을 확인하세요.')
            store.templates.validate(spec)
            blocks=from_plain(data.get('text') or '이곳에 원고의 자료가 배치됩니다.')
            blocks,warnings=store.templates.apply(blocks,{**spec,'builtin':False})
            return {'html':preview_document('템플릿 미리보기',to_markdown(blocks),tuple(warnings),style=spec.get('style','plain'),appearance=spec.get('appearance',{}))}
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from None

    @app.post('/api/templates')
    async def save_template(request: Request):
        data=await body(request)
        try:
            return store.templates.save(data)
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from None

    @app.post('/api/templates/{key}')
    async def update_template(key: str, request: Request):
        data=await body(request)
        try:
            return store.templates.save(data,parent=key,clone=bool(data.get('clone')))
        except FileNotFoundError:
            raise HTTPException(404,'템플릿을 찾을 수 없습니다.') from None
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from None

    @app.post('/api/previews/{key}/template')
    async def apply_template(key: str, request: Request):
        data=await body(request)
        try:
            template_id=data.get('template_id')
            if not isinstance(template_id,str): raise ValueError('템플릿을 선택하세요.')
            return store.apply_template(key,template_id)
        except FileNotFoundError:
            raise HTTPException(404,'원고 또는 템플릿을 찾을 수 없습니다.') from None
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from None

    @app.get('/api/previews/{key}')
    def get_preview(key: str):
        try:
            return store.response(key, store.load(key))
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, '원고를 찾을 수 없습니다.') from None

    @app.post('/api/previews/{key}')
    async def edit(key: str, request: Request):
        data = await body(request)
        try:
            return store.edit(key, data)
        except FileNotFoundError:
            raise HTTPException(404, '원고를 찾을 수 없습니다.') from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get('/api/previews/{key}/download/{name}')
    def download(key: str, name: str):
        try:
            store.load(key)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, '원고를 찾을 수 없습니다.') from None
        if name == 'bundle.zip':
            buffer = BytesIO()
            with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
                for filename in sorted(DOWNLOADS):
                    archive.write(store.root / key / filename, filename)
            return Response(buffer.getvalue(), media_type='application/zip', headers={'Content-Disposition': 'attachment; filename="posting-bundle.zip"'})
        if name not in DOWNLOADS:
            raise HTTPException(404, '지원하지 않는 내보내기 형식입니다.')
        return FileResponse(store.root / key / name, filename=name)

    app.mount('/assets', StaticFiles(directory=ROOT / 'posting_tool/views'), name='assets')
    return app
