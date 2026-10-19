# 여행 에이전트

여자친구와의 여행을 준비하면서 시작한 여행 의사결정 도우미.

## 왜 만들었나

여자친구가 여행을 가자고 해서 Codex에 여행 계획을 요청했다. 불필요하게 토큰을 쓰고 기대한 결과를 얻지 못한다는 불편을 느꼈다. 실제로 필요한 여행 정보를 확인하고 조건에 맞는 후보를 비교하는 전용 에이전트를 직접 만들어, 다른 사람도 쓸 수 있도록 공개하려고 한다.

이 배경은 사용자가 겪은 경험이다. 전용 에이전트가 범용 에이전트보다 더 저렴하거나 정확하다는 것은 아직 입증하지 않았다. 구현과 평가로 확인할 가설이다.

## 로컬 화면 실행

주소는 http://127.0.0.1:50733/ 으로 고정한다. PowerShell에서 시작은 `.\scripts\start_web.ps1`, 코드 변경 후 재시작은 `.\scripts\restart_web.ps1`, 중지는 `.\scripts\start_web.ps1 -Action stop`을 사용한다. 시작을 반복해도 서버를 더 띄우지 않는다. 현재 공유 터널·Docker 웹은 중지했으며 [운영 방식](docs/web-interface.md)을 따른다.

071부터 현재 웹 공급자는 Ollama `qwen3.5:4b-q4_K_M`다. 컨텍스트65536·출력4096을 사용하며 이전 Nexus 대화의 툴 인자도 전송 시 변환한다. [공급자 설정](docs/llm-providers.md)을 따른다.

## 완료 흐름 검증

[여행3턴 인수 테스트](docs/acceptance-testing.md)로 날짜 미정·조건 확정·예산 변경을 확인한다. 068의 보완 실행은3턴을 완주했지만 사실 근거 검토는fail이다. 실행 완료를 제품 품질 통과로 보지 않는다. [숙박 API·공개 페이지 조사](docs/lodging-sources.md)에는 여기어때 실제 읽기와 NOL403, YCS 호텔별 API 범위를 구분했다.

[070 동일 근거 전후 비교](docs/quality-comparison.md)는24회 실행했으나 공급자 오류19회로 정상 쌍은1개였다. 해당 시설 쌍은이전·현재8/8 동점이며 일반 품질 향상을 입증하지 못했다.

## 현재 가능한 것

- 숙소 URL별 OpenBnB 근거 재조회와 동일 추출문 추가 읽기. 요청 날짜·인원·출처별 관측을 분리하며 사실 검증을 대신하지 않는다. [범위와 사용법](docs/lodging-evidence.md)
- Ollama 로컬 공급자 연결 및 설치·실행 모델 상태 확인
- 선택형 Nexus FreeLLMAPI/OpenAI 호환 공급자 연결: 도구 호출·웹·요약·2-Step 메모리 공통 경로. [공급자 설정](docs/llm-providers.md)
- Qwen3.5 4B Q4_K_M 한국어 응답과 가상 도구 호출 왕복 검증
- 대화 원문 저장·BM25/dense/hybrid 검색·검색 근거 기반 답변 CLI
- LLM이 메모리 검색·원문 조회를 선택하는 Agentic RAG와 요청별 실행 추적
- 호스트 에이전트는 공식 Brave 웹검색 MCP와 web_read를 연결한다. 추가 검색 발췌를 완전한 항목 단위로 보존하고 전달한 출처의 본문을 읽는다. OpenBnB는 숙소 조회 MCP로 유지한다. 직접 API 검색은 독립 검색 CLI·이전 비교에 남긴다. 키는 Git 제외 로컬 파일에서 읽는다. [연결 방법](docs/mcp.md)
- 독립 검색 파이프라인: 후보 수집 → 중복 제거·BM25Plus 재정렬 → 본문 읽기 → 제한된 발췌. Bing 직접 HTTP는 명시적 비교 경로로 남기며 자동 대체하지 않는다. [현재 실행법](docs/web-search.md)
- 선택형 webserp Google·Yahoo 연구 경로: Google은 미해결, DuckDuckGo/Yahoo 조합에서 공식 주소 조회와 실제 에이전트 답변 확인 (연구일지019)
- Google HTTP 직접 구현: `python -m travel_agent.google_http "Python official website"`. 쿠키 파일 저장·재사용, HTML 결과 파서, 선택형 QuickJS 확인 스크립트 실험. 브라우저 방식은 폐기했다. 실제 검색은 아직 실패하며 에이전트 연결 전이다. [HTTP 구현 기록](docs/research/2026-10-18-022-google-http-session.md)
- 한 응답의 여러 웹검색을 병렬 실행하고 호출별 결과·오류를 모델에 전달
- 프로젝트 기술 결정과 연구일지 기반

에이전트가 메모리와 공개 웹검색을 선택할 수 있다. 검색 출처의 본문 발췌와 저장된 추출문의 추가 구간을 읽을 수 있다. 로컬 웹 화면을 제공하지만 최신 요금 검증·실시간 예약은 아직 없다. 자율 여행 답변은 금액·인용 오류가 남아 품질 검증을 통과하지 못했다. [평가 기준과 실제 실패](docs/travel-search-evaluation.md)를 참고한다. 기존 PowerShell 테스트는 가상 여행 데이터를 사용하며 서비스 구현과 구분한다.

