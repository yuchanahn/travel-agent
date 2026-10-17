# 웹검색 도구

[후속 요청 검증023](research/2026-10-18-023-google-followup-consistency.md)에서 HTTP·JS 식별 정보, Promise·타이머 순서, HttpOnly 가시성, Referer와 fetch-site를 수정했다. `--javascript --wire`로 실행하면 실제 전송 헤더에서 쿠키 값 없이 이름·SG_SS 길이·요청 맥락을 확인할 수 있다. 실제 SG_SS 전송은 관찰했지만 검색은 여전히302→429이며 성공으로 처리하지 않는다.

현재 진행은 [Google HTTP 직접 구현022](research/2026-10-18-022-google-http-session.md)이다. 사용자 요청에 따라021의 브라우저 모듈·extra·테스트를 제거했다. `python -m travel_agent.google_http "Python official website"`는 브라우저 없이 curl_cffi로 요청하고 쿠키를 `data/private/google-http/cookies.txt`에 저장·재사용한다. `--javascript`는 선택형 QuickJS 실험이며 실제 검색 성공을 보장하지 않는다. 일반·basic 요청은 JS 확인 페이지였고 확인 스크립트 재요청은 /sorry의429였다. 아직 에이전트 공급자로 연결하지 않았다. 아래 webserp 설명은 기존 구현과 비교 이력이다.

최신 [Google 전용 진단020](research/2026-10-18-020-google-failure-stages.md)에서는 다른 엔진을 호출하지 않았다. prog 프레임을 바이트 길이로 해석하도록 수정했지만 실제 응답에는 검색 링크가 없었다. `protocol_error`, `no_search_markup`, `/sorry`의 `access_interstitial`을 구분하며, 최종 URL은 호스트·경로만 기록한다. 새 Chrome의 홈페이지 검색창 제출도 302→429였으나 사용자의 평소 브라우저는 정상이라는 보고를 받았다. Google 검색은 여전히 미해결이며 세션·브라우저 실행 방식의 차이는 아직 분리하지 못했다.

공개 후보 조사(015)·클론 검증(016)·Google 어댑터 비교(017) 이후 [이슈·프로토콜·원본 CLI 재검증](research/2026-10-18-019-webserp-deep-validation.md)을 수행했다. Google 요청은 여전히 실패하지만 webserp의 DuckDuckGo·Yahoo 경로는 실제 결과를 반환했다. 현재는 이 경로도 명시적으로 선택할 수 있다. 세 질문을 두 번씩 실행해6회 모두 기대한 공식 도메인을 찾았고, 실제64K 에이전트도 케이블카·박물관 주소와 출처를 반환했다. 반복 실험의 실질적인 결과 제공 엔진은 Yahoo였으며 범용 안정성이 입증된 것은 아니다. 기본 공급자는 DDGS로 유지한다. Google을 다른 엔진으로 조용히 대체하지 않으며, 계정 인증 파일 재사용 기능은 아직 없다.

`memory agent`가 과거 원문용 메모리 도구와 공개 웹검색을 선택한다. 여행 검색어·사이트 순서는 고정하지 않는다. 기존 `memory answer`는 메모리만 사용하는 2-Step RAG로 유지한다.

## 실행

프로젝트 가상환경에서 변경된 의존성을 설치한다. Ollama는 에이전트 실행 때만 필요하다.

```powershell
python -m pip install -e .
# 검색만 확인: LLM 호출 없음
travel-agent web search "춘천 삼악산 호수케이블카 공식 홈페이지" --top-k 3
# 에이전트: 도구 사용 여부·검색어는 모델이 결정
travel-agent memory --user demo --session trip agent "춘천 삼악산 호수케이블카 공식 홈페이지를 찾아줘"
# 웹 도구 제외: 모델이 요청해도 실행기가 거부
travel-agent memory --user demo --session trip agent "강릉을 제외한 이유가 뭐였지?" --no-web
```

선택형 webserp 설치·검색·에이전트 실행:

```powershell
python -m pip install -e ".[webserp]"
travel-agent web search "국립춘천박물관 공식 홈페이지" --provider webserp --backend duckduckgo,yahoo
# 에이전트의 공급자는 호스트 설정으로 선택한다.
$env:WEB_SEARCH_PROVIDER = 'webserp'
$env:WEB_SEARCH_BACKEND = 'duckduckgo,yahoo'
travel-agent memory --user demo --session trip agent "국립춘천박물관 공식 홈페이지를 찾아줘"
# 기존 공급자로 복귀
$env:WEB_SEARCH_PROVIDER = 'ddgs'
$env:WEB_SEARCH_BACKEND = 'duckduckgo,bing'
```

