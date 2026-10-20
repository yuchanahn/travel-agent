# MCP 서버 연결

078부터 공식 Brave 검색 결과에 [주변 페이지 문서 목록](web-documents.md)을 함께 제공한다. 본문은 비공개 저장 후 모델의 web_read 선택 때 전달한다. WEB_DOCUMENT_COLLECTION=0으로 끌 수 있다. 기능 검증과 실제 답변 품질은 구분하며078 실제 응답은 근거 혼합으로 품질 미통과다.

075부터 Brave 검색 응답 예산은96000 UTF-8바이트다. 완결된 결과와 추가 발췌를 보존하고 생략 수를 표시한다. 첫 후보 검색에 count=20을 안내하지만 공급자가 항상20개를 반환한다고 보장하지 않는다.


이 프로젝트는 MCP 클라이언트(호스트)다. 서버가 제공하는 도구 목록과 JSON Schema를 발견해 모델에게 전달하고, 모델이 선택한 호출을 MCP로 실행한다. 외부 API를 고정 함수로 다시 구현한 방식과 구분한다.

## 현재 범위

074부터 호스트는 OpenBnB 검색·상세와 공식 Brave 웹검색 MCP를 함께 사용한다. Brave는 `adapter=brave_search`, `allowed_tools=["brave_web_search"]`로 연결한다. `examples/mcp-brave.example.json`을 참고한다. 기존 OpenBnB 설정을 제거하지 않고 servers 목록에 추가한다. 일반 여행·펜션 검색은 Brave MCP를 우선하고 Airbnb 숙소 목록·예약 조건이 필요하면 OpenBnB를 선택하도록 안내한다. 검색어는 여전히 모델이 선택한다.

현재 Brave 실행본은 검증용 실험 폴더와 분리해 `data/private/mcp-servers/brave-search`에2.1.4로 고정 설치했다. Node24.19.0으로 실행한다. 새 환경에서는 공식 패키지를 설치한 뒤 예시의 실행 경로와 키 파일을 지정한다. 개인 Claude 설정은 실행 때 읽거나 바꾸지 않는다.

Brave 반환은 완전한 항목 단위96000바이트 한도로 추가 발췌까지 보존한다. 초과 항목은 omitted_results로 표시한다. 공통6000바이트 문자열 절단기를 거치지 않는다. 전달한 항목만 web_read의 허용 출처에 등록하며 임의 URL 읽기는 계속 허용하지 않는다. 검색 결과의 출처 ID는 `web:`이고 MCP 호출 자체 ID도 trace에 보존한다. Brave 설정이 있을 때 기존 직접 API 검색 도구는 숨기고 그 이름으로 우회 요청해도 거절한다.

web_read는 현재 알고 있는 출처만 선택지에 표시하고 이번 실행에서 전체를 전달한 페이지는 제외한다. 순차 읽기는0번부터의 연속 구간이 전체 문서를 덮었을 때만 완료로 본다. 이는 문서 전달 상태의 검사이며 작업의 의미적 완료 판단은 모델에 남긴다. 현재 호스트50733에 적용했고 Docker는 이번에 기동·변경하지 않았다. 실제 첫 실패와 보완 후 결과는 [074](research/2026-10-20-074-official-brave-mcp.md)를 따른다.

063에서 사용자의 도입 지시로 OpenBnB 검색·상세 도구2개를 활성화했다. 모델 전달은 완결된 숙소 항목·가격 원문·페이지 커서·누락 개수를 포함하는 구조적 JSON으로 바꿨다. 호스트 웹50730에서 실제 모델 호출·가격 복사·유효 인용을 확인했지만, 양평 이름 후보를 가평 숙소로 묶는 지역 오류가 남았다. Docker 업데이트는 C: 공간 부족과 Docker 저장소 I/O 오류로 실패해50729·ngrok은 이전 버전이다. 아래062의 활성화 보류는 이전 판정이다.

062에서 OpenBnB를 단독 검증했다. 기본 robots 검사에서는 검색 전 중단했고, 원본의 검사 제외 진단 옵션에서는 국내 숙소 검색·가격 필터·페이지 조회가 됐다. 상세 일부 누락·한국어 지오코딩 오인식·우리 모델 패킷의 내부 JSON 잘림을 확인해 에이전트 활성화는 보류했다. 새 공급자 가입이나 실제 모델 호출 없이 검증했으며 [062 결과](research/2026-10-19-062-openbnb-validation.md)를 따른다.

