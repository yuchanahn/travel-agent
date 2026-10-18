# 030: Bing 장애를 DDGS 유지보수·요청 방식·HTML 파싱으로 나눠 조사하다

## 문제와 좋은 결과의 기준

DDG와 Bing을 함께 쓰기로 했는데, Bing은 라이브러리에서 비활성 상태였고 앞선 직접 진단에서는 무관한 결과가 왔다. 이번 목표는 업데이트 중단 여부, 다른 사용자의 재현, 실제로 고칠 수 있는 부분을 구분하는 것이다. 좋은 결과는 HTTP200이나 제목에 검색어가 있다는 사실을 넘어, 미리 정한 공식 도메인을 상위5개에서 찾는 것이다. 이는 소규모 공식 홈페이지 탐색 검사이며 여행 추천 전체 품질 평가는 아니다.

<callout icon="💬" color="blue_bg">
	**개발 요청**
	빙 왜그래? 좀 알아봐봐... 뭐야? DDGS 요즘 업데이트 멈춤? 조사좀 해봐. 너만이러는지 해결법이 뭔지
</callout>

조사 결과, DDGS 전체가 폐기된 것은 아니었다. 다만 Bing의 무관한 결과 문제는 오래 미해결 상태였다. 이번 실험에서는 관련 결과를 받는 조건도 찾았고, 그 HTML을 DDGS 파서가 놓치는 별도 문제도 재현했다. 애플리케이션의 Bing 활성화 정책은 바꾸지 않았다.

## 실제 질문과 검색 결과

LLM을 호출하지 않고 Bing 검색 응답을 직접 비교했다. 따라서 아래는 에이전트가 작성한 답변이 아니라 검색 결과의 실제 제목·주소다. 처음8회는 두 질문에 네 가지 요청 방식을 비교했고, 다음12회는 세 질문에 DDGS 원본 요청과 단순 HTTP 요청을 두 번씩 실행했다.

<callout icon="🔎" color="blue_bg">
	**실제 검색어1**
	Python official website
</callout>

첫 비교에서 단순 HTTP와 기존 파라미터의 curl 요청은 다음 결과를 반환했다.

> Welcome to Python.org
> https://www.python.org/

그런데 같은 질문에 setlang=en·cc=gb를 붙이면 영국 상업용 부동산 변호사, mkt=en-gb를 붙이면 Canary Wharf 회의실 결과가 왔다. 두 응답 모두 HTTP200이었고 HTML 제목에는 실제 검색어가 있었다. 후속 비교에서는 단순 HTTP와 DDGS 원본 요청 모두 두 번씩 Python 공식 주소를 찾았다.

<callout icon="🔎" color="blue_bg">
	**실제 검색어2**
	국립춘천박물관 공식 홈페이지
</callout>

첫 비교의 네 방식 모두 공식 주소를 찾았다. 후속 단순 HTTP의 첫 결과는 다음과 같았다.

> 국립춘천박물관 - Museum
> https://chuncheon.museum.go.kr/kor/index.do

후속 DDGS 원본 파서는 첫 반복에서는 이 제목·주소를 추출했지만 두 번째 반복의 상위5개에서는 제목과 주소가 모두 빈 문자열이었다. **그 두 번째 HTML을 보완 파서로 읽으면 위 공식 주소가 나왔다.** 서버의 무관한 결과와 파싱 실패가 서로 다른 문제임을 보여준다.

<callout icon="🔎" color="blue_bg">
	**추가 실제 검색어3**
	춘천 삼악산 호수케이블카 공식 홈페이지
</callout>

후속 단순 HTTP 두 반복 모두 첫 결과가 다음과 같았다.

> 춘천 삼악산 호수 케이블카
> https://samaksancablecar.com/

DDGS 원본 파서는 첫 반복의 상위5개 제목·주소가 모두 빈 문자열이었고, 두 번째는 위 결과를 추출했다. 첫 HTML에도 실제 공식 링크가 있었으며 보완 파서로 추출할 수 있었다.

