> 여행 조건을 기억하고, 정보를 찾아 비교하는 로컬 여행 에이전트입니다.

**개인 프로젝트 · Python / Qwen / MCP / RAG / 실행 추적·평가**

여자친구와 여행을 준비하며 범용 에이전트의 반복 검색과 부족한 근거 확인에 불편을 느꼈습니다. 조사 도구부터 메모리·실행 기록·평가까지 연결했고, 구현에는 Codex를 활용했습니다.

## 01 · 필요한 정보를 스스로 찾는 에이전트

![설명용 구조도 · 실제 구현의 도구 호출과 종료 흐름](https://raw.githubusercontent.com/yuchanahn/travel-agent/7cb4731/docs/assets/portfolio-agent-architecture.png)

**기술** · Python · Ollama/Qwen · MCP · 병렬 Tool Calling

**의도·구조** · 검색 순서를 대본으로 고정하지 않고, 모델이 Brave 검색·OpenBnB·본문 읽기를 선택하도록 실행기를 구현했습니다. 도구 결과를 다시 모델에 전달하며 최대3개를 병렬 실행합니다.

**시도·결과** · 별도 종료 태그도 시험했지만 재요청이 늘어 폐기했습니다. 현재는 일반 답변으로 종료하고, 호출 한도·중복 요청·오류를 실행기에서 관리합니다.

<details>
<summary>코드 · 도구 요청을 추적하는 방법</summary>

`agent.py` · `execute_batch.emit_start` · 기준 f5f4a56. 호출 ID와 인자를 남겨 모델의 요청과 실제 실행 결과를 연결합니다.

```python
def emit_start(index, name, call):
    trace.emit("tool_start", step=step, span=f"{step}.{index + 1}", name=name,
               call_index=index, tool_call_id=call.get("id"), arguments=call["function"].get("arguments"))
```
</details>

## 02 · 요약에서 빠진 기억을 되찾는 RAG

![설명용 구조도와 고정 합성 평가 결과 · 웹 BM25와 CLI 비교 경로 구분](https://raw.githubusercontent.com/yuchanahn/travel-agent/7cb4731/docs/assets/portfolio-memory-rag.png)

**기술** · SQLite · BM25 · 임베딩 검색 · RRF · 리랭킹

**의도·구조** · 요약에서 빠진 예산 정정·후보 제외 이유를 되찾기 위해 원문을 별도 보존했습니다. 웹은 BM25로 필요한 기록을 검색하고, CLI에서는 임베딩·순위 결합·리랭킹을 비교했습니다.

**확인한 결과** · 고정 합성 자료의 정답 근거8/8을 검색했습니다. 실제 Qwen 대조에서는 손실 요약만으로 놓친 세부사항2개를 원문 검색으로 복원했습니다. 일반 품질 향상으로 확대하지 않았습니다.

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

## 03 · 행동을 추적하고 품질을 검증하는 실행 환경

![실제 실행 비교 화면 · 질문이 다른 두 턴의 지표 표시이며 품질 향상 대조는 아님](https://raw.githubusercontent.com/yuchanahn/travel-agent/f5f4a56/docs/assets/travel-agent-comparison-metrics.png)

**기술** · JSONL Trace · Eval Harness · 실행 지표·비교 UI

**의도·구조** · 답변 완료와 정확도를 구분하려고 모델·도구 입출력, 검색어, 시간, 오류를 연결했습니다. 같은 Qwen의 Claude Code와 같은 질문으로 비교하며 검색 자료 전달 차이와 시설 혼합을 분석했습니다.

**확인한 결과** · 지표·비교 화면과 검색 없는3턴 조건 정정을 실제 브라우저에서 확인했습니다. Python 계약 검사279개는 통과했지만 최신 여행 두 질문의 근거 검토는0/2여서, 새 지침의 추천 품질은 미확인으로 남겼습니다.

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

현재는 로컬 웹 프로토타입입니다. 실제 예약·대규모 운영·비용 절감은 입증하지 않았습니다.

[GitHub](https://github.com/yuchanahn/travel-agent)
