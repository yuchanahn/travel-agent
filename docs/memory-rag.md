# 대화 원문 메모리 RAG — 첫 구현

## 도입 이유

현재 문맥을 요약하면 세부 근거가 빠질 수 있다. 원문 대화·도구 결과는 별도로 보존하고, 나중에 관련 질문이 들어오면 원문을 검색해 답변에 제공한다. 요약 자체를 원문 대신 저장하지 않는다.

첫 코퍼스는 임의로 모은 여행 안내 문서가 아니라 **사용자·세션별 대화와 조사 기록**이다. 과거 LLM 발언은 검증된 사실이 아니며, 현재 가격이나 영업 여부는 원본에 저장됐더라도 재확인이 필요하다.

## 현재 구현 범위

- SQLite에 원본 이벤트를 보존한다. 같은 이벤트 ID의 내용 덮어쓰기는 거부하며 정정은 새로운 이벤트로 추가한다.
- 사용자·세션 범위 안에서만 인덱스와 원문을 조회한다. CLI의 user/session은 로컬 네임스페이스이며 로그인·권한 검증 기능은 아니다.
- 인접한 같은 turn_id의 발언·도구 결과를 묶고, E5 토크나이저 기준 240토큰 창/32토큰 overlap으로 나눈다. 원문 이벤트 ID·역할·시점·출처·문자 위치를 유지한다.
- Kiwi + BM25Okapi, multilingual-e5-small CPU + 정규화 벡터 정확 검색, RRF(k=60)를 제공한다.
- 원본이 바뀌면 검색을 거부하고 재인덱싱을 요구한다. 임베딩 모델 commit revision과 패키지·청킹 설정을 인덱스에 기록한다.
- answer는 검색 근거와 선택적인 요약을 Ollama에 전달한다. 웹검색은 수행하지 않는다. 생성 답변을 기억에 자동 재저장하지 않는다.
- 리랭킹 경로는 `--rerank`로 분리돼 있다. 첫 사용 시 BGE 모델을 추가 다운로드한다. 최신 예산 정정 질의 1건에서 실제 CPU 실행과 재정렬을 확인했다. 전체 품질 비교는 후속이다.

자동 채팅 저장·문맥 압축·웹검색·세션 인증·최신 사실 자동 병합은 아직 없다. 현재는 명시적 import/index/search/answer와 선택적 도구 루프 agent CLI다. 사용자 동의 없이 이 개발 채팅을 가져와 저장하지 않는다.

이 문서의 `answer`는 프로그램이 검색 후 생성하는 2-Step RAG다. 별도의 `agent` 명령에서는 LLM이 메모리 검색·원문 조회를 선택한다. 두 경로를 모두 유지한다. 도구 루프·실행 추적·제한은 [Agentic RAG](agentic-rag.md)를 따른다.

## 설치

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

재현용으로 검증한 Windows/Python 3.12 패키지 버전은 requirements-lock.txt에 남긴다. 다른 OS의 wheel·torch 호환성은 별도 검증이 필요하다. E5/BGE는 CPU에서 동작하고 Ollama 생성 모델 설정을 바꾸지 않는다.

## 합성 데이터로 실행

examples의 대화는 테스트용으로 직접 작성한 가상 기록이며 실제 개인 여행·실제 가격이 아니다. 기본 DB는 현재 디렉터리의 data/private/memory.sqlite3이며 Git에서 제외한다. 다른 위치에서는 --db로 같은 DB 경로를 지정한다.

```powershell
travel-agent memory --user demo --session trip import examples/memory-history.jsonl
# 처음 실행 시 Hugging Face의 E5 모델을 다운로드한다.
travel-agent memory --user demo --session trip index
travel-agent memory --user demo --session trip search "강릉을 후보에서 제외한 이유가 뭐였지?"
travel-agent memory --user demo --session trip answer "강릉을 후보에서 제외한 이유가 뭐였지?" --summary examples/compressed-summary.txt
travel-agent memory --user demo --session trip answer "현재 우리가 정한 총예산은 얼마야?" --summary examples/compressed-summary.txt
travel-agent memory --user demo --session trip show e02
```

검색 모드 비교:

```powershell
travel-agent memory --user demo --session trip search "강릉을 제외한 이유" --mode bm25
travel-agent memory --user demo --session trip search "강릉을 제외한 이유" --mode dense
travel-agent memory --user demo --session trip search "강릉을 제외한 이유" --mode hybrid
# 추가 모델 다운로드와 CPU 연산이 발생한다.
travel-agent memory --user demo --session trip search "강릉을 제외한 이유" --mode hybrid --rerank
```

## 입력과 보존

JSONL 각 줄은 event_id, turn_id, timestamp(시간대 포함), role(user/assistant/tool), content 문자열을 필수로 가진다. source_url 등 추가 메타데이터도 보존한다. 데이터는 전달한 user/session 아래 저장된다. 원문은 정규화된 JSON 직렬화로 저장되지만 content와 메타데이터 값은 바꾸지 않는다.

모델·토큰화 설정 변경 시 재인덱싱한다. 장기 운영용 자동 마이그레이션·삭제/보존 정책은 후속 작업이다. 검색 인덱스도 개인정보를 포함할 수 있으므로 원문과 동일하게 로컬 비공개로 취급한다.

## 근거와 한계

검색 결과는 관련성 후보이지 참/거짓이나 최신성의 보증이 아니다. 최신 정정·과거 판단·가상 도구 결과를 모델이 구분하도록 시점과 역할을 제공하지만 자동 사실 갱신 엔진은 아니다. 현 시점 답변에는 검색된 근거를 다시 확인해야 한다.

answer는 `AGENT_CONTEXT_TOKENS`(기본65536)를 Ollama의 num_ctx로 전달한다. 이전 3000바이트 본문 제한은 제거하고 시스템·질의·요약·근거의 UTF-8 본문 합에 `AGENT_MAX_INPUT_BYTES`(기본196608)를 적용한다. 전체 청크만 추가하며, 이 한도는 정확한 Qwen 토큰 계수가 아니다. 실제 남은 토큰을 계산하는 패킹, 주변 원문 추가 조회, 고급 문서 재구성은 후속이다. 인덱싱은 원문을 버리지 않으며 show로 전체 이벤트를 다시 읽을 수 있다.

SQLite가 저장을, BM25·dense·RRF가 근거 선택을, Ollama가 근거 기반 답변을 맡는다. “요약만” 대 “원문 검색 추가” 비교로 세부 근거 복원 여부를 확인하며, 한 번의 성공으로 일반적인 기억 정확도를 주장하지 않는다.

실제 첫 합성 결과와 실패: [연구일지 007](research/2026-10-17-007-conversation-memory-rag.md).

참고: [MemGPT](https://arxiv.org/abs/2310.08560), [LongMemEval](https://arxiv.org/abs/2410.10813).
