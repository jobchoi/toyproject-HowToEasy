#!/usr/bin/env python3
"""Build review articles/slides from a curated, evidence-linked story (no network)."""
import argparse
from html import escape
import json
import os
from pathlib import Path
import re

PROJECT=Path(__file__).resolve().parents[1]
REPO=PROJECT.parent
LABELS={'implemented':'구현','verified_historical':'과거 실행 검증','user_reported':'사용자 보고','blocked_current':'현재 차단','planned':'계획'}
BLOCKED_PARTS={'.local','.env','.git','resources'}


def validate(data):
    if data.get('schema_version')!=1 or not data.get('claims'):raise ValueError('STORY_SCHEMA')
    identifiers=set()
    for claim in data['claims']:
        key=claim['id']
        if not re.fullmatch(r'C\d{2}',key) or key in identifiers:raise ValueError('CLAIM_ID')
        identifiers.add(key)
        if claim['status'] not in LABELS or not claim.get('evidence'):raise ValueError('CLAIM_EVIDENCE')
        for ref in claim['evidence']:
            path=REPO/ref
            if not path.is_file() or not path.resolve().is_relative_to(REPO) or BLOCKED_PARTS.intersection(Path(ref).parts) or path.is_symlink():raise ValueError('EVIDENCE_PATH')
    if data.get('publication_ready') and any(c['status']=='blocked_current' for c in data['claims']):raise ValueError('PUBLICATION_BLOCKED')
    public=json.dumps(data,ensure_ascii=False)
    if re.search(r'/home/|(?:\d{1,3}\.){3}\d{1,3}|\.ts\.net|BEGIN .*PRIVATE KEY|Bearer\s+\w+',public):raise ValueError('PRIVATE_METADATA')
    return data


def article(data):
    parts=[f'<h1>{escape(data["title"])}</h1>',f'<p><strong>기준일 {escape(data["as_of"])} · 검토용 기록</strong></p>',f'<p>{escape(data["scope_note"])}</p>']
    markdown=[f'# {data["title"]}',f'기준일 {data["as_of"]} · 검토용 기록',data['scope_note']]
    for c in data['claims']:
        title=f'{c["title"]} [{LABELS[c["status"]]}]'
        parts += [f'<h2>{escape(title)}</h2>',f'<p>{escape(c["text"])}</p>',f'<p><small>근거: {escape(c["id"])}</small></p>']
        markdown += ['## '+title,c['text'],'근거: '+c['id']]
    parts.append('<h2>기록의 근거</h2><ul>')
    markdown.append('## 기록의 근거')
    for c in data['claims']:
        links=[f'<a href="https://github.com/jobchoi/toyproject-HowToEasy/blob/develop/{escape(ref,quote=True)}">{escape(ref)}</a>' for ref in c['evidence']]
        parts.append('<li>'+c['id']+': '+', '.join(links)+'</li>')
        markdown.append('- '+c['id']+': '+', '.join(c['evidence']))
    parts.append('</ul>')
    return '\n'.join(parts), '\n\n'.join(markdown)+'\n'


def deck(data):
    slides=[{'title':'포스팅 자동화 개발 기록','body':data['scope_note'],'tag':'기획 → 구현 → 검증 → 운영','evidence':[] }]
    slides += [{'title':c['title'],'body':c['text'],'tag':LABELS[c['status']]+' · '+c['id'],'evidence':c['evidence']} for c in data['claims']]
    return {'title':data['title'],'as_of':data['as_of'],'slides':slides}


