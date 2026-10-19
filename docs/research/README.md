# 연구일지

코드와 함께 검증 가능한 기록을 버전 관리한다. 노션에는 같은 작업의 맥락과 결론을 정리한다.

노션 허브: https://app.notion.com/p/3fcd058c022e81dda6eff44a0bb29d4f

- [064: Nexus FreeLLMAPI 공급자 전환](2026-10-19-064-nexus-llm-provider.md) — OpenAI 호환 도구 왕복·210개 테스트·실제 검색 한도 종료와 대화 이어가기, 새 호스트50731

064 노션 동기화 완료: https://app.notion.com/p/3fed058c022e8120ab56d08d0200d3cd

- [063: OpenBnB 도입·구조적 패킹·호스트 웹 검증](2026-10-19-063-openbnb-integration.md) — 205개 테스트, 호스트50730에서 실제 MCP·가격·인용 확인; 지역 오류 잔존·디스크 부족으로 Docker/공유 배포 미완료

063 노션 동기화 완료: https://app.notion.com/p/3fed058c022e811b94edc268d50cf5c4

- [062: OpenBnB 국내 숙소 검색·상세·전달부 검증](2026-10-19-062-openbnb-validation.md) — 기본 robots 자체 중단, 진단 조건 검색·가격필터·페이지 성공; 상세 누락·한국어 지역 오인식·모델 패킷 잘림, 활성화 보류

062 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81e58872d903d0493cfb

- [061: 숙박·투어 검색 MCP 후보 조사](2026-10-19-061-lodging-tour-mcp-candidates.md) — OpenBnB·WinWin·GetYourGuide·Viator 소스 조사, 가입·크레딧 의존 구분; 설치·검색 검증 전

061 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8170951bd0309c2cfafc

- [060: TourAPI 도입 취소와 MCP 범위 정리](2026-10-19-060-drop-tourapi.md) — 키 발급 후속 취소·빈 서버 설정 확인, 기존 검색과 MCP 기반 유지

060 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8158b232d4ead08071bd

- [059: MCP 연결 기반과 국문 관광정보 후보 검증](2026-10-19-059-mcp-client-integration.md) — stdio·HTTP·동적 스키마·trace/메모리 연결,202개 테스트·실제 모델 합성 조회; 관광 API는 키 발급 전

059 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81f8a4bae8765c759884

- [058: ngrok 외부 공유·기존 기록 분리](2026-10-19-058-ngrok-share.md) — 별도 공유 컨테이너·볼륨·Basic Auth, 정확한Origin 허용, 실제 외부 질문·답변,192개 테스트

058 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81dd8068fd65c2aea671

- [057: 웹 원본 메모리·요약·RAG 연결과 실제 비교](2026-10-19-057-web-session-memory.md) — 191개 테스트, 실제4턴·요약1회·손실 요약2조건 비교; 분기 격리·자동 색인·원문 근거 주입

057 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8108848ddab1a33a019d

- [056: 출력4096·행동 지침·네이티브 종료 적용](2026-10-19-056-native-output-and-action-prompt.md) — 182개 테스트, 실제 공개2질의 검색 왕복; 관람시간 답변은 본문 미조회·근거 없는 정보·인용 누락으로 실패

056 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81179b46e69e47b7f282

- [055: finish 도입 폐기와 다음 개선 순서](2026-10-19-055-drop-finish-and-improvement-plan.md) — 최종 도구 후보·비교 취소, 네이티브 기준선과 근거 확보/활용 실패 분리 제안; 런타임 변경 없음

055 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81099da8cb8a1d76a1ef

- [054: 모델의 기본 도구 프로토콜과 추가 종료 규칙](2026-10-19-054-native-harness-comparison.md) — Qwen-Agent·Ollama·smolagents 실제 종료 코드, 최종 도구 반복 이슈, 로컬 renderer/parser 확인; 실행 변경·새 추론 없음

054 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81ddbcd5f24b87227b8a

- [053: 모델 호출 기본 한도를6회에서12회로 늘리다](2026-10-19-053-model-call-budget-twelve.md) — Python·CLI·웹 기본값 통일,7회째 완료·12회 상한 검증,178개 테스트

