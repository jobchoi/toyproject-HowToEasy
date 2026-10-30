import json
from pathlib import Path
import shutil
import tempfile
from .models import Article
from .rendering import render_html, preview_document
from .providers import Capability, Publisher, UnsupportedOperation


def export_article(article: Article, output: Path, publisher: Publisher, *, media_root=None) -> Path:
    if Capability.EXPORT not in publisher.capabilities:
        raise UnsupportedOperation('이 게시 모듈은 내보내기를 지원하지 않습니다.')
    from .media import references, embedded
    names = references(article.markdown)
    if names and media_root is None: raise ValueError('사진 저장소를 지정하세요.')
    images = embedded(media_root, article.markdown) if names else {}
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('출력 폴더가 이미 있습니다. 기존 파일을 보존하려면 새 경로를 지정하세요.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.posting-', dir=output.parent))
    try:
        files = {
            'article.md': article.markdown,
            'article.html': preview_document(article.title, article.markdown, (), show_notices=False, style=article.style,appearance=article.appearance,images=images),
            'preview.html': preview_document(article.title, article.markdown, article.warnings, style=article.style,appearance=article.appearance,images=images),
            'article.json': json.dumps({'schema_version': 1, 'delivery': 'export_only', 'provider': publisher.name, **article.to_dict()}, ensure_ascii=False, indent=2),
            'browser-draft.json': json.dumps({'title': article.title, 'body': article.markdown}, ensure_ascii=False, indent=2),
        }
        for name, text in files.items():
            (temporary / name).write_text(text, encoding='utf-8')
        if names:
            (temporary / 'assets').mkdir()
            for name in names: shutil.copyfile(Path(media_root) / name, temporary / name)
        if output.exists() or output.is_symlink():
            raise ValueError('출력 경로가 생성되어 내보내기를 중단했습니다.')
        temporary.rename(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return output
