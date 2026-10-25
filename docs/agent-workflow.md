# 개발 에이전트 워크플로와 폴더 관리

상태: 적용 중 · 검토일: 2026-10-25

## 조사 결과와 적용 범위

“최신 하네스 폴더 표준”이라는 단일 규격은 확인하지 못했다. 현재 공개된 일차 자료에서 공통으로 확인한 탐색·진행 보존·검증 원칙을 기존 Python 저장소에 맞춰 적용한다. 대규모 조직의 폴더나 다중 에이전트 구성을 그대로 복제하지 않는다.

| 확인한 일차 자료 | 이 저장소에 적용한 판단 |
| --- | --- |
| [Karpathy-inspired 원본 저장소](https://github.com/multica-ai/andrej-karpathy-skills)와 [4원칙 본문](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md) | 구현 전 가정 확인, 최소 구조, 필요한 변경, 검증 기준을 루트 AGENTS에 직접 둔다. 커뮤니티 정리임을 표시한다. |
| [OpenAI AGENTS.md 문서](https://learn.chatgpt.com/docs/agent-configuration/agents-md) | 실제 자동 탐색 진입점은 AGENTS.md다. 연결된 다른 문서는 작업에 맞게 명시적으로 읽는다. 기본 합산 제한은 32KiB이며 모든 링크가 자동 주입되는 것은 아니다. |
| [OpenAI Harness engineering, 2026-02-11](https://openai.com/index/harness-engineering/) | 루트는 짧은 지도, 근거와 지식은 버전 관리되는 docs에 둔다. 구조 규칙 일부는 실행 가능한 검사로 만든다. |
| [OpenAI Iterating Development Workflows with Codex](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex) | 작업 계획·검증·진행 기록을 파일로 남긴다. 이 프로젝트는 기존 scripts와 연구일지를 재사용한다. |
| [Anthropic Effective harnesses, 2025-11-26](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | 새 세션은 Git 이력·현재 상태·남은 검증부터 읽고 작은 단위로 끝낸다. 세션 간 재개 정보를 보존한다. |
| [Anthropic Harness design for long-running apps, 2026-03-24](https://www.anthropic.com/research/harness-design-long-running-apps) | 구현과 평가를 구분하고 요구에 비례해 구조를 늘린다. 이 문서만으로 이 프로젝트의 품질 향상을 주장하지 않는다. |

## 저장 위치

| 위치 | 담는 것 | 관리 규칙 |
| --- | --- | --- |
| 루트 | 진입 지침·사용법·구조 지도·패키지/배포 설정 | 새 일회성 메모나 로그를 추가하지 않는다. |
| `src/travel_agent/` | 제품 Python과 `static/` UI | 현재 모듈 역할을 먼저 확인한다. 이름만을 위한 계층 분할은 하지 않는다. |
| `tests/` | 오프라인 계약·회귀 검사 | 실제 모델 평가·검색 비용이 생기는 실행과 분리한다. |
| `scripts/` | 실행·재시작·평가·문서 검사 도구 | 제품 로직을 복사하지 않는다. 실제 외부 호출 여부를 설명한다. |
| `examples/`, `config/` | 공개 합성 사례와 설정 견본 | 실제 인증·개인 대화·실제 비공개 설정은 제외한다. |
| `docs/*.md` | 기능별 현재 사용법·기술 설명 | 과거 설명과 충돌하면 현재 상태를 먼저 표시하고 근거로 연결한다. |
| `docs/knowledge/` | 반복해서 사용할 사실·판단·실패 교훈 | 상태·검토일·근거·한계를 함께 갱신한다. |
| `docs/decisions/` | 선택 이유·대안·영향 | 기존 ADR 번호 다음을 쓴다. 폐기 결정도 이력을 남긴다. |
| `docs/plans/` | 여러 세션이 필요한 작업과 완료 기록 | [계획 규칙](plans/README.md)에 따라 진행·다음 행동을 기록한다. |
| `docs/research/` | 실행 당시 질문·응답·조사·실패·결론 | 같은 번호의 과거 중복은 보존하고 새 기록은 날짜+고유 주제로 구분한다. |
| `docs/papers/`, `docs/portfolio/` | 논문 학습과 발표 자료 | 연구 결과와 발표 문장을 구분한다. 포트폴리오 본문에 연구 로그를 누적하지 않는다. |
| `docs/assets/` | 검토한 공개 그림 | 설명도와 실제 화면을 표시하고 개인 정보를 검토한다. |
| `data/private/` | 인증·개인 원문·실행 로그·내부 조사 | Git 제외. Notion에는 비민감 발췌만 기록한다. |
| `artifacts/` | 재생성 가능한 산출물 | Git 제외. 전달할 공개 결과만 의도한 위치로 복사한다. |

기존 `output/`, `tmp/`, 루트 실험 파일은 이번 작업에서 이동·삭제하지 않는다. 새 작업은 위 위치를 사용하고, 기존 항목 정리가 필요하면 참조·개인정보·재현 필요성을 확인한 별도 변경으로 다룬다. 빈 디렉터리와 쓰지 않는 README를 미리 만들지 않는다.

## 시작 → 실행 → 재개 → 종료

1. `git status --short`, 최근 커밋, [현재 상태](knowledge/current-state.md)를 읽는다. 관련 기능 문서와 소스만 추가로 읽는다.
2. 기대 결과와 검사 방법을 정한다. 짧은 수정은 별도 계획 파일 없이 진행하고, 여러 세션·연동·위험한 변경은 계획 파일을 만든다.
3. 최소 변경을 하고 관련 검사를 실행한다. 실패 원인·실제 환경·미실행 검증을 구분한다.
4. 세션이 끊기기 전에는 진행 중 계획에 완료 항목·막힌 이유·다음 명령·시험 루트 정리 상태를 적는다. 키와 개인 원문은 쓰지 않는다.
5. 반복해서 쓸 지식만 노트로 승격한다. 현재 값이 바뀌면 현재 상태와 관련 기능 문서를 함께 고친다. 과정과 원본 답변은 연구일지에 둔다.
6. Notion 기록은 [연구 기록 정책](knowledge/research-policy.md)과 기존 허브를 따른다. 검증·diff·민감정보 확인 후 이번 변경만 커밋·푸시한다.

## 문서 유지와 검증

루트 AGENTS는 이 프로젝트 자체 예산으로 **120줄·UTF-8 12,000바이트 이하**를 유지한다. 이는 공급자 표준이나 품질 보장이 아니다. 실행별 이력은 추가하지 않는다. 하위 AGENTS는 반복되는 지역 규칙이 실제 필요할 때만 만들고 루트 규칙을 복사하지 않는다.

`.venv/Scripts/python.exe scripts/verify_workspace.py`는 진입 문서와 새 지식·계획의 로컬 링크, 크기, 필수 메타데이터, 지식노트 인덱스, Git 추적 금지 경로를 확인한다. 기존 연구일지 전체·외부 URL·문장의 진실성은 자동 검증하지 않는다. 검사 스크립트는 `verify_local.ps1`에도 연결한다. CI·상주 문서 정리 에이전트는 이번에 추가하지 않았다.

상태의 날짜가 새롭다는 이유로 사실로 확정하지 않는다. 관련 코드·실행 조건이 바뀌거나 충돌을 발견했을 때 원근거를 재확인한다. 기존 311개 검사는 과거 결과이며 새 실행 결과는 새 연구일지에 따로 적는다.
