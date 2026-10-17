# 웹검색 도구

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

이전에 만든 합성 메모리를 활용하려면 [Agentic RAG 실행 절차](agentic-rag.md)를 따른다. 웹검색 자체에는 메모리 색인이 필요 없다. DB를 여는 현재 CLI 구조는 유지한다.

## 공급자와 반환 범위

DDGS 9.x를 사용하며 기본 엔진은 `duckduckgo,bing`이다. API 키·별도 검색 서버는 필요 없다. 엔진은 호스트 환경변수 `WEB_SEARCH_BACKEND`로, 검색 단독 CLI에서는 `--backend`로 선택한다. `auto`는 허용하지 않는다. 지원 목록은 duckduckgo,bing,brave,google,yahoo,mojeek,startpage,yandex다. 엔진별 가용성은 보장하지 않는다.

모델 도구 인자는 `query`(1..500자), `top_k`(정수1..5, 기본3)뿐이다. 결과는 제목·URL·검색 요약·출처 ID다. HTTP(S) 주소 정리·중복 제거, 제목200자·요약600자 제한, 전체3500 UTF-8 바이트 한도를 적용한다. 결과가 길면 요약 잘림과 제외 수를 표시하고 URL을 중간에 자르지 않는다.

`content_kind=search_snippet`, `page_fetched=false`는 **검색 결과만 읽었다**는 뜻이다. `searched_at`은 조회 시각이며 페이지 작성·갱신 시각이 아니다. 공식 홈페이지와 블로그가 함께 나올 수 있다. 현재 가격·잔여 객실·정상 운행을 검증하는 도구가 아니다. 본문 수집·검색 결과 자동 저장·메모리 색인 갱신은 없다.

## 실행 여부와 출처 확인

같은 모델 응답에 포함된 여러 웹검색은 기본 최대3개를 병렬 실행한다. `--tool-workers 1`로 순차 실행, 1..4 범위로 동시 실행 수를 조정할 수 있다. 결과를 전부 모은 뒤 모델에 넘기며, 각 결과는 요청 순서와 호출 ID를 유지한다. [병렬 도구 실험](research/2026-10-17-011-parallel-tools.md)에 실제 모델 요청·실패와 검증 범위를 기록했다.

에이전트 결과에는 `web_search_attempted`(검증을 통과한 도구 실행 시도), `web_search_performed`(제공자가 정상 결과를 반환), `web_sources`(반환된 URL·제목·조회 시각·인용 여부)가 있다. 성공한 빈 검색도 performed=true지만 근거가 생긴 것은 아니다. `no_results`와 `no_usable_results`를 구분한다. 공급자 실패는 tool_error이며 정보가 존재하지 않는다는 증거가 아니다.

최종 답변의 `[web:...]`는 실제 제공된 ID인지 검사한다. 이 검사는 문장별 뒷받침이나 인용 누락을 모두 찾지 못한다. 메모리 인용만 있어도 citation_status=valid가 될 수 있으며, 실제 복합 테스트에서 웹 인용 누락이 관찰됐다. `--no-web`은 네트워크 도구 실행을 차단하지만 모델의 허위 URL 생성을 막아주지는 않는다. 답변 문구만 보고 검색 성공을 판단하지 않는다.

실제 도구 인자·결과·오류·모델 답변·토큰·시간은 기존 요청별 trace에 남는다. 원본 추적 기록은 Git에서 제외한다. 사용자가 질문한 내용 중 모델이 만든 검색어는 외부 검색 엔진으로 전송된다. 자동 개인정보 마스킹은 아직 없다.

## 한계와 검증

웹검색 보강을 위해8개 공개 저장소와 공식 문서·논문을 검토했다. 검색 공급자의 우선 비교 후보는 SearXNG와 OpenSERP, 본문 수집 후보는 Crawl4AI다. Firecrawl·Jina의 호스팅 기능과 자체 운영 범위도 구분했다. [조사와 채택 판단](research/2026-10-17-013-web-search-strengthening.md), [실행 전 평가 입력10개](../examples/web-search-evaluation.json)를 참고한다. 후보를 설치하거나 검색 성공률을 비교한 결과는 아직 없으며 현재 런타임은 DDGS다.

관리형 API 조사 후 비교 순서를 보강했다. Ollama Web Search/Fetch, Tavily, Exa, Brave Search API와 구글 결과를 제공하는 제3자 Serper도 후보에 포함한다. 낮은 운영 부담과 무료 사용 조건을 먼저 비교하고 SearXNG·OpenSERP는 자체 운영이 필요한 경우의 후보로 유지한다. Ollama 검색은 로컬11434가 아닌 ollama.com의 외부 서비스이며 무료 계정과 API 키가 필요하다. 새 계정·키 생성이나 공급자 전환은 아직 수행하지 않았다. 현재 조건과 출처는 같은 연구일지013의 추가 조사에 기록했다.

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
