# 웹검색 도구

## 에이전트의 현재 검색 경로 (074)

호스트 에이전트는 공식 `@brave/brave-search-mcp-server` 2.1.4의 `brave_web_search`를 MCP로 호출한다. `adapter=brave_search`가 설정되면 기존 직접 API 검색 도구는 노출하지 않는다. 연결 실패 시 직접 API로 몰래 대체하지 않는다. 제목·URL·대표 요약·추가 발췌를 항목 단위로 보존하며 기본 모델 전달 한도는48000 UTF-8바이트다. 넣지 못한 항목 수를 표시하고 문장·JSON 중간을 자르지 않는다. 검색 발췌는 원사이트 본문 조회가 아니다.

전달된 각 검색 항목은 `web:` 출처 ID를 받아 기존 `web_read`로 본문을 읽을 수 있다. OpenBnB는 숙소 검색·상세 MCP로 별도 유지한다. 연결 예시는 `examples/mcp-brave.example.json`, 키는 비공개 파일에서 읽는다. 아래042의 직접 API 방식은 독립 `web search`·`web research` 명령과 이전 실험에 남아 있다. 두 경로를 현재 에이전트가 동시에 사용하는 것으로 해석하지 않는다.

## 직접 검색 CLI와 이전 에이전트 경로: Brave Search API (042)

Brave Web Search API에서 제목·URL·요약을 받아 기존 출처 ID·출력 제한·추적 형식으로 반환한다. Claude MCP에서 사용하던 키를 재사용하되 Python에서 API를 직접 호출한다. Node MCP 프로세스를 띄우거나 Claude를 호출하지 않는다. 기존 에이전트 web_search와 독립 web research의 검색 공급자가 모두 기본 brave로 바뀌었다. 연구 파이프라인의 전체 수집·발췌 구조를 에이전트 도구로 교체한 것은 아니다.

프로젝트 루트에서 BRAVE_API_KEY 환경 변수를 주거나, Git 제외 파일 data/private/brave-api-key에 키 한 줄을 둔다. 다른 위치는 BRAVE_API_KEY_FILE 환경 변수로 지정한다. 환경 변수가 파일보다 우선한다. Claude 설정을 런타임마다 읽지 않는다. .env.example은 참고용이며 .env를 자동 로딩하지 않는다. 로컬 키는 저장소에 포함되지 않으므로 새 환경에서는 별도로 설정해야 한다.

```powershell
python -m travel_agent web search "강릉 여행 후기 블로그"
python -m travel_agent web research "강릉 여행 후기 블로그" --pages 2 --keep-dir data/private/search-pipeline/manual
# 이전 Bing 경로를 명시적으로 비교할 때
python -m travel_agent web search "강릉 여행 후기 블로그" --provider http --backend bing
python -m travel_agent web research "강릉 여행 후기 블로그" --provider http --serp-format rss
```

기본 WEB_SEARCH_PROVIDER=brave, WEB_SEARCH_BACKEND=brave다. 기존 프로세스 환경에 http/bing을 설정했다면 해당 값을 변경해야 한다. BRAVE_SEARCH_COUNTRY=KR, BRAVE_SEARCH_LANG=ko가 기본이며 다국어 연구에서는 명시적으로 바꿀 수 있다. web search는 top_k만큼 한 번 요청하고, web research는 페이지당 최대20개를 받은 뒤 후처리한다. 페이지당 API 요청1건이며 기본 최대3페이지다. offset은0부터 시작하고 최대9다. 다음 페이지는 more_results_available=true일 때만 조회하며, 반복 URL·오류에서도 중단한다. 실제 반환 개수나 검색 공간 전체를 보장하지 않는다. 연구의 --serp-format/--locale은 Bing 전용으로 Brave에서 비기본 값을 주면 오류로 알린다.

