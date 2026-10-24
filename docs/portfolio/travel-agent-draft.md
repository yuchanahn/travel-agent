> 여행 조건을 기억하고, 대화를 여행 계획서로 남기는 로컬 AI 도우미입니다.

여자친구와 여행을 준비하며 겪은 반복 검색과 정보 누락을 줄이려 만들었습니다. 개인 프로젝트로 문제 정의·설계·검증을 진행했고 구현에 Codex를 활용했습니다.

## 01 · 검색은 넓게, 모델 입력은 작게

**Python · Qwen · MCP · BM25Plus**

검색 원문을 보존하고 문장 중복 제거·관련도 정렬·최대 30개 선별을 적용했습니다. 같은 저장 결과의 전달량을 **85KB→29KB**로 줄였습니다. 모델은 필요한 본문을 선택해 읽고, 호출 기록으로 동작을 확인합니다.

![검색 구조 · 저장 자료 재포장 측정이며 추천 품질 지표는 아님](https://raw.githubusercontent.com/yuchanahn/travel-agent/b73822f/docs/assets/portfolio-095-search.png)

<details>
<summary>코드 · 관련도 정렬과 개수 제한</summary>

`src/travel_agent/search_selection.py` · `select` · 기준 `b73822f`. 실제 구현 발췌.

```python
    q=tokens(query);overlap=bool(q and any(set(q)&set(t) for t in corpus))
    scores=BM25Plus(corpus).get_scores(q) if hits and overlap else [0]*len(hits)
    # Zero lexical overlap is not proof of irrelevance (e.g. linked English page).
    eligible=list(range(len(hits)))
    order=sorted(eligible,key=lambda i:(-float(scores[i]),i))
    selected=[hits[i] for i in order[:limit]]
    for hit,i in zip(selected,order):hit['relevance_score']=round(float(scores[i]),6)
```
</details>

## 02 · 요약에서 빠진 조건을 원문으로 복원

**SQLite · BM25 · 임베딩 · RRF · 리랭킹**

원문과 요약을 따로 저장하고 매 모델 호출 전에 문맥을 검사합니다. 웹은 BM25, 별도 CLI는 하이브리드 검색을 비교했습니다. 합성 평가 12응답에서 세부 조건 복원은 **요약만 0/2→원문 검색 추가 2/2**였습니다.

![메모리 구조 · 통제된 합성 평가 결과](https://raw.githubusercontent.com/yuchanahn/travel-agent/b73822f/docs/assets/portfolio-095-memory.png)

<details>
<summary>코드 · 서로 다른 검색 점수를 순위로 결합</summary>

`src/travel_agent/memory.py` · `rrf` · 기준 `b73822f`. 실제 구현 발췌.

```python
def rrf(rankings: list[list[int]], k=60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, 1):
            scores[index] = scores.get(index, 0.0) + 1 / (k + rank)
    return scores
```
</details>

## 03 · 대화가 끝나도 남는 여행 계획서

**로컬 웹 · 자동 초안 · JSONL Trace · Eval Harness**

대화 후 초안을 저장하고 요약·시간표·예산으로 보여줍니다. 직접 편집·선택 확정·Markdown 저장·PDF 출력을 제공합니다. 실제 브라우저 3턴의 예산·인원 정정과 모바일 화면, Python 검사 **307개**를 확인했습니다.

![실제 계획서 화면 · 합성 여행이며 숙박비 15만원은 시연용 직접 입력](https://raw.githubusercontent.com/yuchanahn/travel-agent/b73822f/docs/assets/portfolio-095-plan-budget.png)

<details>
<summary>코드 · 자동 정리가 사용자 편집을 덮어쓰지 않도록</summary>

`src/travel_agent/web_app.py` · `RunManager.update_plan` · 기준 `b73822f`. 실제 구현 발췌.

```python
            job=self._job(run_id)
            plan=self._plan(job)
            if expected_revision is not None and plan['revision']!=expected_revision:
                raise RuntimeError('계획이 변경돼 자동 정리를 적용하지 않았습니다.')
            if not model and (type(payload.get('revision')) is not int or payload['revision']!=plan['revision']):
                raise RuntimeError('계획이 변경됐습니다. 새로고침 후 다시 편집해주세요.')
```
</details>

현재는 프로토타입입니다. 고정 여행 질문 2개는 실행을 마쳤지만 **주소·출처 검토 0/2**로 추천 품질은 미통과입니다. 대규모 운영 경험이나 일반적인 품질 향상을 주장하지 않습니다.

[GitHub](https://github.com/yuchanahn/travel-agent)
