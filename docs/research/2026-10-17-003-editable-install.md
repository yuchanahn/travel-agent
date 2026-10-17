# 003 — Python 실행 절차 단순화

## 가상환경을 켠 다음, 무엇을 실행하면 될까

### 문제 정의

> **🛠️ 개발 질문**
>
> 가상환경에 들어간 다음 main.py를 실행하면 되는 건가? 매번 어떻게 실행해야 하나?

src 구조에서는 패키지를 설치하지 않으면 실행할 때마다 소스 경로를 지정해야 했다.

### 문제 분석

가상환경 활성화와 프로그램 실행은 서로 다른 일이다. 활성화는 사용할 Python과 명령의 위치를 바꾸고, 패키지 설치는 travel-agent 명령을 등록한다.

### 연구 과정

기존 console script를 활용하는 개발 모드 설치를 선택했다. 일반 소스 수정이 다음 실행에 반영되므로 매번 재설치할 필요가 없다.

### 문제 해결

처음 한 번 설치하고, 새 터미널에서는 활성화 후 실행하도록 사용법을 정리했다.

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
travel-agent doctor
```

### 결과와 남은 문제

현재 환경에서 CLI와 python -m travel_agent 두 방식이 모두 정상 종료했다. 실행 결과는002의 상태 확인과 같다. 패키지 위치도 확인했다.

```text
travel-agent 0.1.0
package: src\travel_agent\__init__.py
```

이 기록은 실행 절차를 단순하게 만든 과정이며 모델의 답변 품질 실험은 아니다.

## 구현과 실험 상세

날짜: 2026-10-17 (Asia/Seoul). 상태: 설치와 실행 검증 완료.

## 문제와 변경

src 구조의 패키지를 실행할 때 PYTHONPATH를 매번 지정하는 대신 가상환경에 `python -m pip install -e .`로 개발 모드 설치했다. 기존 pyproject.toml의 console script를 활용하고 README에 최초 설치와 반복 실행 방법을 구분했다.

## 검증

설치 성공: travel-agent 0.1.0. PYTHONPATH를 제거한 프로세스에서 `.venv/Scripts/travel-agent.exe doctor`와 `.venv/Scripts/python.exe -m travel_agent doctor` 모두 종료 코드 0. 서버 0.40.5 및 지정 모델 설치 확인. 모델 추론·다운로드·삭제는 수행하지 않았다.

## 결정과 한계

새 터미널에서 가상환경 활성화 후 `travel-agent doctor`로 실행한다. 일반 소스 수정은 다음 실행에 반영되며 패키지 설정·의존성 변경 시 재설치한다. 현재는 상태 조회 CLI만 있으며 여행 실행 루프는 미구현이다.

## 노션 동기화

완료: https://app.notion.com/p/3fcd058c022e81f9a78ef9fb20cb925e