053 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8178a7bbd1c9bc96457b

- [052: 종료 판단은 모델에 두고 명시적 최종 신호를 받는다](2026-10-19-052-explicit-final-protocol.md) — 진행 텍스트 재요청·final 태그·한도 상태 분리, 실제 동일3질의6회 비교에서 조회2개는 새 방식 한도 종료,177개 테스트

052 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81eaa612d527e9273386

- [051: 텍스트 응답과 작업 완료를 분리하는 종료 설계](2026-10-19-051-explicit-completion-design.md) — 실제4회 모델·검색2회·본문0회 진단, 명시적 종료 계약과 하네스 검사 제안, 아직 미구현

051 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e818e8d30dccfe7aec5ca

- [050: 눈부심을 줄이는 다크모드](2026-10-19-050-dark-mode.md) — 기본 다크·테마 전환·선택 저장, 데스크톱/모바일 확인

050 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e814fb7a1f7ee3452c614

처음 읽는 경우 [프로젝트 발표 흐름](notion-presentation.md)에서 배경·구조·실제 사례·평가·남은 문제를 먼저 본다. 노션은 같은 흐름으로 정리하고 기존 연구001~048은 단계별 접힌 기록으로 유지했다.

- [049: 노션을 연구 목록에서 발표 흐름으로 정리하다](2026-10-19-049-notion-presentation-cleanup.md) — 허브 반복 요약 제거, 연구48개·설계·작성 기준 정리, 기존50개 페이지와 코드/출력473블록 보존 대조

049 노션 동기화 완료: 기존 허브의 문서 정리 기록에 통합했다. 새 중복 페이지는 만들지 않았다.

- [048: 입력창을 아래에 둔 대화 화면](2026-10-19-048-bottom-chat-composer.md) — 하단 입력창·독립 스크롤·말풍선·접힌 실행 과정·모바일 메뉴, 브라우저 검증

048 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81d0a95cd3ac653dcffd

- [047: 검색하겠다는 문장과 실제 도구 호출은 다르다](2026-10-19-047-text-intent-without-tool-call.md) — 실제 trace 진단: stop·478토큰·툴콜0회, 출력 한도와 자연어 행동 예고를 구분

047 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e813c86dcc98e24b562c3

- [046: 조건을 수정하며 이어서 질문하는 대화](2026-10-19-046-web-conversations.md) — 이전 메시지·도구 결과·출처 전달, 새 대화·복원, 실제 예산 정정 검증

046 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8187addffd6af78f7e82

- [045: 직접 질문하고 실제 실행을 확인하는 로컬 웹 화면](2026-10-19-045-local-web-interface.md) — Docker 빈 로컬 포트, 실제 모델·검색 연결, 브라우저·복원·모바일 검증

045 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8134ae5dfa72566d7bc0

## 기록 단위

의미 있는 구현·실험·결정 단위로 작성한다. 날짜는 Asia/Seoul 기준, 파일명은 YYYY-MM-DD-NNN-topic.md다. 작은 명령마다 기록을 늘리지 않는다.

기본 흐름은 **쿼리·초기 답변 → 문제 정의 → 문제 분석 → 연구 과정 → 문제 해결 → 개선된 답변과 검증**이다.

1. 문제 정의: 실제 쿼리·초기 답변과 부족한 점, 좋은 답변의 판정 기준을 먼저 둔다.
2. 문제 분석: 검색·정정 반영·근거 사용·출력 형식 등 실패 원인을 실행 기록으로 좁힌다. 관찰과 가설을 구분한다.
3. 연구 과정: 참고 자료, 대안과 트레이드오프, 실험 조건·비교 기준, 실패한 시도를 기록한다.
4. 문제 해결: 선택 이유와 실제 코드·구조·흐름도를 보여준다. 구현과 제안을 구분한다.
5. 검증: 같은 질문의 개선된 답변, 관찰한 변화, 회귀와 추가 비용, 남은 한계를 남긴다. 좋은 결과를 미리 가정하지 않는다.

