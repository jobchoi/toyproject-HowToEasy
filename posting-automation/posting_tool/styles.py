"""Allowlisted, self-contained article styles. No user CSS or remote assets."""
STYLES = {
    'plain': '',
    'editorial': '''body{background:#f7f2e9;color:#302c29;font-family:Georgia,"Malgun Gothic",serif;max-width:760px}main{border-top:5px solid #a43d36;padding-top:24px}main:before{content:"THE EDITORIAL / 읽고 생각하는 시간";font:11px sans-serif;letter-spacing:2px;color:#a43d36}h1{font-size:44px;letter-spacing:-2px;border-bottom:1px solid #c9c0b4;padding-bottom:28px;margin-top:18px}h2{font-size:25px;margin-top:42px}p{line-height:2}ul{border-left:2px solid #b54a42;padding:12px 28px;background:#f0e9dd}hr{border:0;border-top:1px solid #cfc4b7}''',
    'notebook': '''body{background:#eef4e9;color:#304735;max-width:760px}main{background:#fffef7;border:1px solid #d5ddc9;border-radius:14px;padding:30px;box-shadow:6px 6px 0 #dbe5d1}main:before{content:"FIELD NOTES · 관찰하고 기록하기";font-size:11px;letter-spacing:2px;color:#687d50}h1{font-size:34px;color:#335b3c}h2{font-size:21px;border-bottom:2px dashed #c5d2b7;padding-bottom:10px;margin-top:36px}ul{background:#eef4e5;border-radius:10px;padding:20px 36px}li{margin:7px 0}hr{border:0;border-top:2px dashed #c5d2b7}''',
    'manual': '''body{background:#f1f5fb;color:#263c56;max-width:790px}main{counter-reset:step}main:before{content:"PRACTICAL GUIDE / 바로 따라 하는 가이드";color:#2762c6;font-weight:700;font-size:11px;letter-spacing:1px}h1{font-size:36px;line-height:1.4;color:#153867;border-left:6px solid #3376d4;padding-left:20px}h2{counter-increment:step;font-size:22px;background:#e0ebfc;border-radius:8px;padding:14px 18px;margin-top:35px}h2:before{content:counter(step,decimal-leading-zero) "  ";color:#3274d0;font-size:16px}ul{background:white;border:1px solid #d9e4f4;border-radius:8px;padding:20px 38px}hr{border:0;border-top:1px solid #d7e1f0}''',
    'briefing': '''body{background:#14252c;color:#d8e4e7;max-width:780px}main:before{content:"BRIEFING / 핵심만 빠르게";color:#f8b65c;font:700 11px sans-serif;letter-spacing:2px}h1{font-size:38px;color:#fff;border-bottom:3px solid #e9ad58;padding-bottom:24px}h2{font-size:20px;color:#ffc576;letter-spacing:-.5px;margin-top:36px}p{color:#c3d3d9}ul{background:#203840;border-left:3px solid #efb562;padding:18px 36px}li{margin:8px 0}hr{border:0;border-top:1px solid #395059}aside{color:#293a43}''',
}


def style_css(style):
    return STYLES.get(style, STYLES['plain'])

FONTS={'sans':'sans-serif','serif':'Georgia,"Malgun Gothic",serif','mono':'Consolas,monospace'}


def normalize_appearance(value):
    import re
    if value is None:return {}
    if not isinstance(value,dict):raise ValueError('디자인 설정 형식을 확인하세요.')
    allowed={'background','text','accent','font','body_size','line_height','content_width','paragraph_gap','heading'}
    if set(value)-allowed:raise ValueError('지원하지 않는 디자인 항목입니다.')
    for key in ('background','text','accent'):
        if key in value and (not isinstance(value[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value[key])):raise ValueError('색상은 #RRGGBB 형식이어야 합니다.')
    if 'font' in value and (not isinstance(value['font'],str) or value['font'] not in FONTS):raise ValueError('지원하지 않는 글꼴입니다.')
    if 'heading' in value and (not isinstance(value['heading'],str) or value['heading'] not in {'plain','underline','bar'}):raise ValueError('제목 스타일을 확인하세요.')
    for key,low,high in [('body_size',14,22),('line_height',1.4,2.3),('content_width',560,960),('paragraph_gap',8,40)]:
        if key in value and (type(value[key]) not in (int,float) or not low<=value[key]<=high):raise ValueError(f'{key}: 허용 범위를 벗어났습니다.')
    return dict(value)


def appearance_css(value):
    value=normalize_appearance(value)
    if not value:return ''
    body=[]
    for key,css in [('background','background'),('text','color')]:
        if key in value:body.append(f'{css}:{value[key]}')
    for key,css,unit in [('body_size','font-size','px'),('line_height','line-height',''),('content_width','max-width','px')]:
        if key in value:body.append(f'{css}:{value[key]}{unit}')
    if 'font' in value:body.append('font-family:'+FONTS[value['font']])
    css='body{'+ ';'.join(body)+'}'
    if 'text' in value:css+=f'main p,main li{{color:{value["text"]}}}'
    if 'accent' in value:css+=f'main h1,main h2,main h3{{color:{value["accent"]}}}'
    if 'paragraph_gap' in value:css+=f'main p{{margin-top:{value["paragraph_gap"]}px;margin-bottom:{value["paragraph_gap"]}px}}'
    accent=value.get('accent','#276351')
    if value.get('heading')=='underline':css+=f'main h2{{border-left:0;border-bottom:2px solid {accent};padding-bottom:10px}}'
    if value.get('heading')=='bar':css+=f'main h2{{border-bottom:0;border-left:5px solid {accent};padding-left:15px}}'
    if value.get('heading')=='plain':css+='main h2{border:0;background:transparent}'
    return css
