# 웹검색 도구

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

`content_kind=search_snippet`, `page_fetched=false`는 검색 결과만 읽었다는 뜻이다. searched_at은 조회 시각이다. web_search는 본문·현재 가격·잔여 객실·운행을 확인하지 않는다. 앞선 검색 출처의 본문 발췌는 새 web_read 도구로 선택적으로 확인한다. 자동 검색 결과 저장·메모리 색인 갱신은 없다. web_read의 page_fetched=true도 최신 사실 검증을 뜻하지 않는다. 모델의 web_search_attempted·web_search_performed·web_sources와 비공개 trace로 실제 실행을 확인한다. 인용 ID 검사는 문장별 사실 검증이 아니다. 검색어는 외부 엔진으로 전송되며 자동 개인정보 마스킹은 아직 없다.

실제032 검증에서는 Python·박물관·케이블카 세 질의 모두 Bing200과 공식 도메인을 확인했다. 장기 안정성·일반 품질 우위의 증거는 아니다. 실제 로그와 코드는 [연구일지032](research/2026-10-18-032-bing-only-search.md)에 기록한다.

```powershell
python -m unittest discover -s tests -q
```

DDGS는 기본 런타임에서 쓰지 않으며 과거 비교 재현용 search-research extra에만 있다. webserp는 google 또는 yahoo 단독을 명시하는 별도 연구 경로다. Google 직접 HTTP 연구는 중단했다. [031 직접 HTTP 도입](research/2026-10-18-031-direct-http-search.md), [030 Bing 진단](research/2026-10-18-030-bing-maintenance-and-http-diagnosis.md)은 이전 결정과 실패를 보존한다.

## 033: 탐색 범위·입력 표현·본문 읽기 평가

현재 모델 입력은 WEB_TOOL_FORMAT=compact_md가 기본이다. full_json·compact_json도 비교용으로 지원하며 원래 구조화 결과는 trace에 남는다. 실제 top3/top5/다중 질의·토큰·본문 사실 보존·실패 판정은 [평가 기준과 실행법](travel-search-evaluation.md), [실제 연구일지033](research/2026-10-18-033-travel-search-evaluation.md)을 참고한다. 자율적인 여행 답변의 품질 검증은 아직 불합격이다.