먼저 테스트 상황을 설명한다. 예산이25만 원인 답변을 보여주기 전에 언제 어떤 조건을 정했는지 알려준다. 실제 질문은 노션의 콜아웃 박스에 넣고 답변을 바로 아래 배치한다. 다른 실험의 답변에는 그 실험의 질문을 다시 붙인다. 답변 문자열은 기록 그대로 사용하되 JSON 래퍼나 개행 이스케이프 대신 대화문으로 읽을 수 있게 보여준다. 합성 테스트·아직 실행하지 않은 계획·현재 재검증은 짧게 구분한다.

연구일지 본문에는 파일 경로·자료 종류·SHA-256·원문 무변경 선언을 나열하지 않는다. 원본 로그는 내부에 보관하고 실행법·세부 조건·구현 코드는 펼쳐볼 수 있는 상세 영역으로 옮긴다. 필요한 논문·공식 문서 인용은 유지한다. 기획·환경·정책 작업에는 가상의 모델 답변을 만들지 않고 개발 요청과 결과를 대응시킨다.

구현 기록에는 실제 소스의 코드 조각과 구조·데이터 흐름 다이어그램을 함께 넣는다. 파일·함수·기준 커밋을 표시하고 코드와 설계 이유를 연결한다. 의사 코드와 실제 구현, 인용 ID 검사와 의미적 사실 검증 등을 구분한다. 코드가 없는 변경은 해당 설정·문서의 변경 내용을 기록한다.

도구를 사용한 실험에는 **실제 툴콜 로그**를 기본 접힌 토글로 넣는다. 도구 이름·호출 ID·실제 인자(검색어)·성공 결과 또는 오류·실행 순서·시각을 연결한다. 모델의 요청, 실제 실행 결과, 다음 모델 입력으로 전달된 결과를 구분한다. 외부 도구를 직접 검사한 실험은 모델 호출이 없었다고 밝히고 실제 요청·응답을 기록한다. HTTP 상태와 실제 선택 엔진 등 추가 진단은 관찰된 항목만 남긴다. 원본은 비공개 보존하고 비밀정보·개인 대화·인증 헤더·쿠키를 공개하지 않는다. 호출이 없었다면 로그를 만들어 넣지 않는다.

공개 원본 로그에 개인 정보가 섞이지 않도록 검토한다. 실패 사례와 점수는 유리한 결과로 덮어쓰지 않는다. 기존 Codex 경험에 대한 회고는 측정된 비교 실험으로 표시하지 않는다.

## 기존 기록 보강

001~009는 상황과 질문·실제 답변을 먼저 읽고, 문제 분석·실험·해결을 따라가도록 정리했다. 007은 강릉 제외 이유 복원, 009는 예산 답변의 인용 누락 개선을 같은 질문으로 비교한다. 실패한 프롬프트 실험과 다른 검증 사례에도 질문을 붙였다. 실행하지 않은 기획 단계에는 답변을 만들어 넣지 않았다. 기존 코드·다이어그램·실험 내용은 상세 영역에 보존했다.

## 인덱스

- [044: 실제 에이전트13회 검증 — 여행 답변은 아직 불합격](2026-10-18-044-live-brave-agent-validation.md) — 여행3질의 전후·중간 실행과 제어4사례, 보완본 여행 수동0/3, 인사/기억 회상 통과, Python158개 통과

044 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e810db461e02cd63f1e7d

- [043: 같은 본문으로 발췌 검증 — 문장 경계와 메뉴 의심 표시](2026-10-18-043-evidence-boundaries.md) — 기존 추출문10개·패킷3개 고정 비교, 문장/줄 경계 우선·메뉴 레이아웃 경고, 새 API0건·Python154개 통과

043 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81d6a15ef0babb15c59f

- [042: Brave를 기본 검색 공급자로 연결하다](2026-10-18-042-brave-integration.md) — API 공급자 전환·기존 후처리 유지, 실제 두 질문 후보40개/20개·본문 각3개, Python148개 통과

042 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e819293a2d417952f5c7d

- [041: 기존 Claude MCP의 Brave 키 재사용 확인](2026-10-18-041-brave-existing-key-check.md) — 기존 키로 API1건 HTTP200·여행 후보3개, 프로젝트 연결 전