## DDGS 업데이트가 멈춘 것인가

2026-10-18에 GitHub API와 PyPI를 확인했다. 설치본과 최신 배포는 모두 **9.16.0**, 배포일은 **2026-08-26**이다. 최신 main 커밋도 같은 날이며 약53일간 새 main 커밋은 없었다. 저장소는 archived=false·disabled=false이고9월에 접수된 미병합 PR도 있다. 활동이 뜸한 것은 맞지만 폐기됐다고 확정할 근거는 없다. 저장소 updated_at과 코드 push 시각도 구분했다. [최신 릴리스](https://github.com/deedy5/ddgs/releases/tag/v9.16.0), [PyPI](https://pypi.org/project/ddgs/), [열린 PR](https://github.com/deedy5/ddgs/pulls).

Bing 파일의 마지막 변경은 **2025-11-29**의 비활성화다. 이후 최신 릴리스에도 disabled=True가 남아 있다. 단순 pip 업데이트로 이번 Bing 문제를 고칠 새 버전은 없었다. [비활성화 PR399](https://github.com/deedy5/ddgs/pull/399), [설치본과 대응하는 소스](https://github.com/deedy5/ddgs/blob/70a5635510fb8d5b15d5ba6ceced6a67e212149b/ddgs/engines/bing.py).

## 우리 환경만의 문제인가

[DDGS 이슈375](https://github.com/deedy5/ddgs/issues/375)에는2025년11월부터 무관한 검색 결과 보고가 있다. 다른 사용자도 재현했고, 관리자는 해결 전까지 Bing을 비활성화했다. 현실적인 헤더와 쿠키로 고쳤다는 댓글도 있지만 재현 가능한 패치가 없어 해결책으로 채택하지 않았다. 봇에 의도적으로 가짜 결과를 준다는 추측 역시 확인된 사실로 쓰지 않는다.

[SearXNG 이슈4964](https://github.com/searxng/searxng/issues/4964)에도 첫 단어만 반영하거나 무관한 결과가 오는 사례가 있다. 즉 우리 코드에만 국한된 증상은 아니다.

## 최근 수정과 공개 구현을 검증하다

[SearXNG PR6671](https://github.com/searxng/searxng/pull/6671)은2026-09-11 병합됐다. 언어·국가 파라미터 처리와 쿠키 사용을 바꾼다. 그러나 논의에는 효과가 없거나 다시 실패했다는 보고도 있다. 적용하면 무조건 해결되는 패치로 보지 않고, setlang+cc와 setlang+mkt를 비교 가설로만 사용했다. 이번 영어 질의에서는 오히려 무관한 결과가 왔다. 한국어 두 조건은 성공했다. PR 전체 구현을 복사하지 않고 요청 조건을 독립적으로 비교했다.

[ChocoData의 공개 Bing HTTP 코드](https://github.com/ChocoData-com/bing-scraper/blob/9fec1788c7522db1404b4fbde65385f667b81ee0/free_scraper/bing_free_scraper.py)도 클론 후 소스를 확인했다. requests로 q만 보내는 방식과 h2 안에 링크가 없을 때 다른 결과 링크를 읽는 방식이 있었다. 작성자의 성공률 주장은 우리 검증 결과와 구분했다. 저장소 코드를 실행·설치하지 않고, 기존 환경의 표준 urllib로 비슷한 요청을 직접 시험했다. 따라서 원본 requests 구현을 그대로 재현한 실험은 아니다. 브라우저 UA를 지정하지 않아도 Python 클라이언트의 기본 UA는 존재한다.

## 요청 비교 결과와 해석

| 비교 | 방식 | 공식 도메인 상위5개 포함 | 해석 |
| --- | --- | --- | --- |
| 첫 두 질문 | 기존 파라미터·EDGE 쿠키·curl edge101 | 2/2 | 앞선 무관한 응답과 달리 이번에는 관련 결과 |
| 첫 두 질문 | setlang+cc·쿠키 없음·curl edge101 | 1/2 | 영어 질의 실패 |
| 첫 두 질문 | setlang+mkt·쿠키 없음·curl edge101 | 1/2 | 영어 질의 실패 |
| 첫 두 질문 | q만·urllib·저장 쿠키 없음 | 2/2 | 단순 요청 후보 확인 |
| 세 질문×2반복 | q만·urllib·보완 파서 | 6/6 | 이 짧은 실행 구간의 성공 |
| 세 질문×2반복 | DDGS 원본 HTTP·보완 파서 | 6/6 | 관련 HTML은 모두 존재 |
| 위와 같은6개 HTML | DDGS 원본 파서 | 4/6 | 두 HTML에서 상위5개 제목·주소 추출 누락 |

총20회 검색 HTTP 요청이 모두200이었다. 그렇지만 첫 비교의2회는 정한 목표 도메인을 찾지 못했고 결과가 무관했다. 응답 성공률을 검색 품질로 바꾸지 않는다. 후속12회는 모두 목표를 찾았지만 고작3개 질문·짧은 시간대이며 독립적인 장기 가용성 검증이 아니다.

DDGS는 primp의 random impersonation을 사용한다. HTML 형태가 요청마다 달라졌지만 지문이 원인인지, 서버 변동이나 다른 조건 때문인지는 분리하지 못했다. 기존 요청도 후속 비교에서 정상 결과를 받았으므로 “urllib로 바꿔서 무관한 결과 문제가 해결됐다”는 인과 주장은 할 수 없다. en-gb 조건의 실패 역시 IP·국가 설정 중 무엇이 원인인지 확정하지 않는다.

## 확인한 해결 범위와 결정

1. **파싱 누락은 재현·보완했다.** h2 텍스트와 링크가 분리된 HTML도 읽도록 연구용 파서를 만들었다. 같은 응답에서 빈 결과를 공식 링크로 복원했다. URL 안전성 검사·Bing 이동 링크 해석·광고 및 Bing 자체 링크 제외를 적용했다.
2. **무관한 응답의 보편적 해결책은 아직 없다.** 국가 설정 패치·단순 HTTP는 후보이고, 짧은 성공이 DDGS 전체 수정이나 Bing의 안정성 입증은 아니다.
3. **앱의 Bing 비활성화는 유지한다.** disabled 플래그나 설치된 라이브러리를 고치지 않았다. 이번 산출물은 재현 가능한 진단기다. 후속 도입 후보는 DDGS 전체 교체보다 독립 Bing HTTP 어댑터와 두 HTML 형태를 지원하는 파서이며, 실제 혼합 질의·시간 간격을 둔 재검증이 필요하다. 현재 런타임의 두 엔진 실검색 성공으로 기록하지 않는다.

추가 비용은 검색 HTTP20회와 공개 소스·메타데이터 조회다. 유료 API나 LLM 호출, 브라우저 실행, 모델 변경은 없었다. 네트워크 요청 횟수를 토큰 절감 측정으로 표시하지 않는다. 원본 응답은 비공개로 보관하고 공개 기록에 쿠키·인증 헤더는 넣지 않았다.

<details>
<summary>실제 구현·다이어그램·실행 방법</summary>
	기준 코드는 main의59e7ba0이며, 이 기록과 함께 추가한 scripts/diagnose_bing.py의 parse_results·run·main이 진단 실행 경로다. 실제 코드 발췌다.
	```python
	        title = ' '.join(headings[0].text_content().split())
	        anchors = headings[0].xpath('.//a[@href]') or item.xpath('.//a[@href]')
	        target = None
	        for anchor in anchors:
	            candidate = anchor.get('href')
	            if candidate.startswith('https://www.bing.com/ck/a?'):
	                try:
	                    candidate = unwrap_bing_url(candidate)
	                except (ValueError, UnicodeError):
	                    continue
	            clean = _clean_url(candidate) if candidate else None
	            if clean and urlsplit(clean).hostname not in {'bing.com', 'www.bing.com'}:
	                target = clean
	                break
	```
	parse_results는 제목과 링크를 독립적으로 찾는다. run은 실제 요청·응답·원본 파서와 보완 파서 결과를 기록한다. main은 정해진 공개 질의와 반복 횟수를 실행한다. expected_domain_found는 이 실험에서 미리 정한 정답 도메인 검사이며 일반 사용자 검색 결과의 자동 관련성 판정기는 아니다.
	```mermaid
	flowchart TD
	    Q[같은 공개 검색어] --> A[DDGS 원본 요청]
	    Q --> B[단순 urllib 요청]
	    Q --> C[언어 및 국가 조건 비교]
	    A --> H[실제 Bing HTML]
	    B --> H
	    C --> H
	    H --> P[원본 파서와 보완 파서 비교]
	    P --> D[상위5개 기대 도메인 검사]
	    D --> R[요청별 진단 기록]
	    R --> K[앱 활성화와 별도로 판단]
	```
	기본 설치의 DDGS·lxml을 사용하며 legacy·locale·market 비교에는 기존 google-http extra의 curl_cffi가 필요하다. 단순 plain·ddgs 비교에는 curl_cffi가 필요 없다. HTTP 응답은 쿠키 재사용 없이 비교하며 로그인 계정을 쓰지 않는다.
	```powershell
	python scripts/diagnose_bing.py
	python scripts/diagnose_bing.py --variant ddgs --variant plain --include-travel --repeat 2
	python -m unittest discover -s tests -q
	```
	실제 전체 테스트 결과:
	```text
	Ran 106 tests in 2.435s
	OK
	```
	추가4개는 네트워크 없는 회귀 검사다. 제목 안의 링크·분리된 링크·Bing 이동 링크·사용 불가 URL과 유사 CSS 클래스 제외를 확인한다. 실검색 품질 검사는 위20회와 구분한다.
</details>

<details>
<summary>실제 툴콜·HTTP 진단 로그 — 20회 검색과 유지보수 조회</summary>
	모델 요청·다음 모델 입력 전달은 없다. 개발자가 아래 진단 요청을 직접 실행했다. 시각은 UTC이며 한국 시간은9시간을 더한다. 공개 검색어와 결과 제목·주소만 발췌하고 쿠키·헤더·응답 원문은 제외했다. expected_domain_found는 별도의 실험 판정이다.

	**첫 비교 1 — Bing GET /search**
	- 호출 ID: 9c296a1d89ee46cc81f03c4b322589da
	- 순서·시각: 2026-10-18T06:50:44.723878+00:00 → 2026-10-18T06:50:45.271297+00:00 (547ms)
	- 방식: legacy; 반복 1
	- 실제 인자: `{"q": "Python official website", "pq": "Python official website", "cc": "kr"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: Welcome to Python.org
	- 첫 결과 주소: https://www.python.org/

	**첫 비교 2 — Bing GET /search**
	- 호출 ID: 9cf94dfd768e4180907a56c23589c9ff
	- 순서·시각: 2026-10-18T06:50:45.272297+00:00 → 2026-10-18T06:50:45.646593+00:00 (375ms)
	- 방식: locale; 반복 1
	- 실제 인자: `{"q": "Python official website", "setlang": "en", "cc": "gb", "adlt": "moderate"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=False
	- 첫 결과 제목: Commercial property solicitors - Clarke Willmott LLP
	- 첫 결과 주소: https://www.clarkewillmott.com/legal-services/commercial-property/

	**첫 비교 3 — Bing GET /search**
	- 호출 ID: 05e2842aa8d64496a982d4bd3037247b
	- 순서·시각: 2026-10-18T06:50:45.647592+00:00 → 2026-10-18T06:50:45.892806+00:00 (246ms)
	- 방식: market; 반복 1
	- 실제 인자: `{"q": "Python official website", "setlang": "en", "mkt": "en-gb", "adlt": "moderate"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=False
	- 첫 결과 제목: Meeting Room at Regus | Canary Wharf Cabot Square
	- 첫 결과 주소: https://liquidspace.com/uk/england/london/regus-canary-wharf-cabot-square/meeting-room-bfd4

	**첫 비교 4 — Bing GET /search**
	- 호출 ID: 1d8602ad724d4f9286d786d9475a25bb
	- 순서·시각: 2026-10-18T06:50:45.894311+00:00 → 2026-10-18T06:50:46.125398+00:00 (231ms)
	- 방식: plain; 반복 1
	- 실제 인자: `{"q": "Python official website"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: Welcome to Python.org
	- 첫 결과 주소: https://www.python.org/

	**첫 비교 5 — Bing GET /search**
	- 호출 ID: d08ff7839d1847288eb2d9b3278c3622
	- 순서·시각: 2026-10-18T06:50:46.126392+00:00 → 2026-10-18T06:50:46.423112+00:00 (297ms)
	- 방식: legacy; 반복 1
	- 실제 인자: `{"q": "국립춘천박물관 공식 홈페이지", "pq": "국립춘천박물관 공식 홈페이지", "cc": "kr"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 국립춘천박물관 - Museum
	- 첫 결과 주소: https://chuncheon.museum.go.kr/kor/index.do

	**첫 비교 6 — Bing GET /search**
	- 호출 ID: aa97cd9cd765491597e4f6c00f3f15ec
	- 순서·시각: 2026-10-18T06:50:46.424112+00:00 → 2026-10-18T06:50:46.579602+00:00 (156ms)
	- 방식: locale; 반복 1
	- 실제 인자: `{"q": "국립춘천박물관 공식 홈페이지", "setlang": "ko", "cc": "kr", "adlt": "moderate"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 국립춘천박물관 - Museum
	- 첫 결과 주소: https://chuncheon.museum.go.kr/kor/index.do

	**첫 비교 7 — Bing GET /search**
	- 호출 ID: 5fff3aae8b9f429683ba39c658cdf308
	- 순서·시각: 2026-10-18T06:50:46.580600+00:00 → 2026-10-18T06:50:46.833969+00:00 (254ms)
	- 방식: market; 반복 1
	- 실제 인자: `{"q": "국립춘천박물관 공식 홈페이지", "setlang": "ko", "mkt": "ko-kr", "adlt": "moderate"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 국립춘천박물관 - Museum
	- 첫 결과 주소: https://chuncheon.museum.go.kr/kor/index.do

	**첫 비교 8 — Bing GET /search**
	- 호출 ID: b803922018ef433194b264c5bb8ac5f8
	- 순서·시각: 2026-10-18T06:50:46.835487+00:00 → 2026-10-18T06:50:47.060812+00:00 (226ms)
	- 방식: plain; 반복 1
	- 실제 인자: `{"q": "국립춘천박물관 공식 홈페이지"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 국립춘천박물관 - Museum
	- 첫 결과 주소: https://chuncheon.museum.go.kr/kor/index.do

	**후속 반복 1 — Bing GET /search**
	- 호출 ID: 0b7051a17bfe4edba998f61c0c6633bc
	- 순서·시각: 2026-10-18T06:53:10.725810+00:00 → 2026-10-18T06:53:11.071179+00:00 (345ms)
	- 방식: ddgs; 반복 1
	- 실제 인자: `{"q": "Python official website", "pq": "Python official website", "cc": "kr"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: Welcome to Python.org
	- 첫 결과 주소: https://www.python.org/
	- 같은 HTML의 DDGS 원본 파서 상위5개: 제목·주소 추출됨

	**후속 반복 2 — Bing GET /search**
	- 호출 ID: ad7f6cd7f5034155835d0e6739960b5a
	- 순서·시각: 2026-10-18T06:53:11.072180+00:00 → 2026-10-18T06:53:11.389658+00:00 (318ms)
	- 방식: plain; 반복 1
	- 실제 인자: `{"q": "Python official website"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: Welcome to Python.org
	- 첫 결과 주소: https://www.python.org/

	**후속 반복 3 — Bing GET /search**
	- 호출 ID: 8c1127609ee54687bf61581fd549b919
	- 순서·시각: 2026-10-18T06:53:11.390657+00:00 → 2026-10-18T06:53:11.899710+00:00 (509ms)
	- 방식: ddgs; 반복 1
	- 실제 인자: `{"q": "국립춘천박물관 공식 홈페이지", "pq": "국립춘천박물관 공식 홈페이지", "cc": "kr"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 국립춘천박물관 - Museum
	- 첫 결과 주소: https://chuncheon.museum.go.kr/kor/index.do
	- 같은 HTML의 DDGS 원본 파서 상위5개: 제목·주소 추출됨

	**후속 반복 4 — Bing GET /search**
	- 호출 ID: 389186c378114e6ab61e3c129acff366
	- 순서·시각: 2026-10-18T06:53:11.900727+00:00 → 2026-10-18T06:53:12.226443+00:00 (326ms)
	- 방식: plain; 반복 1
	- 실제 인자: `{"q": "국립춘천박물관 공식 홈페이지"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 국립춘천박물관 - Museum
	- 첫 결과 주소: https://chuncheon.museum.go.kr/kor/index.do

	**후속 반복 5 — Bing GET /search**
	- 호출 ID: 91bb31e5d6c04bd3a0182a43d766f92b
	- 순서·시각: 2026-10-18T06:53:12.228583+00:00 → 2026-10-18T06:53:12.450689+00:00 (221ms)
	- 방식: ddgs; 반복 1
	- 실제 인자: `{"q": "춘천 삼악산 호수케이블카 공식 홈페이지", "pq": "춘천 삼악산 호수케이블카 공식 홈페이지", "cc": "kr"}`
	- 응답: HTTP200; 추출 5개; 기대 도메인 포함=True
	- 첫 결과 제목: 춘천 삼악산 호수 케이블카
	- 첫 결과 주소: https://samaksancablecar.com/
	- 같은 HTML의 DDGS 원본 파서 상위5개: 제목·주소 모두 빈 문자열

	**후속 반복 6 — Bing GET /search**
	- 호출 ID: 5bd3e276f76b4428bf659b0d73496221
	- 순서·시각: 2026-10-18T06:53:12.451689+00:00 → 2026-10-18T06:53:12.753313+00:00 (301ms)
	- 방식: plain; 반복 1
	- 실제 인자: `{"q": "춘천 삼악산 호수케이블카 공식 홈페이지"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 춘천 삼악산 호수 케이블카
	- 첫 결과 주소: https://samaksancablecar.com/

	**후속 반복 7 — Bing GET /search**
	- 호출 ID: 349af923bd3c47a285727d0b876731f3
	- 순서·시각: 2026-10-18T06:53:12.754314+00:00 → 2026-10-18T06:53:13.045257+00:00 (291ms)
	- 방식: ddgs; 반복 2
	- 실제 인자: `{"q": "Python official website", "pq": "Python official website", "cc": "kr"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: Welcome to Python.org
	- 첫 결과 주소: https://www.python.org/
	- 같은 HTML의 DDGS 원본 파서 상위5개: 제목·주소 추출됨

	**후속 반복 8 — Bing GET /search**
	- 호출 ID: 9c5cf2d48ff8417281f0a1da1d11cc4a
	- 순서·시각: 2026-10-18T06:53:13.047259+00:00 → 2026-10-18T06:53:13.338462+00:00 (291ms)
	- 방식: plain; 반복 2
	- 실제 인자: `{"q": "Python official website"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: Welcome to Python.org
	- 첫 결과 주소: https://www.python.org/

	**후속 반복 9 — Bing GET /search**
	- 호출 ID: f93032ac64a94ecebe0cfbd7230f82d4
	- 순서·시각: 2026-10-18T06:53:13.339462+00:00 → 2026-10-18T06:53:13.501395+00:00 (162ms)
	- 방식: ddgs; 반복 2
	- 실제 인자: `{"q": "국립춘천박물관 공식 홈페이지", "pq": "국립춘천박물관 공식 홈페이지", "cc": "kr"}`
	- 응답: HTTP200; 추출 5개; 기대 도메인 포함=True
	- 첫 결과 제목: 국립춘천박물관 - Museum
	- 첫 결과 주소: https://chuncheon.museum.go.kr/kor/index.do
	- 같은 HTML의 DDGS 원본 파서 상위5개: 제목·주소 모두 빈 문자열

	**후속 반복 10 — Bing GET /search**
	- 호출 ID: 9a31298d1379496a9dffad5fcd20c8c0
	- 순서·시각: 2026-10-18T06:53:13.502416+00:00 → 2026-10-18T06:53:13.793399+00:00 (291ms)
	- 방식: plain; 반복 2
	- 실제 인자: `{"q": "국립춘천박물관 공식 홈페이지"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 국립춘천박물관 - Museum
	- 첫 결과 주소: https://chuncheon.museum.go.kr/kor/index.do

	**후속 반복 11 — Bing GET /search**
	- 호출 ID: 4774a0690a6e414db46dd0eecf1bde68
	- 순서·시각: 2026-10-18T06:53:13.794398+00:00 → 2026-10-18T06:53:14.053018+00:00 (259ms)
	- 방식: ddgs; 반복 2
	- 실제 인자: `{"q": "춘천 삼악산 호수케이블카 공식 홈페이지", "pq": "춘천 삼악산 호수케이블카 공식 홈페이지", "cc": "kr"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 춘천 삼악산 호수 케이블카
	- 첫 결과 주소: https://samaksancablecar.com/
	- 같은 HTML의 DDGS 원본 파서 상위5개: 제목·주소 추출됨

	**후속 반복 12 — Bing GET /search**
	- 호출 ID: 1a75e02c94684e9db18a5979ab8e967b
	- 순서·시각: 2026-10-18T06:53:14.055018+00:00 → 2026-10-18T06:53:14.445058+00:00 (390ms)
	- 방식: plain; 반복 2
	- 실제 인자: `{"q": "춘천 삼악산 호수케이블카 공식 홈페이지"}`
	- 응답: HTTP200; 추출 10개; 기대 도메인 포함=True
	- 첫 결과 제목: 춘천 삼악산 호수 케이블카
	- 첫 결과 주소: https://samaksancablecar.com/

	**공개 메타데이터 조회**
	- 실제 실행 호출: exec b37819; 조회 묶음 기록 시각 2026-10-18T06:48:35.286047+00:00; 요청별 별도 호출 ID·시각은 수집하지 않았다.
	- urllib GET으로 아래9개 URL을 조회했고 응답을 보존했다. 조회 결과는 본문에 요약했다.
	- https://api.github.com/repos/deedy5/ddgs
	- https://api.github.com/repos/deedy5/ddgs/releases/latest
	- https://api.github.com/repos/deedy5/ddgs/commits?per_page=5
	- https://api.github.com/repos/deedy5/ddgs/commits?path=ddgs/engines/bing.py&per_page=5
	- https://api.github.com/repos/deedy5/ddgs/pulls/399
	- https://api.github.com/repos/deedy5/ddgs/issues/375/comments
	- https://api.github.com/repos/deedy5/ddgs/pulls?state=open&per_page=30
	- https://pypi.org/pypi/ddgs/json
	- https://api.github.com/repos/ChocoData-com/bing-scraper/contents
	- Git 클론: ChocoData-com/bing-scraper; 검토 HEAD 9fec1788c7522db1404b4fbde65385f667b81ee0. 설치·원본 실행은 하지 않았다.
	- 첫 진단 실행은 requests 모듈 누락으로 네트워크 전에 중단됐다. urllib로 바꾼 뒤 위 요청20회를 실행했다.
</details>
