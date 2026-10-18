# 035: 검색 응답 변동을 확인하고 출력 예산 안에서 문단을 다시 고르다

## 문제 정의와 실제 검색 결과

034의 수집·재정렬 경로를 만든 뒤에도 관련 자료가 원래 후보에 없거나, 있어도 출력 과정에서 뒤의 근거를 잃는 문제가 남았다. 사용자는 에이전트 평가에 앞서 웹검색 툴을 충분히 검증하고 내장 검색과 품질을 맞추길 원했다. 이번에는 요청 옵션 비교와 동일한 저장 본문에서의 출력 비교를 분리했다.

<callout icon="🔎" color="blue_bg">
	**실제 검색어1**
	국립춘천박물관 관람시간 휴관일 교통
</callout>

034의 마지막 실행은 국립중앙도서관·국립국어원·표준국어대사전을 앞에 반환했고 최종 후보는0개였다. 이번에는 같은 q만 보낸 대조군에서도 [국립춘천박물관 공식 첫 화면](https://chuncheon.museum.go.kr/kor/index.do)과 [공식 관람안내](https://chuncheon.museum.go.kr/kor/sub01_0101.do)가 나왔다.

<callout icon="🔎" color="blue_bg">
	**실제 검색어2**
	Python asyncio TaskGroup cancellation official documentation
</callout>

034에서는 Python 일반 첫 화면·다운로드·온라인 실행기가 앞에 나왔다. 이번 q만 보낸 대조군의 첫 결과는 [TaskGroup 상세 공식 문서](https://docs.python.org/3/library/asyncio-task.html)였다. 즉 새 수정 없이도 응답이 달라졌다. 옵션 하나를 정답으로 고르거나 검색이 안정화됐다고 주장할 근거는 아니다.

## 요청 옵션과 검색어 변경을 구분한 조사

같은 쿼리에서 q만 전송, mkt 지정, qs=n·form=QBRE, count=50을 비교하고, 별도로 따옴표·집중 검색어를 실험했다. 브라우저·다른 엔진·LLM은 호출하지 않았다. 실제 curl_cffi 요청은 최대3worker로 실행했고 총12회였다.

| 사례 | 변형 | 실제 q | HTTP | 카드 | 목표 공식 주소 확보 |
|---|---|---|---|---|---|
| museum | baseline | 국립춘천박물관 관람시간 휴관일 교통 | 200 | 10 | True |
| museum | market | 국립춘천박물관 관람시간 휴관일 교통 | 200 | 10 | True |
| museum | form | 국립춘천박물관 관람시간 휴관일 교통 | 200 | 10 | True |
| museum | count | 국립춘천박물관 관람시간 휴관일 교통 | 200 | 10 | True |
| museum | quoted | "국립춘천박물관" 관람시간 휴관일 교통 | 200 | 10 | True |
| museum | focused | 국립춘천박물관 | 200 | 파싱 실패 | ParserError |
| technical | baseline | Python asyncio TaskGroup cancellation official documentation | 200 | 10 | True |
| technical | market | Python asyncio TaskGroup cancellation official documentation | 200 | 10 | False |
| technical | form | Python asyncio TaskGroup cancellation official documentation | 200 | 10 | True |
| technical | count | Python asyncio TaskGroup cancellation official documentation | 200 | 10 | True |
| technical | quoted | Python asyncio "TaskGroup" cancellation official documentation | 200 | 10 | True |
| technical | focused | TaskGroup cancellation Python asyncio | 200 | 10 | True |

count=50도 실제 카드는10개였다. 이 환경에서 요청 숫자를 곧 수집 숫자로 볼 수 없다. mkt=en-US를 붙인 Python 응답은 Finix 요금 페이지 등 무관한 결과였고, 박물관 이름만 보낸 focused 요청은200 뒤 파싱에 실패했다. 실패를 숨기지 않았다. 표본이 작고 시간·세션·서버 상태를 통제하지 못했으므로 요청 기본값은 바꾸지 않았다.

## 같은 코드로 검색 파이프라인을 반복 실행

본문 선택 변경 전 코드9819c1b로 다시 세 질의를 실행했다. 이 반복은 과거034와 같은 HTTP 응답을 재사용한 것이 아니다. 따라서 아래 차이를 압축 수정의 효과로 계산하지 않는다.

| 검색어 | 받은 카드 | 묶음 | 실제 전달 | 본문 발췌 | 출력 바이트 |
|---|---|---|---|---|---|
| 국립춘천박물관 관람시간 휴관일 교통 | 20 | 10 | 5 | 5 | 5134 |
| 강릉 비오는날 부모님 실내 여행 걷기 적은 곳 | 26 | 10 | 5 | 3 | 4545 |
| Python asyncio TaskGroup cancellation official documentation | 20 | 10 | 5 | 4 | 4882 |

이번에는 춘천·Python의 비교 기준 공식 문서가 모두 후보와 출력에 있었다. 강릉은 다른 여행 자료를 확보했지만 부모님의 걷기 부담을 판단할 근거가 발췌에 남았는지는 별개다. 세 사례 모두 반복 페이지를 감지해 중단했고 수십·수백 개의 고유 자료를 확보했다고 기록하지 않았다.

## 문제 분석: 문단 선택 뒤 앞부분을 자르면 근거를 잃는다

034의 순서는 관련 문단을 최대1000자로 고른 뒤 출처별 바이트 예산에 맞춰 앞부분을 자르는 방식이었다. 문단을 원래 문서 순서로 돌려놓고 자르기 때문에, 뒤에서 선택한 중요한 문장이 출력에서 사라질 수 있었다. 개선은 **출처별 예산을 먼저 정하고, 전체 추출본에서 그 예산에 들어가는 문단을 선택하는 것**이다. 모델 요약을 추가하지 않고 원문 발췌로 유지한다.

```mermaid
flowchart LR
 A[저장된 전체 추출본] --> B[출처별 UTF-8 예산 계산]
 B --> C[예산에 맞는 작은 문단 묶음]
 C --> D[질의에 대한 BM25Plus 순위]
 D --> E[최대3묶음: 총 예산 안에서 선택]
 E --> F[문서 순서 복원과 출처 표기]
 F --> G[전체 출력6000바이트 확인]
```

## 같은 원문·같은 예산에서의 검증

앞의 반복 실행에서 저장한 HTML과 추출본을 그대로 사용해 다시 패킷을 만들었다. 추가 네트워크 요청0회, 모델 호출0회다. q·선택 출처·전체6000바이트 한도를 고정했다. 각 표식은 제목·질의 헤더를 제외하고 실제 전달 본문에서 검사했다. 표식 유무는 문장 의미나 예외 조건의 보존 점수가 아니다.

| 사례 | 이전 출력 바이트 | 개선 출력 바이트 | 전달 본문 표식: 이전 → 이후 |
|---|---|---|
| museum | 5134 | 4573 | 09:00: True → True, 18:00: True → True, 월요일: True → True |
| rainy | 4545 | 4304 | 부모님: False → False, 걷: False → False |
| technical | 4882 | 4032 | TaskGroup: True → True, CancelledError: True → True, ExceptionGroup: True → True |

Python 공식 상세 문서만 따로 보면 이전에는 TaskGroup·CancelledError는 있었으나 ExceptionGroup은 빠졌고, 개선 후에는 세 표식이 모두 남았다. 다만 다른 블로그 한 출처에서는 반대로 ExceptionGroup 표식이 빠졌다. 패킷 전체에서는 이전에도 다른 출처에 그 표식이 있었으므로 전체 품질 상승으로 일반화하지 않는다.

<callout icon="🔎" color="blue_bg">
	**발췌 비교에 사용한 원래 검색어**
	Python asyncio TaskGroup cancellation official documentation
</callout>

이전 공식 문서 발췌의 시작은 Future 사용 예제였다. 실제 첫 줄은 다음과 같았다.

> async def main():
>     await function_that_returns_a_future_object()

개선 발췌에는 공식 문서의 다음 구절도 들어왔다.

> those exceptions are combined in an
> `ExceptionGroup` or `BaseExceptionGroup`

강릉은 개선 전후 모두 전달 본문에 부모님·걷 표식이 없었다. 질문 헤더에 그 단어가 있다는 것을 근거 보존으로 세지 않았다. 따라서 여행 조건 충족은 계속 미달이다. 출력 바이트는 줄었지만 입력 토큰 수·비용 절감은 측정하지 않았다.

## 실제 구현과 선택 이유

기준 커밋9819c1b에 대해 `src/travel_agent/web_pipeline.py`의 `passages`와 `pack_digest`를 수정했다. 원문 전체는 내부 선택에만 사용하고 반환 source에는 넣지 않는다. 최대600자 문단 묶음 크기도 가용 바이트에 맞춰 줄이고, 선택 중 UTF-8 바이트 한도를 검사한다. 실제 선택 코드 발췌는 다음과 같다.

```python
        if source.get('_page_text'):
            text, selected_blocks = passages(source['_page_text'],query,max_bytes=available)
            if not text:
                continue
            shortened = text != source['_page_text']
        else:
            shortened = len(body.encode()) > available
            text = body.encode()[:available].decode('utf-8',errors='ignore') if shortened else body
```

`scripts/repack_search_evidence.py`는 검색 응답을 바꾸지 않고 위 출력을 재현한다. `scripts/probe_bing_query_quality.py`는 직접 HTTP 조사 전용이고 운영 기본값을 바꾸지 않는다. 실제 원문·HTTP 이벤트·전후 패킷은 비공개에 보존한다.

## 검증 결과와 남은 한계

Python133개 테스트가 통과했다. 추가 회귀 검사는 앞에 긴 도입부가 있고 뒤에 관람시간·휴관·교통 문장이 있을 때, 전체 예산 안에서 뒤의 문장을 고르는지 확인한다. 파이프라인의 검색 품질 통과를 의미하지는 않는다.

수집 결과의 변동, 반복 페이지, 핵심 개체 구분, 걷기 부담 같은 조건을 담은 본문 확보, 문단 선택과 숫자·예외의 의미 보존이 남아 있다. 현재 상태는 독립 검색 파이프라인을 구현하고 한 압축 손실 경로를 수정한 것이며 내장 검색 동등 품질 완료가 아니다. 에이전트 연결과 답변 평가는 보류한다.

<details>
<summary>실제 검색 HTTP·본문 요청·오프라인 재구성 기록</summary>

	```json
	{"id": "9cdec2cbd6e1405cb2740a1c07b21bc8", "case": "museum", "variant": "baseline", "tool": "bing_http_query_probe", "arguments": {"q": "국립춘천박물관 관람시간 휴관일 교통"}, "started_at": "2026-10-18T12:23:55.438783+00:00", "http_status": 200, "response_bytes": 540316, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:55.914986+00:00"}
	```

	```json
	{"id": "bedef0c83cb543a3aa97cf151f21efc9", "case": "museum", "variant": "market", "tool": "bing_http_query_probe", "arguments": {"q": "국립춘천박물관 관람시간 휴관일 교통", "mkt": "ko-KR"}, "started_at": "2026-10-18T12:23:55.438783+00:00", "http_status": 200, "response_bytes": 553282, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:55.876307+00:00"}
	```

	```json
	{"id": "bc91af780b194bc1901af55d98e5e1f3", "case": "museum", "variant": "form", "tool": "bing_http_query_probe", "arguments": {"q": "국립춘천박물관 관람시간 휴관일 교통", "qs": "n", "form": "QBRE"}, "started_at": "2026-10-18T12:23:55.438783+00:00", "http_status": 200, "response_bytes": 559148, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:55.972173+00:00"}
	```

	```json
	{"id": "9feceef9f0454e0ead3114bae7f955d8", "case": "museum", "variant": "count", "tool": "bing_http_query_probe", "arguments": {"q": "국립춘천박물관 관람시간 휴관일 교통", "count": "50"}, "started_at": "2026-10-18T12:23:55.876307+00:00", "http_status": 200, "response_bytes": 123442, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:56.080809+00:00"}
	```

	```json
	{"id": "0ee5853b92d5432288c4d4016daf1c96", "case": "museum", "variant": "quoted", "tool": "bing_http_query_probe", "arguments": {"q": "\"국립춘천박물관\" 관람시간 휴관일 교통"}, "started_at": "2026-10-18T12:23:55.915493+00:00", "http_status": 200, "response_bytes": 509531, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:56.376440+00:00"}
	```

	```json
	{"id": "234e4339029a4f6383c1cd114466e90f", "case": "museum", "variant": "focused", "tool": "bing_http_query_probe", "arguments": {"q": "국립춘천박물관"}, "started_at": "2026-10-18T12:23:55.976668+00:00", "http_status": 200, "response_bytes": 0, "error": "ParserError", "finished_at": "2026-10-18T12:23:56.056382+00:00"}
	```

	```json
	{"id": "66984521d21d446a8bb22eea28e77780", "case": "technical", "variant": "baseline", "tool": "bing_http_query_probe", "arguments": {"q": "Python asyncio TaskGroup cancellation official documentation"}, "started_at": "2026-10-18T12:23:56.056515+00:00", "http_status": 200, "response_bytes": 437905, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:56.639310+00:00"}
	```

	```json
	{"id": "948c19abbdbb45a4906fc8065403d8b8", "case": "technical", "variant": "market", "tool": "bing_http_query_probe", "arguments": {"q": "Python asyncio TaskGroup cancellation official documentation", "mkt": "en-US"}, "started_at": "2026-10-18T12:23:56.080809+00:00", "http_status": 200, "response_bytes": 115288, "result_cards": 10, "parsed_results": 10, "target_found": false, "finished_at": "2026-10-18T12:23:56.251859+00:00"}
	```

	```json
	{"id": "71a78de70794452c91754f39d4005f1b", "case": "technical", "variant": "form", "tool": "bing_http_query_probe", "arguments": {"q": "Python asyncio TaskGroup cancellation official documentation", "qs": "n", "form": "QBRE"}, "started_at": "2026-10-18T12:23:56.251859+00:00", "http_status": 200, "response_bytes": 438752, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:56.756363+00:00"}
	```

	```json
	{"id": "09016b5a432d437ebfe6eed0055c380b", "case": "technical", "variant": "count", "tool": "bing_http_query_probe", "arguments": {"q": "Python asyncio TaskGroup cancellation official documentation", "count": "50"}, "started_at": "2026-10-18T12:23:56.376440+00:00", "http_status": 200, "response_bytes": 115462, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:56.545047+00:00"}
	```

	```json
	{"id": "b1d157cf61ad4eb987caf82f3acaeb03", "case": "technical", "variant": "quoted", "tool": "bing_http_query_probe", "arguments": {"q": "Python asyncio \"TaskGroup\" cancellation official documentation"}, "started_at": "2026-10-18T12:23:56.546563+00:00", "http_status": 200, "response_bytes": 454496, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:57.005941+00:00"}
	```

	```json
	{"id": "31f0276b3663499d81d1b85ccbb2ebcc", "case": "technical", "variant": "focused", "tool": "bing_http_query_probe", "arguments": {"q": "TaskGroup cancellation Python asyncio"}, "started_at": "2026-10-18T12:23:56.639834+00:00", "http_status": 200, "response_bytes": 430354, "result_cards": 10, "parsed_results": 10, "target_found": true, "finished_at": "2026-10-18T12:23:57.118055+00:00"}
	```

	**파이프라인 실행 67392464ef824a94ac850c84f3dd6614** — 국립춘천박물관 관람시간 휴관일 교통

	```json
	{"id": "51bf77d983b34ecfa63f7e862841e04b", "tool": "bing_search_http", "query": "국립춘천박물관 관람시간 휴관일 교통", "page": 1, "first": 1, "started_at": "2026-10-18T12:24:17.414074+00:00", "method": "GET", "http_transport": "curl", "http_status": 200, "response_bytes": 518577, "pagination_param_names": [], "result_cards": 10, "parsed_results": 10, "new_urls": 10, "finished_at": "2026-10-18T12:24:18.032794+00:00"}
	```

	```json
	{"id": "29257d28b4d64e2aa33f6db622b4a235", "tool": "bing_search_http", "query": "국립춘천박물관 관람시간 휴관일 교통", "page": 2, "first": 11, "started_at": "2026-10-18T12:24:18.033819+00:00", "method": "GET", "http_transport": "curl", "http_status": 200, "response_bytes": 123801, "pagination_param_names": ["FORM", "FPIG"], "result_cards": 10, "parsed_results": 10, "new_urls": 0, "finished_at": "2026-10-18T12:24:18.275447+00:00"}
	```

	```json
	{"id": "658cdb01b2f744678a0af52ff28bcf4a", "tool": "page_http_extract", "url": "https://www.ktravelmate.com/ko/chuncheon-city/place/130654", "started_at": "2026-10-18T12:24:18.292924+00:00", "method": "GET", "http_status": 200, "download_bytes": 147956, "extracted_bytes": 2904, "selected_blocks": [1, 2], "excerpt_bytes": 2387, "selection_status": "ok", "finished_at": "2026-10-18T12:24:19.444659+00:00"}
	```

	```json
	{"id": "c247bddfbb524373ab54cc6beca5c7d9", "tool": "page_http_extract", "url": "https://chuncheon.museum.go.kr/kor/sub01_0101.do", "started_at": "2026-10-18T12:24:18.293452+00:00", "method": "GET", "http_status": 200, "download_bytes": 146916, "extracted_bytes": 3979, "selected_blocks": [0, 1], "excerpt_bytes": 1238, "selection_status": "ok", "finished_at": "2026-10-18T12:24:18.856515+00:00"}
	```

	```json
	{"id": "00004302fe85477bab5dfb9720025f45", "tool": "page_http_extract", "url": "https://m.blog.naver.com/zavawork07/224163758274", "started_at": "2026-10-18T12:24:18.293969+00:00", "method": "GET", "http_status": 200, "download_bytes": 193772, "extracted_bytes": 381, "selected_blocks": [0], "excerpt_bytes": 371, "selection_status": "ok", "finished_at": "2026-10-18T12:24:19.050735+00:00"}
	```

	```json
	{"id": "3b10e370e12142669ab8857628c4f1f9", "tool": "page_http_extract", "url": "https://chuncheon.museum.go.kr/kor/index.do", "started_at": "2026-10-18T12:24:18.856515+00:00", "method": "GET", "http_status": 200, "download_bytes": 147291, "extracted_bytes": 662, "selected_blocks": [0], "excerpt_bytes": 655, "selection_status": "ok", "finished_at": "2026-10-18T12:24:19.212327+00:00"}
	```

	```json
	{"id": "30730bc8bf704a1087236da48528ce23", "tool": "page_http_extract", "url": "https://m.blog.naver.com/jinnn25/223190041563", "started_at": "2026-10-18T12:24:19.050735+00:00", "method": "GET", "http_status": 200, "download_bytes": 90652, "extracted_bytes": 2342, "selected_blocks": [0, 1, 2], "excerpt_bytes": 2325, "selection_status": "ok", "finished_at": "2026-10-18T12:24:19.248688+00:00"}
	```

	**파이프라인 실행 5def451ddabc43a1849453a5bdb55255** — 강릉 비오는날 부모님 실내 여행 걷기 적은 곳

	```json
	{"id": "698c3a96db9f4922b613703937797d04", "tool": "bing_search_http", "query": "강릉 비오는날 부모님 실내 여행 걷기 적은 곳", "page": 1, "first": 1, "started_at": "2026-10-18T12:24:19.448914+00:00", "method": "GET", "http_transport": "curl", "http_status": 200, "response_bytes": 425929, "pagination_param_names": [], "result_cards": 6, "parsed_results": 6, "new_urls": 6, "finished_at": "2026-10-18T12:24:20.063675+00:00"}
	```

	```json
	{"id": "eccc70e338cb453a8e04f5c26013ffcd", "tool": "bing_search_http", "query": "강릉 비오는날 부모님 실내 여행 걷기 적은 곳", "page": 2, "first": 7, "started_at": "2026-10-18T12:24:20.064739+00:00", "method": "GET", "http_transport": "curl", "http_status": 200, "response_bytes": 126791, "pagination_param_names": ["FORM", "FPIG"], "result_cards": 10, "parsed_results": 10, "new_urls": 4, "finished_at": "2026-10-18T12:24:20.244940+00:00"}
	```

	```json
	{"id": "cce1cbd651ce42b680e70369a920625a", "tool": "bing_search_http", "query": "강릉 비오는날 부모님 실내 여행 걷기 적은 곳", "page": 3, "first": 11, "started_at": "2026-10-18T12:24:20.245601+00:00", "method": "GET", "http_transport": "curl", "http_status": 200, "response_bytes": 122485, "pagination_param_names": ["FORM", "FPIG"], "result_cards": 10, "parsed_results": 10, "new_urls": 0, "finished_at": "2026-10-18T12:24:20.493314+00:00"}
	```

	```json
	{"id": "cfdb4a51f0bb4e68b6e45a34df427cdb", "tool": "page_http_extract", "url": "https://blog.naver.com/smile11410/224352305991", "started_at": "2026-10-18T12:24:20.510441+00:00", "method": "GET", "http_status": 200, "download_bytes": 2860, "error": {"reason": "empty_extraction"}, "finished_at": "2026-10-18T12:24:20.696636+00:00"}
	```

	```json
	{"id": "fa929290f69947acab3fd8ae36451966", "tool": "page_http_extract", "url": "https://m.blog.naver.com/yj5891_/224338070006", "started_at": "2026-10-18T12:24:20.510441+00:00", "method": "GET", "http_status": 200, "download_bytes": 166859, "extracted_bytes": 5026, "selected_blocks": [0, 4, 5], "excerpt_bytes": 1961, "selection_status": "ok", "finished_at": "2026-10-18T12:24:20.882481+00:00"}
	```

	```json
	{"id": "9b87b24b6c764158b05dea2107192a48", "tool": "page_http_extract", "url": "https://blog.naver.com/everydaygoodshot/224401655050", "started_at": "2026-10-18T12:24:20.513961+00:00", "method": "GET", "http_status": 200, "download_bytes": 2874, "error": {"reason": "empty_extraction"}, "finished_at": "2026-10-18T12:24:20.663460+00:00"}
	```

	```json
	{"id": "3e281ca3a18a48bb8b32498f9272bf9e", "tool": "page_http_extract", "url": "https://m.blog.naver.com/yudory_/224377910315", "started_at": "2026-10-18T12:24:20.663460+00:00", "method": "GET", "http_status": 200, "download_bytes": 180164, "extracted_bytes": 6547, "selected_blocks": [2, 6], "excerpt_bytes": 1575, "selection_status": "ok", "finished_at": "2026-10-18T12:24:21.008848+00:00"}
	```

	```json
	{"id": "79b697e4641444999986cd73b7e05c3a", "tool": "page_http_extract", "url": "https://seoulbest3.latteis.co.kr/2026/06/best-5_01708485149.html", "started_at": "2026-10-18T12:24:20.696636+00:00", "method": "GET", "http_status": 200, "download_bytes": 806788, "extracted_bytes": 3573, "selected_blocks": [0, 1], "excerpt_bytes": 1637, "selection_status": "ok", "finished_at": "2026-10-18T12:24:23.131492+00:00"}
	```

	**파이프라인 실행 3ead5ae9132844d794ac51ad9ecef4be** — Python asyncio TaskGroup cancellation official documentation

	```json
	{"id": "b2405e7c2a7c43cea900a9dee0304f75", "tool": "bing_search_http", "query": "Python asyncio TaskGroup cancellation official documentation", "page": 1, "first": 1, "started_at": "2026-10-18T12:24:23.137216+00:00", "method": "GET", "http_transport": "curl", "http_status": 200, "response_bytes": 459863, "pagination_param_names": [], "result_cards": 10, "parsed_results": 10, "new_urls": 10, "finished_at": "2026-10-18T12:24:23.567985+00:00"}
	```

	```json
	{"id": "7a5296d4dc574f6b8d69fe83128d0dd3", "tool": "bing_search_http", "query": "Python asyncio TaskGroup cancellation official documentation", "page": 2, "first": 11, "started_at": "2026-10-18T12:24:23.570131+00:00", "method": "GET", "http_transport": "curl", "http_status": 200, "response_bytes": 116253, "pagination_param_names": ["FORM", "FPIG"], "result_cards": 10, "parsed_results": 10, "new_urls": 0, "finished_at": "2026-10-18T12:24:23.736776+00:00"}
	```

	```json
	{"id": "8025b142b9b54ebdb460293a533d2b25", "tool": "page_http_extract", "url": "https://asyncio-cancel-token.readthedocs.io/en/latest/cancel_token.html", "started_at": "2026-10-18T12:24:23.804932+00:00", "method": "GET", "http_status": 200, "download_bytes": 19708, "extracted_bytes": 3599, "selected_blocks": [0, 1], "excerpt_bytes": 850, "selection_status": "ok", "finished_at": "2026-10-18T12:24:24.389977+00:00"}
	```

	```json
	{"id": "d8f54daf42054a88928e0f1660226f3d", "tool": "page_http_extract", "url": "https://docs.python.org/3/library/asyncio.html", "started_at": "2026-10-18T12:24:23.806443+00:00", "method": "GET", "http_status": 200, "download_bytes": 25411, "extracted_bytes": 2245, "selected_blocks": [1, 4], "excerpt_bytes": 800, "selection_status": "ok", "finished_at": "2026-10-18T12:24:24.295063+00:00"}
	```

	```json
	{"id": "ff96a1f82c664129a405682e220fe8e0", "tool": "page_http_extract", "url": "https://docs.python.org/3/library/asyncio-task.html", "started_at": "2026-10-18T12:24:23.806443+00:00", "method": "GET", "http_status": 200, "download_bytes": 177177, "extracted_bytes": 44421, "selected_blocks": [10, 16, 42], "excerpt_bytes": 855, "selection_status": "ok", "finished_at": "2026-10-18T12:24:24.440336+00:00"}
	```

	```json
	{"id": "a69ea9973070414d9a8f67f38f3cdf51", "tool": "page_http_extract", "url": "https://universopython.com/en/blog/python-asyncio-taskgroup", "started_at": "2026-10-18T12:24:24.295063+00:00", "method": "GET", "http_status": 200, "download_bytes": 60359, "extracted_bytes": 8783, "selected_blocks": [0, 2, 7], "excerpt_bytes": 942, "selection_status": "ok", "finished_at": "2026-10-18T12:24:26.612896+00:00"}
	```

	```json
	{"id": "710b3369b8894b89aad01a22f29ff497", "tool": "page_http_extract", "url": "https://superfastpython.com/asyncio-taskgroup", "started_at": "2026-10-18T12:24:24.389977+00:00", "error": {"reason": "http_error", "method": "GET", "http_status": 301}, "finished_at": "2026-10-18T12:24:24.718685+00:00"}
	```

	```json
	{"id": "26f97b582dc24fd99cb57f1db9ab4b12", "tool": "offline_repack", "started_at": "2026-10-18T12:25:58.664590+00:00", "network_requests": 0, "model_invoked": false, "finished_at": "2026-10-18T12:25:58.697388+00:00"}
	```

	모델이 요청한 도구 호출과 다음 모델 입력은 없었다. 검색은 Bing 직접 HTTP이고 본문은 선택 URL의 공개 주소 검증을 거쳐 읽었다. 시각은 UTC다. 인증 헤더·쿠키·추적 매개변수 값은 공개하지 않았다.

</details>