041 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81feb71ccbacc7d28171

- [040: 블로그는 읽을 수 있나 — 검색 실패와 본문 읽기 분리 검증](2026-10-18-040-blog-reading-validation.md) — Bing RSS2질의는 무관한 후보, 별도 확보한 티스토리2개·네이버 글1개는 현 수집기로 본문 추출 성공

040 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81e1964ecdddb7a3f54e

- [039: 명소 정보는 어디에서 빠졌나 — 원본·추출·전달 단계 진단](2026-10-18-039-page-acquisition-audit.md) — 관광공사 HTML·추출·발췌 대조, 추가 JS 데이터 경로 미수집 확인, 런타임 수정 없음

039 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8167a9e6f581e33832a8

- [038: 위키만 모은 검색은 실패 — 한국어 토큰 불일치를 고치고 남은 문제를 확인하다](2026-10-18-038-korean-token-mismatch.md) — 관광/한국관광공사 토큰 불일치 수정, 동일 수집본에서 관광공사9위→1위 복구, 새 실행은 홈페이지 메뉴 발췌로 명소 품질 미달, Python138개 통과

038 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e813c9cecff234cc857db

- [037: 검색어에서 모델에 넘길 데이터까지 — 실제 수집·후처리 내용을 펼쳐 보기](2026-10-18-037-search-data-walkthrough.md) — 한국 관광 명소 실제 검색, 페이지별 HTML 발췌·20→10 중복 처리·순위·선택 본문·실제4807바이트 패킷의 출처별 발췌를 한 흐름으로 연결

037 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81fd915cd4c5e85f01bc

- [036: 같은 검색어가 달라지는 이유 — Bing 언어·지역 실패 재현과 RSS 대조](2026-10-18-036-bing-context-and-rss-diagnosis.md) — 공개 이슈·수정 코드 조사,42회 조건 대조·RSS12회 반복, 특정 locale 실패 재현, 선택형 RSS·명시 locale 구현, 과거 기본 요청 원인 미확인, Python137개 통과

036 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81c3b082e31aa74d0443

- [035: 검색 응답 변동을 확인하고 출력 예산 안에서 문단을 다시 고르다](2026-10-18-035-search-variance-and-budgeted-passages.md) — Bing12요청 행렬·같은 코드 반복 실행·동일 본문 오프라인 발췌 비교, Python133개 통과, 검색 안정성·여행 조건 품질 미달 보존

035 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81c3a9f8c74dd7e3bc9f

- [034: 에이전트보다 검색 툴부터 — 후보 수집·재정렬·발췌와 실제 품질 격차](2026-10-18-034-search-evidence-pipeline.md) — 독립 수집·임시 저장·BM25Plus·중복 묶음·본문 발췌·출력 예산, 내장 검색과3질의 비교, 품질 미달 보존, Python132개 통과

034 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8144bc48ef3a28233b76

- [033: 여행 검색의 범위·본문·토큰 평가 — 기능 통과와 답변 불합격](2026-10-18-033-travel-search-evaluation.md) — 합성3사례·top3/top5/병렬 탐색, 동일 근거 토큰 비교·본문 발췌·web_read 구현, 실제 답변 실패 보존, 실제 검색 결과·원본 HTML 대조 보강, Python125개 통과

033 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8103bda5fe1cc0f73788

- [032: 덕덕고를 제거하고 Bing 단독 검색으로 정리하다](2026-10-18-032-bing-only-search.md) — DDG 요청·파서·기본primp 의존성 제거, Bing3질의 공식 주소 확인, 병렬 툴 호출 유지, Python110개·pip check 통과

032 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81288307e20940fc717a

- [031: DDGS 런타임을 제거하고 덕덕고·Bing을 직접 요청하다](2026-10-18-031-direct-http-search.md) — 직접 요청·자체 파서·기본http 전환, 두 엔진 성공2/3·Bing 공식 도메인3/3, 실제 모델 부분 실패 설명, Python115개·pip check 통과

031 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81a9b66dcba0bfc96a08

