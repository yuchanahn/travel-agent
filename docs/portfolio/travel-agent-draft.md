> 여행 조건을 기억하고, 후보와 출처를 비교하는 로컬 여행 도우미입니다.

여자친구와 여행을 준비하며 느낀 조사·근거 확인의 불편을 해결하려 만들었습니다. 개인 프로젝트이며 구현에 Codex를 활용했습니다.

## 01 · 검색·숙소 조회·본문 읽기

**Python · Qwen · MCP**

모델이 필요한 도구를 선택하고 결과를 받아 다음 행동을 정합니다. 최대3개 병렬 호출·중복 차단·실행 한도를 구현했습니다.

![설명용 실행 구조도](https://raw.githubusercontent.com/yuchanahn/travel-agent/7cb4731/docs/assets/portfolio-agent-architecture.png)

<details>
<summary>코드 · 도구 요청을 추적하는 방법</summary>

`agent.py` · `execute_batch.emit_start` · 기준 f5f4a56. 호출 ID와 인자를 남겨 모델의 요청과 실제 실행 결과를 연결합니다.

```python
def emit_start(index, name, call):
    trace.emit("tool_start", step=step, span=f"{step}.{index + 1}", name=name,
               call_index=index, tool_call_id=call.get("id"), arguments=call["function"].get("arguments"))
```
</details>

## 02 · 과거 조건을 되찾는 메모리

**SQLite · BM25 · 임베딩 · RRF · 리랭킹**

요약과 원문을 분리하고 필요한 기록을 검색합니다. 웹은 BM25, CLI는 하이브리드를 비교했습니다. 합성 평가 근거8/8·통제된 세부 복원0/2→2/2를 확인했습니다.

![설명용 메모리 구조와 합성 평가 결과](https://raw.githubusercontent.com/yuchanahn/travel-agent/7cb4731/docs/assets/portfolio-memory-rag.png)

<details>
<summary>코드 · 검색 순위 결합</summary>

`memory.py` · `rrf` · 기준 f5f4a56. BM25와 임베딩의 서로 다른 점수를 직접 더하지 않고 순위로 결합합니다. 웹 기본 검색은 BM25입니다.

```python
def rrf(rankings: list[list[int]], k=60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, 1):
            scores[index] = scores.get(index, 0.0) + 1 / (k + rank)
    return scores
```
</details>

## 03 · 대화 이어가기·실행 비교

**로컬 웹 · JSONL Trace · Eval Harness**

후속 질문·조건 정정·출처·호출/오류/시간 확인과 실행 비교를 제공합니다. 실제 브라우저3턴과 Python 계약 검사279개를 확인했습니다.

![새 UI의 실제 실행 비교 · 서로 다른 두 턴의 기능 시연](https://raw.githubusercontent.com/yuchanahn/travel-agent/ef9145c/docs/assets/notebook-comparison.png)

<details>
<summary>코드 · 누락된 사용량을0으로 표시하지 않기</summary>

`observability.py` · `summarize` · 기준 f5f4a56. 보고된 합계와 수집 완전성을 함께 표시합니다.

```python
**{key: {'reported_sum': sum(v for v in values if v is not None) if any(v is not None for v in values) else None,
         'reported_calls': sum(v is not None for v in values), 'expected_calls': model_starts,
         'complete': len(values) == model_starts and all(v is not None for v in values)}
   for key, values in tokens.items()},
```
</details>

현재는 프로토타입입니다. 최신 여행 답변의 근거 검토0/2로 추천 품질 개선은 미입증입니다.

[GitHub](https://github.com/yuchanahn/travel-agent)
