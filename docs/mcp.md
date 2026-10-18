# MCP 서버 연결

이 프로젝트는 MCP 클라이언트(호스트)다. 서버가 제공하는 도구 목록과 JSON Schema를 발견해 모델에게 전달하고, 모델이 선택한 호출을 MCP로 실행한다. 외부 API를 고정 함수로 다시 구현한 방식과 구분한다.

## 현재 범위

- MCP Python SDK 2.3.0을 고정했다. stdio와 Streamable HTTP를 지원한다.
- 설정은 호스트의 비공개 JSON에서만 읽는다. 브라우저·모델이 주소·실행파일·인증파일을 고르지 않는다.
- 서버별 allowed_tools에 명시한 도구만 노출한다. 실제 서버 스키마로 인자를 검사하고 이름 충돌은 네임스페이스로 분리한다.
- timeout·isError·구조화 결과·텍스트 반환을 구분한다. 원본 반환은 비공개 trace에 보존하고 모델에는 최대6000바이트 패킷을 준다. 큰 결과는 truncated로 표시하며, 1MiB 초과 반환은 거부한다.
- 연결 상태·실제 인자·모델 툴콜ID·반환/오류·모델 전달 형식을 trace와 웹 화면에 남긴다. MCP 결과도 기존 대화 원본 저장·BM25 색인 대상이다.
- MCP 자료는 [mcp:...]로 인용한다. 연결 성공이나 유효한 ID는 최신성·정확성의 보장이 아니다.

현재 TourAPI 키는 없다. 기본 설정에 외부 관광·예약 서버를 활성화하지 않았다. 검증한 것은 실제 MCP 전송·도구 발견·로컬 메타데이터 조회와 합성 서버를 통한 모델 호출이다. 실제 관광 데이터 조회 성공을 주장하지 않는다.

## 호스트 설정

examples/mcp-servers.example.json을 data/private/mcp-servers.json으로 복사해 설정한다. 예시는 모두 enabled=false다. 서버ID·실행위치·도구 이름·키 파일을 확인한 뒤 활성화한다. MCP_CONFIG_FILE로 다른 경로를 명시할 수 있다. 기본 설정 파일이 없으면 기존 에이전트로 동작하고, 명시한 파일이 없으면 오류다.

인증은 env_files·header_files의 파일에서 읽는다. 상대 경로는 설정 파일의 폴더 기준이다. 키·인증 헤더를 모델 스키마에 넣지 않으며, 반환에 동일한 값이나 URL 인코딩 값이 있으면 가린다. stdio 자식은 SDK의 최소 환경과 명시한 env_files만 받는다. stderr와 상세 연결 오류는 data/private/mcp-logs에만 남긴다.

stdio는 검토한 로컬 프로그램을 실행한다. 원격 HTTP는 HTTPS를 쓰며 로컬 주소·Docker 호스트에 한해 HTTP를 허용한다. URL에 인증정보·쿼리를 넣지 않고 header_files를 사용한다. OAuth 로그인·예약 결제 승인·MCP 리소스/프롬프트·이미지 렌더링은 이번 범위가 아니다. 현재 설정에는 조회 도구만 선택한다.

연결·도구 발견은 에이전트 루프 시작 전 수행한다. 이 준비 시간은 기존 모델/도구 루프의180초·모델12회에 포함되지 않는다. 요청마다 연결을 열고 닫으므로 연결 지연과 서버 프로세스 실행 비용이 남는다. 연결 풀과 전체 요청 기한의 통합은 후속이다.

## 한국 관광 데이터 후보

국문 후보는 [Atrani-Labs/visitkorea-tour-mcp](https://github.com/Atrani-Labs/visitkorea-tour-mcp)다. 공식 기관 운영 MCP가 아닌 커뮤니티 래퍼이며, 실제 소스에서 ko→KorService2를 확인했다. 우선 검토한 조회 도구는 area_code·search_by_keyword·search_stay·detail_common·detail_intro다. 숙박 목록은 실시간 객실 가격·예약 가능 여부가 아니다.

키는 [한국관광공사 국문 관광정보 서비스](https://www.data.go.kr/data/15101578/openapi.do)의 활용신청으로 준비한다. 채팅이나 Git에 키를 올리지 않고 data/private/ 아래 파일에 보관한다. 승인 범위·할당량·실제 오퍼레이션은 발급 후 검증한다. 하나의 키로 모든26개 서비스가 허용된다고 가정하지 않는다.

Node23.1.0으로 이 후보를 실행하면 현재 환경에서 종료코드3221225477로 중단됐다. 번들 Node24.19.0에서는 stdio 연결·21개 도구 발견·정적 서비스 목록 조회가 됐다. 전역 Node를 바꾸거나 서버 코드를 수리하지 않았다. 실제 데이터 검증 전의 잠정 후보이며, 메타데이터 시험에는 식별용 가짜 키를 사용하고 외부 API는 호출하지 않았다.

[harimkang/mcp-korea-tourism-api](https://github.com/harimkang/mcp-korea-tourism-api)는 소스의 언어 매핑에 국문ko가 없어 국문 키의 첫 연결 대상으로 선택하지 않았다. README만으로 국문 지원이나 HTTP 배포 동작을 확정하지 않았다.

## 숙소·예약 후보

[Booking.com 공식 MCP 안내](https://developers.booking.com/mcp-server/docs/implementation-guide)는 Streamable HTTP 엔드포인트를 제공한다. Affiliate ID와 Demand API 키가 필요하고 계정별 도구가 다르다. 현재 계정·키를 확인하지 않았으며 접속·가격·재고·예약 성공은 미검증이다. 예시의 도구 이름 자리표시는 실제 계정에서 발견한 이름으로 바꿔야 한다.

## Docker

웹 이미지에는 SDK가 포함되지만 설정·키·외부 서버는 자동으로 포함되지 않는다. stdio의 Node와 실행파일은 컨테이너 안에 있어야 한다. Python 웹 이미지에 호스트 Windows의 Node 경로를 그대로 넣어도 동작하지 않는다.

호스트나 사이드카에서 MCP를 Streamable HTTP로 제공하거나 검토한 런타임을 추가하고, 비공개 설정·키를 읽기 전용으로 마운트한다. ngrok 공유 인스턴스에도 별도 설정이 필요하다. 키와 서버가 없는 현재 배포에는 외부 관광 MCP를 활성화하지 않는다.

## 메모리 상태

호스트 CLI는 SQLite에 임베딩 벡터를 저장하고 정확 유사도 검색·BM25·RRF·선택적 리랭킹을 한다. 별도 벡터DB 제품을 설치한 상태는 아니다. 웹은057의 BM25 메모리다. MCP 도입이 웹 벡터 검색 도입을 뜻하지 않으며 기존 하이브리드 학습 경로는 유지한다.
