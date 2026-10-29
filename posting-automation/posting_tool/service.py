from pathlib import Path
import re
from .ingestion import import_sources
from .models import Article


def prepare_article(root: Path, bundle: str, title: str | None = None) -> Article:
    sources = import_sources(root, bundle)
    if title is not None and (not title.strip() or len(title) > 200 or '\n' in title or '\r' in title):
        raise ValueError('제목은 줄바꿈 없이 1~200자로 입력하세요.')
    first_heading = re.search(r'^#\s+(.+)$', sources[0].text, re.M)
    title = title.strip() if title else (first_heading[1].strip() if first_heading else Path(bundle).name)
    if not title or len(title) > 200:
        raise ValueError('자료 제목이 없거나 너무 깁니다. --title로 지정하세요.')
    warnings = ['AI 요약·사실 검증을 수행하지 않았습니다. 원문과 출처를 검토하세요.',
                '사진은 자동으로 가져오지 않습니다. 이미지와 사용 권한을 별도로 확인하세요.']
    sections = []
    for number, source in enumerate(sources, 1):
        lines = source.text.splitlines()
        label = Path(source.name).stem
        if lines[0].startswith('# '):
            label, lines = lines[0][2:].strip(), lines[1:]
        # Demote headings so source H1/H2 do not override the template hierarchy.
        body = '\n'.join(re.sub(r'^(#{1,6})\s+', lambda m: '#' * min(len(m[1]) + 2, 6) + ' ', line) for line in lines).strip()
        sections.append(f'## {number}. {label}\n\n{body}')
        if not re.search(r'https?://', source.text):
            warnings.append(f'{source.name}: 외부 근거 URL이 없습니다. 출처를 확인하세요.')
    provenance = '\n'.join(f'- {s.name}' for s in sources)
    markdown = f'# {title}\n\n' + '\n\n---\n\n'.join(sections) + '\n\n---\n\n## 입력 자료 기록\n\n' + provenance + '\n'
    if len(markdown) > 100_000:
        raise ValueError('변환 원고가 100,000자를 초과합니다. 자료 묶음을 나누세요.')
    return Article(title, markdown, sources, tuple(warnings))
