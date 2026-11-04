"""Editor handoff adapters: no credentials, external calls, or false saved-post claims."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit
from . import Publisher, Capability
from ..rendering import render_html
from ..documents import from_markdown


@dataclass(frozen=True)
class EditorPackage:
    provider: str
    title: str
    html: str
    plain: str
    target_url: str
    editor_url: str
    warnings: tuple[str,...]
    state: str = 'prepared_for_editor'
    remote_saved: bool = False


class EditorPublisher(Publisher):
    capabilities=frozenset({Capability.EXPORT,Capability.PREPARE_EDITOR})
    def _prepare_editor(self,article):
        images=[b for b in from_markdown(article.markdown) if b['type']=='image']
        body=render_html(article.markdown)
        # Local image references cannot become valid remote uploads by copying HTML.
        body=re.sub(r'<img src="[^"]*" alt="([^"]*)">',lambda m:'<p>사진 별도 첨부: '+m[1]+'</p>',body)
        warnings=['편집기에 전달할 자료만 준비했습니다. 플랫폼에 저장·게시되지 않았습니다.','글꼴·색상·여백은 플랫폼 편집기에서 달라질 수 있습니다.']
        if images:warnings.append(f'사진 {len(images)}개는 플랫폼 편집기에 별도로 첨부하세요. 캡션·출처는 본문에 유지했습니다.')
        return EditorPackage(self.name,article.title,body,article.markdown,self.target_url,self.editor_url,tuple(warnings))


def blog_host(url,suffix):
    value=urlsplit(url)
    if value.scheme!='https' or value.username or value.password or value.port or value.query or value.fragment or value.path not in ('','/') or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.'+re.escape(suffix),value.netloc):
        raise ValueError('대상 블로그의 HTTPS 기본 주소를 확인하세요.')
    return value.netloc


class TistoryEditorPublisher(EditorPublisher):
    name='tistory-editor'
    def __init__(self,url='https://rt-jobchoi.tistory.com'):
        host=blog_host(url,'tistory.com');self.target_url='https://'+host;self.editor_url=self.target_url+'/manage/newpost'


class BloggerEditorPublisher(EditorPublisher):
    name='blogger-editor'
    def __init__(self,url='https://lealnspire.blogspot.com'):
        host=blog_host(url,'blogspot.com');self.target_url='https://'+host;self.editor_url='https://www.blogger.com/'
