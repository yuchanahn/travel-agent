# 012 — 같은 검색어를 찾지 못한 이유: HTTP 응답까지 내려가 보기

2026-10-17 · 검색 비교·실패 진단과 기록 규칙 보강

## 문제 정의

사용자는 앞으로 실제 툴콜 로그도 노션의 접힌 토글에 기록하도록 요청했다. 동시에 “내장 웹검색은 찾는데 프로젝트 검색은 왜 못 찾는가”를 확인하기로 했다. 기록 규칙을 AGENTS와 연구일지 운영 규칙, 노션 작성 양식에 반영했다. 요청·실제 실행·결과 또는 오류를 연결하고 비밀정보는 제외한다.

좋은 진단은 같은 검색어를 사용하고 모델의 도구 선택, 검색 서비스 접근, HTML 결과 추출을 분리하는 것이다. 이전 실패의 오류 문구만으로 차단 원인을 단정하지 않는다. 이번 실험은 LLM을 호출하지 않고 웹 도구를 직접 재현했다. 따라서 아래는 새 모델 답변이 아니라 실제 검색 결과와 HTTP 관찰이다.

## 같은 검색어로 직접 비교

> **질문 — 실제 검색어**
> 춘천 삼악산 호수케이블카 공식 홈페이지

**프로젝트 검색의 실제 결과**

```text
춘천 삼악산 호수 케이블카
https://samaksancablecar.com/
삼천동에서 의암호를 가로질러 삼악산을 연결하는 3.61km의 국내 최장 케이블카
```

> **질문 — 실제 검색어**
> 국립춘천박물관 공식 홈페이지

**프로젝트 검색의 실제 결과**

```text
Web search provider failed: No results found.
```