- [030: Bing 장애를 DDGS 유지보수·요청 방식·HTML 파싱으로 나눠 조사하다](2026-10-18-030-bing-maintenance-and-http-diagnosis.md) — 최신 배포·이슈 조사, HTTP20회 비교, 원본 파서 누락2건 복원, 런타임 활성화 보류, Python106개 통과

030 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e817c8d34f9024a2ab0ea

- [029: 덕덕고·Bing을 명시적으로 병렬 수집하고 결과를 통합하다](2026-10-18-029-dual-engine-fusion.md) — 엔진별 실행·중복 제거·RRF·부분 실패 구현, Bing 비활성 유지, DuckDuckGo GET·실제 모델 답변 확인, Python102개 통과

029 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81ec8d63e6889ee105a4

- [028: iframe 불일치를 검증하고 확인 데이터를 바꾸지 않는 DOM 관찰을 만들다](2026-10-18-028-google-iframe-dom-observation.md) — 영향 없는 getter·DOM 관찰 검증, iframe 보정 후에도 검색 실패, 실제 srcdoc·innerHTML 입력은 빈 문자열, Python92개·Node8개 통과

028 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e8176bdcdd4be88047d90

- [027: HTTP 계열·프로토콜·생성자와 Google 대조 경로를 나누어 검증하다](2026-10-18-027-google-transport-and-runtime.md) — 일반 검색8조건 실패, 자동완성·RSS 대조 성공, iframe 래퍼의 영향 확인, Python92개·Node4개 통과

027 노션 동기화 완료: https://app.notion.com/p/3fdd058c022e81628e0fdf1509337dc2

- [026: DOM 누락을 실제 HTTP 결과와 대조하다](2026-10-18-026-google-dom-server-validation.md) — 실제3조건 모두302→/sorry, 별도 좌표 누락 비교604→609바이트, 검색 미해결, Python88개·Node3개 통과

026 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e8132b362ef5ea924f8f7

- [025: 같은 확인 응답의 입력을 하나씩 바꿔 레코드 구간을 찾다](2026-10-18-025-google-record-differential.md) — 고정 입력14조건·28회 VM 실행, 언어·너비·수치·생성자 의존 구간 확인, Python88개·Node3개 테스트 통과, 서버 검증 전

025 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81e9a457de8d61a1bc23

- [024: Reddit 사례에서 GitHub 소스와 실제 재현으로 이어가기](2026-10-18-024-community-http-research.md) — 원본 Lynx·SearXNG WML·jsdom 재현 실패, 오프라인 접근표·604바이트 레코드 분석, 관찰한 URL 입력 수정, 88개 테스트 통과

024 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81b78659ccd879796f40

- [023: Google 확인 값과 후속 요청의 불일치를 검증하다](2026-10-18-023-google-followup-consistency.md) — HTTP·JS 식별 정보, 작업 순서와 HttpOnly 수정, SG_SS 실제 전송 확인, 검색 미해결, 87개 테스트 통과

023 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e8138b17ceb2e311d2f74

- [022: 브라우저 없이 Google HTTP 세션과 확인 스크립트를 구현하다](2026-10-18-022-google-http-session.md) — HTTP 직접 요청·파일 쿠키·선택형 QuickJS, 실제 SG_SS 생성 후 재요청429, 검색 미해결, 브라우저 구현 제거, 최종83개 테스트 통과

022 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e818b8abfc10fe60ae3a1

- [021: 직접 만드는 Google 검색기 — 전용 프로필과 첫 실행](2026-10-18-021-google-browser-first-step.md) — webserp 수리 중단, 독립 브라우저 모듈·디스크 프로필·DOM 추출, 실제 Google429, 79개 테스트 통과

021 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81ff996beabdc2ff9aeb

- [020: Google 실패를 요청·프로토콜·브라우저 단계로 나누다](2026-10-18-020-google-failure-stages.md) — Google만 진단, prog 디코딩·오류 분류 수정, 실제 검색은 미해결, 74개 테스트 통과

020 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81c1ba6ade99cbd02359

