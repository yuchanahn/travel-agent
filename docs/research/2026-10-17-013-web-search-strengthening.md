# 013 — 웹검색 기능 보강: 공개 프로젝트와 도입 후보 조사

2026-10-17 · GitHub·공식 문서·논문 조사, 공급자 비교 실험 설계

## 어떤 실패를 보강하려는가

웹 도구를 연결하고 병렬 처리까지 구현했지만 실제 여행 정보를 찾는 기본 기능이 불안정했다. 아래는 앞선 실행에서 보낸 질문과 실제 답변이다. 이번에 새 모델 응답을 생성한 것이 아니라, 개선 대상인 기존 실패를 다시 놓고 시작한다.

> **실제로 보낸 질문**
> 춘천 삼악산 호수케이블카와 국립춘천박물관의 공식 홈페이지 주소를 각각 찾아줘. 서로 독립적인 두 웹검색을 한 응답의 도구 요청 묶음으로 보내고, 각 검색은 top_k=1로 해줘. 반환된 주소와 출처를 간결하게 알려줘. 본문을 읽었다고 말하지 마.

```text
죄송합니다. 현재 웹 검색을 통해 공식 홈페이지를 찾을 수 없었습니다.

*   **춘천 삼악산 호수케이블카**: 공식 홈페이지가 확인되지 않았습니다.
*   **국립춘천박물관**: 공식 홈페이지가 확인되지 않았습니다.

다른 검색어로 시도하거나, 과거에 기록된 정보를 찾아보시는 것이 좋을 것 같습니다.
```

이후 HTTP 진단에서는 DuckDuckGo의 봇 확인 응답, Brave 429, Google 403과 DDGS의 오류 정보 손실을 확인했다. “검색어를 더 잘 만들면 된다”만으로 해결할 수 없는 문제였다. 사용자는 공개 GitHub 프로젝트도 충분히 조사해 웹검색 기능 보강의 근거를 남기도록 요청했다.

좋은 후보는 공식 출처를 실제로 찾고, 정상적인 빈 결과와 접근 실패를 구분하며, 4B 로컬 모델에 과도한 본문을 밀어 넣지 않아야 한다. 비용·운영 부담도 비교한다. 별점·기능 설명만으로 한국어 검색 품질이 입증됐다고 취급하지 않는다.

## 조사 방법과 최신성

공식 저장소·문서·저자 논문을 확인하고 GitHub API로8개 저장소의 별점, 마지막 push, 라이선스, archived 여부를 조회했다. 아래는 2026-10-17의 스냅샷이다. push는 태그·브랜치 작업도 포함하므로 최근 릴리스나 실제 버그 수정의 증거와 같지 않다. 별점은 관심·채택 신호이며 성능 점수가 아니다.

