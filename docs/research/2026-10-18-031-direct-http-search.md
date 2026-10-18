# 031: DDGS 런타임을 제거하고 덕덕고·Bing을 직접 요청하다

## 문제 정의와 좋은 결과

Bing만 직접 구현하고 덕덕고는 DDGS에 남기는 안에 사용자가 일관성 문제를 지적했다. 이미 앱이 엔진별 병렬 실행과 결과 통합을 맡고 있고, DDGS가 제공하던 덕덕고 요청·파서도 직접 소유할 수 있었다. 기본 검색 경로를 두 엔진의 직접 HTTP 요청으로 바꾸기로 했다.

<callout icon="💬" color="blue_bg">
	**개발 요청**
	차라리 그럴꺼면, DDGS를 버리고 덕덕고도 직접 HTTP 요청하지 왜?
</callout>

좋은 결과의 기준은 DDGS를 가져오지 않고 두 엔진을 직접 실행하며, 제목·주소·요약·엔진 출처를 제공하고, 한쪽 실패에도 나머지 결과를 보존하는 것이다. 라이브러리 제거와 봇 확인 해결은 별도로 검증한다. 두 엔진의 HTTP200·정상 파싱·기대 도메인 포함도 구분한다.

## 같은 검색어로 확인한 초기·변경 결과

LLM 없는 검색 도구에 먼저 세 가지 공개 질의를 보냈다. 초기 구현은 두 엔진 모두 urllib였고, 최종 구현은 덕덕고에 primp HTTP 클라이언트, Bing에 urllib를 직접 사용한다. 엔진별 파서·병렬 수집·결과 형식은 앱이 소유한다.

<callout icon="🔎" color="blue_bg">
	**실제 검색어**
	Python official website
</callout>

초기 urllib 경로는 DDG202·Bing200으로 Bing 결과만 반환했다. 최종 경로는 두 엔진 모두200으로 결과를 반환했다. 실제 최종 첫 결과는 다음과 같다.

> Welcome to Python.org
> https://www.python.org/

<callout icon="🔎" color="blue_bg">
	**실제 검색어**
	국립춘천박물관 공식 홈페이지
</callout>

초기 urllib 경로는 DDG202·Bing200으로 Bing 결과만 반환했다. 최종 경로는 두 엔진 모두200으로 결과를 반환했다. 실제 최종 첫 결과는 다음과 같다.

> 국립춘천박물관 - Museum
> https://chuncheon.museum.go.kr/kor/index.do

<callout icon="🔎" color="blue_bg">
	**실제 검색어**
	춘천 삼악산 호수케이블카 공식 홈페이지
</callout>

초기 urllib 경로는 DDG202·Bing200으로 Bing 결과만 반환했다. 최종 경로는 DDG202·Bing200으로 Bing 결과만 반환했다. 실제 최종 첫 결과는 다음과 같다.

> 춘천 삼악산 호수 케이블카
> https://samaksancablecar.com/

최종 비교에서 두 엔진 동시 성공은2/3, 결과에 목표 공식 도메인이 포함된 질의는3/3이었다. 부분 실패가 남아 비교 스크립트는 종료 코드1을 반환했다. 이 종료 조건은 모든 질의에서 모든 엔진 성공을 요구한다. 정상 결과를 받은 것과 검증 전체 통과를 구분한다.

## 실제 에이전트에 같은 질문을 보내기

029에서 보낸 질문을 그대로 사용했다. 그때는 덕덕고 성공·Bing 비활성화를 답했다. 이번에는 DDGS 없는 기본 경로로 실행했다.

<callout icon="💬" color="blue_bg">
	**실제 사용자 질문**
	국립춘천박물관 공식 홈페이지를 찾아줘. 검색에 사용한 엔진과 실패한 엔진도 알려줘.
</callout>

모델의 실제 최종 답변:

국립춘천박물관 공식 홈페이지는 다음과 같습니다.

*   **홈페이지 URL**: https://chuncheon.museum.go.kr/kor/index.do
*   **검색 엔진 상태**:
    *   성공: bing (5 개 결과)
    *   실패: duckduckgo (HTTP 오류 발생)

[web:7dbf48b80cbb29b7]

이번 모델 실행에서는 덕덕고가 다시202였고 Bing이 공식 주소를 반환했다. 모델도 그 부분 실패를 설명했다. 앞선 도구 단독 비교의 박물관 검색 성공을 모델 실행 시점의 성공으로 바꾸어 적지 않는다.

completed, 웹 도구1회·모델3회, 인용 검사 valid였다. 인용 누락 보정이1회 있었다. 보고된 입력 토큰5036·출력203, 전체12.821초다. 인용 ID 유효성과 답변의 모든 문장에 대한 사실 검증은 다르다. 이전 실행과의 토큰·속도 우위를 주장하지 않는다.

