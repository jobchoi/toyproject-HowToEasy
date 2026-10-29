"""Plain text / small Markdown subset to user-editable document blocks."""
import re

TYPES = {'title', 'heading', 'subheading', 'paragraph', 'list', 'divider'}


def validate_blocks(blocks):
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 300:
        raise ValueError('문서 블록은 1~300개가 필요합니다.')
    result = []
    for block in blocks:
        if not isinstance(block, dict) or block.get('type') not in TYPES or not isinstance(block.get('text'), str):
            raise ValueError('문서 블록 형식을 확인하세요.')
        text = block['text'].strip()
        if block['type'] in {'title', 'heading', 'subheading'} and '\n' in text:
            raise ValueError('제목 블록에는 줄바꿈을 사용할 수 없습니다.')
        result.append({'type': block['type'], 'text': text})
    if sum(len(b['text']) for b in result) > 100_000:
        raise ValueError('원고는 100,000자 이하로 작성하세요.')
    return result


def to_markdown(blocks):
    prefixes = {'title':'# ', 'heading':'## ', 'subheading':'### '}
    output = []
    for block in validate_blocks(blocks):
        kind, text = block['type'], block['text']
        if kind == 'divider':
            output.append('---')
        elif kind == 'list':
            output.append('\n'.join('- '+line.lstrip('-•· ').strip() for line in text.splitlines() if line.strip()))
        elif text:
            output.append(prefixes.get(kind, '')+text)
    markdown = '\n\n'.join(output)
    if not markdown.strip():
        raise ValueError('원고 내용을 입력하세요.')
    if len(markdown)>100_000: raise ValueError('원고는 100,000자 이하로 작성하세요.')
    return markdown+'\n'


def from_markdown(markdown):
    blocks, pending = [], []
    def flush():
        if pending:
            blocks.append({'type':'paragraph','text':'\n'.join(pending)})
            pending.clear()
    for line in markdown.splitlines():
        heading = re.match(r'^(#{1,6})\s+(.+)$',line)
        bullet = re.match(r'^[-*]\s+(.+)$',line)
        if heading:
            flush()
            blocks.append({'type':{1:'title',2:'heading'}.get(len(heading[1]),'subheading'),'text':heading[2]})
        elif line.strip() == '---':
            flush(); blocks.append({'type':'divider','text':''})
        elif bullet:
            flush()
            if blocks and blocks[-1]['type']=='list':
                blocks[-1]['text']+='\n'+bullet[1]
            else:
                blocks.append({'type':'list','text':bullet[1]})
        elif line.strip():
            pending.append(line)
        else:
            flush()
    flush()
    return blocks


def from_plain(text):
    if not isinstance(text,str) or not text.strip() or len(text)>100_000 or '\x00' in text:
        raise ValueError('평문을 1~100,000자로 입력하세요.')
    blocks, pending = [], []
    def flush():
        if pending:
            blocks.append({'type':'paragraph','text':'\n'.join(pending)})
            pending.clear()
    for line in text.replace('\r\n','\n').splitlines():
        value=line.strip()
        heading=re.match(r'^\d+[.)]\s+(.{1,70})$',value)
        bullet=re.match(r'^[•·*-]\s+(.+)$',value)
        if heading and not value.endswith(('.', '다', '요')):
            flush(); blocks.append({'type':'heading','text':heading[1]})
        elif bullet:
            flush()
            if blocks and blocks[-1]['type']=='list': blocks[-1]['text']+='\n'+bullet[1]
            else: blocks.append({'type':'list','text':bullet[1]})
        elif not value: flush()
        else: pending.append(line.rstrip())
    flush()
    return validate_blocks(blocks)