060 결정: TourAPI 도입을 중단했다. 사용자가 신청 과정에서 신고 안내를 확인하고 도입하지 않기로 했다. 해당 안내의 법적 적용 여부를 이번에 조사·판단한 것은 아니다. 키 발급·기관 API 연동을 다음 작업의 전제 조건으로 두지 않는다. 아래 관광·예약 후보 조사는059의 이력이며 현재 도입 계획이 아니다. 기존 Brave 검색은 유지한다.

- MCP Python SDK 2.3.0을 고정했다. stdio와 Streamable HTTP를 지원한다.
- 설정은 호스트의 비공개 JSON에서만 읽는다. 브라우저·모델이 주소·실행파일·인증파일을 고르지 않는다.
- 서버별 allowed_tools에 명시한 도구만 노출한다. 실제 서버 스키마로 인자를 검사하고 이름 충돌은 네임스페이스로 분리한다.
- timeout·isError·구조화 결과·텍스트 반환을 구분한다. 원본 반환은 비공개 trace에 보존하고 모델에는 최대6000바이트 패킷을 준다. 큰 결과는 truncated로 표시하며, 1MiB 초과 반환은 거부한다.
- 연결 상태·실제 인자·모델 툴콜ID·반환/오류·모델 전달 형식을 trace와 웹 화면에 남긴다. MCP 결과도 기존 대화 원본 저장·BM25 색인 대상이다.
- MCP 자료는 [mcp:...]로 인용한다. 연결 성공이나 유효한 ID는 최신성·정확성의 보장이 아니다.

현재 TourAPI 키는 없다. 기본 설정에 외부 관광·예약 서버를 활성화하지 않았다. 검증한 것은 실제 MCP 전송·도구 발견·로컬 메타데이터 조회와 합성 서버를 통한 모델 호출이다. 실제 관광 데이터 조회 성공을 주장하지 않는다.

## 호스트 설정

OpenBnB는 examples/mcp-openbnb.example.json의 실행파일·clone 경로를 수정해 data/private/mcp-servers.json으로 설정한다. 현재 호스트는 번들 Node24.19.0·고정 소스d5a8f18을 사용한다. 새 환경은 해당 커밋을 checkout한 뒤 npm ci --ignore-scripts 및 npm run build로 준비한다. 호스트 웹은 scripts/start_web_host.ps1(기본50730), 데이터는 data/private/web-host다. 기존 Docker 볼륨과 별도이므로 과거 대화가 이 화면으로 자동 이전되지 않는다.

--ignore-robots-txt는 사용자가063에서 도입한 서버 실행 정책이다. 모델 스키마에서 호출별 ignoreRobotsText를 제거하고 해당 인자를 모델이 보내면 거부한다. 새 키·로그인·브라우저는 요구하지 않는다. 한국어 지오코딩은 여전히 오인식할 수 있어 안내를 제공하지만 자동 정규화·행정구역 검증이 구현된 것은 아니다.

examples/mcp-servers.example.json은 빈 서버 목록으로 시작한다. data/private/mcp-servers.json에 검토한 서버만 추가한다. 서버ID·전송 방식·실행위치 또는 URL·allowed_tools를 지정하고, 인증이 필요한 경우에만 env_files·header_files를 추가한다. MCP_CONFIG_FILE로 다른 경로를 명시할 수 있다. 기본 설정 파일이 없으면 기존 에이전트로 동작하고, 명시한 파일이 없으면 오류다.

인증은 env_files·header_files의 파일에서 읽는다. 상대 경로는 설정 파일의 폴더 기준이다. 키·인증 헤더를 모델 스키마에 넣지 않으며, 반환에 동일한 값이나 URL 인코딩 값이 있으면 가린다. stdio 자식은 SDK의 최소 환경과 명시한 env_files만 받는다. stderr와 상세 연결 오류는 data/private/mcp-logs에만 남긴다.

stdio는 검토한 로컬 프로그램을 실행한다. 원격 HTTP는 HTTPS를 쓰며 로컬 주소·Docker 호스트에 한해 HTTP를 허용한다. URL에 인증정보·쿼리를 넣지 않고 header_files를 사용한다. OAuth 로그인·예약 결제 승인·MCP 리소스/프롬프트·이미지 렌더링은 이번 범위가 아니다. 현재 설정에는 조회 도구만 선택한다.