## 문제 분석과 구현 선택

DDGS 유지보수·Bing 무관한 응답·파싱 누락은 [030](https://github.com/yuchanahn/travel-agent/blob/79ed6e6/docs/research/2026-10-18-030-bing-maintenance-and-http-diagnosis.md)에 조사했다. DDGS를 제거한다고 서버의 무관한 결과가 없어지지는 않는다. 대신 요청 조건·파서·오류·실제 실행 엔진을 우리가 추적하고 바꿀 수 있다.

처음에는 단순 urllib를 두 사이트에 사용했다. 예비 덕덕고 요청은 urllib202·curl202였고, 이전 동작 경로의 인자를 유지한 직접 primp 요청은200이었다. 최종 도구 비교에서도 primp 덕덕고가2개 질의에서 성공했다. 다만 클라이언트·인자·시점이 함께 바뀌었으므로 특정 TLS 지문이나 파라미터가 원인이라고 확정하지 않는다. primp는 HTTP 라이브러리이며 DDGS나 실행 중인 브라우저가 아니다.

두 사이트의 HTTP 클라이언트는 달라도 직접 요청·자체 파서·공통 오류와 병합을 쓰는 구조는 같다. Bing에는030에서 성공한 q만 보내는 urllib 경로를 사용했다. 새 익명 클라이언트를 호출마다 만들고 로그인·파일 쿠키·유료 API·자동 엔진 대체·재시도는 추가하지 않았다.

## 해결한 것과 남는 책임

- 기본 공급자를 http로 변경했다. DDGS 엔진 클래스·DDGS 예외·DDGS 파서·DDGS URL 해석의 런타임 사용을 제거했다.
- 덕덕고와 Bing HTML을 앱에서 파싱한다. Bing의 h2와 링크가 분리된 형태도 읽고, 검색엔진 이동 링크를 목적지로 해석한다. HTTP(S)·길이·호스트·인증 정보·공백을 검사한다.
- 기존 엔진별 병렬 실행·RRF·중복 제거·부분 실패·출처를 유지했다. 모두 실패하면 도구 오류, 한쪽 성공하면 실제 엔진과 실패를 함께 반환한다.
- 기본 의존성은 lxml·primp다. DDGS는 과거 비교를 재현하는 search-research extra에만 남긴다. 이미 설치된 연구 패키지를 삭제한 것은 아니며 런타임에서 쓰지 않는다.
- 이전 WEB_SEARCH_PROVIDER=ddgs는 http로 바꾸도록 명시적 오류를 준다. README·환경 예시·현재 실행 문서·협업 정책·비교 스크립트를 맞췄다. webserp는 별도 명시적 연구 경로다.

사이트의 HTML 변경, 봇 확인, 관련성 검증을 직접 관리해야 한다. 현재 파서는 결과가 질문에 맞는지 일반적으로 판정하지 못한다.2MiB 크기 검사는 파싱 입력 한도이며 primp의 다운로드 메모리를 스트리밍으로 제한하는 구현은 아니다. urllib는 시스템 프록시를 따를 수 있다. 결과는 검색 요약이며 본문·실시간 운행·예약을 검증하지 않는다.

## 검증

전체115개 테스트와 pip check를 통과했다. DDGS import를 강제로 거부한 상태에서도 두 엔진 파싱·공통 통합이 동작하는 오프라인 회귀 검사를 포함했다. 네트워크 없는 회귀 검사와 위 실제 조회는 별개다.

```text
Ran 115 tests in 1.914s
OK
No broken requirements found.
```

실제 네트워크는 예비5회·초기 도구6회·최종 도구6회·에이전트 도구2회로 총19회였다. 실제 로컬 LLM3회 호출 비용은 위 토큰으로 기록했다. 무료·유료 API 할당은 사용하지 않았다. 예비 실패·부분 실패도 남긴다.

<details>
<summary>실제 코드·데이터 흐름·실행 방법</summary>
	기준 코드는79ed6e6이며 이 기록과 함께 변경한 src/travel_agent/web.py의 _request_html·_parse_search_html·_provider_search가 직접 요청·파싱·엔진 선택 경로다. _combined_search의 병렬 통합과 web_search의 출력 계약은 유지했다. src/travel_agent/agent.py는 trace의 기본 공급자를http로 맞췄다.
	```python
	def _provider_search(query, top_k, timeout, backend):
	    if backend not in SEARCH_URLS:
	        raise ValueError("HTTP search supports duckduckgo and bing only")
	    return _direct_search(query, top_k, timeout, backend)

	def _parse_search_html(text, engine):
	    """Extract organic titles, target URLs and snippets, including linkless Bing h2."""
	    tree = html.fromstring(text)
	    selector = _class_xpath("div", "result__body") if engine == "duckduckgo" else _class_xpath("li", "b_algo")
	    rows = []
	    for card in tree.xpath(selector):
	        headings = card.xpath('.//h2')
	        if not headings:
	            continue
	        title = " ".join(headings[0].text_content().split())
	        anchors = headings[0].xpath('.//a[@href]') or card.xpath('.//a[@href]')
	        target = next((url for anchor in anchors if (url := _unwrap_search_url(anchor.get('href'), engine))), None)
	        snippets = card.xpath('.//a[contains(concat(" ", normalize-space(@class), " "), " result__snippet ")]') if engine == "duckduckgo" else card.xpath('.//p')
	        snippet = " ".join(" ".join(node.text_content().split()) for node in snippets)
	        if title and target:
	            rows.append({"title": title, "href": target, "body": snippet})
	    return rows
	```
	첫 조각은 검색 SDK 없이 사이트별 요청을 선택하는 부분이다. 두 번째는 제목과 링크를 독립적으로 읽어 Bing HTML 변형을 지원하는 파서다. URL 해석은 _unwrap_search_url, 공통 검증은 _clean_url이 수행한다.
	```mermaid
	flowchart TD
	    M[모델 web_search 요청] --> W[인자 검사 및 http 공급자]
	    W --> D[덕덕고 직접 GET: primp]
	    W --> B[Bing 직접 GET: urllib]
	    D --> P[자체 HTML 파서 및 URL 검증]
	    B --> P
	    P --> R[엔진별 결과와 오류]
	    R --> F[URL 중복 제거 및 RRF]
	    F --> T[출처와 부분 실패를 모델에 전달]
	    T --> A[최종 답변 및 trace]
	```
	```powershell
	python -m pip install -e .
	travel-agent web search "국립춘천박물관 공식 홈페이지" --provider http --backend duckduckgo,bing
	python scripts/evaluate_search_fusion.py
	python -m unittest discover -s tests -q
	```
</details>

<details>
<summary>실제 툴콜 로그 — 모델 요청·엔진 실행·모델에 전달한 결과</summary>
	공개 질의만 사용했다. 원본 응답·쿠키·헤더는 공개하지 않는다. 시각은UTC다. 아래 도구 단독 실행에는 모델 호출이 없다.

	**초기 urllib 경로 / web_search / 2927e521bf4d46c8bee04d1b23529850**
	- 실제 인자: `{"query": "Python official website", "top_k": 3}`
	- 실제 시각: 2026-10-18T07:00:27.986833+00:00 → 2026-10-18T07:00:28.352999+00:00
	- 엔진 실행 결과: `{"duckduckgo": {"status": "error", "reason": "http_error", "http_status": 202, "method": "GET", "start_ms": 1, "elapsed_ms": 365}, "bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 2, "elapsed_ms": 348}}`
	- duckduckgo 실제 HTTP 인자: `{"q": "Python official website", "kl": "kr-kr"}`
	- bing 실제 HTTP 인자: `{"q": "Python official website"}`
	- 첫 결과: Welcome to Python.org — https://www.python.org/

	**초기 urllib 경로 / web_search / 8f1d7afcd3894c58b61abd2cd0783af0**
	- 실제 인자: `{"query": "국립춘천박물관 공식 홈페이지", "top_k": 3}`
	- 실제 시각: 2026-10-18T07:00:28.354505+00:00 → 2026-10-18T07:00:28.764669+00:00
	- 엔진 실행 결과: `{"duckduckgo": {"status": "error", "reason": "http_error", "http_status": 202, "method": "GET", "start_ms": 0, "elapsed_ms": 393}, "bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 1, "elapsed_ms": 408}}`
	- duckduckgo 실제 HTTP 인자: `{"q": "국립춘천박물관 공식 홈페이지", "kl": "kr-kr"}`
	- bing 실제 HTTP 인자: `{"q": "국립춘천박물관 공식 홈페이지"}`
	- 첫 결과: 국립춘천박물관 - Museum — https://chuncheon.museum.go.kr/kor/index.do

	**초기 urllib 경로 / web_search / c4ed050cf5284613be5601b85a320532**
	- 실제 인자: `{"query": "춘천 삼악산 호수케이블카 공식 홈페이지", "top_k": 3}`
	- 실제 시각: 2026-10-18T07:00:28.766090+00:00 → 2026-10-18T07:00:29.143171+00:00
	- 엔진 실행 결과: `{"duckduckgo": {"status": "error", "reason": "http_error", "http_status": 202, "method": "GET", "start_ms": 0, "elapsed_ms": 375}, "bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 1, "elapsed_ms": 274}}`
	- duckduckgo 실제 HTTP 인자: `{"q": "춘천 삼악산 호수케이블카 공식 홈페이지", "kl": "kr-kr"}`
	- bing 실제 HTTP 인자: `{"q": "춘천 삼악산 호수케이블카 공식 홈페이지"}`
	- 첫 결과: 춘천 삼악산 호수 케이블카 — https://samaksancablecar.com/

	**최종 직접 HTTP 경로 / web_search / 8e4e1420b9c346a3a745424610868250**
	- 실제 인자: `{"query": "Python official website", "top_k": 3}`
	- 실제 시각: 2026-10-18T07:01:14.039559+00:00 → 2026-10-18T07:01:15.179827+00:00
	- 엔진 실행 결과: `{"duckduckgo": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 1, "elapsed_ms": 1138}, "bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 2, "elapsed_ms": 278}}`
	- duckduckgo 실제 HTTP 인자: `{"q": "Python official website", "b": "", "l": "kr-kr"}`
	- bing 실제 HTTP 인자: `{"q": "Python official website"}`
	- 첫 결과: Welcome to Python.org — https://www.python.org/

	**최종 직접 HTTP 경로 / web_search / 440d396d6543463496f20e8d632c73d0**
	- 실제 인자: `{"query": "국립춘천박물관 공식 홈페이지", "top_k": 3}`
	- 실제 시각: 2026-10-18T07:01:15.181847+00:00 → 2026-10-18T07:01:16.038199+00:00
	- 엔진 실행 결과: `{"duckduckgo": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 0, "elapsed_ms": 856}, "bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 1, "elapsed_ms": 258}}`
	- duckduckgo 실제 HTTP 인자: `{"q": "국립춘천박물관 공식 홈페이지", "b": "", "l": "kr-kr"}`
	- bing 실제 HTTP 인자: `{"q": "국립춘천박물관 공식 홈페이지"}`
	- 첫 결과: 국립춘천박물관 - Museum — https://chuncheon.museum.go.kr/kor/index.do

	**최종 직접 HTTP 경로 / web_search / cab73e873626448d97c1befe9afe7ef5**
	- 실제 인자: `{"query": "춘천 삼악산 호수케이블카 공식 홈페이지", "top_k": 3}`
	- 실제 시각: 2026-10-18T07:01:16.039211+00:00 → 2026-10-18T07:01:16.337011+00:00
	- 엔진 실행 결과: `{"duckduckgo": {"status": "error", "reason": "http_error", "http_status": 202, "method": "GET", "start_ms": 0, "elapsed_ms": 296}, "bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 1, "elapsed_ms": 246}}`
	- duckduckgo 실제 HTTP 인자: `{"q": "춘천 삼악산 호수케이블카 공식 홈페이지", "b": "", "l": "kr-kr"}`
	- bing 실제 HTTP 인자: `{"q": "춘천 삼악산 호수케이블카 공식 홈페이지"}`
	- 첫 결과: 춘천 삼악산 호수 케이블카 — https://samaksancablecar.com/

	**예비 직접 HTTP 비교**
	- exec c43aa4: 박물관 질의, urllib·Accept-Language ko-KR,ko;q=0.9,en;q=0.8, q만 전송. DDG202(봇 확인 표식), Bing200.
	- exec 7e5185: 같은 질의, curl edge101, q만 전송. DDG202(봇 확인 표식), Bing200.
	- exec c0d827: 같은 질의, primp random, q·b 빈 문자열·l=kr-kr. DDG200·봇 확인 표식 없음.
	- 예비 요청별 별도 호출 ID·시각은 수집하지 않았다. 위 exec 호출로 구분한다.

	**실제 모델 실행 — 요청 8d66898ab1ab4cbe9cb9450f8d326311**
	- 모델 요청: call_20idqixo; web_search; `{"query": "국립춘천박물관 공식 홈페이지", "top_k": 5}`; 2026-10-18T07:02:01.678108+00:00; span 1.1
	- 같은 span의 실행 종료: 2026-10-18T07:02:02.068883+00:00; 0.3901초
	- 엔진 결과: `{"duckduckgo": {"status": "error", "reason": "http_error", "http_status": 202, "method": "GET", "start_ms": 1, "elapsed_ms": 389}, "bing": {"status": "ok", "hits": 5, "method": "GET", "http_status": 200, "start_ms": 1, "elapsed_ms": 236}}`
	- 다음 모델 입력: 도구 결과 provider=http, search_complete=false, Bing 결과5개·출처 ID와 DDG202 오류가 전달됐다.
	- 반환 첫 근거: web:7dbf48b80cbb29b7; 국립춘천박물관 - Museum — https://chuncheon.museum.go.kr/kor/index.do
	- 모델의 실제 최종 답변은 본문에 있다. 도구 단독 비교와 모델 실행의 결과를 혼동하지 않는다.
</details>