`webserp` extra는 검토한 Git 커밋 e13148334995745f104a69ce7127179785ee741e를 고정한다. 원본의 요청 생성·파싱 단계를 재사용하고 세션은 호출마다 소유하고 닫는다. HTML 엔진은 원본의 최종 URL 소문자 중복 제거 전에 결과를 받아 공통 URL 처리로 보낸다. Google은 원본 영어·arc 요청을 유지하며 `--backend google`로 별도 진단할 수 있다. 다른 엔진으로 자동 대체하지 않는다.

이전에 만든 합성 메모리를 활용하려면 [Agentic RAG 실행 절차](agentic-rag.md)를 따른다. 웹검색 자체에는 메모리 색인이 필요 없다. DB를 여는 현재 CLI 구조는 유지한다.

## 공급자와 반환 범위

공급자는 `WEB_SEARCH_PROVIDER` 또는 검색 단독 CLI의 `--provider`로 선택한다. 기본 `ddgs`의 엔진은 `duckduckgo,bing`이다. `webserp`는 `google` 단독, 또는 `duckduckgo`·`yahoo` 단독/조합을 지원한다. 공급자를 바꿀 때 엔진도 명시적으로 맞춘다. webserp의 엔진 설정을 생략하면 기존 호환성상 google이 선택되므로 현재 동작 사례를 재현하려면 반드시 `duckduckgo,yahoo`를 지정한다. `auto`는 허용하지 않는다. DDGS 지원 목록은 duckduckgo,bing,brave,google,yahoo,mojeek,startpage,yandex다. API 키·별도 검색 서버는 필요 없지만 엔진별 가용성은 보장하지 않는다.

HTML 경로의 각 결과에는 실제 `engine`이 포함되고 `engines_returned`, `empty_or_unparsed_engines`, `engine_errors`가 개별 엔진 상태를 나타낸다. 한 엔진만 결과를 냈을 때 두 엔진 모두 성공했다고 기록하지 않는다. 모든 엔진이 빈 파싱 결과를 내면 정상적인 빈 검색으로 단정하지 않고 오류를 반환한다. 한 도구에서 두 엔진을 선택하면 내부 요청도 두 개이며, 병렬 도구 worker3개와 조합하면 동시에 최대6개 엔진 요청이 생길 수 있다.

webserp의 HTTP 오류·접근 안내·해석되지 않은 응답은 `WebSearchError`로 전달한다. `provider`, `status`, `http_status`, `response_kind` 등을 CLI JSON과 에이전트 trace의 오류 결과에 보존한다. HTTP 200의 빈 파싱 결과를 검색 성공으로 만들지 않는다. 검색 단독 CLI는 이 오류에 종료 코드1을 반환한다. 응답 HTML·쿠키·인증 헤더는 기록하지 않는다.

모델 도구 인자는 `query`(1..500자), `top_k`(정수1..5, 기본3)뿐이다. 결과는 제목·URL·검색 요약·출처 ID다. HTTP(S) 주소 정리·중복 제거, 제목200자·요약600자 제한, 전체3500 UTF-8 바이트 한도를 적용한다. 결과가 길면 요약 잘림과 제외 수를 표시하고 URL을 중간에 자르지 않는다.

`content_kind=search_snippet`, `page_fetched=false`는 **검색 결과만 읽었다**는 뜻이다. `searched_at`은 조회 시각이며 페이지 작성·갱신 시각이 아니다. 공식 홈페이지와 블로그가 함께 나올 수 있다. 현재 가격·잔여 객실·정상 운행을 검증하는 도구가 아니다. 본문 수집·검색 결과 자동 저장·메모리 색인 갱신은 없다.

## 실행 여부와 출처 확인

같은 모델 응답에 포함된 여러 웹검색은 기본 최대3개를 병렬 실행한다. `--tool-workers 1`로 순차 실행, 1..4 범위로 동시 실행 수를 조정할 수 있다. 결과를 전부 모은 뒤 모델에 넘기며, 각 결과는 요청 순서와 호출 ID를 유지한다. [병렬 도구 실험](research/2026-10-17-011-parallel-tools.md)에 실제 모델 요청·실패와 검증 범위를 기록했다.

에이전트 결과에는 `web_search_attempted`(검증을 통과한 도구 실행 시도), `web_search_performed`(제공자가 정상 결과를 반환), `web_sources`(반환된 URL·제목·조회 시각·인용 여부)가 있다. 성공한 빈 검색도 performed=true지만 근거가 생긴 것은 아니다. `no_results`와 `no_usable_results`를 구분한다. 공급자 실패는 tool_error이며 정보가 존재하지 않는다는 증거가 아니다.

