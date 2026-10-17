# 003 — Python 실행 절차 단순화

날짜: 2026-10-17 (Asia/Seoul). 상태: 설치와 실행 검증 완료.

## 문제와 변경

src 구조의 패키지를 실행할 때 PYTHONPATH를 매번 지정하는 대신 가상환경에 `python -m pip install -e .`로 개발 모드 설치했다. 기존 pyproject.toml의 console script를 활용하고 README에 최초 설치와 반복 실행 방법을 구분했다.

## 검증

설치 성공: travel-agent 0.1.0. PYTHONPATH를 제거한 프로세스에서 `.venv/Scripts/travel-agent.exe doctor`와 `.venv/Scripts/python.exe -m travel_agent doctor` 모두 종료 코드 0. 서버 0.40.5 및 지정 모델 설치 확인. 모델 추론·다운로드·삭제는 수행하지 않았다.

## 결정과 한계

새 터미널에서 가상환경 활성화 후 `travel-agent doctor`로 실행한다. 일반 소스 수정은 다음 실행에 반영되며 패키지 설정·의존성 변경 시 재설치한다. 현재는 상태 조회 CLI만 있으며 여행 실행 루프는 미구현이다.

## 노션 동기화

완료: https://app.notion.com/p/3fcd058c022e81f9a78ef9fb20cb925e
