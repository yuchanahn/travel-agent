# 002 — 프로젝트 기반과 기록 체계

## 문제에서 검증까지 — 실험을 실행하고 검증할 프로젝트 기반 만들기

보강일: 2026-10-17. 아래는 기존 기록·보존 산출물에 근거한 보강이며, 당시 기록은 뒤에 남겼다. 재실행 출력에는 시점과 코드 버전을 별도로 표시한다.

**흐름:** 로컬 모델만 있는 상태 → Python 실행 입구·상태 확인·기록 기반 → 재현 가능한 개발 시작

### 1. 문제 정의 — 요청과 초기 결과

이 단계는 LLM 답변 개선 실험이 아니라 개발 기반 작업이다. 실제 개발 요청은 현재 워크스페이스에서 Python으로 구현하고 GitHub·노션에 진행을 남기는 것이었다. 기준은 명확한 실행 입구와 공급자 상태 확인이다. 초기 모델만으로는 애플리케이션 실행·평가 경로가 없었다.

### 2. 문제 분석

모델 실행, 앱 실행, 배포, 기록을 구분해야 했다. Docker부터 구성하면 로컬 Ollama와 앱의 실행 경로를 설명하기 전에 운영 변수가 늘어난다. Python 가상환경·패키지와 읽기 전용 진단을 우선했다.

### 3. 연구 과정

Python3.12, src 패키지 구조와 console script를 검토하고 ADR에 선택 이유를 남겼다. 당시 PYTHONPATH로 실행한 터미널 stdout 전체는 남아 있지 않다. 아래 확인은 현재 코드에서의 재실행이다.

### 4. 문제 해결

패키지·doctor·gitignore·로드맵·노션 허브를 만들었다. 실제 console script 연결은 다음 설정이다.

출처: `pyproject.toml`. 종류: **현재 설정 원문**. 원본 파일 SHA-256: `8cc90f515e9fdbf82801bcf8170c6633a8017a2984b50db9689f769c55e3eb8f`. 발췌 내용은 고치지 않았다.

```toml
[project.scripts]
travel-agent = "travel_agent.__main__:main"
```


### 5. 검증 — 개선 결과·대가·남은 한계

명령: `.\.venv\Scripts\travel-agent.exe doctor`. 재실행 시작(UTC): `2026-10-17T11:05:30.886512+00:00`. 코드: `e6fd0f5`. 종료 코드: `0`. 아래는 **이번 보강 시점의 재실행 stdout**이며 최초 구현 당시 출력이 아니다.

출처: `artifacts/research-evidence-2026-10-17/doctor.stdout.txt`. 종류: **현재 재실행 stdout 전체**. 원본 파일 SHA-256: `b5ba4fc6975cc6bf7e82040757a245a0aa9b08a467e43fdbc75b64591cd7453e`. 발췌 내용은 고치지 않았다.

```text
{
  "server_version": "0.40.5",
  "configured_model": "qwen3.5:4b-q4_K_M",
  "model_installed": true,
  "installed_models": [
    "qwen3.5:4b-q4_K_M"
  ],
  "loaded_models": []
}
```

doctor 출력은 서버·설치·적재 상태 확인이다. 여행 추천 품질이나 생성 성공을 판정하지 않는다. 당시 미구현 범위는 아래 원래 기록에 남기고, 후속 구현은007·009로 구분한다.

## 기존 상세 기록 — 작성 당시의 구현·실험·해설

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
