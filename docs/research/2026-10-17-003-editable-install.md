# 003 — Python 실행 절차 단순화

## 문제에서 검증까지 — 소스 경로를 매번 지정하지 않고 실행하기

보강일: 2026-10-17. 아래는 기존 기록·보존 산출물에 근거한 보강이며, 당시 기록은 뒤에 남겼다. 재실행 출력에는 시점과 코드 버전을 별도로 표시한다.

**흐름:** PYTHONPATH 지정 필요 → 개발 모드 설치 → CLI와 모듈 실행 확인

### 1. 문제 정의 — 요청과 초기 결과

src 구조의 패키지를 실행할 때 매번 PYTHONPATH를 지정하는 번거로움이 있었다. 좋은 결과는 가상환경 안에서 동일한 코드가 명령과 모듈 두 방식으로 실행되는 것이다. 모델 답변 품질을 비교하는 단계는 아니다.

### 2. 문제 분석

모듈 탐색 경로 문제와 모델 연결 문제는 별개다. 패키지 설치 없이 소스 디렉터리만 만드는 것으로 실행 명령이 생기지는 않는다.

### 3. 연구 과정

pyproject의 console script와 editable install을 활용했다. 최초 설치와 새 터미널의 활성화 절차를 구분했다. 당시 pip install stdout 전체는 남아 있지 않으며 설치 성공 로그를 새로 만들어 과거 기록에 넣지 않는다.

### 4. 문제 해결

가상환경에 개발 모드로 설치하고 README에 실행법을 기록했다. 아래는 현재 설치 메타데이터와 모듈 실행 확인이다.

명령: `가상환경 Python으로 importlib.metadata.version과 패키지 위치 조회`. 재실행 시작(UTC): `2026-10-17T11:05:31.427636+00:00`. 코드: `e6fd0f5`. 종료 코드: `0`. 아래는 **이번 보강 시점의 재실행 stdout**이며 최초 구현 당시 출력이 아니다.

출처: `artifacts/research-evidence-2026-10-17/package.stdout.txt`. 종류: **현재 재실행 stdout 전체**. 원본 파일 SHA-256: `1547083f3f03d2caaff697f7d361526286c4bacb8687f08affb46caea5d04ffc`. 발췌 내용은 고치지 않았다.

```text
travel-agent 0.1.0
package: src\travel_agent\__init__.py
```


### 5. 검증 — 개선 결과·대가·남은 한계

명령: `.\.venv\Scripts\python.exe -m travel_agent doctor`. 재실행 시작(UTC): `2026-10-17T11:05:31.177217+00:00`. 코드: `e6fd0f5`. 종료 코드: `0`. 아래는 **이번 보강 시점의 재실행 stdout**이며 최초 구현 당시 출력이 아니다.

출처: `artifacts/research-evidence-2026-10-17/module-doctor.stdout.txt`. 종류: **현재 재실행 stdout 전체**. 원본 파일 SHA-256: `b5ba4fc6975cc6bf7e82040757a245a0aa9b08a467e43fdbc75b64591cd7453e`. 발췌 내용은 고치지 않았다.

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

002의 CLI stdout과 이 모듈 stdout은 이번 재실행에서 같은 상태를 반환했다. 현재 소스 수정 반영과 설치가 확인된 것이며 최초 설치 당시 stdout의 복구는 아니다.

## 기존 상세 기록 — 작성 당시의 구현·실험·해설

날짜: 2026-10-17 (Asia/Seoul). 상태: 설치와 실행 검증 완료.

## 문제와 변경

src 구조의 패키지를 실행할 때 PYTHONPATH를 매번 지정하는 대신 가상환경에 `python -m pip install -e .`로 개발 모드 설치했다. 기존 pyproject.toml의 console script를 활용하고 README에 최초 설치와 반복 실행 방법을 구분했다.

## 검증

설치 성공: travel-agent 0.1.0. PYTHONPATH를 제거한 프로세스에서 `.venv/Scripts/travel-agent.exe doctor`와 `.venv/Scripts/python.exe -m travel_agent doctor` 모두 종료 코드 0. 서버 0.40.5 및 지정 모델 설치 확인. 모델 추론·다운로드·삭제는 수행하지 않았다.

## 결정과 한계

새 터미널에서 가상환경 활성화 후 `travel-agent doctor`로 실행한다. 일반 소스 수정은 다음 실행에 반영되며 패키지 설정·의존성 변경 시 재설치한다. 현재는 상태 조회 CLI만 있으며 여행 실행 루프는 미구현이다.

## 노션 동기화

완료: https://app.notion.com/p/3fcd058c022e81f9a78ef9fb20cb925e
