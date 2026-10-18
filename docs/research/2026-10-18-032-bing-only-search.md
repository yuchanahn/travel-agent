# 032: 덕덕고를 제거하고 Bing 단독 검색으로 정리하다

## 문제 정의·결정

<callout icon="💬" color="blue_bg">
	**개발 요청**
	덕덕고 버리자....
</callout>

031에서 덕덕고202가 반복되고 실제 에이전트도 Bing 결과만 사용했다. 사용자는 덕덕고를 중단하기로 했다. 좋은 결과의 기준은 기본 검색과 명시적 설정 모두에서 덕덕고를 호출하지 않고, Bing 검색·출처·오류·여러 검색어의 병렬 도구 실행을 유지하는 것이다.

## 문제 분석·해결

기본 backend를bing으로 바꾸고 덕덕고 HTTP 요청·HTML 분기·이동 링크 해석·primp 기본 의존성을 제거했다. 예전duckduckgo,bing 설정은 네트워크 전에 거부한다. webserp의 덕덕고 경로도 차단했다. 과거 연구일지와 선택형 재현 환경은 보존했다. 이미 설치된 연구 패키지를 삭제한 것은 아니다.

검색 엔진 간 통합과 여러 검색어의 병렬 요청은 다르다. 엔진은 Bing 하나지만 모델이 여러 web_search를 보내면 기존 최대3개 병렬 처리는 유지한다. 원래 순위·URL 중복 제거·출처·호환 메타데이터도 유지한다. RRF 필드는 단일 엔진에서 다른 검색엔진의 합의를 뜻하지 않는다. Bing 실패 시 다른 공급자를 자동 호출하지 않는다.

## 실제 질문과 결과

아래는 LLM 없이 실행한 검색 도구 결과다. 이전031의 같은 질문 비교에는 덕덕고 실패가 섞였고 이번 요청 엔진은 Bing뿐이다.

<callout icon="🔎" color="blue_bg">
	**실제 검색어**
	Python official website
</callout>

> Welcome to Python.org
> https://www.python.org/

Bing HTTP200, search_complete=true였다.

<callout icon="🔎" color="blue_bg">
	**실제 검색어**
	국립춘천박물관 공식 홈페이지
</callout>

> 국립춘천박물관 - Museum
> https://chuncheon.museum.go.kr/kor/index.do

Bing HTTP200, search_complete=true였다.

<callout icon="🔎" color="blue_bg">
	**실제 검색어**
	춘천 삼악산 호수케이블카 공식 홈페이지
</callout>

> 춘천 삼악산 호수 케이블카
> https://samaksancablecar.com/

Bing HTTP200, search_complete=true였다.

## 검증과 한계

공개3질의 모두 공식 주소를 포함했다. 테스트110개와 제거 엔진의 실행 전 거부를 확인했다. 이전 덕덕고·다중 엔진 전용 검사를 Bing 단독 계약으로 교체해 테스트 수가 바뀌었다. 기존 병렬 툴 실행 검사는 유지한다. 이번에는 모델을 다시 호출하지 않았다. 검색 요청3회이며 토큰 절감·일반 품질 향상을 측정한 것은 아니다. Bing의 무관한 응답·HTML 변경·접근 제한 가능성은 남는다.

```text
Ran 110 tests in 1.945s
OK
```

<details>
<summary>실제 설정·코드·구조</summary>
	기준 커밋74ac485 이후 이번 변경의src/travel_agent/web.py와.env.example이다. 요청 주소를 Bing 하나로 제한해 덕덕고 실행 경로를 없앴다. agent.py의trace 기본값·비교 스크립트·현재 실행 문서도 맞췄다.
	```python
	SEARCH_URLS = {"bing": "https://www.bing.com/search"}
	```
	```text
	WEB_SEARCH_PROVIDER=http
	WEB_SEARCH_BACKEND=bing
	```
	```mermaid
	flowchart LR
	    A[모델의 검색 요청 묶음] --> B[최대3개 도구 병렬 실행]
	    B --> C[Bing 직접 HTTP 요청]
	    C --> D[제목·주소·요약 파싱]
	    D --> E[출처 또는 오류를 모델에 전달]
	```
</details>

<details>
<summary>실제 툴콜 로그 — Bing 검색3회</summary>
	모델 호출과 다음 모델 입력 전달은 없었다. 아래는 개발자가 직접 실행한web_search 결과다. 시각은UTC이며 쿠키·인증 헤더·원본 HTML은 공개하지 않는다.
	- 도구 web_search / 호출 ID f9ddc38efaf54ab4a9e395cc2724b77c / 실제 인자 `{"query": "Python official website", "top_k": 3}` / 2026-10-18T07:07:36.600601+00:00 → 2026-10-18T07:07:36.878330+00:00
	- 엔진 Bing GET, HTTP 인자 q=Python official website / 결과 `{"bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 1, "elapsed_ms": 276}}` / 첫 주소 https://www.python.org/
	- 도구 web_search / 호출 ID 96f2a41696584647a63c241bd8cd5460 / 실제 인자 `{"query": "국립춘천박물관 공식 홈페이지", "top_k": 3}` / 2026-10-18T07:07:36.879339+00:00 → 2026-10-18T07:07:37.089576+00:00
	- 엔진 Bing GET, HTTP 인자 q=국립춘천박물관 공식 홈페이지 / 결과 `{"bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 0, "elapsed_ms": 209}}` / 첫 주소 https://chuncheon.museum.go.kr/kor/index.do
	- 도구 web_search / 호출 ID a7db488ea2814f0191fd381443dc432e / 실제 인자 `{"query": "춘천 삼악산 호수케이블카 공식 홈페이지", "top_k": 3}` / 2026-10-18T07:07:37.090585+00:00 → 2026-10-18T07:07:37.464007+00:00
	- 엔진 Bing GET, HTTP 인자 q=춘천 삼악산 호수케이블카 공식 홈페이지 / 결과 `{"bing": {"status": "ok", "hits": 3, "method": "GET", "http_status": 200, "start_ms": 0, "elapsed_ms": 374}}` / 첫 주소 https://samaksancablecar.com/
</details>