연결·도구 발견은 에이전트 루프 시작 전 수행한다. 이 준비 시간은 기존 모델/도구 루프의180초·모델12회에 포함되지 않는다. 요청마다 연결을 열고 닫으므로 연결 지연과 서버 프로세스 실행 비용이 남는다. 연결 풀과 전체 요청 기한의 통합은 후속이다.

## 한국 관광 데이터 후보

국문 후보는 [Atrani-Labs/visitkorea-tour-mcp](https://github.com/Atrani-Labs/visitkorea-tour-mcp)다. 공식 기관 운영 MCP가 아닌 커뮤니티 래퍼이며, 실제 소스에서 ko→KorService2를 확인했다. 우선 검토한 조회 도구는 area_code·search_by_keyword·search_stay·detail_common·detail_intro다. 숙박 목록은 실시간 객실 가격·예약 가능 여부가 아니다.

059에서 [한국관광공사 국문 관광정보 서비스](https://www.data.go.kr/data/15101578/openapi.do) 활용신청을 후속으로 제시했으나060에서 취소했다. 키 발급이나 실제 관광 API 검증을 진행하지 않는다.

Node23.1.0으로 이 후보를 실행하면 현재 환경에서 종료코드3221225477로 중단됐다. 번들 Node24.19.0에서는 stdio 연결·21개 도구 발견·정적 서비스 목록 조회가 됐다. 전역 Node를 바꾸거나 서버 코드를 수리하지 않았다. 실제 데이터 검증 전의 잠정 후보이며, 메타데이터 시험에는 식별용 가짜 키를 사용하고 외부 API는 호출하지 않았다.

[harimkang/mcp-korea-tourism-api](https://github.com/harimkang/mcp-korea-tourism-api)는 소스의 언어 매핑에 국문ko가 없어 국문 키의 첫 연결 대상으로 선택하지 않았다. README만으로 국문 지원이나 HTTP 배포 동작을 확정하지 않았다.

## 숙소·예약 후보

[Booking.com 공식 MCP 안내](https://developers.booking.com/mcp-server/docs/implementation-guide)는 Streamable HTTP 엔드포인트를 제공한다. Affiliate ID와 Demand API 키가 필요하고 계정별 도구가 다르다. 현재 계정·키를 확인하지 않았으며 접속·가격·재고·예약 성공은 미검증이다. 060에서 설정 예시에서 제거했으며 현재 도입 계획이 아니다.

## Docker

063 Dockerfile은 Node24 빌드 단계에서 OpenBnB 고정 커밋을 가져와 빌드하고 최종 웹 이미지에 런타임·서버를 포함한다. config/mcp-docker.json이 두 조회 도구를 활성화한다. Docker 빌드의 첫 이미지 생성은 됐으나 마지막 소스 수정 후 재빌드·재배포는 저장소 I/O 오류로 실패했다. 디스크 공간을 확보한 뒤 scripts/start_web.ps1로 다시 빌드하고 실제 검색을 확인해야 한다. 현재 배포 완료로 해석하지 않는다.

새 Docker 빌드 구성에는 OpenBnB 실행파일·Node·설정이 포함된다. 그 밖의 외부 MCP 서버·키는 자동 포함되지 않는다. stdio의 실행파일은 컨테이너 안에 있어야 하며 호스트 Windows 경로를 그대로 사용할 수 없다.

호스트나 사이드카에서 MCP를 Streamable HTTP로 제공하거나 검토한 런타임을 추가하고, 비공개 설정·키를 읽기 전용으로 마운트한다. ngrok 공유 인스턴스에도 별도 설정이 필요하다. 키와 서버가 없는 현재 배포에는 외부 관광 MCP를 활성화하지 않는다.

## 메모리 상태

호스트 CLI는 SQLite에 임베딩 벡터를 저장하고 정확 유사도 검색·BM25·RRF·선택적 리랭킹을 한다. 별도 벡터DB 제품을 설치한 상태는 아니다. 웹은057의 BM25 메모리다. MCP 도입이 웹 벡터 검색 도입을 뜻하지 않으며 기존 하이브리드 학습 경로는 유지한다.
