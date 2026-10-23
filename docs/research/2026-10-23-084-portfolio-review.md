# 084 · 문서 상태 정리와 로컬 검사 재확인

## 개발 요청과 결과

<callout icon="💬">
	계속 재시도 ㄱㄱ
</callout>

앞선 요청은 기능과 문서를 점검하고 실제 브라우저 화면을 캡처해 반영하는 것이었다. 이번 작업은 새 여행 질문 실험이 아니라 문서·검사 절차 점검이다. 모델 답변이나 에이전트 툴콜 로그를 새로 만들지 않았다.

README의 Docker 필수 실행 안내를 현재 호스트 Python 방식으로 바로잡았다. 포트폴리오 상세4페이지와 마무리 계획에서 ‘구현 전’과 뒤에 붙은 완료 기록이 충돌하던 부분을 통합했다. 주 문서에는082 메모리 평가와083 실행 비교·응답 지침·조건 정정 결과를 반영했다.

브라우저는 연결 목록이 비어 있었고, 기존 로컬 URL로 다시 연결해도 `No browser is available`이었다. 따라서 실제 화면을 봤거나 캡처했다고 기록하지 않았다. 사용자가 Chrome에서 로컬 페이지를 열어 두도록 요청했으며 캡처는 미완료다. 이전 Windows Computer Use의 URL 확인 실패도 제품 UI 버그로 단정하지 않았다.

## 문제 분석과 해결

| 문제 | 확인한 원인·상황 | 조치 |
|---|---|---|
| 구현 완료와 계획 문구의 충돌 | 081 계획 뒤082·083 결과를 계속 덧붙임 | 현재 상태로 합치고 최초 계획은081 연구 기록에 보존 |
| README 실행 안내 불일치 | Docker 웹을 사용하던 설명이 남음 | 고정50733·호스트 Python·Docker 불필요로 정정 |
| 반복 검사 환경이 다름 | 기본 Node23.1.0에서 과거 연구용2파일 실패, 설치된 Node24.19.0에서8검사 통과 | Node24 이상을 명시하고 검사를 한 스크립트로 묶음 |
| 브라우저 캡처 불가 | 연결 목록0개·URL 연결 실패 | 캡처 보류, 실제 확인 전 사진을 만들지 않음 |

Node 버전이 다른 두 실행의 결과 차이는 확인했지만, Node23 자체의 결함이나 개별 검사 실패의 내부 원인까지 확정한 것은 아니다. 제품 UI 계약 검사5종은 기본 Node에서도 통과했다.

```mermaid
flowchart LR
 A["실제 소스·082/083 결과 대조"] --> B["예정/완료 충돌 정리"]
 B --> C["로컬 검사 일괄 실행"]
 C --> D["Notion 저장·읽기 검토"]
 D --> E["실제 브라우저 캡처: 연결 대기"]
```

## 실제 검사 결과

`scripts/verify_local.ps1`은 Python279개, 현재 UI 관련 JS5종, 과거 HTTP 연구용 JS8개를 실행했다. 모두 통과했다. 연구용 검사는 네트워크 없는 고정 자료 검사이며 Google 검색 성공을 뜻하지 않는다. Python 검사도 모의 모델·도구를 포함한 계약 검사로 실제 여행 답변 정확도가 아니다.

<details>
<summary>실제 실행 출력 발췌</summary>

	```text
	Node: v24.19.0
	----------------------------------------------------------------------
	Ran 279 tests in 23.498s

	OK
	PASS: budget-stop followup, missing-context guard, explicit new chat
	PASS: deletion cancel, active-chat preservation, failure handling, successful reset
	PASS: comparison distinguishes input changes and missing/partial tokens
	PASS: bare/angle booking links, zero-width citation, unsafe protocol remains text
	PASS: real finish handler renders separate counters and incomplete usage
	```

	연구용 JS 검사8개도 pass8·fail0이었다. 자동 검사 전체를 같은 모델의 실제 추천 성공률로 합산하지 않았다.
</details>

<details>
<summary>실제 코드 · 외부 MCP 없이 검사하고 기존 환경 복원</summary>

	`scripts/verify_local.ps1` · 기준 b01fa69. 개인 MCP 설정을 발견하지 않도록 검사에 빈 설정을 사용한다. 종료 때 기존 환경변수를 복원하며 런타임·모델을 설치하지 않는다.

	```powershell
	$env:MCP_CONFIG_FILE = (Resolve-Path -LiteralPath 'examples/mcp-servers.example.json').Path
	& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -q
	if ($LASTEXITCODE -ne 0) { throw 'Python contract tests failed.' }
	```

	[전체 검사 스크립트](https://github.com/yuchanahn/travel-agent/blob/b01fa69/scripts/verify_local.ps1)
</details>

새 문서의 관측·실행 목록 코드 조각은 실제 소스와 공백 정규화 후 일치함을 확인했다. Notion에 저장 후 다시 읽었을 때, 기존 주 문서의 코드가 인라인 한 줄로 바뀌는 들여쓰기 문제를 발견했다. 토글 안의 코드 블록 들여쓰기를 통일해 재저장했고 Python 코드4개·Mermaid2개·JSON 로그2개가 별도 코드 블록으로 유지됨을 확인했다. 주 페이지의 상세 자식4개도 보존했다. RAG·평가·제품 상세 페이지의 코드·다이어그램도 읽기 검토했다. 이는 Notion 반환 구조 확인이며 브라우저 시각 검토와는 다르다.

Notion 동기화: https://app.notion.com/p/402d058c022e81cdbe9ef432449b03f4

## 남은 완료 조건

브라우저 시연·캡처는 아직 수행하지 못했다. 새 지침으로 실제 검색을 수행한 여행 두 질문과 원래 추천3턴도 새로 실행하지 않았다. 새 유료 서비스·다운로드·외부 공유는 추가하지 않았고 기존079 품질0/2를 유지한다. ‘더 이상 점검이 필요 없는 완벽한 제품’이라고 결론 내리지 않는다.