최종 답변의 `[web:...]`는 실제 제공된 ID인지 검사한다. 이 검사는 문장별 뒷받침이나 인용 누락을 모두 찾지 못한다. 메모리 인용만 있어도 citation_status=valid가 될 수 있으며, 실제 복합 테스트에서 웹 인용 누락이 관찰됐다. `--no-web`은 네트워크 도구 실행을 차단하지만 모델의 허위 URL 생성을 막아주지는 않는다. 답변 문구만 보고 검색 성공을 판단하지 않는다.

실제 도구 인자·결과·오류·모델 답변·토큰·시간은 기존 요청별 trace에 남는다. 원본 추적 기록은 Git에서 제외한다. 사용자가 질문한 내용 중 모델이 만든 검색어는 외부 검색 엔진으로 전송된다. 자동 개인정보 마스킹은 아직 없다.

## 한계와 검증

웹검색 보강을 위해8개 공개 저장소와 공식 문서·논문을 검토했다. 검색 공급자의 우선 비교 후보는 SearXNG와 OpenSERP, 본문 수집 후보는 Crawl4AI다. Firecrawl·Jina의 호스팅 기능과 자체 운영 범위도 구분했다. [조사와 채택 판단](research/2026-10-17-013-web-search-strengthening.md), [실행 전 평가 입력10개](../examples/web-search-evaluation.json)를 참고한다. 후보를 설치하거나 검색 성공률을 비교한 결과는 아직 없으며 현재 런타임은 DDGS다.

관리형 API 조사에는 Ollama Web Search/Fetch, Tavily, Exa, Brave Search API와 제3자 Serper도 포함했다. 이후 사용자는 종량 요금뿐 아니라 무료 API의 사용량 제한도 강하게 꺼린다고 밝혔다. 현재는 자체 운영을 우선 검토한다. SearXNG·OpenSERP 같은 외부 검색 중계와 YaCy 같은 독립 색인을 구분하며, 현재 결과만으로 한국어 범용 검색 품질을 보장하지 않는다. [로컬 검색과 비용 조사](research/2026-10-17-014-local-search-and-cost.md)를 참고한다. 계정·키 생성이나 공급자 전환은 아직 수행하지 않았고 현재 런타임은 DDGS다.

DDGS는 비공식 검색 경로이므로 차단·속도 제한·결과 변동이 가능하다. 기본 도구 timeout은15초, 단독 CLI에서 최대30초다. 라이브러리 내부 재시도·동기 작업 때문에 전체 종료 시각을 강제 보장하지는 않는다. 과거 메모리와 공개 웹을 구분하도록 프롬프트를 제공하지만 완전한 라우팅·프롬프트 인젝션 방어는 검증하지 않았다.

DDGS 9.16.0 진단에서 기본 설정의 bing은 비활성화되어 실제 선택 엔진이 duckduckgo 하나였다. 재현 시 박물관 검색은 DuckDuckGo 202(봇 확인 표식), 대체 엔진은 Brave 429·Google 403을 반환했다. DDGS가 200 이외 응답을 결과 없이 처리해 최종 `No results found.` 예외로 나타났다. 이전 실패의 HTTP 원인을 소급 확정하는 결과는 아니다. 검색 결과 부재와 접근 실패를 현재 오류 문구만으로 구분하지 못한다.

```powershell
# LLM 없이 같은 공개 검색어의 실제 엔진·HTTP 응답·추출 개수를 진단
python scripts/diagnose_web.py
```

진단은 해당 프로세스에서만 DDGS 호출을 관찰하고 원본 HTML·쿠키·인증 헤더를 저장하지 않는다. 실제 결과와 내장 웹검색의 비교는 [연구일지012](research/2026-10-17-012-search-diagnosis.md)에 기록한다. 이 진단은 기존 에이전트 trace에 자동 적용되지 않는다.

```powershell
python -m unittest discover -s tests -v
python scripts/evaluate_web.py
# 한 사례만 실행할 수도 있다.
python scripts/evaluate_web.py --case official --output artifacts/web-official.json
```

6개 소규모 개발 사례에 같은 로컬 모델을 사용한다. 웹 비활성화·공식 홈페이지·인사·과거 기억·복합 요청·의도적 공급자 오류를 구분한다. 결과 변동과 실패를 포함한 실제 질문·답변은 [연구일지010](research/2026-10-17-010-web-search.md)에 정리했다. 완료 상태는 품질 통과가 아니다.
