"""Render explanatory figures, not application screenshots. Requires Pillow and a Korean font."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BG, INK, MUTED, ACCENT = '#f5f4ef', '#1d3430', '#546761', '#245f4a'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', default='C:/Windows/Fonts/malgun.ttf')
    args = parser.parse_args()
    fonts = {n: ImageFont.truetype(args.font, n) for n in (20, 23, 26, 30, 40)}
    output = ROOT/'docs/assets'
    output.mkdir(parents=True, exist_ok=True)

    def canvas(number, title, purpose):
        img = Image.new('RGB', (1440, 820), BG)
        draw = ImageDraw.Draw(img)
        draw.text((58, 36), f'TRAVEL AGENT / {number}', font=fonts[20], fill=ACCENT)
        draw.text((58, 77), title, font=fonts[40], fill=INK)
        draw.text((58, 145), purpose, font=fonts[23], fill=MUTED)
        return img, draw

    def card(draw, rect, label, lines, dark=False):
        draw.rounded_rectangle(rect, radius=18, fill=ACCENT if dark else 'white', outline='#d6ded5', width=2)
        x, y = rect[:2]
        draw.text((x+23, y+21), label, font=fonts[26], fill='white' if dark else INK)
        for i, text in enumerate(lines):
            draw.text((x+23, y+68+i*35), text, font=fonts[23], fill='#e5f0e7' if dark else MUTED)

    def arrow(draw, points, label=None, label_at=None):
        draw.line(points, fill=ACCENT, width=3, joint='curve')
        x, y = points[-1];px, py = points[-2]
        if x>px: triangle=[(x,y),(x-12,y-7),(x-12,y+7)]
        elif x<px: triangle=[(x,y),(x+12,y-7),(x+12,y+7)]
        elif y>py: triangle=[(x,y),(x-7,y-12),(x+7,y-12)]
        else: triangle=[(x,y),(x-7,y+12),(x+7,y+12)]
        draw.polygon(triangle, fill=ACCENT)
        if label:draw.text(label_at, label, font=fonts[20], fill=MUTED)

    img, draw = canvas('01', '모델의 행동을 연결하는 실행 구조', '의도  /  조사 순서를 고정하지 않고, 모델이 필요한 조회와 다음 행동을 선택하도록')
    card(draw,(58,230,390,410),'질문 · 이전 대화',['최근 대화 + 요약','필요한 과거 원문'])
    card(draw,(500,230,925,410),'Python 실행기 + Qwen',['모델이 도구 요청 / 답변 선택','실행기는 인자·예산·결과 관리'],True)
    card(draw,(1035,230,1382,410),'MCP · 본문 읽기',['Brave 검색 / OpenBnB','선택한 출처와 주변 문서'])
    arrow(draw,[(390,315),(500,315)])
    arrow(draw,[(925,315),(1035,315)])
    arrow(draw,[(1208,410),(1208,475),(715,475),(715,410)],'조회 결과를 다음 모델 입력으로',(823,439))
    card(draw,(500,550,925,705),'native 종료',['도구 없는 일반 답변이면 종료','별도 finish 태그는 요구하지 않음'])
    arrow(draw,[(540,410),(540,550)])
    draw.text((58,754),'구현  /  최대 3개 병렬 실행 · 반복 요청 차단 · 모델/도구/시간 예산 · 호출 ID 기록',font=fonts[23],fill=ACCENT)
    img.save(output/'portfolio-agent-architecture.png')

    metrics = json.loads((ROOT/'docs/research/082-results.json').read_text(encoding='utf-8'))['retrieval']
    img, draw = canvas('02','요약에서 빠진 기억을 원문 검색으로 복원','의도  /  오래된 예산 정정·후보 제외 이유를 요약만 믿지 않고 다시 확인하도록')
    card(draw,(58,230,445,410),'원문과 요약을 분리',['SQLite에 원문 이벤트 보존','웹은 대화 조상 경로만 검색'])
    card(draw,(525,230,912,410),'웹 메모리 RAG',['BM25로 관련 원문 검색','요약 + 원문을 모델에 제공'],True)
    card(draw,(992,230,1382,410),'확인한 결과',['정답 근거 상위3개 포함',f'{metrics["hit_at_3_count"]}/{metrics["positive_count"]} · MRR@3 {metrics["mrr_at_3"]}'])
    arrow(draw,[(445,315),(525,315)]);arrow(draw,[(912,315),(992,315)])
    card(draw,(58,465,715,645),'실제 Qwen의 세부 복원 대조',['손실 요약만 0/2  →  요약 + 원문 검색 2/2','대표 4질문 × 3조건의 통제 실험'])
    card(draw,(755,465,1382,645),'별도 CLI에서 비교한 기술',['BM25 · 임베딩 검색 · RRF · 리랭킹','웹 기본 경로에 모두 연결한 것은 아님'])
    draw.text((58,703),'고정 합성 자료의 결과 · 자연 압축 손실과 일반적인 답변 품질 향상은 미입증',font=fonts[23],fill=MUTED)
    draw.text((58,754),'구조  /  원문 보존 → 필요한 기록 검색 → 현재 문맥 보완 → 모델 응답',font=fonts[23],fill=ACCENT)
    img.save(output/'portfolio-memory-rag.png')


if __name__ == '__main__':
    main()
