"""Four immutable sample templates and clearly fictional demonstration content."""
SAMPLES = [
    {'id':'sample-editorial-v1','family':'sample-editorial-v1','version':1,'name':'01 에디토리얼 · 매거진','style':'editorial','description':'따뜻한 종이색과 세리프 제목. 배경과 이야기를 풀어내는 칼럼형 구성.','intro':'하나의 주제를 천천히 살펴봅니다.','sections':['이야기의 시작','한 걸음 더 들여다보기','생각을 남기며'],'outro':'읽고 난 뒤의 질문을 남겨 보세요.','builtin':True},
    {'id':'sample-notebook-v1','family':'sample-notebook-v1','version':1,'name':'02 필드노트 · 탐구 일지','style':'notebook','description':'초록색 노트와 점선 구분. 질문·관찰·배운 점을 쌓는 기록형 구성.','intro':'작은 질문에서 시작한 관찰을 기록합니다.','sections':['오늘의 질문','관찰과 확인','배운 점과 다음 질문'],'outro':'다음 기록에서 이어갑니다.','builtin':True},
    {'id':'sample-manual-v1','family':'sample-manual-v1','version':1,'name':'03 스텝가이드 · 실용 매뉴얼','style':'manual','description':'파란 단계 카드와 자동 번호. 준비부터 실행·확인까지 읽는 매뉴얼형 구성.','intro':'먼저 준비하고, 차근차근 따라 해 보세요.','sections':['시작 전 준비','실행 순서','확인과 문제 해결'],'outro':'자신의 상황에 맞게 확인한 뒤 활용하세요.','builtin':True},
    {'id':'sample-briefing-v1','family':'sample-briefing-v1','version':1,'name':'04 브리핑 · 핵심 요약','style':'briefing','description':'짙은 남색과 노란 강조. 요점·근거·다음 행동을 빠르게 읽는 요약형 구성.','intro':'핵심 내용과 확인할 사항을 빠르게 살펴봅니다.','sections':['핵심 요점','확인한 근거','다음 행동'],'outro':'판단에 앞서 출처와 기준일을 확인하세요.','builtin':True},
]


def sample_blocks(template):
    """Demo text is authored example data, never a claim about a real institution."""
    bodies = [
        [{'type':'paragraph','text':'동네 도서관에서 작은 독서 모임을 연다고 가정해 보겠습니다. 책을 고르고, 함께 읽고, 생각을 나누는 하루를 소개하는 가상 예제입니다.'}, {'type':'list','text':'함께 읽을 책 한 권\n서로에게 묻고 싶은 질문 세 가지\n짧게 남기는 한 줄 기록'}],
        [{'type':'paragraph','text':'참여자의 관심과 준비할 자료를 먼저 살펴봅니다. 실제 원고에서는 확인한 기록이나 출처를 여기에 연결하세요.'}],
        [{'type':'paragraph','text':'모임 뒤에는 인상 깊은 문장과 다음에 나누고 싶은 주제를 남깁니다. 실제 일정·인원·효과를 주장하는 내용은 아닙니다.'}],
    ]
    blocks=[{'type':'title','text':'작은 도서관에서 시작하는 독서 모임'},{'type':'paragraph','text':template['intro']}]
    for heading,body in zip(template['sections'],bodies):
        blocks.append({'type':'heading','text':heading});blocks.extend(body)
    blocks.append({'type':'paragraph','text':template['outro']})
    return blocks
