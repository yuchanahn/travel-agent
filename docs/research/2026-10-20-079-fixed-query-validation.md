# 고정 질문 재검증 — 079

## 왜 질문을 되돌렸나
078은 문서 수집·열람 기능을 확인하려고 특정 숙소와 읽기 행동을 질문에 직접 넣었다. 기능 검증으로는 쓸 수 있지만, 기존 Claude Code 비교 질문과 달라 추천 품질 비교를 이어갈 수 없었다. 이번에는 기존 두 질문을 한 글자도 바꾸지 않고 우리 에이전트만 다시 실행했다. Claude는074에 저장한 답변을 그대로 재사용했다.

## 시스템 프롬프트는 어디까지 바꿨나
078에서 추가한 것은 문서 목록의 의미와 저장 본문을 고르는 방법이다. 조사·비교 지침을 전반적으로 새로 설계한 것은 아니다. 이번079 평가 중에는 시스템 프롬프트·도구 설명·제품 코드를 바꾸지 않았다. 기준 제품 코드는1dfa20b다.

이미 있던 지침은 첫 후보 검색 count=20, 후보 이름으로 주소·시설 추가 검색, 공식/예약 사이트 함께 활용하기였다. 아래 실제 실행에서 모델이 count=10을 선택하고 추가 웹검색을 하지 않았으므로, 지침 존재와 행동 준수는 구분해야 한다.

## 좋은 답변의 기준
펜션: 최대3곳의 이름·실제 주소·수영장·개별 바비큐를 후보별 근거와 연결하고, 불명확한 시설과 주소는 미확인으로 남긴다. 다른 숙소의 설명을 섞거나 예약 중개 사이트를 숙소 공식 홈페이지로 표시하면 실패다.
수목원: 공식 안내에서 성인 요금·운영 시간·입장 마감·주차를 확인하고,2명 합계와2026년10월 말의 변동 가능성을 구분한다. 다른 내용의 공식 페이지를 읽은 것만으로 요금이 확인됐다고 쓰면 실패다.

## 실행 조건과 결과
두 구성 모두 같은 로컬 Qwen 가중치다. 우리 쪽은 Ollama qwen3.5:4b-q4_K_M·문맥65536·출력4096·온도0·thinking 비활성·native 종료·모델40/도구36/360초다. 공식 Brave MCP와 OpenBnB를 제공했고 주변 문서 수집은 활성 상태다. Claude074는 공식 Brave 검색만 사용한 기존 구성이다. 도구 범위·프롬프트·검색 시점이 달라 순수한 프롬프트 효과 실험이 아니다.

| 질문 | 우리079 | 이전 Claude074 | 근거 검토 |
|---|---|---|---|
| 가평 펜션 | 완료·모델12/도구13·171.221초 | 완료·모델6/검색5 | 양쪽 미통과 |
| 아침고요수목원 | 완료·모델3/도구2·60.910초 | 완료·모델2/검색1 | 양쪽 미통과 |

우리 시간은 실행기 내부 기준이다. Claude의 저장 시간은 CLI 준비·종료까지 포함해 직접 속도 비교하지 않는다. 반복 거절도 우리 도구 수에 포함하며 자동 HTTP 수집은 별도로 센다. 각 질문1회로 일반적인 우열이나 개선률을 주장하지 않는다. 근거 검토는 구현자가 직접 수행했으며 독립·블라인드 평가가 아니다.

```mermaid
flowchart LR
 A[고정된 사용자 질문] --> B[현재 에이전트 실행]
 B --> C[모델의 검색·본문 선택]
 C --> D[실제 다음 모델 입력과 최종 답변 대조]
 E[저장된074 Claude 결과] --> F[같은 질문끼리 비교]
 D --> F
 F --> G[완료 여부와 사실 품질 별도 판정]
```

## 가평 펜션 — 같은 질문, 실제 두 답변
<callout icon="💬">
	가평에서 성인 두 명이 갈 펜션을 찾아줘. 수영장과 개별 바비큐가 둘 다 있는 후보를 최대 3곳 찾아서 이름, 실제 주소, 두 시설의 확인 근거와 출처 링크를 비교해줘. 날짜는 아직 미정이라 확정 가격이나 예약 가능 여부는 필요 없어. 공식 숙소 안내를 우선하고, 확인되지 않은 항목은 그대로 구분해줘.
</callout>
### 우리 에이전트079의 실제 답변
<callout icon="🤖">
	가평 지역에 수영장 및 개별 바비큐 시설이 모두 있는 펜션을 찾았습니다. OpenBnB 검색 결과와 웹검색 결과를 종합하여 두 시설이 모두 명시된 후보를 선정하겠습니다.
	
	**최종 후보 선정:**
	
	1. **Heterotopia Pension (Luxury Large Private Pool Villa)** - Airbnb listing_key: airbnb:1371622131077299087
	   - 수영장: ✅ Private indoor pool (공식 확인)
	   - 바비큐: ✅ Private BBQ grill: charcoal (공식 확인)
	
	2. **가평스파펜션 콜린 (Coline Pension)** - 공식 홈페이지: https://collineps.com/special2.html
	   - 수영장: ✅ 야외수영장 (공식 확인)
	   - 바비큐: ✅ 개별 실내 바베큐장 (공식 확인)
	
	3. **풀빌라아쿠아밸리** - 공식 홈페이지: www.pensionzava.com
	   - 수영장: ✅ 개별실내수영장 (웹검색에서 명시)
	   - 바비큐: ✅ 개별테라스바비큐 (웹검색에서 명시)
	
	각 후보의 조건과 출처를 비교하여 정리하겠습니다.
	
	| 순위 | 숙소 이름 | 주소 | 수영장 확인 근거 | 바비큐 확인 근거 | 출처 링크 |
	|------|-----------|------|------------------|------------------|-----------|
	| 1 | Heterotopia Pension (Luxury Large Private Pool Villa) | 가평, South Korea (좌표: 37.896859685229515, 127.57839994962063) | ✅ Private indoor pool - available all year, open specific hours, heated (Airbnb 상세 정보) | ✅ Private BBQ grill: charcoal (Airbnb 상세 정보) | https://www.airbnb.com/rooms/1371622131077299087 |
	| 2 | 가평스파펜션 콜린 (Coline Pension) | 경기도 가평군 가평읍 태봉두밀로 269-45 | ✅ 야외수영장 (공식 홈페이지) | ✅ 개별 실내 바베큐장 (사계절 이용 가능) | https://collineps.com/special2.html |
	| 3 | 풀빌라아쿠아밸리 | 경기도 가평군 가평읍 두밀리 4-10 | ✅ 개별실내수영장 (웹검색 정보) | ✅ 개별테라스바비큐 (웹검색 정보) | www.pensionzava.com |
	
	**선택 이유:**
	1. **Heterotopia Pension**: Airbnb 상세 정보를 통해 수영장 (Private indoor pool, all year available) 과 바비큐 (Private BBQ grill: charcoal) 시설이 모두 명시되어 있으며, 공식적인 숙소 정보입니다.
	2. **가평스파펜션 콜린**: 공식 홈페이지에서 수영장, 개별 바비큐 시설이 명확히 기재되어 있으며, 사계절 이용 가능한 프라이빗한 개별 바베큐장이 있다고 명시되었습니다.
	3. **풀빌라아쿠아밸리**: 웹검색 결과에서 수영장 및 개별테라스바비큐 시설이 명시되었으며, 공식 홈페이지 URL도 확인 가능합니다.
	
	**주의사항:**
	- 날짜가 미정인 경우 실제 가격과 예약 가능 여부는 확인할 수 없습니다.
	- 풀빌라아쿠아밸리의 정보는 웹검색 결과를 바탕으로 하며, 공식 홈페이지 직접 확인이 필요합니다.
	- Heterotopia Pension의 주소는 좌표 기반으로 제공되며, 정확한 행정구역명은 확인되지 않았습니다.
	
	이제 비교가 완료되었습니다.