인증 실패·429·네트워크·JSON 오류는 명시적으로 기록하며 자동 재시도·다른 엔진 대체는 없다. 키·인증 헤더·오류 응답 본문은 로그에 넣지 않는다. 검색 요약과 실제로 받은 본문은 계속 구분한다. Brave가 관련 후보를 반환해도 원사이트의403·429·동적 렌더링·오래된 글·광고성 글 문제는 남는다.

실제 042의 두 질문은 각각40개·20개 후보를 받았고 네이버·티스토리 여행 본문 및 명소 설명을 확보했다. 일부 출처 읽기는 실패해 검색 요약만 전달했고 광고성 호텔 글도 포함됐다. 이 결과는 일반 품질이나 최신 정보 검증 통과가 아니다. 요금·플랜·잔액은 계정에서 별도로 확인해야 한다. 검색 데이터 공급: [Brave Search API](https://brave.com/search/api/).

## 이전 Bing 구현과 조사 이력 (010~041)

034의 최신 작업은 에이전트 연결을 보류하고 검색 툴을 독립 검증하는 [수집·재정렬·발췌 경로](search-pipeline.md)다. `web research`는 임시 원문 저장과 페이지 수집 이후 top_k를 적용한다. 아래 `web search`와 기존 에이전트의 즉시 검색 요약 경로는 그대로 구분한다.

기본 공급자는 `http`, 엔진은 `bing`이다.032부터 DuckDuckGo의 요청·파서·URL 해석 경로와 기본 primp 의존성을 제거했다. webserp 연구 공급자에서도 DuckDuckGo를 거부한다. 과거 연구일지는 보존한다.

```powershell
python -m pip install -e .
$env:WEB_SEARCH_PROVIDER = 'http'
$env:WEB_SEARCH_BACKEND = 'bing'
travel-agent web search "국립춘천박물관 공식 홈페이지"
python scripts/evaluate_search_fusion.py
```

이전 `WEB_SEARCH_BACKEND=duckduckgo,bing` 설정은 `bing`으로 바꾼다. 제거한 엔진을 조용히 무시하지 않고 네트워크 전에 오류를 반환한다. 기본값을 사용하면 별도 설정은 필요 없다.

033부터 Bing은 기본 curl_cffi(edge101)로 `https://www.bing.com/search`에 q만 GET 전송한다. 로그인·브라우저 실행·유료 API·자동 재시도·다른 엔진으로의 자동 대체는 없다. WEB_HTTP_TRANSPORT=urllib로 이전 요청을 비교할 수 있다. 클라이언트는 시스템 프록시 설정의 영향을 받을 수 있다. 리다이렉트·200 이외 상태·접근 확인·해석되지 않은200은 오류다. 새 익명 요청이며 파일 쿠키를 저장하지 않는다. 응답은 UTF-8 HTML을 전제로 하고 파싱 입력을2MiB로 제한한다. urllib는 읽기 단계에, curl은 다운로드 후 크기에 한도를 적용한다. 요청 timeout은 기본15초·최대30초이며 전체 실행 마감 시간을 엄격히 보장하지 않는다.

제목과 링크가 분리된 Bing HTML도 파싱한다. `/ck/a?u=a1…` 이동 링크를 목적지로 해석하고 HTTP(S)·호스트·길이·인증 정보·공백을 검사한다. 검색엔진 내부 링크·광고 이동 링크를 제외한다. URL 중복 제거와 원래 순위·출처를 보존한다. RRF 호환 메타데이터는 남지만 현재 단일 엔진이므로 여러 엔진의 합의나 품질 가산을 뜻하지 않는다.

모델 도구 인자는 query(1..500자), top_k(정수1..5, 기본3)다. 제목200자·요약600자·URL·출처 ID와 기본3500 UTF-8 바이트 한도를 적용한다. 요약 잘림·제외 수를 표시하고 URL을 자르지 않는다. `engine_status`, `engines_returned`, `search_complete`와 결과별 `engines`, `engine_ranks`를 반환한다. Bing 실패는 도구 오류이며 다른 엔진을 호출하지 않는다. 검색 결과의 관련성을 일반적으로 자동 판정하지 못한다.

한 모델 응답이 여러 web_search를 요청하면 기본 최대3개 병렬 실행한다. `--tool-workers 1`이면 순차이고 허용 범위는1..4다. 검색 엔진 하나를 쓰는 것과 여러 검색어를 병렬로 조회하는 것은 별개다. 메모리 도구는 호출 스레드에서 실행한다.

검색은 HTML 한 페이지만 받으며 서버에 결과 개수를 지정하거나 다음 페이지를 요청하지 않는다. `top_k`는 로컬 선택 한도다. HTTP 공급자의 `engine_status.bing`에는 `response_bytes`(HTTP 라이브러리가 반환한 본문 크기), `result_cards`(HTML 카드 수), `parsed_results`(사용 가능한 제목·URL 추출 수), `selected_results`(top_k 선택 수), `not_selected_results`(top_k 제외 수)를 기록한다. 최상위 `returned_results`는 최종 반환 수이며 `omitted_results`는 선택 이후 중복·출력 제한으로 제외된 수다. HTML 전체에서 제외한 개수와 혼동하지 않는다. 카드가 항상 10개라는 보장은 없다.

원본 HTML과 top_k 전 전체 결과를 비교하려면 다음 진단을 사용한다. 원본은 비공개 경로에 저장하며 같은 응답으로 도구 출력을 재구성한다. LLM 호출은 없다.

```powershell
python scripts/inspect_search_response.py --query "국립춘천박물관 관람시간 휴관일 교통" --top-k 3 --output data/private/search-response/manual/report.json
```

`content_kind=search_snippet`, `page_fetched=false`는 검색 결과만 읽었다는 뜻이다. searched_at은 조회 시각이다. web_search는 본문·현재 가격·잔여 객실·운행을 확인하지 않는다. 앞선 검색 출처의 본문 발췌는 새 web_read 도구로 선택적으로 확인한다. 자동 검색 결과 저장·메모리 색인 갱신은 없다. web_read의 page_fetched=true도 최신 사실 검증을 뜻하지 않는다. 모델의 web_search_attempted·web_search_performed·web_sources와 비공개 trace로 실제 실행을 확인한다. 인용 ID 검사는 문장별 사실 검증이 아니다. 검색어는 외부 엔진으로 전송되며 자동 개인정보 마스킹은 아직 없다.

실제032 검증에서는 Python·박물관·케이블카 세 질의 모두 Bing200과 공식 도메인을 확인했다. 장기 안정성·일반 품질 우위의 증거는 아니다. 실제 로그와 코드는 [연구일지032](research/2026-10-18-032-bing-only-search.md)에 기록한다.

```powershell
python -m unittest discover -s tests -q
```

DDGS는 기본 런타임에서 쓰지 않으며 과거 비교 재현용 search-research extra에만 있다. webserp는 google 또는 yahoo 단독을 명시하는 별도 연구 경로다. Google 직접 HTTP 연구는 중단했다. [031 직접 HTTP 도입](research/2026-10-18-031-direct-http-search.md), [030 Bing 진단](research/2026-10-18-030-bing-maintenance-and-http-diagnosis.md)은 이전 결정과 실패를 보존한다.

## 033: 탐색 범위·입력 표현·본문 읽기 평가

현재 모델 입력은 WEB_TOOL_FORMAT=compact_md가 기본이다. full_json·compact_json도 비교용으로 지원하며 원래 구조화 결과는 trace에 남는다. 실제 top3/top5/다중 질의·토큰·본문 사실 보존·실패 판정은 [평가 기준과 실행법](travel-search-evaluation.md), [실제 연구일지033](research/2026-10-18-033-travel-search-evaluation.md)을 참고한다. 자율적인 여행 답변의 품질 검증은 아직 불합격이다.
