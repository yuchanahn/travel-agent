# 웹검색 도구

## 현재 방향: DuckDuckGo·Bing 직접 HTTP

031부터 기본 공급자는 `http`다. DDGS의 런타임 의존성·엔진 선택·요청 생성·HTML 파서를 제거하고 두 엔진의 공개 검색 페이지를 직접 요청한다. API 키·검색 서버·브라우저 프로세스는 필요 없다. HTML 변경·접근 제한·무관한 결과에 대한 유지보수는 우리가 맡는다.

DuckDuckGo는 `primp` HTTP 클라이언트로 `https://html.duckduckgo.com/html/`에 GET 요청한다. 기존 동작 경로의 `q`, `b`, `l=kr-kr`와 random impersonation을 유지한다. 이는 브라우저 실행이 아니다. Bing은 표준 `urllib`로 `https://www.bing.com/search`에 `q`만 보낸다. 두 사이트에 같은 HTTP 클라이언트를 강제하지 않는다. 예비 urllib·curl DuckDuckGo는202였고 직접 primp 요청은200이었다. 클라이언트와 인자가 함께 바뀌어 하나만 원인이라고 확정하지 않는다.

두 엔진 모두 새 익명 클라이언트를 사용한다. 로그인·디스크 쿠키 재사용·재시도·다른 엔진 자동 대체는 없다. urllib는 시스템 프록시 설정을 따를 수 있다. Bing 리다이렉트는 따라가지 않고 오류로 보고한다. UTF-8 HTML을 전제로 한다. 파싱 대상은2MiB 이하다. Bing은 읽기 단계에 한도를 적용하며 primp는 다운로드 후 크기를 검사한다. timeout은 요청별 값이며 전체 작업의 엄격한 마감 시간은 아니다.

## 실행과 설정 변경

```powershell
python -m pip install -e .
travel-agent web search "국립춘천박물관 공식 홈페이지" --provider http --backend duckduckgo,bing
python scripts/evaluate_search_fusion.py
$env:WEB_SEARCH_PROVIDER = 'http'
$env:WEB_SEARCH_BACKEND = 'duckduckgo,bing'
travel-agent memory --user demo --session trip agent "국립춘천박물관 공식 홈페이지를 찾아줘"
```

기본값은 `http`·`duckduckgo,bing`이다. 예전 `WEB_SEARCH_PROVIDER=ddgs`는 `http`로 바꾼다. 옛 이름을 조용히 매핑하지 않고 변경 안내 오류를 반환한다. http 지원 엔진은 duckduckgo·bing뿐이다. auto·미지원 엔진은 네트워크 전에 거부한다.

## 병렬 실행·실패·출처

한 웹 도구는 엔진을 각각 한 번씩 최대2개 병렬 호출한다. 정규화 URL로 중복을 제거하고 RRF(`sum(1/(60+rank))`)로 통합한다. 동점은 엔진 요청 순서·원래 순위를 따른다. 추가 LLM 호출은 없다. 공통 URL의 높은 점수는 사실 검증이나 독립 색인의 합의를 보장하지 않는다.

`engine_status`에 엔진별 상태·HTTP 상태·메서드·후보 수·시작 상대 시각·소요 시간이 있다. `engines_returned`는 후보를 반환한 엔진, `search_complete=false`는 요청 엔진 중 실패가 있었다는 뜻이다. 한쪽 실패면 나머지 결과를 살리고 모두 실패하면 WebSearchError다. 202·리다이렉트·접근 확인·해석되지 않은200은 성공으로 처리하지 않는다. 원본 HTML·쿠키·인증 헤더는 앱 trace에 넣지 않는다.

DDG `/l/?uddg=`·Bing `/ck/a?u=a1…`는 목적지로 해석한다. HTTP(S)·호스트·길이를 검사하고 인증 정보·공백 주소·검색엔진 내부 링크를 제외한다. Bing 제목과 링크가 분리된 HTML도 읽는다. 결과별 `engines`·`engine_ranks`는 최종 `web_sources`에도 남는다.

같은 모델 응답의 웹 도구는 기본 최대3개 병렬 실행한다. `--tool-workers 1`이면 순차, 허용 범위는1..4다. 기본적으로 최대6개 엔진 요청이 겹칠 수 있다. 결과를 모두 모아 요청 순서·호출 ID대로 모델에 전달한다. 메모리 도구는 호출 스레드에서 실행한다.

## 반환 범위와 에이전트 확인

모델 도구 인자는 `query`(1..500자), `top_k`(정수1..5, 기본3)다. 공급자·엔진은 호스트가 정한다. 제목200자·요약600자·URL·출처 ID, 기본 전체3500 UTF-8 바이트 한도를 적용한다. 요약 잘림·제외 수를 표시하고 URL을 자르지 않는다.

`content_kind=search_snippet`, `page_fetched=false`는 검색 결과만 읽었다는 뜻이다. `searched_at`은 조회 시각이다. 본문·현재 가격·잔여 객실·운행은 확인하지 않는다. 본문 수집·검색 결과 자동 저장·메모리 갱신은 없다.

에이전트는 `web_search_attempted`, `web_search_performed`, `web_sources`로 실행 여부를 구분한다. 인용 ID 검사는 제공한 ID인지 확인하며 문장별 근거·인용 누락·사실성을 모두 검증하지 못한다. `--no-web`은 실행을 막지만 모델의 허위 URL 생성을 완전히 막지 못한다. 라우팅·프롬프트 인젝션 방어도 완전히 검증하지 않았다.

실제 인자·결과·오류·모델 답변·토큰·시간은 비공개 요청별 trace에 남는다. 검색어는 외부 엔진으로 전송되며 자동 개인정보 마스킹은 아직 없다.

## 실제 검증과 한계

031 최종 비교에서 Python·박물관은 두 엔진 모두200으로 공식 주소를 찾았다. 케이블카는 DDG202·Bing200으로 Bing 결과만 제공했다. 세 질의 모두 목표 도메인을 찾았지만 두 엔진 성공은2/3이다. 짧은 실행 구간이며 장기 안정성·일반 품질·비용 우위의 증거는 아니다.

```powershell
python -m unittest discover -s tests -q
python scripts/evaluate_search_fusion.py
```

실제 질의·응답·코드·접힌 툴콜 로그는 [031 연구일지](research/2026-10-18-031-direct-http-search.md)를 참고한다.

## 이전 구현·선택형 연구 경로

[029 DDGS 통합](research/2026-10-18-029-dual-engine-fusion.md)과 [030 Bing 진단](research/2026-10-18-030-bing-maintenance-and-http-diagnosis.md)은 변경 배경이다. DDGS는 과거 재현용 `search-research` extra에만 남으며 기본 설치·런타임에는 필요 없다. 이미 설치된 연구 패키지를 자동 삭제하지 않는다.

기존 webserp extra는 검토한 Git 커밋을 고정한 연구 경로다. `--provider webserp --backend duckduckgo,yahoo` 또는 `--backend google`을 명시한다. Google 실패와 Yahoo의 제한된 성공은 [019](research/2026-10-18-019-webserp-deep-validation.md)에 기록했다. Google 직접 HTTP 연구는 중단했으며022~028은 과거 기록이다. 관리형 API와 자체 운영의 차이는 [014](research/2026-10-17-014-local-search-and-cost.md)를 참고한다.
