"""Explanatory diagrams, not UI screenshots. Frozen measurements, no model calls."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
BG='#f8f7f2';INK='#243f36';GREEN='#35664f';MUTED='#687b70';LINE='#dae1d4';TINT='#eaf0e3'
F={n:ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',n) for n in (19,22,25,30,38,50)}


def base(number,title,subtitle):
    im=Image.new('RGB',(1440,880),BG);d=ImageDraw.Draw(im)
    d.text((60,40),'TRAVEL NOTE  /  '+number,font=F[19],fill=GREEN)
    d.text((60,85),title,font=F[38],fill=INK);d.text((60,150),subtitle,font=F[22],fill=MUTED)
    return im,d


def card(d,box,title,lines,dark=False):
    x,y,_,_=box;d.rounded_rectangle(box,radius=20,fill=GREEN if dark else '#fff',outline=LINE,width=2)
    d.text((x+23,y+25),title,font=F[25],fill='#fff' if dark else INK)
    for i,s in enumerate(lines):d.text((x+23,y+77+i*36),s,font=F[22],fill='#e7eee4' if dark else MUTED)


def arrow(d,a,b):
    d.line([a,b],fill=GREEN,width=3);x,y=b;d.polygon([(x,y),(x-11,y-7),(x-11,y+7)],fill=GREEN)


im,d=base('01','검색 결과를 쌓는 대신, 읽을 근거를 고르도록','의도  /  검색량 확대 → 입력 누적 문제를 원문 보존·선별·문맥 관리로 해결')
card(d,(60,235,455,450),'Brave MCP · 원문 보존',['검색 결과와 주변 문서 수집','원본·출처를 비공개로 저장'])
card(d,(520,235,915,450),'중복 제거 · BM25Plus',['병렬 묶음 최대 30개 선별','바이트 예산 · 생략량 표시'],True)
card(d,(980,235,1380,450),'Qwen · 다음 행동 선택',['필요한 본문·기억을 선택 조회','최대 3개 병렬 도구 실행'])
arrow(d,(455,342),(520,342));arrow(d,(915,342),(980,342))
d.rounded_rectangle((60,500,1380,725),radius=20,fill=TINT)
d.text((90,527),'문제 재현 → 변경 → 측정',font=F[22],fill=GREEN)
d.text((90,575),'85 KB   →   29 KB',font=F[50],fill=INK)
d.text((670,565),'동일 저장 검색 자료의 전달량 비교',font=F[25],fill=INK)
d.text((670,610),'최종 전달 21개 · 새 검색 0회',font=F[22],fill=MUTED)
d.text((60,780),'구현  /  호출 ID·인자·반환·오류 기록 · 매 추론 전 문맥 검사 · 원문 BM25 재검색',font=F[22],fill=GREEN)
d.text((60,825),'재포장 측정이며 추천 정확도 개선을 입증하는 수치는 아닙니다.',font=F[19],fill=MUTED)
im.save(ROOT/'docs/assets/portfolio-095-search.png')

im,d=base('02','요약은 가볍게, 필요한 기억은 원문에서','의도  /  예산 정정·후보 제외 이유가 요약에서 빠져도 다시 확인할 수 있도록')
card(d,(60,235,455,450),'SQLite · 원문 저장',['사용자·모델·도구 기록 분리','현재 대화의 조상 경로만 조회'])
card(d,(520,235,915,450),'LLM 요약 + BM25',['매 모델 호출 전 크기 검사','필요한 원문을 검색해 보완'],True)
card(d,(980,235,1380,450),'별도 CLI 비교',['BM25 · 임베딩 · RRF','리랭킹의 역할을 분리해 실험'])
arrow(d,(455,342),(520,342));arrow(d,(915,342),(980,342))
card(d,(60,500,695,725),'고정 합성 검색 평가',['정답 근거 포함 8/8 · MRR@3 0.875','다른 대화 범위 누출 0/2'])
card(d,(745,500,1380,725),'실제 Qwen · 세부 복원 대조',['요약만 0/2 → 원문 검색 추가 2/2','4질문 × 3조건 · 12응답 재확인'])
d.text((60,780),'구조  /  원문 보존 → 요약/검색 분리 → 문맥 보완 → 응답 · 요약 사용량 별도 추적',font=F[22],fill=GREEN)
d.text((60,825),'통제된 합성 자료의 결과입니다. 자연 압축 손실·일반 여행 품질은 별도입니다.',font=F[19],fill=MUTED)
im.save(ROOT/'docs/assets/portfolio-095-memory.png')