def html_slides(data):
    items=[]
    for i,s in enumerate(data['slides'],1):
        items.append(f'<section><small>{escape(s["tag"])}</small><h1>{escape(s["title"])}</h1><p>{escape(s["body"])}</p><footer>{i:02d} / {len(data["slides"]):02d} · {escape(data["as_of"])}</footer></section>')
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><title>개발 과정 발표</title><style>body{margin:0;background:#e7ecf2;font-family:Arial,"Noto Sans KR",sans-serif;color:#172b43}section{box-sizing:border-box;max-width:1100px;min-height:600px;background:white;margin:32px auto;padding:65px;border-top:12px solid #087f8c;position:relative}h1{font-size:38px;line-height:1.4}p{font-size:25px;line-height:1.9}small{color:#087f8c;font-weight:bold}footer{margin-top:55px;color:#52657c}@media(max-width:700px){section{padding:25px;margin:12px;min-height:0}h1{font-size:27px}p{font-size:19px}}@media print{@page{size:landscape;margin:0}section{margin:0;max-width:none;min-height:100vh;break-after:page}}</style>'+''.join(items)+'</html>'


def write_pptx(data,path):
    try:
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.util import Inches,Pt
    except ImportError:raise ValueError('PPTX_DEPENDENCY: bash scripts/setup_project.sh --profile publication') from None
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    for index,spec in enumerate(data['slides'],1):
        slide=prs.slides.add_slide(prs.slide_layouts[6])
        def box(text,x,y,w,h,size,color,bold=False):
            frame=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)).text_frame
            frame.word_wrap=True;frame.text=text
            for p in frame.paragraphs:
                p.font.name='Noto Sans KR';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color)
                p.space_after=Pt(12)
        box(spec['tag'],.7,.4,12,.5,15,'087F8C',True)
        box(spec['title'],.7,1.2,12,1.2,30,'172B43',True)
        box(spec['body'],.7,2.7,11.9,3.4,23,'172B43')
        box(f'{index:02d} / {len(data["slides"]):02d} · {data["as_of"]}',.7,6.8,12,.4,11,'52657C')
        slide.notes_slide.notes_text_frame.text='근거:\n'+'\n'.join(spec['evidence'])
    prs.core_properties.title=data['title'];prs.core_properties.subject='확인된 사실과 미완료를 구분한 검토용 프로젝트 기록'
    prs.save(path)


def build(source,output,pptx=False):
    data=validate(json.loads(source.read_text(encoding='utf-8')))
    # No partial output folder if optional dependencies are unavailable.
    if pptx:
        import importlib.util
        if importlib.util.find_spec('pptx') is None:raise ValueError('PPTX_DEPENDENCY: setup --profile publication 필요')
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    body,md=article(data);slides=deck(data)
    payload={'title':data['title'],'content':body,'labels':['개발기록','포스팅자동화']}
    files={'article.md':md,'blogger.html':body,'tistory.html':body,'slides.html':html_slides(slides),
           'slides.json':json.dumps(slides,ensure_ascii=False,indent=2),
           'blogger-post.json':json.dumps(payload,ensure_ascii=False,indent=2),
           'manifest.json':json.dumps({'as_of':data['as_of'],'publication_ready':data['publication_ready'],'targets':data['targets'],'claim_ids':[c['id'] for c in data['claims']],'cloud_executed':False,'published':False},ensure_ascii=False,indent=2)}
    template=(PROJECT/'operations/google/ProjectStory.gs').read_text()
    files['ProjectStory.gs']=template.replace('__DECK_JSON__',json.dumps(slides,ensure_ascii=False)).replace('__POST_JSON__',json.dumps(payload,ensure_ascii=False)).replace('__READY_JSON__',json.dumps(data['publication_ready'])).replace('__BLOG_URL_JSON__',json.dumps(data['targets']['blogger']))
    for name,text in files.items():
        path=output/name;path.write_text(text,encoding='utf-8');path.chmod(0o600)
    if pptx:write_pptx(slides,output/'project-story.pptx')
    return {'directory':str(output),'files':len(files)+int(pptx),'slides':len(slides['slides']),'published':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=PROJECT/'docs/publication/project-story.json')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--pptx',action='store_true')
    args=parser.parse_args()
    try:result=build(args.source,args.output,args.pptx)
    except (ValueError,OSError) as error:print('BUILD_FAILED:',error);return 2
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