</callout>
### 이전 Claude Code074의 실제 답변
<callout icon="🤖">
	가평에서 수영장과 개별 바비큐 시설이 모두 있는 펜션을 찾았습니다. 공식 안내를 바탕으로 3 곳의 후보를 정리해 드립니다.
	
	---
	
	## 가평 수영장 및 개별 바비큐 펜션 추천 (최대 3곳)
	
	### 1. 가평 가보자독채애견풀빌라수영장펜션
	| 항목 | 내용 | 출처 링크 |
	|------|------|-----------|
	| **숙소명** | 가평 가보자독채애견풀빌라수영장펜션 | [야놀자](https://nol.yanolja.com/stay/domestic/10063510) |
	| **실제 주소** | 경기도 가평군 애견동 47-2 | [여기어때](https://www.yeogi.com/domestic-accommodations/84961) |
	| **수영장 시설 확인 근거** | - 야외 대형 풀장 (가로 20M × 세로 13M, 물높이 1M)<br>- 야외 유아 풀장 운영<br>- 사계절 이용 가능 (미온수 30도)<br>- VIP 객실: 가로 3M × 세로 5M, 물높이 70CM | [여기어때 공식 안내](https://www.yeogi.com/domestic-accommodations/84961) |
	| **개별 바비큐 시설 확인 근거** | - 개별 테라스 바베큐 (숯불)<br>- 공용 바베큐장<br>- 비용: 2인 기준 20,000원 / 인원 추가 시 1인당 5,000원<br>- 준비시간: 입실 후 ~ 오후 9시<br>- 우천 및 동계 이용 가능 | [여기어때 공식 안내](https://www.yeogi.com/domestic-accommodations/84961) |
	| **입실 시간** | 15:00 (퇴실 11:00)<br>21시 이후 입실 시 사전 연락 필수 | [여기어때 공식 안내](https://www.yeogi.com/domestic-accommodations/84961) |
	| **특이사항** | - 애견 동반 펜션<br>- 현재 특실 3 객실은 개별 미끄럼틀 철거되어 이용 불가 | [반려생활](https://ban-life.com/accommodation/21739) |
	
	---
	
	### 2. 가평 콜린스파 펜션
	| 항목 | 내용 | 출처 링크 |
	|------|------|-----------|
	| **숙소명** | 가평 콜린스파 펜션 | [공식 홈페이지](https://collineps.com/) |
	| **실제 주소** | 경기도 가평군 가평읍 태봉두밀로 269-45 | [G마켓 투어](https://gtour.gmarket.co.kr/TourV2/Item?goodscode=2275065702) |
	| **수영장 시설 확인 근거** | - 야외 수영장 운영<br>- 스파 시설 포함 | [야놀자 공식 안내](https://place-site.yanolja.com/places/10045237) |
	| **개별 바비큐 시설 확인 근거** | - 전 객실 실내 개별 테라스 바베큐<br>- 사계절 이용 가능한 프라이빗한 개별 바베큐장 | [G마켓 투어 공식 안내](https://gtour.gmarket.co.kr/TourV2/Item?goodscode=2275065702) |
	| **입실 시간** | 15시 이후 (퇴실 11시 이전)<br>21시 이후 입실 시 펜션으로 사전 연락 필수 | [G마켓 투어 공식 안내](https://gtour.gmarket.co.kr/TourV2/Item?goodscode=2275065702) |
	| **특이사항** | - 남이섬, 가평레일바이크 인근 위치<br>- 전 객실 넷플릭스 이용 가능 (개인 ID 사용)<br>- 마트 픽업: 농수산물마켓, 조은마트, 씨씨할인마트 | [공식 홈페이지](https://collineps.com/) |
	
	---
	
	### 3. 가평 보타니칼펜션
	| 항목 | 내용 | 출처 링크 |
	|------|------|-----------|
	| **숙소명** | 가평 보타니칼펜션 | [야놀자](https://www.yanolja.com/pension/1000111770) |
	| **실제 주소** | 경기도 가평군 아침고요수목원 인근 (구체적 주소 미확인) | [여기어때](https://www.yeogi.com/domestic-accommodations/62421) |
	| **수영장 시설 확인 근거** | - 수영장 운영<br>- 동남아를 연상시키는 이국적인 수영장 특징 | [여행 블로그](https://travel-hotel-culinary.tistory.com/2244) |
	| **개별 바비큐 시설 확인 근거** | - 개별 바베큐 시설<br>- 사랑하는 사람과 맛있는 바비큐 파티 가능 | [야놀자 공식 안내](https://www.yanolja.com/pension/1000111770) |
	| **입실 시간** | 미확인 (공식 안내 확인 필요) | - |
	| **특이사항** | - 애견 동반 가능<br>- 주차 가능<br>- 커피숍 운영<br>- 복층 구조<br>- 마트 픽업: 365마트 (청평역에서 하차 후 택시 이용)<br>- 펜션 자체 픽업 운영 안함 | [여기어때](https://www.yeogi.com/domestic-accommodations/62421) |
	
	---
	
	## 요약
	| 순위 | 숙소명 | 수영장 | 개별 바비큐 | 주소 확인 여부 |
	|------|--------|--------|-------------|----------------|
	| 1 | 가평 가보자독채애견풀빌라수영장펜션 | ✅ (야외대형+유아풀) | ✅ (개별테라스+공용) | ✅ |
	| 2 | 가평 콜린스파 펜션 | ✅ (야외) | ✅ (전 객실 개별테라스) | ✅ |
	| 3 | 가평 보타니칼펜션 | ✅ (이국적 수영장) | ✅ (개별 바베큐) | ⚠️ (미확인) |
	
	**참고사항:**
	- 날짜가 미정이라 확정 가격이나 예약 가능 여부는 확인되지 않았습니다.
	- 공식 숙소 안내를 우선으로 작성하였으며, 일부 항목은 실제 방문 후 확인이 필요합니다.
	- 가보자독채애견풀빌라수영장펜션은 애견 동반 펜션임을 고려하여 반려동물 동반 여부를 확인하시기 바랍니다.
</callout>
### 실제 행동에서 달라진 점
이전076은 웹검색1회 이후 본문 반복으로360초에 실패했다. 이번에는 먼저 OpenBnB 검색1회와 상세3회를 실행하고, 동일 검색을2회 더 요청했다가 로컬에서 거절됐다. 이후 Brave 검색1회(count=10), web_read7회 요청을 거쳐 최종 비교표를 썼다. web_read는5회 성공·1회403·1회동일요청 거절이었다. 총13개 도구 요청 중 실제 성공9·로컬 중복 거절3·HTTP 실패1이다.

검색 래퍼는6개 URL을 자동 수집했다.4개 ready·Hotels.com429·NOL403이었다. 모델은 저장된 콜린 바비큐 본문358자를 읽었지만, 목록에 있던 콜린 수영장·소개·객실의 주변 문서3개는 열지 않았다. 나머지 성공 본문4개는 기존 HTTP 읽기 경로였다. 주변 문서 기능이 있어도 이번 모델은 새 주변 페이지를 선택하지 않았다.

### 근거와 답변을 대조하면
| 답변 내용 | 실제 받은 근거 | 판단 |
|---|---|---|
| Heterotopia 전용 실내 수영장·숯불 바비큐 | Airbnb 상세의 Private indoor pool / Private BBQ grill: charcoal | 두 시설은 해당 숙소의 상세에 있음 |
| Heterotopia 실제 주소 | 검색 목록의 가평 표기와 좌표, 상세 LOCATION_DEFAULT는 비어 있음 | 정확한 주소 미확인. 답변도 이를 밝혔지만 요청한 실제 주소는 미충족 |
| 콜린 개별 실내 바비큐·주소 | 저장 바비큐 본문과 공식 URL의 검색 extra_snippets | 근거 있음. 야외 수영장은 공식 사이트 메타 설명에 있으나 수영장 본문은 열지 않음 |
| 아쿠아밸리 개별 실내 수영장 | 읽은 블로그에서 이 문구는 다음 숙소인 화인스톤빌리지 단락에 있음 | 다른 숙소 정보가 섞인 것으로 판단. 아쿠아밸리 단락의 수영장·개별테라스 바비큐와 구분 필요 |
| www.pensionzava.com을 공식 홈페이지로 표시 | 여러 숙소를 중개하는 펜션자바 공통 예약 링크 | 숙소의 공식 홈페이지로 단정할 근거 부족 |

모델에 실제 전달된 블로그 발췌:
> 풀빌라아쿠아밸리 … 경기도 가평군 가평읍 두밀리 4-10 … 수영장,펜션앞계곡,개별테라스바베큐
>
> **#화인스톤빌리지** … 두번째로 소개해드릴 가평 개별수영장펜션은 화인스톤빌리지예요. … 넓은 #개별실내수영장 과 … 히노끼탕

검색·본문의 숙소 경계를 보존해서 읽어야 했는데 최종 표에서는 그 경계가 무너졌다. 내부 사고 과정은 확인할 수 없으며, 이는 전달된 문장과 최종 주장 사이의 대조다.

### 이전 Claude와 비교
Claude는 첫 검색 뒤 가보자·콜린·보타니칼 이름으로4번 더 검색했다. 우리 쪽은 후보별 추가 웹검색 없이 기존 발췌·본문·Airbnb 상세를 조합했다. Claude는 읽기 좋은 표를 만들었지만 근거에 없는 가보자 주소와 보타니칼의 다른 숙소 링크 문제가 있어 역시 미통과다. 이번에는 우리도 표와 선택 이유를 제시했으나, 종료·형식 개선이 사실 정확성 통과를 뜻하지 않는다.
<details>
<summary>우리 실제 도구 요청·결과·자동 수집 기록</summary>
	**1.1 · 2026-10-20T13:14:40.471481+00:00 · mcp_openbnb_airbnb_search**
	호출 ID: `call_ud6cf78x`
	```json
	{
	  "location": "가평, South Korea",
	  "propertyType": "entire_home"
	}
	```
	결과 시각: 2026-10-20T13:14:44.924316+00:00 · 다음 모델 전달 5953바이트.
	MCP airbnb_search 응답 수신. 숙소별 편의시설은 실제 다음 모델 입력에 전달됐으며 요청 날짜·인원이 없는 가격은 확정값으로 사용하지 않는다.
	**2.1 · 2026-10-20T13:14:49.904556+00:00 · mcp_openbnb_airbnb_listing_details**
	호출 ID: `call_k35q65ea`
	```json
	{
	  "id": "1371622131077299087"
	}
	```
	결과 시각: 2026-10-20T13:14:50.709835+00:00 · 다음 모델 전달 2912바이트.
	MCP airbnb_listing_details 응답 수신. 숙소별 편의시설은 실제 다음 모델 입력에 전달됐으며 요청 날짜·인원이 없는 가격은 확정값으로 사용하지 않는다.
	**2.2 · 2026-10-20T13:14:49.905089+00:00 · mcp_openbnb_airbnb_listing_details**
	호출 ID: `call_r3su9wrl`
	```json
	{
	  "id": "943693827310676434"
	}
	```
	결과 시각: 2026-10-20T13:14:50.744230+00:00 · 다음 모델 전달 2420바이트.
	MCP airbnb_listing_details 응답 수신. 숙소별 편의시설은 실제 다음 모델 입력에 전달됐으며 요청 날짜·인원이 없는 가격은 확정값으로 사용하지 않는다.
	**2.3 · 2026-10-20T13:14:49.906199+00:00 · mcp_openbnb_airbnb_listing_details**
	호출 ID: `call_oabw90cm`
	```json
	{
	  "id": "1026601644011540093"
	}
	```
	결과 시각: 2026-10-20T13:14:50.940939+00:00 · 다음 모델 전달 2923바이트.
	MCP airbnb_listing_details 응답 수신. 숙소별 편의시설은 실제 다음 모델 입력에 전달됐으며 요청 날짜·인원이 없는 가격은 확정값으로 사용하지 않는다.
	**3.1 · 2026-10-20T13:14:57.212092+00:00 · mcp_openbnb_airbnb_search**
	호출 ID: `call_2j1swmt5`
	```json
	{
	  "location": "가평, South Korea",
	  "propertyType": "entire_home"
	}
	```
	결과 시각: 2026-10-20T13:14:57.213140+00:00 · 다음 모델 전달 180바이트.
	오류: Identical tool call already attempted; change query or answer from available evidence · HTTP None
	**4.1 · 2026-10-20T13:14:59.318250+00:00 · mcp_openbnb_airbnb_search**
	호출 ID: `call_7ln0w42k`
	```json
	{
	  "location": "가평, South Korea",
	  "propertyType": "entire_home"
	}
	```
	결과 시각: 2026-10-20T13:14:59.318787+00:00 · 다음 모델 전달 180바이트.
	오류: Identical tool call already attempted; change query or answer from available evidence · HTTP None
	**5.1 · 2026-10-20T13:15:01.139509+00:00 · mcp_brave_brave_web_search**
	호출 ID: `call_hk3zd2dg`
	```json
	{
	  "query": "가평 펜션 수영장 개별 바비큐 시설",
	  "country": "KR",
	  "search_lang": "ko",
	  "ui_lang": "ko-KR",
	  "count": 10
	}
	```
	결과 시각: 2026-10-20T13:15:02.883524+00:00 · 다음 모델 전달 25469바이트.
	검색 결과 10개 전달 · 생략 0개. 본문 자동 주입 없이 발췌와 문서 목록 전달.
	- [불쾌지수 낮추는 시원한, 가평 수영장 펜션 베스트 5 - 계곡? 수영장? 어디든 좋아! 가평 펜션 추천 5곳 - Go Guides](https://kr.hotels.com/go/south-korea/blog-gapyeong-pool-pensions-best-5) · `web:d1dfae4d51b8bbd3` · 추가 발췌 4개
	- [가평 콜린스파 펜션](https://collineps.com/special2.html) · `web:9bfb57a07ed32264` · 추가 발췌 2개
	- [가평 실내수영장 온수무료펜션](https://nol.yanolja.com/stay/domestic/10042159) · `web:9fa387414bc19c9d` · 추가 발췌 4개
	- [2026 경기 가평 추천 펜션 풀빌라 베스트 10](https://www.yeogi.com/accommodation/pension/kr/%EA%B2%BD%EA%B8%B0%EB%8F%84/%EA%B0%80%ED%8F%89%EA%B5%B0) · `web:57b91816927a14c1` · 추가 발췌 4개
	- [가평 실내수영장 온수무료펜션 펜션/풀빌라 사진, 가격, 위치소개 | NOL](https://place-site.yanolja.com/places/10042159) · `web:8d1eb40412ad4745` · 추가 발췌 4개
	- [가평 힐링풀빌라펜션타운](http://healing-town.kr/) · `web:505731150a5bc68b` · 추가 발췌 2개
	- [가평 개별수영장펜션 모음 : 네이버 블로그](https://m.blog.naver.com/penzava/221608778044) · `web:aa3dd72afe5c57c2` · 추가 발췌 4개
	- [나비잠펜션](https://navizam.kr/facility3) · `web:c35398fb21f4a56f` · 추가 발췌 4개
	- [가평 풀빌라 펜션 추천 BEST 3 | 실내 수영장, 키즈 펜션, 가족여행 독채 숙소 모음](https://www.yeogi.com/content/dom-ko-gapyeong-poolvilla-bx2-gapyeong-pool-villa-pension-best-3) · `web:294cedc2ef937af8` · 추가 발췌 4개
	- [가평 빌라드가평 펜션/풀빌라 예약, 가격, 위치, 객실](https://nol.yanolja.com/stay/domestic/10065245) · `web:794f1d72f05cd300` · 추가 발췌 4개
	**래퍼의 자동 HTTP 수집 — 모델의 별도 도구 요청과 구분**
	- 2026-10-20T13:15:02.246356+00:00 · [https://kr.hotels.com/go/south-korea/blog-gapyeong-pool-pensions-best-5](https://kr.hotels.com/go/south-korea/blog-gapyeong-pool-pensions-best-5) · failed · HTTP 429 · 312ms · Page HTTP failure; redirects are not followed
	- 2026-10-20T13:15:02.248116+00:00 · [https://collineps.com/special2.html](https://collineps.com/special2.html) · ready · HTTP 200 · 406ms
	- 2026-10-20T13:15:02.248116+00:00 · [https://nol.yanolja.com/stay/domestic/10042159](https://nol.yanolja.com/stay/domestic/10042159) · failed · HTTP 403 · 156ms · Page HTTP failure; redirects are not followed
	- 2026-10-20T13:15:02.653637+00:00 · [https://collineps.com/special3.html](https://collineps.com/special3.html) · ready · HTTP 200 · 234ms
	- 2026-10-20T13:15:02.653637+00:00 · [https://collineps.com/about.html](https://collineps.com/about.html) · ready · HTTP 200 · 203ms
	- 2026-10-20T13:15:02.654183+00:00 · [https://collineps.com/room.html?room_id=20529](https://collineps.com/room.html?room_id=20529) · ready · HTTP 200 · 219ms
	목록의 주변 문서:
	- `web:aed50e540d1cc37e` · https://collineps.com/special3.html · anchors=['수영장'] · ready
	- `web:b588e1cfed15e206` · https://collineps.com/about.html · anchors=['ABOUT펜션소개'] · ready
	- `web:ba68b382e4d90b2e` · https://collineps.com/room.html?room_id=20529 · anchors=['101호(스파,개별 BBQ)'] · ready
	**6.1 · 2026-10-20T13:15:13.909757+00:00 · web_read**
	호출 ID: `call_92ph0it1`
	```json
	{
	  "query": "수영장 개별 바비큐 시설",
	  "source_id": "web:9bfb57a07ed32264"
	}
	```
	결과 시각: 2026-10-20T13:15:13.918320+00:00 · 다음 모델 전달 996바이트.
	https://collineps.com/special2.html · HTTP None · 전체 358자 · 전달 358자 · 저장소 True · truncated=False · 다음 위치 None。
	**7.1 · 2026-10-20T13:15:30.503868+00:00 · web_read**
	호출 ID: `call_m215ptg6`
	```json
	{
	  "query": "수영장 개별 바비큐 시설 주소",
	  "source_id": "web:aa3dd72afe5c57c2"
	}
	```
	결과 시각: 2026-10-20T13:15:30.974704+00:00 · 다음 모델 전달 4223바이트.
	https://m.blog.naver.com/penzava/221608778044 · HTTP 200 · 전체 3826자 · 전달 1683자 · 저장소 False · truncated=True · 다음 위치 0。
	**8.1 · 2026-10-20T13:15:38.141167+00:00 · web_read**
	호출 ID: `call_9d25bt8d`
	```json
	{
	  "query": "수영장 개별 바비큐 시설 주소",
	  "source_id": "web:c35398fb21f4a56f"
	}
	```
	결과 시각: 2026-10-20T13:15:39.632706+00:00 · 다음 모델 전달 1071바이트.
	https://navizam.kr/facility3 · HTTP 200 · 전체 318자 · 전달 317자 · 저장소 False · truncated=True · 다음 위치 0。
	**9.1 · 2026-10-20T13:15:49.277904+00:00 · web_read**
	호출 ID: `call_h7or7pge`
	```json
	{
	  "query": "수영장 개별 바비큐 시설 주소",
	  "source_id": "web:505731150a5bc68b"
	}
	```
	결과 시각: 2026-10-20T13:15:49.483340+00:00 · 다음 모델 전달 1275바이트.
	http://healing-town.kr/ · HTTP 200 · 전체 403자 · 전달 403자 · 저장소 False · truncated=False · 다음 위치 None。
	**10.1 · 2026-10-20T13:16:30.437390+00:00 · web_read**
	호출 ID: `call_ql19vs5x`
	```json
	{
	  "query": "수영장 개별 바비큐 시설 주소",
	  "source_id": "web:794f1d72f05cd300"
	}
	```
	결과 시각: 2026-10-20T13:16:30.506815+00:00 · 다음 모델 전달 171바이트.
	오류: Page HTTP failure; redirects are not followed · HTTP 403
	**11.1 · 2026-10-20T13:16:38.462819+00:00 · web_read**
	호출 ID: `call_g8uoki6k`
	```json
	{
	  "query": "수영장 개별 바비큐 시설 주소",
	  "source_id": "web:aa3dd72afe5c57c2"
	}
	```
	결과 시각: 2026-10-20T13:16:38.463869+00:00 · 다음 모델 전달 152바이트.
	오류: Identical tool call already attempted; change query or answer from available evidence · HTTP None
</details>
<details>
<summary>이전 Claude 실제 검색 기록 — 새 실행 아님</summary>
	**2026-10-19T16:00:52.427Z · mcp__brave-search__brave_web_search**
	도구 ID `call_wk7tbrkb` · MCP 요청 ID `2`
	```json
	{
	  "query": "가평 펜션 수영장 개별 바비큐 시설 두 가지 모두",
	  "count": 15
	}
	```
	다음 모델 2번에 23322바이트 전달. 추가 발췌 포함, 별도 본문 읽기 없음.
	**2026-10-19T16:01:08.656Z · mcp__brave-search__brave_web_search**
	도구 ID `call_okghsamk` · MCP 요청 ID `3`
	```json
	{
	  "query": "가평 가보자독채애견풀빌라수영장펜션 수영장 개별 바비큐 시설 공식 안내",
	  "count": 5
	}
	```
	다음 모델 3번에 9878바이트 전달. 추가 발췌 포함, 별도 본문 읽기 없음.
	**2026-10-19T16:01:19.391Z · mcp__brave-search__brave_web_search**
	도구 ID `call_nhzf68f0` · MCP 요청 ID `4`
	```json
	{
	  "query": "가평 콜린스파 펜션 수영장 개별 바비큐 공식 안내",
	  "count": 5
	}
	```
	다음 모델 4번에 9617바이트 전달. 추가 발췌 포함, 별도 본문 읽기 없음.
	**2026-10-19T16:01:29.463Z · mcp__brave-search__brave_web_search**
	도구 ID `call_0h0o0b4m` · MCP 요청 ID `5`
	```json
	{
	  "query": "가평 보타니칼펜션 수영장 개별 바비큐 공식 안내",
	  "count": 5
	}
	```
	다음 모델 5번에 5530바이트 전달. 추가 발췌 포함, 별도 본문 읽기 없음.
	**2026-10-19T16:01:39.484Z · mcp__brave-search__brave_web_search**
	도구 ID `call_u2hxh4mw` · MCP 요청 ID `6`
	```json
	{
	  "query": "\"가평 가보자독채애견풀빌라수영장펜션\" 공식 홈페이지 수영장 개별 바비큐 시설 안내",
	  "count": 3
	}
	```
	다음 모델 6번에 5844바이트 전달. 추가 발췌 포함, 별도 본문 읽기 없음.
</details>

## 아침고요수목원 — 같은 질문, 실제 두 답변
<callout icon="💬">
	2026년 10월 말에 성인 두 명이 아침고요수목원을 방문하려고 해. 공식 안내를 찾아서 일반 성인 입장료, 운영 시간과 입장 마감, 주차 안내를 정리해줘. 두 명 입장료 합계도 계산하고, 계절·행사 때문에 달라질 수 있는 사항과 확인한 출처 링크를 분명히 해줘.
</callout>
### 우리 에이전트079의 실제 답변
<callout icon="🤖">
	검색 결과에서 공식 홈페이지의 본문을 확인했습니다. 하지만 운영 시간, 입장료, 주차 안내 등 구체적인 정보는 아직 확인되지 않았습니다. 검색 결과에서 일부 정보를 발견했으니 이를 바탕으로 정리해 보겠습니다.
	
	**아침고요수목원 공식 안내 정보 요약:**
	
	### 📍 위치
	- **주소**: 경기도 가평군 능수면 능수리 123 (가평 아침고요수목원)
	- **공식 홈페이지**: https://www.morningcalm.co.kr/
	
	### 💰 입장료 (2026 년 기준)
	| 구분 | 가격 |
	|------|------|
	| 성인 | 11,000 원 |
	| 청소년 | 8,500 원 |
	| 어린이 | 7,500 원 |
	| 영유아 (36개월 미만) | 무료 |
	| 우대 성인 | 9,000 원 |
	| 가평군민 할인 | 지역 할인 적용 |
	
	**2 명 입장료 합계**: 11,000 × 2 = **22,000 원**
	
	### 🕒 운영 시간 및 입장 마감
	- **일반 운영 시간**: 오전 8:30 ~ 오후 7:00
	- **입장 마감 시간**: 오후 6:00
	- **주의사항**: 계절 행사 기간에는 운영 시간이 달라질 수 있음
	
	### 🅿️ 주차 안내
	- **주차비**: 무료
	- **반려동물 동반**: 불가 (안내견 등 불가피한 경우 방문 전 문의 필요)
	
	### 📅 휴무일 및 기타
	- 공식 홈페이지에서 최신 정보를 확인해야 함
	- 온라인 사전 예약 없이 현장 매표소에서 입장권 구매 가능
	- 계절에 따라 야간 조명 축제 (12 월 초 ~ 3 월 중순) 기간에는 운영 시간이 연장될 수 있음
	
	### ⚠️ 확인되지 않은 사항 (미확인)
	- 정확한 휴무일 정보
	- 2026 년 10 월 말의 특정 행사나 할인 정책
	- 현장 매표소의 운영 시간
	
	**출처 링크**: https://www.morningcalm.co.kr/info/info01.php
	
	이 정보는 공식 홈페이지와 검색 결과에서 확인된 내용이며, 방문 전에는 공식 홈페이지에서 최신 정보를 반드시 확인하시기 바랍니다.
</callout>
### 이전 Claude Code074의 실제 답변
<callout icon="🤖">
	공식 홈페이지와 관련 정보를 바탕으로 아침고요수목원의 이용 정보를 정리해드리겠습니다.
	
	---
	
	## 🌿 아침고요수목원 방문 안내 (2026 년 10 월)
	
	### 💰 입장료 (성인 기준)
	
	| 구분 | 요금 |
	|------|------|
	| **일반 성인** | 11,000 원/명 |
	| 우대 성인 | 9,000 원/명 |
	| 가평군민 할인 | 지역 할인 적용 (증빙 필요) |
	
	**두 명 입장료 합계:** 22,000 원 (일반 성인 기준)
	
	---
	
	### 🕒 운영 시간 및 입장 마감
	
	| 구분 | 시간 |
	|------|------|
	| **개장 시간** | 08:30 |
	| **폐장 시간** | 19:00 |
	| **입장 마감 시간** | 18:00 (폐장보다 1 시간 앞선다) |
	
	> ⚠️ **주의사항:** 계절·행사 기간에 운영 시간이 달라질 수 있습니다. 특히 오색별빛정원전 등 특별 행사 시에는 운영 시간이 변경될 수 있으므로 방문 당일 공식 홈페이지를 확인하세요.
	
	---
	
	### 🅿️ 주차 안내
	
	| 구분 | 정보 |
	|------|------|
	| **주차료** | 무료 |
	| **주차장 위치** | 수목원 입구 인근 |
	| **참고사항** | 성수기 주말에는 주차장이 조기 만차가 될 수 있으므로 오전 10 시 이전 도착을 권장합니다. |
	
	---
	
	### 📝 기타 이용 정보
	
	- **입장권 구매:** 방문 당일 현장 매표소만 (사전 예매 시스템은 운영되지 않음)
	- **반려동물 동반:** 불가
	- **동반 인원:** 원내 동반 입장이 불가능하며 안내견 등 불가피한 경우 방문 전 수목원에 문의해야 합니다.
	- **관람 소요 시간:** 천천히 걸으면 약 2 시간, 사진 촬영을 겸하거나 아이와 함께하면 2 시간 30 분 이상 권장
	
	---
	
	### 📌 계절·행사 관련 확인 사항
	
	1. **오색별빛정원전 등 특별 행사 기간**에는 운영 시간이 달라질 수 있습니다.
	2. **야간 점등:** 2025~2026 시즌 (12 월 5 일 ~ 3 월 15 일) 에는 야간 개장이 있었으나, 10 월은 주간 운영만 확인됩니다.
	3. **단풍 시기:** 10 월 말은 단풍 절정기입니다. 단풍 명소 방문 시에는 오후 6 시 이후 방문을 피하는 것이 좋습니다.
	
	---
	
	### 🔗 공식 출처 링크
	
	- [아침고요수목원 공식 홈페이지](https://www.morningcalm.co.kr/)
	- [입장료·운영시간·할인 안내 페이지](https://www.morningcalm.co.kr/use/use01.php)
	- [관람안내 페이지](https://www.morningcalm.co.kr/info/info01.php)
	
	---
	
	**최종 확인:** 2026 년 8 월 25 일 기준 공식 안내입니다. 기상 및 시설 사정에 따라 변경될 수 있으므로 방문 당일 공식 홈페이지를 다시 한번 확인하는 것이 안전합니다.
</callout>
### 실제 행동에서 달라진 점
Brave 검색1회(count=10) 뒤 자동으로 공식 사이트6문서를 수집했다. 모델은 그중 info/info01.php 하나를 web_read로 열었다. 실제 추출문은 정원별 식물·산책 공간 소개였고,4894자 중 첫4661자를 전달받았다. 다음 위치4661이 있었지만 이어 읽거나 다른 공식 안내를 선택하지 않고 종료했다.

검색 첫 결과 use/use01.php는 제목이 입장료·운영시간·할인 안내였고 저장 상태도 ready였다. 그런데 목록에서는 수집한 페이지의 title인 '아침고요수목원'으로 보였다. 다른 공식 페이지도 같은 title이어서 구분 정보가 약했다. 잘못된 페이지를 고른 정확한 원인은 단정할 수 없지만, 검색 제목과 수집 title을 함께 유지할 필요가 드러났다.

### 근거와 답변을 대조하면
| 답변 내용 | 실제 받은 근거 | 판단 |
|---|---|---|
| 성인11000원·2명22000원 | 제3자 검색 발췌에는 있음. 읽은 공식 정원 소개 본문에는 없음 | 산술은 맞지만 공식 요금 확인으로는 미통과 |
| 08:30~19:00·입장 마감18:00·무료 주차 | 제3자 발췌에서 얻은 내용 | 공식 안내로 묶어 출처를 표시하면 안 됨 |
| 주소 '경기도 가평군 능수면 능수리123' | 다음 모델 입력의 도구 메시지 전체에서 이 주소를 찾지 못함 | 근거 없는 주소 생성. 사용자가 요구하지 않은 정보까지 추가 |
| 2026년10월 말 적용 여부 | 정확한 행사·변동은 미확인이라고 표시 | 단서는 남겼지만 공식 안내 확인을 대체하지 못함 |

실제로 읽은 공식 본문의 첫 부분:
> 능수라는 이름처럼 늘어져 자라는 모양을 갖는 식물을 한데 모아 정원을 조성한 곳입니다. 처진개벚꽃, 능수느릅나무, 등나무, 공작단풍 등 쉽게 만나보지 못한 형태의 식물을 만나볼 수 있습니다.

이 문서가 공식 도메인이라는 사실과 요금 안내의 근거가 된다는 것은 다르다. 주소 생성이 위 '능수' 표현에서 유래했는지는 확인할 수 없다.

### 이전 Claude와 비교
Claude는 검색1회 뒤 제3자 extra_snippets로 요금·시간·주차를 답했다. 우리 쪽은 공식 본문을1회 더 읽었지만 질문과 다른 본문을 읽었으므로 핵심 정보의 근거는 여전히 제3자 발췌였다. Claude의 반려동물 문구 오독·제3자 작성일을 검증일로 표시한 문제도 남아 있다. 양쪽 모두 공식 확인 기준 미통과이며, 본문 호출 수가 늘었다고 품질이 높아진 것은 아니다.
<details>
<summary>우리 실제 도구 요청·결과·자동 수집 기록</summary>
	**1.1 · 2026-10-20T13:17:31.729301+00:00 · mcp_brave_brave_web_search**
	호출 ID: `call_zwvuri30`
	```json
	{
	  "query": "아침고요수목원 공식 홈페이지 입장료 운영 시간 주차 안내",
	  "country": "KR",
	  "search_lang": "ko",
	  "ui_lang": "ko-KR",
	  "count": 10
	}
	```
	결과 시각: 2026-10-20T13:17:33.566029+00:00 · 다음 모델 전달 15752바이트.
	검색 결과 10개 전달 · 생략 0개. 본문 자동 주입 없이 발췌와 문서 목록 전달.
	- [아침고요수목원 입장료·운영시간·할인 안내](https://www.morningcalm.co.kr/use/use01.php) · `web:130b07a5987274bf` · 추가 발췌 0개
	- [아침고요수목원 - 가평군](https://www.morningcalm.co.kr/) · `web:62aa89b2b75af649` · 추가 발췌 0개
	- [관람안내](https://www.morningcalm.co.kr/info/info01.php) · `web:8cb9b8145c50899d` · 추가 발췌 0개
	- [아침고요수목원 단풍시기 2026년 절정과 실속 방문 팁](https://www.sano.co.kr/%EC%95%84%EC%B9%A8%EA%B3%A0%EC%9A%94%EC%88%98%EB%AA%A9%EC%9B%90-%EB%8B%A8%ED%92%8D%EC%8B%9C%EA%B8%B0-2026%EB%85%84-%EC%A0%88%EC%A0%95%EA%B3%BC-%EC%8B%A4%EC%86%8D-%EB%B0%A9%EB%AC%B8-%ED%8C%81) · `web:448952ec1719bd47` · 추가 발췌 4개
	- [2026 아침고요수목원 입장료·할인 총정리｜무료주차·운영시간·소요시간](https://soso-cho.com/entry/2026-%EC%95%84%EC%B9%A8%EA%B3%A0%EC%9A%94%EC%88%98%EB%AA%A9%EC%9B%90-%EC%9E%85%EC%9E%A5%EB%A3%8C%C2%B7%ED%95%A0%EC%9D%B8-%EC%B4%9D%EC%A0%95%EB%A6%AC%EF%BD%9C%EB%AC%B4%EB%A3%8C%EC%A3%BC%EC%B0%A8%C2%B7%EC%9A%B4%EC%98%81%EC%8B%9C%EA%B0%84%C2%B7%EC%86%8C%EC%9A%94%EC%8B%9C%EA%B0%84) · `web:784cd1639665c967` · 추가 발췌 4개
	- [가평 아침고요수목원 입장료·주차·관람 코스](https://thetravelnews.co.kr/2026/07/gapyeong-morning-calm-garden-admission-parking-course/) · `web:f48e6272ea863ccc` · 추가 발췌 4개
	- [[경기도] 가평 아침고요수목원 주차 정보, 입장권 가격](https://bryank.tistory.com/52) · `web:402d2e34104ef461` · 추가 발췌 4개
	- [아침고요수목원 입장료 운영시간 가평 위치](https://brunch.co.kr/@nsrangel91/151) · `web:cd24c54a031b21b6` · 추가 발췌 4개
	- [아침고요수목원 예약 방법·입장료·휴무일 총정리 – 정보허브](https://hub.mindpang.com/morning-calm-arboretum) · `web:de28e913168bf905` · 추가 발췌 3개
	- [운영시간 및 이용요금 안내](http://mczoo.co.kr/22) · `web:79c14fbdc961c6b5` · 추가 발췌 2개
	**래퍼의 자동 HTTP 수집 — 모델의 별도 도구 요청과 구분**
	- 2026-10-20T13:17:32.657173+00:00 · [https://www.morningcalm.co.kr/use/use01.php](https://www.morningcalm.co.kr/use/use01.php) · ready · HTTP 200 · 390ms
	- 2026-10-20T13:17:32.657173+00:00 · [https://www.morningcalm.co.kr/](https://www.morningcalm.co.kr/) · ready · HTTP 200 · 375ms
	- 2026-10-20T13:17:32.657173+00:00 · [https://www.morningcalm.co.kr/info/info01.php](https://www.morningcalm.co.kr/info/info01.php) · ready · HTTP 200 · 531ms
	- 2026-10-20T13:17:33.197572+00:00 · [https://www.morningcalm.co.kr/about/about01.php](https://www.morningcalm.co.kr/about/about01.php) · ready · HTTP 200 · 265ms
	- 2026-10-20T13:17:33.197572+00:00 · [https://www.morningcalm.co.kr/about/about021.php](https://www.morningcalm.co.kr/about/about021.php) · ready · HTTP 200 · 359ms
	- 2026-10-20T13:17:33.201143+00:00 · [https://www.morningcalm.co.kr/use/use02_view.php?idx=121](https://www.morningcalm.co.kr/use/use02_view.php?idx=121) · ready · HTTP 200 · 297ms
	목록의 주변 문서:
	- `web:62aa89b2b75af649` · https://www.morningcalm.co.kr/ · anchors=['아침고요수목원'] · ready
	- `web:914e3ef46fa7be2a` · https://www.morningcalm.co.kr/about/about01.php · anchors=['아침고요수목원'] · ready
	- `web:8c33f9d66b58ef8c` · https://www.morningcalm.co.kr/about/about021.php · anchors=['아침고요수목원 사계절'] · ready
	- `web:a1433fdfc9c298e7` · https://www.morningcalm.co.kr/use/use02_view.php?idx=121 · anchors=['[안내] 산림복지서비스제공자 우수등급 기관 아침고요수목원 선정'] · ready
	**2.1 · 2026-10-20T13:17:52.921878+00:00 · web_read**
	호출 ID: `call_wmmf12so`
	```json
	{
	  "source_id": "web:8cb9b8145c50899d",
	  "query": "입장료 운영 시간 주차 안내 휴무일"
	}
	```
	결과 시각: 2026-10-20T13:17:52.946193+00:00 · 다음 모델 전달 11740바이트.
	https://www.morningcalm.co.kr/info/info01.php · HTTP None · 전체 4894자 · 전달 4661자 · 저장소 True · truncated=True · 다음 위치 4661。
</details>
<details>
<summary>이전 Claude 실제 검색 기록 — 새 실행 아님</summary>
	**2026-10-19T16:03:27.886Z · mcp__brave-search__brave_web_search**
	도구 ID `call_ob6fh7i7` · MCP 요청 ID `2`
	```json
	{
	  "query": "아침고요수목원 입장료 운영 시간 주차 안내 2026 년",
	  "count": 10
	}
	```
	다음 모델 2번에 14681바이트 전달. 추가 발췌 포함, 별도 본문 읽기 없음.
</details>

## 이번에 확인한 것과 다음 개선
두 질문 모두 completed로 종료했지만 엄격 품질은0/2다. 이전076의 펜션 무응답에서 이번에는 답변까지 갔다는 관찰은 가능하다. 다만 검색 결과·도구 선택·새 문서 안내가 함께 달라 수집 기능 하나가 원인이라고 입증하지는 못했다. Claude도 같은 두 기준에서 실패하므로 Claude를 정답지로 채점하지 않는다.

다음 개선은 프롬프트에 단순히 '더 검색해'를 추가하는 것보다 구체적이어야 한다. 후보별 이름·주소·시설·출처를 연결하고 다른 숙소 단락을 합치지 않도록 안내하며, 읽은 문서가 질문 항목을 증명하지 않으면 다른 안내 페이지나 후보 이름 검색을 선택하게 해야 한다. 문서 목록에는 검색 제목과 수집 title을 함께 보존하는 보완도 필요하다. 이는 이번 평가에서 찾은 다음 작업이며 아직 구현·검증하지 않았다. 하네스가 의미적 완료를 대신 결정하거나 finish 태그를 다시 도입한 것은 아니다.

## 고정 검증을 반복하는 방법
이번에 만든 `scripts/evaluate_fixed_travel.py`는 `examples/live-harness-cases.json`의 질문을 그대로 읽고 기존 비교 기록과 같은지 검사한다. 질문을 즉석에서 바꾸지 않으며, 변경할 필요가 생기면 기존 비교와 분리된 새 사례로 다룬다. 출력은 비공개 경로에 저장하고 실패도 보존한다. 사용자 웹 대화는 생성하지 않았고 Claude도 다시 실행하지 않았다.

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_fixed_travel.py --output data/private/fixed-eval-next
```

실제 새 실행 스크립트의 `main` 발췌. 제품 기준1dfa20b 위에 이번079에서 추가한 평가 실행 코드다:
```python
for case in cases:
    assert case['query'] == next(row['query'] for row in reference if row['case'] == case['id'])
```
제품의 시스템 안내 추가는078의 `agent.run_agent`에 이미 있던 다음 한 줄이며079에서 바꾸지 않았다:
```python
system += '\n검색 결과의 document_catalog는 사전 수집한 주변 페이지의 목록이다. 목록의 page_fetched는 수집기의 HTTP 성공이며 너의 본문 열람이 아니다. ready 문서를 제목·anchors·설명으로 골라 web_read로 읽을 수 있다. 저장 문서는 query 발췌 대신 첫 원문 구간을 전달하며, 잘리면 document_token과 next_start_index로 이어 읽는다. 부족한 정보는 추가 웹검색으로 찾을 수 있다.'
```
평가 실행기의 도움말·문법과 실제 두 실행을 확인했다. 제품 코드나 UI는 이번에 바꾸지 않아 서버를 추가하거나 재시작하지 않았다. 기존273개 검사 통과는078의 결과이며 이번 두 답변의 품질 통과를 뜻하지 않는다.
