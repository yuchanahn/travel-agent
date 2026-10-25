# 현재 상태

상태: 적용 중
검토일: 2026-10-25
근거: 제품 기준 커밋 cc6c513, 아래 연결한 실제 코드와 연구일지. 실행 중 개인 설정을 새로 조회한 기록은 아니다.

## 제품·환경

- Python 3.12 이상, Ollama `qwen3.5:4b-q4_K_M`를 사용하는 로컬 여행 에이전트다. 단일 주소는 `http://127.0.0.1:50733/`이며 호스트 시작·같은 포트 재시작을 사용한다. Docker·ngrok 공유는 중단한 상태로 유지한다. [운영 규칙](../web-interface.md).
- 공식 Brave MCP와 OpenBnB를 연결해 사용해 왔다. 개인 MCP·공급자 설정은 비공개이며 현재 연결 건강 상태를 이번 문서 작업에서 검사하지 않았다. [MCP](../mcp.md), [Brave 도입 기록](../research/2026-10-20-074-official-brave-mcp.md).
- TourAPI 도입은 취소됐다. Google/webserp 직접 검색은 과거 연구다. 신규 서비스·모델 다운로드·외부 공유를 당연한 다음 단계로 두지 않는다.

## 현재 코드의 기본값

| 항목 | 값 | 근거 |
| --- | --- | --- |
| 일반 출력 / 문맥 | 8192 / 65536 토큰 | [generation_options](../../src/travel_agent/llm_config.py), [097](../research/2026-10-24-097-output-budget.md) |
| 입력 하드 제한 | 196608 UTF-8바이트 | [input_byte_limit](../../src/travel_agent/llm_config.py) |
| 압축 시작 / 목표 | 128000 / 96000바이트 | [runtime_context.prepare](../../src/travel_agent/runtime_context.py), [096](../research/2026-10-24-096-conservative-context.md) |
| 요약 | 최대180초·출력2048토큰 | [096](../research/2026-10-24-096-conservative-context.md) |
| 모델 / 도구 / 실행 예산 | 40회 / 36회 / 360초 | [run_agent](../../src/travel_agent/agent.py), [웹 실행](../../src/travel_agent/web_app.py) |
| 웹 실행의 시간 배분 | 메인330초·대화 후 계획 최대30초 | [RunManager._execute](../../src/travel_agent/web_app.py), [094](../research/2026-10-24-094-search-plan-reliability.md) |
| 독립 웹 도구 병렬 | 최대3개 | [웹 도구](../agentic-rag.md) |
| 종료 기본 | native | [056](../research/2026-10-19-056-native-output-and-action-prompt.md) |

환경 변수와 개인 공급자 설정이 일부 값을 바꿀 수 있다. 토큰과 바이트는 다른 단위다. 모델40회에 요약 등 별도 모델 호출을 무조건 합산하거나, 실행360초를 전체 HTTP 요청의 보장 시간으로 표현하지 않는다.

## 메모리·계획

웹은 대화·도구 원문을 비공개로 보존하고 분기 범위의 BM25 검색과 매 추론 전 문맥 검사를 사용한다. CLI의 Kiwi/E5·하이브리드·리랭킹은 별도 경로이며 사용자의 구현·학습 목표다. [메모리 문서](../memory-rag.md), [093](../research/2026-10-23-093-runtime-context.md).

계획서는 실행별 저장·직접 편집·사용자 확정·Markdown/PDF 흐름을 제공한다. 내용 변경 시 확정을 해제하며 사용자 확정은 예약 완료가 아니다. 후보 자동 추출 실패는 실패 상태로 표시한다. [계획서](../travel-plan.md), [094](../research/2026-10-24-094-search-plan-reliability.md), [095](../research/2026-10-24-095-release-validation-portfolio.md).

## 확인한 결과와 열린 문제

- 기존 Python 검사는 096 시점311개 통과다. 이 수치는 이번 작업에서 새로 실행한 결과와 구분한다.
- 고정 실제 여행 질문은 095 재검증에서도 실행2/2·근거 검토0/2다. 주소 창작·시설 혼합·출처 범위 과장은 해결로 표시하지 않는다. [095](../research/2026-10-24-095-release-validation-portfolio.md), [고정 질문](../../examples/live-harness-cases.json).
- 고정 합성 메모리 평가는 세부 복원 summary0/2 → summary_rag2/2다. 자연 발생 압축 손실·일반 추천 품질 향상을 입증한 것은 아니다. [082](../research/2026-10-23-082-memory-eval-and-monitoring.md).
- 097의 반복 응답은 공급자가4096토큰에서 `length`로 잘랐다. 출력8192 변경만으로 반복을 해결했다고 쓰지 않는다. [097](../research/2026-10-24-097-output-budget.md).
- 포트폴리오는 여섯 파트·이미지6·코드토글6·본문 세부링크0이다. 로컬 운영과 금융 규정 미구현을 명시한다. [098](../research/2026-10-25-098-portfolio-six-capabilities.md), [현재 본문](../portfolio/travel-agent-draft.md).

이번 개발 지침·폴더·노트 적용 기록은 [099](../research/2026-10-25-099-workspace-harness.md)에 둔다. 향후 실행 결과를 여기에 계속 늘리지 말고 위 주제별 현재 판단과 근거를 갱신한다.

지원 서류 작업은 [토스 두 공고의 분석](toss-hiring-brief.md)을 먼저 읽는다. 공고별 인재상과 서류 전략은 검토할 가설이며, 기존 여섯 파트 구성이나 수치 중심 설명을 새 지원서의 고정 정답으로 취급하지 않는다.

최신 서류 편집은 [사람이 읽는 포트폴리오 규칙](portfolio-presentation.md)을 따른다. Notion에서 먼저 구성하고 요청 시 별도 디자인의 PDF를 만든다. 과거 발표 본문의 한계 명시 방식은 새 지원서의 필수 양식이 아니다.