| 프로젝트 | 별점 | 마지막 push(KST) | 저장소 라이선스 | 역할 |
|---|---:|---|---|---|
| [searxng/searxng](https://github.com/searxng/searxng) | 38,508 | 2026-10-17 | AGPL-3.0 | 메타검색 서버 |
| [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) | 192,361 | 2026-10-17 | AGPL-3.0 | 검색·스크래핑 통합 |
| [unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) | 85,693 | 2026-10-15 | Apache-2.0 | 본문 수집·크롤링 |
| [jina-ai/reader](https://github.com/jina-ai/reader) | 12,156 | 2026-05-22 | Apache-2.0 | URL Reader·호스팅 검색 |
| [karust/openserp](https://github.com/karust/openserp) | 1,480 | 2026-09-29 | MIT | 브라우저 기반 SERP API |
| [ItzCrazyKns/Vane](https://github.com/ItzCrazyKns/Vane) | 37,364 | 2026-09-01 | MIT | 검색·답변 완성형 앱 |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 30,134 | 2026-10-11 | Apache-2.0 | 조사·보고서 에이전트 |
| [sentient-agi/OpenDeepSearch](https://github.com/sentient-agi/OpenDeepSearch) | 3,831 | 2025-04-05 | Apache-2.0 | 검색 도구·추론 연구 |

8개 모두 archived=false였지만 유지보수 속도는 달랐다. Perplexica 주소는 현재 Vane으로 리다이렉트됐다. OpenDeepSearch는 논문과 구현을 참고할 수 있지만 마지막 push가2025년이므로 최신 운영 대안이라고 소개하지 않는다. 모델·클라우드·하위 구성요소의 라이선스는 저장소 루트 라이선스와 별도로 확인해야 한다.

## 우리 상황에서 비교한 결과

### SearXNG — 첫 검색 공급자 비교 후보

여러 검색 서비스를 집계하고 JSON HTTP API를 제공한다. Python 에이전트는 서버의 /search를 호출하면 되어 LLM·도구 루프를 교체할 필요가 없다. [공식 Search API](https://docs.searxng.org/dev/search_api.html)는 JSON 형식을 설정에서 활성화해야 하며 공개 인스턴스가 이를 막을 수 있다고 명시한다. 직접 운영하는 인스턴스를 기준으로 평가하는 것이 맞다.

API 키 없이 사용할 수 있는 엔진 조합을 구성할 수 있지만 모든 엔진이 무조건 무료이거나 차단되지 않는 것은 아니다. 자체 서버·설정·업데이트 비용이 생긴다. 원래 검색엔진에 의존하므로 현재 접근 제한을 자동 해결한다고 보장할 수 없다. 우리 코드에서 실제 사용 엔진과 실패 정보를 보존할 수 있는지도 검증해야 한다. 후보 중 규모와 지속적인 업데이트를 확인했고, 우선 비교할 이유가 충분하다.

### OpenSERP — 별도 구현 경로의 두 번째 검색 후보

[공식 README](https://github.com/karust/openserp)는 브라우저 렌더링을 사용하는 여러 엔진, 결과 병합·중복 제거, 페이지 추출, JSON API와 Docker 실행을 설명한다. Python에서 HTTP로 붙일 수 있고 로컬 LLM을 추가로 올릴 필요는 없다. MIT 저장소이며 자체 운영 시 서비스별 검색 API 키 없이 실행할 수 있는 경로를 제공한다.

DDGS의 단순 HTML 요청과 다른 실행 경로를 비교할 수 있다는 점이 유용하다. 브라우저와 서버 운영 부담은 생기고 자동화 접근 제한도 남을 수 있다. 별점·커뮤니티 규모는 SearXNG보다 작다. 한국어 검색 결과와 오류 형태를 실제로 확인하기 전에는 기본값으로 확정하지 않는다.

### Crawl4AI — 검색 결과의 본문 읽기 후보

[공식 저장소](https://github.com/unclecode/crawl4ai)는 Python 비동기 브라우저 크롤링, Markdown 변환, CSS/XPath 추출, 캐시와 다중 URL 처리를 제공한다. LLM 없이 본문을 추출하는 경로가 있어 현재 Qwen의8GB VRAM과 별도로 거대한 모델을 올릴 필요는 없다. 다만 브라우저가 사용하는 CPU·RAM과 실제 처리량은 우리 환경에서 측정해야 한다.

중요한 구분은 오픈소스 본문 수집 기능과 클라우드 검색 API다. 현재 README는 /search와 /serp를 클라우드 추가 기능으로 소개한다. 로컬 Crawl4AI를 설치하면 무료 검색 공급자가 생긴다고 설명하면 틀린다. 이번에는 검색 API 대체가 아니라 search로 얻은 URL을 read하는 구성요소로 검토한다.

### Firecrawl — 통합 후보, 자체 호스팅 범위 확인 필요

[공식 자체 호스팅 문서](https://docs.firecrawl.dev/contributing/self-host)는 검색·스크래핑 경로를 지원하지만 여러 서버 구성요소와 운영 작업이 필요하다고 설명한다. Fire-engine의 고급 봇 대응은 기본 구성에 포함되지 않으며 클라우드와 기능이 같지 않다. 저장소의 높은 별점을 로컬 설치의 검색 성공 보장으로 읽어서는 안 된다.

호스팅 API는 별도 키·사용량 조건이 있고 자체 호스팅도 인프라 운영 비용이 있다. 검색과 본문 수집을 한 서비스로 묶고 싶을 때 유용한 후보이나, 지금은 좁은 검색 어댑터와 본문 도구를 검증하는 것보다 도입 범위가 커질 수 있다. 즉시 기본 구성으로 채택하지 않는다.

### Jina Reader/Search — 작은 호스팅 비교 후보

[Reader 저장소](https://github.com/jina-ai/reader)는 r.jina.ai의 URL 읽기와 s.jina.ai 검색을 구분한다. [현재 공식 사용량 표](https://jina.ai/reader/)는 s.jina.ai의 키 없는 사용을 block으로, 키를 사용하는 검색을 토큰 사용량과 연결해 표시한다. 과거의 “URL만 붙이면 무료 검색” 안내를 그대로 적용하지 않는다.

통합은 작지만 호스팅 서비스 의존성과 사용량 조건이 있다. 공개 Reader 코드가 있다는 것과 검색 인덱스·운영 서비스를 전부 로컬에서 재현할 수 있다는 것은 별개다. 무료 키가 있는 조건에서 소규모 비교 대상으로는 남기되 API 키를 새로 만들거나 비용을 발생시키지는 않았다.

### Vane·GPT Researcher·OpenDeepSearch — 구조와 평가 참고

[Vane](https://github.com/ItzCrazyKns/Vane)은 SearXNG를 포함하거나 외부 SearXNG에 연결하는 답변 앱이다. 완성된 제품 흐름을 참고할 수 있지만 별개의 검색 인덱스가 생기는 것은 아니다. [GPT Researcher](https://github.com/assafelovic/gpt-researcher)는 조사·보고서 오케스트레이션에 가깝고 기본 안내에 검색·모델 API 키가 등장한다. 현재 우리 루프 전체를 대체하기보다 검색 공급자 분리와 근거 관리 구조를 참고한다.

[OpenDeepSearch](https://github.com/sentient-agi/OpenDeepSearch)는 Serper 또는 SearXNG 공급자, 본문 처리와 리랭킹을 결합한다. [저자 논문](https://arxiv.org/abs/2503.20201)은 SimpleQA·FRAMES 결과를 보고한다. 이는 평가를 갖춘 공개 참고 자료라는 의미가 있지만 우리 한국어 여행 질문·Qwen4B·8GB 환경의 결과가 아니다. 논문 모델과 외부 서비스 조건도 달라 점수를 우리 프로젝트 예상 성능으로 옮기지 않는다.

## 잠정 결론과 다음 비교 실험

1. 검색은 SearXNG를 첫 후보, OpenSERP를 비교 후보로 둔다. 본문 수집은 Crawl4AI를 별도로 검토한다.
2. 완성형 에이전트를 통째로 가져오기보다 기존 bounded tool loop·출처 ID·실행 추적을 유지하고 공급자 경계를 교체한다.
3. DDGS는 기존 실패를 재현하는 기준으로 남긴다. 설치·전환·한국어 성공률 검증은 아직 하지 않았다.

“이 프로젝트가 더 잘 찾을 것”은 현재 가설이다. 새 검색 서버를 띄우거나 패키지·브라우저·Docker를 설치한 결과로 기록하지 않는다. 실제 검색 기능이 보강 완료됐다는 뜻도 아니다. 이번 완료 범위는 공개 대안 조사와 도입 후보·평가 계획이다.

## 어떤 질문으로 좋은 검색인지 확인할까

10개 공개 개발 질문을 평가 입력으로 만들었다. 기존 실패인 두 공식 홈페이지 검색, 박물관 안내·기상 정책·대중교통·실내 여행 검색과 존재하지 않는 이름의 합성 질문을 포함한다. 모두 실행 전이며 반복 검증용 개발셋이다. 독립 평가셋이나 사용자 성공률로 취급하지 않는다.

먼저 모델 없이 같은 query·한국어 조건·top_k=5로 비교한다. 요청 성공 여부와 검색 적합성을 분리한다. 정상 빈 결과, 전체 실패, 일부 엔진 실패, 접근 제한, timeout을 각각 기록한다. 공식 주소가 이미 확인된2개는 공식 도메인 hit@5를 보고, 나머지는 상위 결과를 수동으로 검토한다. 블로그 제목에 “공식”이 있다는 이유만으로 통과시키지 않는다.

서로 다른 시각·캐시 상태의 영향을 기록하고 순차 실행부터 시작한 뒤2개 동시 요청을 비교한다. 지연·응답 크기·실제 사용 엔진·호스팅 사용량과 운영 자원은 측정한 값만 적는다. 본문 도구 평가는 동일 URL로 따로 하고 원문 종류·조회 시각·본문 추출 성공을 확인한다. 그다음 같은 Qwen으로 최종 답변의 인용·조건 반영·유보 품질을 평가한다.

<details>
<summary>실제 툴콜 로그 — 검색어·문서 조회·GitHub API 응답</summary>

	이번 작업에서는 에이전트의 새 모델 추론을 실행하지 않았다. 아래는 조사에 실제 사용한 검색 요청과 공식 문서·저장소 조회 기록이다. 전체 원본은 비공개 보존하고, 이 토글에는 관련 요청과 판단에 사용한 결과를 발췌한다. 호출 ID를 제공하지 않은 도구에 임의 ID를 만들지 않는다.

	### 공개 프로젝트 탐색에 사용한 실제 검색어

	```json
	{
	  "search_query": [
	    {
	      "q": "github open source web search API AI agents searxng search crawl 2026"
	    },
	    {
	      "q": "github firecrawl search crawl4ai open source agents search"
	    },
	    {
	      "q": "github jina reader search api open source agents"
	    },
	    {
	      "q": "github open source search engine agent search self hosted SearXNG"
	    }
	  ],
	  "response_length": "long"
	}
	```

	관련 반환 결과에는 SearXNG, Firecrawl, Jina Reader와 SearXNG를 감싼 소규모 프로젝트들이 있었다. 기술 판단은 검색 요약에만 의존하지 않고 아래 공식 저장소·문서를 열어 확인했다.

	### 실제 저장소 조회

	```json
	{
	  "open": [
	    {
	      "ref_id": "https://github.com/searxng/searxng"
	    },
	    {
	      "ref_id": "https://github.com/firecrawl/firecrawl"
	    },
	    {
	      "ref_id": "https://github.com/unclecode/crawl4ai"
	    },
	    {
	      "ref_id": "https://github.com/jina-ai/reader"
	    },
	    {
	      "ref_id": "https://github.com/karust/openserp"
	    },
	    {
	      "ref_id": "https://github.com/ItzCrazyKns/Perplexica"
	    },
	    {
	      "ref_id": "https://github.com/athina-ai/opendeepsearch"
	    },
	    {
	      "ref_id": "https://github.com/assafelovic/gpt-researcher"
	    }
	  ],
	  "response_length": "long"
	}
	```

	athina-ai/opendeepsearch 조회는 도구의 Internal Error로 내용을 얻지 못했다. 검색으로 실제 저자 저장소 sentient-agi/OpenDeepSearch를 찾아 다시 열었다. Perplexica는 Vane으로 리다이렉트됐고 비교표에는 현재 이름을 썼다.

	### 추가 검색 요청과 공식 문서 조회

	```json
	{
	  "search_query": [
	    {
	      "q": "Open Deep Search github OpenSearchTool Serper Jina 2025 paper"
	    },
	    {
	      "q": "site.docs.firecrawl.dev self host search SearXNG"
	    },
	    {
	      "q": "site:docs.searxng.org search api unresponsive_engines JSON"
	    },
	    {
	      "q": "site:jina.ai reader search API key tokens s.jina.ai"
	    }
	  ],
	  "response_length": "long"
	}
	```

	공식 문서를 직접 연 요청은 다음과 같다.

	```json
	{
	  "open": [
	    {
	      "ref_id": "https://docs.searxng.org/dev/search_api.html"
	    },
	    {
	      "ref_id": "https://docs.firecrawl.dev/contributing/self-host"
	    },
	    {
	      "ref_id": "https://raw.githubusercontent.com/firecrawl/firecrawl/main/SELF_HOST.md"
	    },
	    {
	      "ref_id": "https://jina.ai/reader/"
	    },
	    {
	      "ref_id": "https://raw.githubusercontent.com/sentient-agi/OpenDeepSearch/main/README.md"
	    },
	    {
	      "ref_id": "https://raw.githubusercontent.com/karust/openserp/main/README.md"
	    }
	  ],
	  "response_length": "long"
	}
	```

	이후 본문 안에서 Cloud, Tavily, SERPER, unresponsive_engines, SimpleQA 등을 찾아 기능 범위와 의존성을 확인했다. Jina 검색 구현에서 Brave 문자열은 발견되지 않아 이를 근거로 특정 검색 공급자를 사용한다고 주장하지 않았다.

	### GitHub API의 실제 요청과 응답 발췌

	GET /repos/{owner}/{repo}로 조회했고, 호출은 인증 없이 수행했다. 아래 숫자·시각은 실제 응답 필드다. 라이선스는 GitHub의 루트 식별값이고 법률 검토 결과가 아니다.

	```json
	{
	  "observed_at": "2026-10-17T12:46:19.471360+00:00",
	  "responses": [
	    {
	      "request": "https://api.github.com/repos/searxng/searxng",
	      "full_name": "searxng/searxng",
	      "stargazers_count": 38508,
	      "pushed_at": "2026-10-17T09:19:07Z",
	      "archived": false,
	      "license": "AGPL-3.0"
	    },
	    {
	      "request": "https://api.github.com/repos/firecrawl/firecrawl",
	      "full_name": "firecrawl/firecrawl",
	      "stargazers_count": 192361,
	      "pushed_at": "2026-10-17T09:05:40Z",
	      "archived": false,
	      "license": "AGPL-3.0"
	    },
	    {
	      "request": "https://api.github.com/repos/unclecode/crawl4ai",
	      "full_name": "unclecode/crawl4ai",
	      "stargazers_count": 85693,
	      "pushed_at": "2026-10-15T10:16:13Z",
	      "archived": false,
	      "license": "Apache-2.0"
	    },
	    {
	      "request": "https://api.github.com/repos/jina-ai/reader",
	      "full_name": "jina-ai/reader",
	      "stargazers_count": 12156,
	      "pushed_at": "2026-05-22T02:56:46Z",
	      "archived": false,
	      "license": "Apache-2.0"
	    },
	    {
	      "request": "https://api.github.com/repos/karust/openserp",
	      "full_name": "karust/openserp",
	      "stargazers_count": 1480,
	      "pushed_at": "2026-09-28T22:25:47Z",
	      "archived": false,
	      "license": "MIT"
	    },
	    {
	      "request": "https://api.github.com/repos/ItzCrazyKns/Perplexica",
	      "full_name": "ItzCrazyKns/Vane",
	      "stargazers_count": 37364,
	      "pushed_at": "2026-09-01T14:12:12Z",
	      "archived": false,
	      "license": "MIT"
	    },
	    {
	      "request": "https://api.github.com/repos/assafelovic/gpt-researcher",
	      "full_name": "assafelovic/gpt-researcher",
	      "stargazers_count": 30134,
	      "pushed_at": "2026-10-10T22:03:53Z",
	      "archived": false,
	      "license": "Apache-2.0"
	    },
	    {
	      "request": "https://api.github.com/repos/sentient-agi/OpenDeepSearch",
	      "full_name": "sentient-agi/OpenDeepSearch",
	      "stargazers_count": 3831,
	      "pushed_at": "2025-04-04T18:20:24Z",
	      "archived": false,
	      "license": "Apache-2.0"
	    }
	  ]
	}
	```
</details>

<details>
<summary>현재 실제 코드·후보 연결 구조·평가 입력</summary>

	코드 기준 커밋: 2cd4a74. 이번 변경은 조사 문서와 실행 전 평가 입력이며 런타임 공급자는 바꾸지 않았다.

	`src/travel_agent/agent.py` · `execute_tool`에서 현재 웹 도구는 아래 경계로 호출된다. 공급자 교체를 이 경계 아래에서 검토하면 모델의 tool schema와 병렬 실행·인용 추적을 유지할 수 있다. 아직 후보 어댑터를 구현한 코드는 아니다.

	```python
	    if name == "web_search":
	        return web_search(args["query"], top_k=args["top_k"], timeout=timeout, max_bytes=max_bytes)
	```

	```mermaid
	flowchart TD
	    Q["Qwen: web_search 요청"] --> V["현재 인자 검증·병렬 실행·추적"]
	    V --> D["현재: DDGS 어댑터"]
	    V -. "미구현 비교 후보" .-> S["SearXNG HTTP API"]
	    V -. "미구현 비교 후보" .-> O["OpenSERP HTTP API"]
	    D --> R["제목·URL·검색 요약"]
	    S -.-> R
	    O -.-> R
	    R -. "미구현 본문 도구" .-> C["Crawl4AI: 선택한 URL 읽기"]
	    C -.-> E["본문·출처·시점·오류"]
	```

	실제 비교 입력은 `examples/web-search-evaluation.json`이다. status=planned_not_executed로 표시했고 알려진 공식 도메인은 기존 조사로 확인한2개만 넣었다. 나머지 질의의 현재 요금·운영시간을 정답처럼 미리 채우지 않았다. 테스트 스크립트·후보 서버는 아직 없다.

	규모·별점과 README의 신뢰성 주장은 채택 근거 중 일부일 뿐이다. 특정 후보의 성능이 더 좋다는 측정 결과는 이번 문서에 없다. 소규모 자기 보고 벤치마크도 한국어 여행 실사용 평가와 분리했다.
</details>