내장 웹검색은 동일한 두 검색어에서 관련 자료를 반환했다. [케이블카 공식 사이트의 시설 안내](https://www.samaksancablecar.com/home/guide/floor.php)와 [FAQ](https://samaksancablecar.com/home/board/faq.php)가 검색됐고, 박물관은 [문화포털 안내](https://www.culture.go.kr/localperform/amateur/perform/view.do?menuNo=400013&pageIndex=20&pblprfrSn=270)에 홈페이지 `http://chuncheon.museum.go.kr/`가 표시됐다. 박물관 홈페이지 본문을 직접 읽었다고 주장하는 결과는 아니다.

두 시스템은 같은 검색 구현이 아니다. 프로젝트는 로컬 DDGS가 검색엔진 HTML 엔드포인트를 직접 요청하는 구조다. 내장 검색은 별도 관리형 도구이며 내부 엔진·네트워크·캐시 구현은 여기서 확인할 수 없다. 어느 쪽 LLM이 더 똑똑해서 생긴 차이라고 해석하지 않는다. 또한 내장 도구는 여러 검색 결과를 반환하므로 top_k=1의 순위 품질을 비교한 실험도 아니다.

## HTTP 응답을 보니 무엇이 달랐나

기존 에이전트 trace에는 HTTP 상태가 없었다. 진단 전용 스크립트로 DDGS가 실제 선택한 엔진, 실제 HTTP 요청의 검색어, 상태 코드, 봇 확인 관련 표식과 추출 개수를 관찰했다. 검색·TLS 검증 동작은 유지하고 원본 HTML·헤더·쿠키는 저장하지 않았다.

| 요청 엔진 설정 | 검색어 | 실제 HTTP 응답 | 결과 |
|---|---|---|---|
| duckduckgo,bing | 케이블카 | html.duckduckgo.com 200 | 10개 추출 후 요청한 1개 반환 |
| duckduckgo,bing | 박물관 | html.duckduckgo.com 202 | No results found. 예외 |
| brave,google | 케이블카 | search.brave.com 429, www.google.com 403 | No results found. 예외 |
| brave,google | 박물관 | search.brave.com 429, www.google.com 403 | No results found. 예외 |

DuckDuckGo의 박물관 응답은 202였고 `anomaly.js`, `anomaly-modal` 표식이 있었다. 정상 검색 결과 대신 봇 확인 관련 화면이 반환된 것으로 판단한다. Brave의 두 응답은429와 captcha 표식, Google의 두 응답은403이었다. 적어도 이번 재현에서는 “찾을 정보가 없음”보다 **검색 서비스 접근이 제한되어 결과를 받지 못함**이 실패 설명에 맞는다. CAPTCHA를 풀거나 우회하지 않았다.

다른 문제도 확인했다. 기본 설정 문자열은 duckduckgo,bing인데 실제 선택 엔진은 duckduckgo 하나였다. 설치된 DDGS 9.16.0의 Bing 구현은 disabled=True다. 따라서 기본 설정이 독립적인 검색엔진 두 개를 보장한다는 생각은 잘못이었다. 이 비활성화는 이번 설치 버전에서 확인한 사실이며 모든 DDGS 버전의 특성이라고 일반화하지 않는다.

## 왜 모델에게는 No results found라고 전달됐나

설치된 DDGS의 BaseSearchEngine.request는 HTTP 200일 때만 본문을 넘기고, 다른 상태는 None으로 처리한다. 결과가 끝까지 없으면 DDGS가 마지막 엔진 예외 또는 기본 문자열 No results found.로 예외를 발생시킨다. 프로젝트는 그 예외를 WebSearchError로 감싸 모델에 전달한다.

이 때문에 HTTP202·429·403이 실제로 관찰된 재현도 기존 로그와 같은 `Web search provider failed: No results found.`로 보였다. 이전에 검색 서버가 직접 이 문구를 반환했다고 설명해서는 안 됐다. 라이브러리 내부에서 원래 응답 상태를 잃어버리는 경로다. 이번 HTTP 실패는 결과 추출 단계에 들어가기 전에 발생했으므로 프로젝트의 URL 정리나 결과 바이트 한도가 원인인 것도 아니다.

단, 이전 병렬 실패 당시의 HTTP 원인은 기록이 없어 그대로 미확인이다. 이번 재현은 workers=1로 순차 실행했는데도 같은 제한 응답이 나왔다. 따라서 병렬 실행기가 결과를 잘못 전달했다는 설명은 이번 관찰과 맞지 않지만, 병렬화가 제공자 제한에 미치는 일반적인 영향까지 배제한 것은 아니다.

## 해결 방향과 이번 범위

이번에는 진단 스크립트와 기록 규칙을 추가했다. 에이전트의 기본 공급자나 재시도 정책은 바꾸지 않았고, 검색 실패가 해결됐다고 주장하지 않는다.

다음 구현에서는 정상적인 빈 결과와 접근 제한·timeout·파싱 실패를 구분해 도구에 전달해야 한다. 설정한 엔진과 실제 가용 엔진도 확인해야 한다. 429·봇 확인 응답을 받았을 때 같은 검색을 계속 반복하는 대신 제한된 대기·중단·다른 허용 공급자 선택 정책이 필요하다. 제품의 안정성을 판단하려면 공식 검색 API나 별도 검색 서비스도 성공률·비용·운영 부담으로 비교해야 한다. 공급자 교체만으로 무조건 해결된다고 가정하지 않는다.

총4개의 프로젝트 검색 호출과6개의 HTTP 응답을 관찰했다. 추출 성공은 케이블카의 DuckDuckGo 응답1건뿐이다. 소수 개발 검색어의 일회 재현이며 서비스 전체 성공률·비용·성능 비교가 아니다. 내장 검색의 관련 자료 확인과 프로젝트 검색의 실패 진단을 구분해 기록했다.

<details>
<summary>실제 툴콜 로그 — 검색 요청·선택 엔진·HTTP 응답·결과</summary>

	모델 호출: 없음. 프로젝트 도구를 직접 실행한 진단이다. 아래는 실제 요청과 관찰 결과다. 인증 헤더·쿠키·HTML 전체는 수집하지 않았다.

	### 프로젝트 검색 1

	```json
	{
	  "query": "춘천 삼악산 호수케이블카 공식 홈페이지",
	  "backend_requested": "duckduckgo,bing",
	  "http": [
	    {
	      "method": "POST",
	      "url": "https://html.duckduckgo.com/html/",
	      "query": "춘천 삼악산 호수케이블카 공식 홈페이지",
	      "status": 200,
	      "body_bytes": 30704,
	      "title": "춘천 삼악산 호수케이블카 공식 홈페이지 at DuckDuckGo",
	      "markers": [],
	      "duration": 0.733106
	    }
	  ],
	  "parsing": [
	    {
	      "engine": "duckduckgo",
	      "extracted_results": 10
	    }
	  ],
	  "selected_engines": [
	    "duckduckgo"
	  ],
	  "result": {
	    "provider": "ddgs",
	    "backend_requested": "duckduckgo,bing",
	    "searched_at": "2026-10-17T12:30:52.550451+00:00",
	    "content_kind": "search_snippet",
	    "page_fetched": false,
	    "web_search_performed": true,
	    "status": "ok",
	    "omitted_results": 0,
	    "hits": [
	      {
	        "id": "web:42a1dc11003496ff",
	        "title": "춘천 삼악산 호수 케이블카",
	        "url": "https://samaksancablecar.com/",
	        "snippet": "삼천동에서 의암호를 가로질러 삼악산을 연결하는 3.61km의 국내 최장 케이블카",
	        "snippet_truncated": false
	      }
	    ]
	  }
	}
	```

	### 프로젝트 검색 2

	```json
	{
	  "query": "국립춘천박물관 공식 홈페이지",
	  "backend_requested": "duckduckgo,bing",
	  "http": [
	    {
	      "method": "POST",
	      "url": "https://html.duckduckgo.com/html/",
	      "query": "국립춘천박물관 공식 홈페이지",
	      "status": 202,
	      "body_bytes": 14397,
	      "title": "DuckDuckGo",
	      "markers": [
	        "anomaly.js",
	        "anomaly-modal"
	      ],
	      "duration": 0.37735
	    }
	  ],
	  "parsing": [],
	  "selected_engines": [
	    "duckduckgo"
	  ],
	  "error_type": "WebSearchError",
	  "error": "Web search provider failed: No results found."
	}
	```

	### 프로젝트 검색 3

	```json
	{
	  "query": "춘천 삼악산 호수케이블카 공식 홈페이지",
	  "backend_requested": "brave,google",
	  "http": [
	    {
	      "method": "GET",
	      "url": "https://search.brave.com/search",
	      "query": "춘천 삼악산 호수케이블카 공식 홈페이지",
	      "status": 429,
	      "body_bytes": 73914,
	      "title": "Brave Search",
	      "markers": [
	        "captcha"
	      ],
	      "duration": 0.216864
	    },
	    {
	      "method": "GET",
	      "url": "https://www.google.com/wml/search",
	      "query": "춘천 삼악산 호수케이블카 공식 홈페이지",
	      "status": 403,
	      "body_bytes": 1833,
	      "title": "Error 403 (Forbidden)!!1",
	      "markers": [],
	      "duration": 0.461083
	    }
	  ],
	  "parsing": [],
	  "selected_engines": [
	    "brave",
	    "google"
	  ],
	  "error_type": "WebSearchError",
	  "error": "Web search provider failed: No results found."
	}
	```

	### 프로젝트 검색 4

	```json
	{
	  "query": "국립춘천박물관 공식 홈페이지",
	  "backend_requested": "brave,google",
	  "http": [
	    {
	      "method": "GET",
	      "url": "https://search.brave.com/search",
	      "query": "국립춘천박물관 공식 홈페이지",
	      "status": 429,
	      "body_bytes": 73923,
	      "title": "Brave Search",
	      "markers": [
	        "captcha"
	      ],
	      "duration": 0.204843
	    },
	    {
	      "method": "GET",
	      "url": "https://www.google.com/wml/search",
	      "query": "국립춘천박물관 공식 홈페이지",
	      "status": 403,
	      "body_bytes": 1795,
	      "title": "Error 403 (Forbidden)!!1",
	      "markers": [],
	      "duration": 0.500918
	    }
	  ],
	  "parsing": [],
	  "selected_engines": [
	    "brave",
	    "google"
	  ],
	  "error_type": "WebSearchError",
	  "error": "Web search provider failed: No results found."
	}
	```

	### 내장 웹검색 호출

	도구: web.run. 실제 요청 인자는 다음과 같다. 반환 결과는 많은 자료를 포함하므로 이번 판단에 사용한 관련3건의 제목·URL만 발췌한다.

	```json
	{
	  "search_query": [
	    {
	      "q": "춘천 삼악산 호수케이블카 공식 홈페이지"
	    },
	    {
	      "q": "국립춘천박물관 공식 홈페이지"
	    }
	  ],
	  "response_length": "short"
	}
	```

	```json
	[
	  {
	    "title": "춘천 삼악산 호수케이블카",
	    "url": "https://www.samaksancablecar.com/home/guide/floor.php"
	  },
	  {
	    "title": "춘천 삼악산 호수케이블카",
	    "url": "https://samaksancablecar.com/home/board/faq.php"
	  },
	  {
	    "title": "공연정보(상세) | 공연정보 | 지역공연 ON",
	    "url": "https://www.culture.go.kr/localperform/amateur/perform/view.do?menuNo=400013&pageIndex=20&pblprfrSn=270"
	  }
	]
	```
</details>

<details>
<summary>실제 코드와 실패 전달 흐름·재현 방법</summary>

	코드 기준: aa8057e 다음의 진단 추가 변경(이 문서와 같은 커밋). DDGS 내부 동작은 설치된9.16.0 소스로 확인했다. 진단용 monkeypatch는 해당 스크립트 프로세스에서만 적용한다. 기본 에이전트 trace에 HTTP 관찰 기능을 자동 추가한 것은 아니다.

	```mermaid
	flowchart TD
	    Q["같은 공개 검색어"] --> D["로컬 DDGS: 검색엔진 HTML 요청"]
	    D --> S["200: 검색 결과 추출"]
	    S --> H["URL·요약 반환"]
	    D --> B["202 봇 확인 / 429 / 403"]
	    B --> N["DDGS: None → 결과 없음 예외"]
	    N --> W["프로젝트: WebSearchError"]
	    Q --> M["내장 관리형 검색"]
	    M --> R["관련 페이지·홈페이지 링크 반환"]
	```

	`scripts/diagnose_web.py`의 http 함수는 실제 요청을 호출한 뒤 상태·길이·제목·표식을 기록한다. 이것은 정상 검색 결과를 만들어 주입하는 모의 실험이 아니다.

	```python
	            response = original_http(client, method, url, **kwargs)
	            title = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.I | re.S)
	            markers = [word for word in ['anomaly.js', 'anomaly-modal', 'captcha', 'verify you are human', 'unusual traffic', 'access denied']
	                       if word in response.text.lower()]
	            record.update(status=response.status_code, body_bytes=len(response.content),
	                          title=re.sub(r'\s+', ' ', title.group(1)).strip()[:160] if title else '', markers=markers)
	```

	정책 변경은 코드 대신 실제 기록 규칙에 반영했다. AGENTS.md와 docs/research/README.md에 “실제 툴콜 로그를 기본 접힌 토글로 남긴다”를 추가했다. 도구 이름·호출 ID(있는 경우)·검색어와 인자·결과 또는 오류·실행 순서와 시간을 연결한다. 호출이 없으면 없다고 적으며 로그를 만들어 넣지 않는다.

	```powershell
	python scripts/diagnose_web.py
	# 동시 호출이 필요한 별도 재현에만 사용한다.
	python scripts/diagnose_web.py --workers 2 --output artifacts/web-diagnostic-parallel.json
	```

	이번 기록은 첫 명령의 순차 실행이다. 두 번째 명령을 실행했다고 기록하지 않는다. 원본 로그는 비공개로 보존하며 공개 기록에는 비민감 검색어와 선별된 진단만 포함한다.
</details>