RAG의 첫 사용처는 **문맥 요약에서 빠진 대화·조사 원문을 다시 찾아오는 메모리**로 정했다. 웹의 원문 자동 저장·BM25·문맥 요약은 [웹 메모리](docs/web-interface.md), CLI의 별도 검색 경로는 [대화 메모리 RAG](docs/memory-rag.md)를 참고한다.

파일·함수별 구현과 실제 코드 조각, 구조·검색·답변 흐름도는 [전체 코드 해설](docs/research/2026-10-17-008-code-walkthrough.md)에 정리했다.

기존 2-Step 경로와 새 Agentic 경로의 차이, 실행 기록 조회: [Agentic RAG](docs/agentic-rag.md).

웹검색 실행과 출처·실패 상태 확인: [웹검색 도구](docs/web-search.md).

Brave 연결 후 실제 에이전트는044에서 초기·중간·보완본 여행3질의와 제어4사례를 합쳐13회 실행했다. 보완본 여행3개는 모두 종료했으나 수동 근거 검토는0/3 통과다. 인사·과거 예산/제외 이유는 통과했고 검색 장애·웹 비활성화에서도 추측을 덧붙였다. 자동 기능 검사158개 통과를 추천 품질 통과로 해석하지 않는다. [실제 질문·답변·호출 기록](docs/research/2026-10-18-044-live-brave-agent-validation.md).

## 첫 제품 범위 — 초기 제안

출발지·날짜·총예산·인원·차량 유무를 확인하고, 근거를 조회해 국내 1박 2일 여행 후보를 비교한다. 실시간 숙박·교통 가격 확정이나 예약은 첫 범위에 넣지 않는다. 데이터 출처와 사용 조건은 다음 단계에서 선정한다.

## 기술 방향

- Python 3.12 이상, 로컬 개발은 가상환경 사용
- Ollama HTTP API, 기본 모델 `qwen3.5:4b-q4_K_M`
- 단일 에이전트의 구조화된 도구 호출 루프: 관찰 → 행동 → 결과 → 재판단
- Docker는 앱 배포 시 도입 예정. 로컬 Ollama는 호스트에서 실행
- 프레임워크·RAG·멀티 에이전트는 필요를 평가한 뒤 선택

구체적인 선택 이유: [초기 기술 결정](docs/decisions/0001-initial-architecture.md).

## 개발 시작

웹 화면으로 직접 실험하려면 호스트 Ollama와 Docker를 켜고 `.\scripts\start_web.ps1`을 실행한다. 출력된 로컬 주소에서 질문과 실제 도구 기록을 확인한다. 답변 뒤 이어서 질문하거나 새 대화로 시작할 수 있다. [Docker 웹 화면 사용법](docs/web-interface.md)에 실행·중지·기록 보존 방식을 정리했다.

Windows PowerShell, Python 3.12가 필요하다. 처음 한 번 가상환경을 만들고 프로젝트를 개발 모드로 설치한다. 가상환경이 이미 있으면 생성 명령은 생략한다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
travel-agent doctor
```

이후 새 터미널에서는 활성화 후 바로 실행한다. `PYTHONPATH` 설정은 필요 없다. 개발 모드 설치는 소스를 수정하면 다음 실행에 반영되므로 일반적인 코드 변경마다 다시 설치할 필요가 없다. 의존성이나 실행 명령 등 패키지 설정을 바꿨다면 다시 설치한다.

```powershell
.\.venv\Scripts\Activate.ps1
travel-agent doctor
# 같은 동작을 모듈로 실행할 수도 있다.
python -m travel_agent doctor
```

활성화 없이 가상환경의 실행 파일을 직접 지정해도 된다.

```powershell
.\.venv\Scripts\travel-agent.exe doctor
```

환경 설정은 `.env.example`을 참고한다. 현재 CLI는 프로세스 환경변수를 읽으며 `.env` 자동 로딩은 하지 않는다.

```powershell
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:OLLAMA_MODEL = 'qwen3.5:4b-q4_K_M'
```

`doctor`는 조회만 수행하며 모델을 다운로드·로드·삭제하지 않는다.

## 연구와 평가

- [MCP 서버 연결·국문 관광정보 후보·현재 검증 범위](docs/mcp.md)

- [검색 툴 단독 수집·재정렬·발췌 실행과 검증](docs/search-pipeline.md) — 현재 우선순위, 에이전트 연결 보류

- [연구일지 인덱스와 기록 규칙](docs/research/README.md)
- [첫 실험: 로컬 모델 공급과 실패 발견](docs/research/2026-10-17-001-local-llm.md)
- [개발 단계](docs/roadmap.md)
- [대표 질문·검증 기준·구현 접근](docs/research/2026-10-17-005-questions-and-validation.md)
- [BM25·하이브리드·리랭킹 구현안 고찰](docs/research/2026-10-17-006-rag-design-review.md) — 최신 우선순위 검토안

실제 사용자 대화와 원본 실행 로그는 기본적으로 Git에서 제외한다. 공개용 평가 사례는 익명화한 고정 데이터로 별도 관리한다. GitHub 원격은 https://github.com/yuchanahn/travel-agent.git 이며 공개 라이선스는 아직 정하지 않았다.
