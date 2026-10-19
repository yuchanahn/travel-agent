# LLM 공급자 연결

기본 공급자는 Ollama다. `agent.chat`의 공통 클라이언트를 Agentic RAG·웹 문맥 요약·CLI 2-Step 답변이 함께 사용한다. `doctor`는 기존 Ollama 설치 진단 명령이다.

## Nexus FreeLLMAPI

이 환경의 로컬 게이트웨이는 `http://127.0.0.1:3001/v1`이다. 실제 추론은 게이트웨이에 등록된 외부 공급자에서 수행한다. 질문·선택된 대화 문맥·도구 결과도 해당 공급자로 전달된다. 게이트웨이의 요금·할당 제한이 사라진다는 뜻은 아니다.

`examples/llm-config.example.json`을 Git 제외 파일 `data/private/llm-config.json`으로 복사하고 키 자체는 `key_file`에 지정한 별도 파일에 저장한다. 게이트웨이에 이미 저장된 인증정보를 설정 과정에서 재사용했으며 클라이언트는 이후 게이트웨이 DB를 읽지 않는다.

```powershell
$env:LLM_CONFIG_FILE = (Resolve-Path 'data/private/llm-config.json').Path
.\.venv\Scripts\python.exe -m travel_agent.web_app --host 127.0.0.1 --port 50731 --data-dir data/private/web-host
```

`scripts/start_web_host.ps1 -Port 50731`은 해당 비공개 설정 파일이 있으면 사용한다. 일반 CLI는 `LLM_CONFIG_FILE`을 명시해야 한다. `.env`는 Python에서 자동 로드하지 않는다. Docker50729와 별도 공유 컨테이너의 공급자를 자동 변경하지 않는다. Docker에서 연결할 경우 주소는 `host.docker.internal:3001/v1`이고 인증 파일도 컨테이너 안에 별도로 읽기 전용 마운트해야 한다.

파일 대신 `LLM_PROVIDER=openai`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY_FILE` 또는 `LLM_API_KEY`로 설정할 수 있다. 명시적인 `LLM_PROVIDER`는 파일 읽기를 생략하며, 이 경우 필요한 주소·모델·키도 환경 변수로 지정한다. `LLM_PROVIDER=ollama`로 돌아가면 기존 `OLLAMA_MODEL`·`OLLAMA_BASE_URL`을 사용한다. 실패 시 다른 공급자나 모델로 자동 대체하지 않는다. 게이트웨이 내부 라우팅은 별개이며 응답에 표시된 모델명이 실제 가중치의 독립적인 검증은 아니다.

## 프로토콜과 검증 범위

OpenAI 호환 경로는 `/chat/completions`에 `stream=false`, `max_tokens=4096`, `temperature=0`과 실제 도구 스키마를 보낸다. Ollama의 `think`·`num_ctx`는 보내지 않는다. 외부 모델의 문맥 길이는 공급자가 결정하며 `AGENT_CONTEXT_TOKENS=65536`으로 바뀌지 않는다. 입력 바이트 가드는 유지한다.

기존 Ollama 대화에 ID가 없는 툴콜은 안정적인 ID를 붙여 대응하는 tool 결과와 연결한다. 함수 인자를 JSON 문자열로 전환하고 응답의 usage·finish_reason을 기존 실행기의 지표·종료 사유로 매핑한다. API의 `length`는 출력 한도로 기록한다. 요청 모델과 응답에 표시된 모델은 trace에서 구분한다. 추론용 비공개 reasoning 필드는 대화·공개 trace에 추가하지 않는다.

실제 합성 도구 왕복과 웹검색 연결은 연구일지064를 따른다. 연결 성공·스키마 준수·웹 본문 접근 성공·답변 품질은 각각 확인해야 한다. 단일 실행으로 기존 Qwen보다 품질이 높다고 결론 내리지 않는다.
