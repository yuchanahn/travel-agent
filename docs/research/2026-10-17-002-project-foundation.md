# 002 — 프로젝트 기반과 기록 체계

날짜: 2026-10-17 (Asia/Seoul). 상태: 기반 생성과 상태 조회 검증 완료.

## 질문과 결정

실제 여행 계획에서 겪은 불편을 출발점으로 Python 프로젝트를 만들고 이후 실험을 재현 가능하게 기록한다. Python 3.12와 단일 ReAct 계열 도구 호출 루프로 시작하며 Docker는 앱 배포 단계로 미룬다. 세부 근거는 ADR-0001에 있다.

## 변경

- README에 사용자가 설명한 계기와 검증되지 않은 가설을 구분.
- pyproject.toml, src/travel_agent, .venv, 읽기 전용 doctor 명령 생성.
- .gitignore로 가상환경·비밀 설정·원본 로그 제외.
- docs에 기술 결정·로드맵·연구 기록 규칙 추가.
- 노션 비공개 초안 허브와 하위 기록 생성.
- AGENTS.md에 기록 지속 지침과 허브 연결을 저장.

## 검증

- Python 3.12의 tomllib로 pyproject.toml 파싱 성공.
- .venv Python에서 PYTHONPATH=src로 python -m travel_agent doctor 실행 성공.
- Ollama 0.40.5, 대상 모델 설치 확인. 모델 목록과 적재 상태를 구분하여 출력.
- git check-ignore로 .env, .venv/pyvenv.cfg, 원본 테스트 JSON 제외 확인.
- 노션 허브를 다시 읽어 본문과 하위 페이지 연결 확인.

## 한계와 다음 작업

여행 데이터 소스·도구·에이전트 런타임·웹 API·Docker·사용자 배포는 미구현이다. Git 원격·커밋이 없으며 GitHub 공개와 라이선스 선택도 남아 있다. doctor는 실행 모델 상태 조회만 하므로 제품 품질을 검증하지 않는다.

다음 작업은 실제 여행 요청 예시와 데이터 출처 선정이다.

## 노션 동기화

동기화 완료: https://app.notion.com/p/3fcd058c022e81aebe49f39397ffa23e
