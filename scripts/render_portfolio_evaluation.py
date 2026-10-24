"""Portfolio illustration of recorded evaluation scopes; not a UI screenshot."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parents[1]
im=Image.new('RGB',(1440,630),'#f8f7f2');d=ImageDraw.Draw(im)
fonts={n:ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',n) for n in (20,25,30,40)}
d.text((55,35),'TRAVEL NOTE  /  EVALUATION',font=fonts[20],fill='#35664f')
d.text((55,85),'기능 동작과 답변 정확도를 나누어 확인합니다',font=fonts[40],fill='#243f36')
rows=[('기능·저장·실행 규칙','Python 311개 통과','회귀 검사 · 실제 여행 정확도와 별도'),
      ('원문 기억 복원','세부 조건 2/2','통제된 합성 평가 · 실제 Qwen 12응답'),
      ('여행 답변의 사실·출처','근거 검토 0/2','고정 질문 · 현재 추천 품질 미통과')]
for i,(name,value,note) in enumerate(rows):
 y=175+i*120
 d.rounded_rectangle((55,y,1385,y+100),radius=17,fill='#ffffff',outline='#dae1d4',width=2)
 d.text((80,y+18),name,font=fonts[30],fill='#243f36')
 d.text((650,y+15),value,font=fonts[30],fill='#35664f')
 d.text((650,y+58),note,font=fonts[20],fill='#687b70')
d.text((55,565),'설명용 평가 요약 · 기존 095/097 결과 · 새 실험이나 실제 대시보드 캡처가 아닙니다.',font=fonts[20],fill='#687b70')
im.save(root/'docs/assets/portfolio-evaluation-scopes.png')
