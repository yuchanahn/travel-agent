> 여행 조건을 기억하고, 필요한 정보를 찾아 비교하는 로컬 여행 에이전트를 만들었습니다.

**개인 프로젝트 · Python · Ollama/Qwen · MCP · SQLite**

## 왜 만들었나

여자친구와 여행을 준비하며 범용 에이전트에 조사를 맡겼지만, 검색을 반복해도 원하는 조건과 근거를 충분히 확인하지 못했습니다. 여행 정보를 찾는 도구뿐 아니라 **모델의 행동과 답변을 확인하고 개선할 수 있는 실행 환경**을 직접 만들었습니다. 구현에는 Codex를 활용했습니다.

## 무엇을 시도하고 구현했나

### 1. 모델이 필요한 도구를 선택하도록

Python으로 도구 호출 루프를 만들고 Brave 검색·OpenBnB 숙소 조회를 MCP로 연결했습니다. 검색 발췌만으로 부족하면 본문과 주변 페이지를 선택해 읽도록 했습니다. 여러 도구는 최대3개 병렬 실행하고 반복 요청·시간·호출 한도를 관리했습니다.

종료 태그를 강제하는 방식도 시도했지만 재요청이 늘어 폐기했습니다. 현재는 모델이 도구 없이 답변하면 종료합니다.

<details>
<summary>코드 · 도구 요청을 추적하는 방법</summary>

`agent.py` · `execute_batch.emit_start` · 기준 f5f4a56. 호출 ID와 인자를 남겨 모델의 요청과 실제 실행 결과를 연결합니다.

```python
def emit_start(index, name, call):
    trace.emit("tool_start", step=step, span=f"{step}.{index + 1}", name=name,
               call_index=index, tool_call_id=call.get("id"), arguments=call["function"].get("arguments"))
```
</details>

### 2. 요약에서 사라진 기억을 다시 찾도록

예산 정정이나 후보 제외 이유가 요약에서 빠지는 문제에 RAG를 적용했습니다. 원문과 요약을 나눠 저장하고, 필요한 과거 기록을 검색해 모델에 제공합니다.

웹은 BM25를 사용하고, 별도 CLI에서 임베딩 검색·RRF 순위 결합·리랭킹을 비교했습니다. 고정 합성 평가에서는 정답 근거8/8을 찾았고, 실제 Qwen 대조에서 요약만으로 놓친 세부사항2개를 원문 검색으로 복원했습니다. 작은 통제 실험의 결과입니다.

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

### 3. 답변이 끝난 것과 잘한 것을 구분하도록

모델·도구 입출력, 검색어, 시간, 오류를 기록하고 실행별 지표와 비교 화면을 만들었습니다. 같은 Qwen을 사용하는 Claude Code와 같은 질문으로 비교하며 검색 발췌 전달 차이와 숙소 간 시설 혼합을 분석했습니다. 이후 검색 자료 전달과 본문 읽기를 보완하고 간결한 답변·후보별 근거 분리 지침을 적용했습니다.

최신 실제 여행 두 질문은 종료했지만 근거 검토는0/2였습니다. 도구가 정상 실행돼도 정확한 추천이 보장되지 않는다는 점을 확인했습니다. 새 지침의 최종 추천 품질은 아직 미확인입니다.

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

## 어디까지 만들었나

로컬 웹에서 후속 대화·조건 정정·실행 기록 확인·대화 삭제까지 연결했습니다. 실제 브라우저의 검색 없는3턴에서 다른 조건을 유지하며 숙박비40→30만 원 정정을 확인했습니다. Python 계약 검사279개도 통과했습니다.

**현재는 로컬 프로토타입입니다.** 실제 예약·대규모 운영·일반적인 추천 품질 향상은 입증하지 않았습니다.

![실제 후속 질문과 예산 정정 답변 · 검색 없는 합성 시연](https://raw.githubusercontent.com/yuchanahn/travel-agent/f5f4a56/docs/assets/travel-agent-budget-correction.png)

[GitHub](https://github.com/yuchanahn/travel-agent)