- [001: 로컬 LLM 공급과 초기 실패](2026-10-17-001-local-llm.md)
- [002: 프로젝트 기반과 기록 체계](2026-10-17-002-project-foundation.md)
- [003: Python 실행 절차 단순화](2026-10-17-003-editable-install.md)
- [004: 변경 완료 시 커밋·푸시 정책](2026-10-17-004-git-workflow.md)
- [005: 미정인 여행 요청에서 시작하는 구현·검증 계획](2026-10-17-005-questions-and-validation.md)
- [006: 한국어 여행 RAG 구현안 고찰](2026-10-17-006-rag-design-review.md) — 초기 검토 이력, 첫 코퍼스는 007에서 변경
- [007: 문맥 압축에 대비한 대화 원문 메모리 RAG](2026-10-17-007-conversation-memory-rag.md) — 첫 구현·합성 검증 완료
- [008: 전체 구현 해설과 코드·다이어그램 기록](2026-10-17-008-code-walkthrough.md)
- [009: Agentic RAG와 요청별 실행 추적](2026-10-17-009-agentic-rag.md)
- [010: 메모리 도구 옆에 웹검색을 연결하다](2026-10-17-010-web-search.md)
- [011: 한 응답의 웹 도구 요청을 병렬로 실행하기](2026-10-17-011-parallel-tools.md) — 실제 검색어·호출 ID·오류 전달 기록 보강
- [012: 같은 검색어를 찾지 못한 이유: HTTP 응답 진단](2026-10-17-012-search-diagnosis.md)
- [013: 웹검색 기능 보강: 공개 프로젝트·관리형 API 조사와 비교 계획](2026-10-17-013-web-search-strengthening.md)
- [014: 검색 비용과 실제 로컬 검색기의 차이](2026-10-17-014-local-search-and-cost.md) — 자체 운영 우선, 설치·검색 품질 실험 전

014 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e8115b3afd982490dd92d

- [015: 구글 웹 검색 요청 재현과 로컬 세션 재사용 후보](2026-10-17-015-google-web-reverse-repositories.md) — 공개 소스 확인, 설치·검색 실험 전

015 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e8140870bcef43c5dc7df

- [016: webserp 클론 검증 — 성공 표시와 검색 성공을 구분하다](2026-10-17-016-webserp-clone-validation.md) — 격리 설치·실제 요청 검증 완료, 검색 결과 미확보로 기본 도입 보류

016 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e8113b94ce7dc9dded318

- [017: webserp 공급자 연결과 DDGS 비교 — 연결과 품질을 구분하다](2026-10-17-017-webserp-integration-comparison.md) — 선택형 공급자 구현, 같은 검색 질의10개·실제 모델 답변 비교 완료, 품질 향상 없음

017 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e814a9e54c34a67c2ab9e

- [018: 실패 상태를 명확히 하고 컨텍스트 64K를 요청에 반영하다](2026-10-18-018-context-64k.md) — Agentic·2-Step 공통 설정, 별도 바이트 제한 정리, 짧은 실제 호출과63개 테스트

018 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81488ec9c03d46d6258b

- [019: webserp 재검증 — Google 실패와 다중 엔진 동작을 구분하다](2026-10-18-019-webserp-deep-validation.md) — 이슈·변경 이력·응답 프레임·익명 쿠키 재사용 검증, HTML 엔진 경로 연결, 공식 도메인6/6 및 실제 모델 답변 확인

019 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81c3a984d9dfecf8b13b

013 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81d192ecefeaad3c20ab

012 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81d1a6efccb5f55af2a2

011 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e8173aca9e5396ef098b1

010 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81829b63f3d304cb9b16

009 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81c9b671c1ed757cc8b1

008 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e812db527e925dddeb9dd

007 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e81cdaf18e02657f84d18

006 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e8196b896e69ed2353bfb

005 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e811ca9cafd98586ef76a
- 초기 아키텍처 결정은 docs/decisions/0001-initial-architecture.md에 기록.

노션 기술 결정: https://app.notion.com/p/3fcd058c022e81d9b7fbe5fb6f37652a

노션 작성 양식: https://app.notion.com/p/3fcd058c022e81aa82b7e5da4e6851ae
