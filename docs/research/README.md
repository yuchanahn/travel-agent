# 연구일지

코드와 함께 검증 가능한 기록을 버전 관리한다. 노션에는 같은 작업의 맥락과 결론을 정리한다.

노션 허브: https://app.notion.com/p/3fcd058c022e81dda6eff44a0bb29d4f

## 기록 단위

의미 있는 구현·실험·결정 단위로 작성한다. 날짜는 Asia/Seoul 기준, 파일명은 YYYY-MM-DD-NNN-topic.md다. 작은 명령마다 기록을 늘리지 않는다.

1. 문제·질문: 실제로 무엇이 불편했나?
2. 가설: 어떤 변경이 왜 도움이 될 것으로 보는가?
3. 조건: 모델 태그·digest·양자화·문맥·thinking·프롬프트·fixture·실제 데이터 구분.
4. 변경: 직접 설계하고 구현한 부분.
5. 검증: 실행 명령, 사례 수, 지표, 원본 산출물 위치.
6. 결과: 성공과 실패를 함께 기록. 측정과 해석을 구분.
7. 결정·다음 실험: 채택·보류·기각 이유.
8. 노션 동기화 상태와 페이지 URL.

공개 원본 로그에 개인 정보가 섞이지 않도록 검토한다. 실패 사례와 점수는 유리한 결과로 덮어쓰지 않는다. 기존 Codex 경험에 대한 회고는 측정된 비교 실험으로 표시하지 않는다.

## 인덱스

- [001: 로컬 LLM 공급과 초기 실패](2026-10-17-001-local-llm.md)
- [002: 프로젝트 기반과 기록 체계](2026-10-17-002-project-foundation.md)
- [003: Python 실행 절차 단순화](2026-10-17-003-editable-install.md)
- [004: 변경 완료 시 커밋·푸시 정책](2026-10-17-004-git-workflow.md)
- [005: 미정인 여행 요청에서 시작하는 구현·검증 계획](2026-10-17-005-questions-and-validation.md)
- [006: 한국어 여행 RAG 구현안 고찰](2026-10-17-006-rag-design-review.md) — 검토안, 구현 전

006 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e8196b896e69ed2353bfb

005 노션 동기화 완료: https://app.notion.com/p/3fcd058c022e811ca9cafd98586ef76a
- 초기 아키텍처 결정은 docs/decisions/0001-initial-architecture.md에 기록.

노션 기술 결정: https://app.notion.com/p/3fcd058c022e81d9b7fbe5fb6f37652a

노션 작성 양식: https://app.notion.com/p/3fcd058c022e81aa82b7e5da4e6851ae
