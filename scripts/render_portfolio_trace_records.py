"""Render actual capture-run log excerpts; these are figures, not product screenshots."""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from export_portfolio_capture_records import build

ROOT = Path(__file__).resolve().parents[1]
FONT = 'C:/Windows/Fonts/malgun.ttf'
BG, INK, MUTED, GREEN = '#f7f6f1', '#173f37', '#62756a', '#315f4c'
FONTS = {n: ImageFont.truetype(FONT, n) for n in (19, 21, 24, 27, 33, 42)}
RUNS = ['845a4b72272d4a5ca2189ebb7695d3a8', '89a6f9d3723646f6bfe45125578186c5']


def wrapped(draw, text, x, y, width, size=24, limit=None):
    count = 0
    for paragraph in str(text).split('\n'):
        line = ''
        for char in paragraph:
            if draw.textlength(line + char, font=FONTS[size]) > width:
                draw.text((x, y), line, font=FONTS[size], fill=INK)
                y += size + 12
                count += 1
                line = char
                if limit and count >= limit:
                    return y
            else:
                line += char
        draw.text((x, y), line, font=FONTS[size], fill=INK)
        y += size + 12
        count += 1
        if limit and count >= limit:
            return y
    return y


def canvas(title, subtitle, run, height=1040):
    img = Image.new('RGB', (1440, height), BG)
    d = ImageDraw.Draw(img)
    d.text((54, 30), 'TRAVEL NOTE / ACTUAL TRACE RECORDS', font=FONTS[19], fill=GREEN)
    d.text((54, 74), title, font=FONTS[42], fill=INK)
    d.text((54, 140), subtitle, font=FONTS[24], fill=MUTED)
    d.text((54, 188), f"RUN {run['run_id'][:8]}    TRACE {run['request_id'][:8]}", font=FONTS[21], fill=GREEN)
    d.line((54, 232, 1386, 232), fill='#d1dccb', width=2)
    d.text((54, height - 49), '실제 저장 로그 발췌를 시각화한 자료 · 제품 화면 캡처와 구분', font=FONTS[21], fill=MUTED)
    return img, d


def card(d, rect, title, text, size=24, limit=None):
    d.rounded_rectangle(rect, radius=18, fill='#fffefa', outline='#d1dccb', width=2)
    x, y, right, bottom = rect
    d.text((x + 22, y + 17), title, font=FONTS[27], fill=GREEN)
    end = wrapped(d, text, x + 22, y + 65, right - x - 44, size, limit)
    if end > bottom - 12:
        raise ValueError(f'Text overflow: {title}')


def render(data_file):
    search, memory = json.loads(data_file.read_text(encoding='utf-8'))
    dest = ROOT / 'docs/assets'
    dest.mkdir(parents=True, exist_ok=True)
    st = search['tools'][0]
    before, after = search['requests'][0], search['requests'][1]
    im, d = canvas('도구 호출이 다음 모델 입력으로 이어지는 경로', '실제 웹 검색 실행 · 요청 순서와 호출 ID를 연결', search)
    items = [
        (f"#{before['sequence']}  STEP 1 · model_start", f"system → user / 입력 {before['input_bytes']:,} B"),
        (f"#{st['start_sequence']}  tool_start", f"{st['name']} / {st['call_id']}"),
        (f"#{st['end_sequence']}  tool_end", f"반환 결과 ID  {st['result_id']}"),
        (f"#{after['sequence']}  STEP 2 · model_start", ' → '.join(m['role'] for m in after['messages'])),
    ]
    for i, (title, detail) in enumerate(items):
        top = 265 + i * 170
        card(d, (74, top, 1366, top + 143), title, detail, 24)
        if i < len(items) - 1:
            d.line((116, top + 143, 116, top + 170), fill=GREEN, width=3)
    im.save(dest / 'portfolio-107-trajectory-records.png')

    request = memory['requests'][-1]
    mt = memory['tools'][0]
    tool_message = next(m for m in reversed(request['messages']) if m['role'] == 'tool')
    assert tool_message['tool_call_id'] == mt['call_id']
    hit = tool_message['hits'][0]
    source = hit['text']
    im, d = canvas('원문 검색 결과가 실제 Context에 들어가는 방식', 'memory_search 반환 → 다음 model_start의 messages 원문 대조', memory, 1120)
    card(d, (54, 262, 1386, 404), f"STEP {request['step']} · 실제 메시지 역할 순서",
         ' → '.join(m['role'] for m in request['messages']), 21)
    args = json.dumps(mt['arguments'], ensure_ascii=False)
    card(d, (54, 426, 1386, 582), '도구 요청과 다음 입력의 동일한 tool_call_id', mt['call_id'] + '\n' + args, 24)
    card(d, (54, 588, 1386, 860), '모델의 tool 메시지에 들어간 원문 근거', f"근거 ID  {hit['id']}\n{source}", 24)
    ctx = request['context']
    card(d, (54, 882, 1386, 1042), '같은 호출의 Context 검사',
         f"input_bytes {request['input_bytes']:,} B  /  trigger {ctx['trigger_bytes']:,} B\ncompacted = {str(ctx['compacted']).lower()}  ·  이번 호출은 요약 없이 원문 검색을 사용", 24)
    im.save(dest / 'portfolio-107-context-input-records.png')

    tool_message = next(m for m in after['messages'] if m['role'] == 'tool')
    selected = tool_message['hits'][0]
    im, d = canvas('검색 반환과 선별된 모델 입력을 같은 호출로 추적', f"tool_call_id  {st['call_id']}", search, 1120)
    card(d, (54, 264, 1386, 414), '검색 도구의 실제 요청 인자', json.dumps(st['arguments'], ensure_ascii=False), 24)
    raw = st['result']['text']
    try:
        first = json.loads(raw)
        raw_text = f"제목  {first.get('title', '')}\nURL  {first.get('url', '')}\n{first.get('description', '')}"
    except ValueError:
        raw_text = raw[:330]
    card(d, (54, 436, 1386, 690), 'MCP 원시 반환 · 첫 검색 항목 발췌', raw_text, 24, 4)
    selected_text = f"ID  {selected.get('id', '')}\n제목  {selected.get('title', '')}\nURL  {selected.get('url', '')}\n{selected.get('snippet', selected.get('description', ''))}"
    card(d, (54, 712, 1386, 1036), '실제 모델 입력 · 선별 hits의 첫 항목 발췌', selected_text, 24, 6)
    d.text((78, 995), 'URL 내 세션 식별자는 마스킹했습니다.', font=FONTS[19], fill=MUTED)
    im.save(dest / 'portfolio-107-search-input-records.png')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/private/research/107-capture-runs')
    args = parser.parse_args()
    data_file = build(args.data_dir, RUNS, ROOT / 'artifacts/portfolio-107-records')
    render(data_file)
    print('Rendered three figures from actual capture-run records; not UI screenshots.')
