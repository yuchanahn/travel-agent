> 여행 조건을 기억하고, 조사한 내용을 편집 가능한 계획서로 남기는 로컬 AI 도우미입니다.

여자친구와 여행을 준비하며 겪은 반복 검색과 정보 누락을 줄이기 위해 만들었습니다. 개인 프로젝트로 구조 설계·평가·제품 흐름을 구성했고, 구현에 Codex를 활용했습니다.

## 01 · 구조 설계

**Python · Qwen · MCP · 병렬 Tool Calling**

대화·검색·본문 조회·계획서 저장을 하나의 실행 흐름으로 연결했습니다. 모델은 다음 행동을 선택하고, 실행기는 최대 3개 병렬 호출과 중복 요청·실행 예산을 관리합니다.

![설명용 검색 구조 · 85KB→29KB는 동일 저장 자료의 전달량 비교](https://raw.githubusercontent.com/yuchanahn/travel-agent/997fd29/docs/assets/portfolio-095-search.png)

<details>
<summary>구현 코드 · 선택한 네트워크 도구를 병렬 실행</summary>

`src/travel_agent/agent.py` · `execute_batch` · 기준 `997fd29`.

```python
    else:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="travel-web") as pool:
            futures = []
            for job in jobs:
                if job[2] in network_tools:
                    attempted_web |= is_web_search(job[2]) and time.perf_counter() < deadline
```
</details>

## 02 · Observability·trajectory 추적

**JSONL Trace · 호출 ID · 실행 비교**

모델 요청부터 도구 인자·검색어·반환 결과·오류·다음 모델 입력까지 연결해 기록합니다. 화면에서 실행별 시간·토큰·중복 호출을 확인하고, 서로 다른 실행을 비교할 수 있습니다.

![실제 실행 비교 화면 · 서로 다른 두 턴의 기능 시연](https://raw.githubusercontent.com/yuchanahn/travel-agent/997fd29/docs/assets/portfolio-095-comparison.png)

<details>
<summary>구현 코드 · 모델 요청과 실행을 호출 ID로 연결</summary>

`src/travel_agent/agent.py` · `execute_batch.emit_start` · 기준 `997fd29`.

```python
    def emit_start(index, name, call):
        trace.emit("tool_start", step=step, span=f"{step}.{index + 1}", name=name,
                   call_index=index, tool_call_id=call.get("id"), arguments=call["function"].get("arguments"))
```
</details>

## 03 · Memory 등 필요한 미들웨어

**SQLite · BM25 · 임베딩 · RRF · 리랭킹**

대화 원문과 요약을 분리하고, 매 모델 호출 전에 문맥을 관리합니다. 과거 조건은 원문 검색으로 보완하며 대화 분기별 조회 범위를 분리합니다. 웹은 BM25를 사용하고, 별도 CLI에서 하이브리드 검색과 리랭킹을 제공합니다.

![설명용 메모리 구조 · 웹 BM25와 별도 CLI 하이브리드를 구분](https://raw.githubusercontent.com/yuchanahn/travel-agent/997fd29/docs/assets/portfolio-095-memory.png)

<details>
<summary>구현 코드 · BM25와 임베딩 검색 순위 결합</summary>

`src/travel_agent/memory.py` · `rrf` · 기준 `997fd29`.

```python
def rrf(rankings: list[list[int]], k=60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, 1):
            scores[index] = scores.get(index, 0.0) + 1 / (k + rank)
    return scores
```
</details>

## 04 · 데이터와 평가 체계로 품질 증명

**고정 평가셋 · Eval Harness · 근거 검토**

기능 동작·메모리 복원·답변의 사실 정확도를 분리해 평가합니다. Python 검사 311개를 통과했고, 통제된 합성 평가에서 세부 조건 복원은 요약만 0/2·원문 검색 추가 2/2였습니다. 실제 여행 두 질문은 근거 검토 0/2로, 추천 품질 개선은 아직 미입증입니다.

![설명용 평가 요약 · 기존 결과를 구분한 자료이며 실제 대시보드가 아님](https://raw.githubusercontent.com/yuchanahn/travel-agent/997fd29/docs/assets/portfolio-evaluation-scopes.png)

<details>
<summary>구현 코드 · 기능 통과와 사실 검토를 별도 판정</summary>

`src/travel_agent/acceptance.py` · `assessment` · 기준 `997fd29`.

```python
    quality=report.get('manual_review',{}).get('verdict','pending')
    return {'mechanical_gate':mechanical,'quality_verdict':quality,
            'release_gate':mechanical and quality=='pass','cleanup':report.get('cleanup')}
```
</details>

## 05 · 프로덕션 개발·운영 기본기

**요청 대기열 · 체크포인트 · 장애 처리**

실행 1개·대기 2개로 요청을 제한하고, 시간·호출 예산과 오류 상태를 관리합니다. 대화·계획서를 저장해 재시작 후 복원하며 세션 삭제와 고정 주소 재시작을 제공합니다. 현재는 로컬 운영이며 대규모 서비스 운영 경험은 포함하지 않습니다.

![실제 로컬 웹 화면 · 대화·계획서·실행 비교 진입점](https://raw.githubusercontent.com/yuchanahn/travel-agent/997fd29/docs/assets/portfolio-095-home-light.png)

<details>
<summary>구현 코드 · 일시적 파일 교체 실패만 제한적으로 재시도</summary>

`src/travel_agent/session_context.py` · `write_json` · 기준 `997fd29`.

```python
    for attempt in range(4):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt==3:raise
            time.sleep(.025*(attempt+1))

```
</details>

## 06 · 신뢰·설명가능성·컴플라이언스

**출처 표시 · 미확인 상태 · 사용자 선택 확정**

후보의 출처를 함께 보여주고, 계획서에서 조회·예상·미확인 비용을 분리합니다. 사용자가 직접 편집·선택 확정하며, 선택 확정은 실제 예약이나 가격 검증과 구분합니다. 금융 규정 준수·감사 체계를 구현한 프로젝트는 아닙니다.

![실제 계획서 · 합성 여행과 직접 입력한 시연용 숙박비](https://raw.githubusercontent.com/yuchanahn/travel-agent/997fd29/docs/assets/portfolio-095-plan-budget.png)

<details>
<summary>구현 코드 · 확정 작업은 사용자 요청에만 허용</summary>

`src/travel_agent/travel_plan.py` · `mutate` · 기준 `997fd29`.

```python
    elif action in {'confirm','delete'} and not model:
        item=next((x for x in out['items'] if x['id']==payload.get('id')),None)
        if item is None:raise ValueError('항목을 찾을 수 없습니다.')
        if action=='confirm':
            if type(payload.get('confirmed')) is not bool:raise ValueError('확정 여부는 true/false입니다.')
            item['confirmed']=payload['confirmed']
```
</details>

[GitHub](https://github.com/yuchanahn/travel-agent)
