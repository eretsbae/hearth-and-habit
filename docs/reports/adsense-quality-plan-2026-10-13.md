# 애드센스 마지막 심사를 위한 콘텐츠 품질 전략·실행 계획 (2026-10-13, 개정)

작성: Claude Code 세션 (hearth-and-habit). 결재자: 오너. 상태: **Phase 0 구현 완료, PR #42 머지 대기**.

오너 결정(10-13 반영): 편집 책임자 표기는 **peter.bae**로 통일. 사진은 제공하지 않는다. 오너 공수는
더 들이지 않는다. 따라서 이 계획은 **세션이 생성·자동화로 만들 수 있는 것만**으로 짜고, 오너가 할 일은
PR 머지와 애드센스 제출 버튼 두 번으로 줄였다.

## 0. 한 줄 결론

글을 더 쓰는 것으로는 통과하지 못한다(43→51→70편 모두 같은 사유 "가치가 별로 없는 콘텐츠").
사진 없이 사람 흔적을 만들 수는 없으므로, 대신 **(1) 책임자 식별, (2) 대량 생산 티 제거, (3) 글마다
다른 곳에 없는 계산된 자산 1개, (4) 자연 클릭 발생**에 집중한다. (1)(2)는 이 PR에서 코드로 끝냈고,
(3)은 생성 규칙에 넣어 이후 발행 글에 자동 적용된다. 제출은 11월 셋째 주 이후 게이트 충족 시 1회만.

## 1. 현재 상태 (2026-10-13 확인)

| 항목 | 값 | 출처 |
|---|---|---|
| 거절 횟수 | 6회 (07-16, 07-30, 08-05, 08-19, 09-11, 10-11) | AdSense 메일, 메모리 |
| 10-11 거절이 본 사이트 | **리서치 재작성 전** 버전 (10-05 제출, 재작성은 10-11 머지·동기화) | git log f6b69ca, c1c99e1 |
| 발행 글 | 71편 (필러별 12~16), 대기 주제 4개 | `config/topics.yml` |
| 글 길이 | 최소 1,346 / 중앙값 1,876 / 최대 3,050 단어 | `content/posts` |
| Search Console 28일 | 클릭 0, 노출 약 30, 노출 페이지 6개 | `docs/reports/weekly-2026-10-12.md` |
| 노출이 잡히는 주제 | leftover rice, garbage disposal humming, clothes worn once, About 페이지(노출 12·순위 5.9·클릭 0) | 같은 보고서 |
| 다음 제출 가능일 | **2026-11-04 이후**, 실질 변화가 있을 때만. 거절 시 애드센스 경로 종료 | `docs/SETUP_GUIDE.md` 중단 기준 |
| 1차 점검 | 2026-11-16, 28일 클릭 100 미만이면 자동 발행 중지 | 같은 절 |
| 수익 | 승인돼도 광고 수익 수령 보류(겸업 승인 전) | 메모리 adsense-revenue-hold |
| 제약 | API 크레딧 없음(세션 토큰만), 11-16까지 새 기능 PR 금지·고장 수정만 | AGENTS.md, PR #41 |

### 라이브 사이트를 심사자 눈으로 본 결과 (10-13 curl 확인)

1. **"Last reviewed October 11, 2026"이 71편 전부의 첫 줄**. 홈 카드 스니펫, `og:description`,
   검색 스니펫의 첫 단어가 돼 "같은 날 일괄 편집한 사이트"로 읽힌다.
2. **구조 획일**: 71편 모두 `## Sources`, 68편 `## FAQ`, 70편에 표. 같은 골격.
3. **이미지 148장 전부 플랫 SVG**, 사진 0장. (오너 결정으로 이 항목은 바꾸지 않는다.)
4. **책임자 없음**: 바이라인 숨김, About에 사람 이름 없음.
5. **라벨 170개 중 148개가 2편 이하**에 쓰임. 라벨 위젯이 지저분하고 얇은 라벨 페이지 수십 개 생성.
6. **허브 없음**: 필러별 "여기서 시작" 페이지가 없다.
7. 정적 4페이지·HTTPS·ads.txt·JSON-LD·내부 링크는 이미 정상.

## 2. 전략 (오너 공수 0 기준)

### 원칙

- **폭 → 깊이.** 새 필러·새 소주제 중단. 노출이 잡힌 주제 주변과 필러당 코너스톤 1편.
- **사람 흔적 대신 "여기서만 볼 수 있는 계산".** 사진은 없으니, 글마다 출처 수치로 직접 계산한 표·
  워크드 예시 1개를 의무화한다. 상위 검색결과를 요약한 글과 구분되는 유일한 자동화 가능 수단이다.
- **티 제거는 코드로.** 날짜 줄 위치, 바이라인, 라벨 통합, 허브, FAQ 기본 해제. 전부 이 PR에 포함.
- **제출은 달력이 아니라 게이트로.** 11-04는 하한선이지 목표일이 아니다.

### 세 축과 완료 기준

| 축 | 할 일 | 상태 |
|---|---|---|
| B. 책임자 | About "Who runs this site"에 peter.bae, 글 하단 "Written and reviewed by peter.bae" 바이라인, JSON-LD author를 Person peter.bae로 | **구현 완료**(이 PR) |
| C. 양산 티 제거 | ① Last reviewed 줄을 본문 끝 바이라인 옆으로 ② 라벨 170→22개(`config/labels.yml`, check_post가 강제) ③ FAQ 기본 해제 ④ 필러 허브 페이지 5개(필러 글 전체 목록 자동 생성) + About에서 링크 ⑤ 히어로를 평면 SVG에서 오픈 라이선스 실사진으로(10-13 오너 승인) | **구현 완료**(이 PR) |
| D. 깊이·유입 | ① 글마다 계산된 원본 자산 1개 의무(생성 규칙) ② 코너스톤 5편 ③ 노출 잡힌 주제 클러스터 4편 ④ 노출 상위 페이지 제목·설명 CTR 개선 | ①은 규칙 반영 완료, ②③④는 Phase 1 |

### 하지 않는 것

- 발행 빈도 올리기, 새 필러, 트렌드 주제.
- 날짜·경험담·사진 날조. "Last reviewed"는 위치만 옮기고 값은 그대로. 1인칭 경험담은 생성 규칙에서 금지.
- 11-04 되자마자 제출. 게이트 미충족 제출은 10-05에 이미 한 번 써 버렸다.
- 광고 켜기·지급 정보 등록(겸업 보류).
- 오너에게 사진·메모·캡처 요청.
- AI 이미지 생성으로 '사진'을 만드는 것. 실제 집·실제 사물이 아닌 것을 사진처럼 내는 순간 날조다.
  대신 CC0·CC BY·CC BY-SA·퍼블릭 도메인 실사진만 쓰고, 사진 아래에 출처·라이선스를 적는다.

## 3. 실행 계획

### Phase 0 — 이 PR(#42)에 포함, 머지 즉시 라이브 반영

| # | 변경 | 파일 |
|---|---|---|
| 0-1 | 날짜 줄을 본문 맨 앞에서 끝으로, 바이라인과 합쳐 `Written and reviewed by peter.bae for Hearth & Habit · Last reviewed …` | `generator/blogger_publish.py` `editorial_footer` |
| 0-2 | JSON-LD author `Organization` → `Person peter.bae`; `config/site.yml`에 `author` | `blogger_publish.py`, `config/site.yml` |
| 0-3 | 라벨 체계 신설(필러 5 × 소주제 4~6 = 22개) + 별칭표, 71편 `tags` 일괄 치환(1~4개), check_post가 체계 밖 태그 거부 | `config/labels.yml`, `scripts/consolidate_labels.py`, `generator/check_post.py`, `content/posts/*` |
| 0-4 | 필러 허브 페이지 5개(소개 + 해당 필러 글 전체 목록 자동 생성) | `content/pages/{home-maintenance,cleaning-organization,energy-savings,kitchen-habits,yard-outdoor}.md`, `generator/blogger_pages.py` |
| 0-5 | About: "Who runs this site"(peter.bae), 필러 허브 링크, AI 고지 문구를 "편집자가 수치 전수 확인·서명"으로 | `content/pages/about.md` |
| 0-6 | 생성 규칙: FAQ 기본 해제, 계산된 원본 자산 1개 의무, 측정값·일화 날조 금지, 본문에 서명 금지(발행 단계가 붙임) | `generator/prompts.py`, `generator/CLAUDE_RUN.md` |
| 0-7 | 히어로 스톡 사진(10-13 오너 승인 "스톡 사진으로 교체하거나 추가"): Openverse(키 없음, 상업·수정 허용 라이선스만)에서 검색→대조표로 세션이 눈으로 고름→16:9 1200px JPG로 저장→frontmatter `hero_credit`·`hero_credit_url`·`hero_license_url`. 발행 단계가 사진 아래 12px 출처 캡션(작가·출처·라이선스 링크)을 붙인다. 적용: 노출 상위·최근 글 20편(노출 상위·최근 글; stop-losing-time-before-leaving-house는 맞는 사진이 없어 SVG 유지) + 필러 허브 5페이지. 나머지 글은 SVG 유지, 새 글은 생성 규칙에서 사진을 1순위로 | `scripts/stock_photo.py`, `blogger_publish.py` `hero_image_tag`, `blogger_pages.py` `page_html`, `content/images/*-hero.jpg`, `content/posts/*`, `content/pages/*`, `CLAUDE_RUN.md` |

검증: `py_compile` 통과, `check_post` 2편 PASS, 렌더 테스트에서 첫 1,500자에 "Last reviewed" 없음·
바이라인 본문 끝·JSON-LD author Person peter.bae·허브 5페이지에 글 목록 생성 확인.

머지 후 반영 경로: `content/posts/**` 변경이므로 `sync-posts.yml`이 자동 실행돼 71편이 재동기화된다
(URL 불변, 색인 영향 없음). 허브·About은 `publish-pages.yml`을 workflow_dispatch로 1회 실행해야
하며, 세션이 REST로 디스패치한다. 오너는 머지만 하면 된다.

### Phase 1 — 10-15 ~ 11-03, 발행 슬롯 월/수/금 9회 (세션 단독)

| 슬롯 | 내용 |
|---|---|
| 5회 | 코너스톤(필러당 1편, 2,500단어+, 계산 자산 2개 이상): ① Winter home prep master checklist(home-maintenance) ② Fridge/freezer food-safety reference(kitchen) ③ Whole-house energy audit you can do yourself(energy) ④ Cleaning schedule by room and frequency(cleaning) ⑤ Fall-to-spring yard calendar by zone(yard). 발행 후 각 허브 페이지 상단에 "Start here"로 고정 |
| 4회 | 클러스터: leftover rice · garbage disposal · clothes worn once · musty laundry 주변 롱테일 1편씩 |
| 0회 | 대기 주제 4개는 보류(큐 뒤로) |

- 주제 큐 교체는 `config/topics.yml` 편집이며 세션이 10-14에 별도 PR 없이 이 브랜치 머지 후 처리한다
  (데이터 변경, 기능 아님). `target_words` 같은 필드 추가는 하지 않고 코너스톤 길이는 주제 `notes`에
  지시한다.
- 선택 과제(검토 후 적용): 글 안에 인라인 JS 계산기(예: 난방비 계산기). Blogger가 `<script>`를 허용하는지
  라이브 1편으로 확인한 뒤 코너스톤 2편에만 넣는다. 미동작 시 정적 표로 대체.

### Phase 2 — 11-04 ~ 11-16, 검증

- `dev:검증`에 80편 전수 독립 검증: 근거 없는 수치, 상위 검색결과 반복, 골격 동일성.
- Search Console API(이미 서비스 계정 연결됨)로 색인 수·노출 상위 페이지를 세션이 조회해 제목·설명 수정.
- 11-16 1차 점검은 규정대로 적용(클릭 100 미만 → 자동 발행 중지). 애드센스 제출은 별도 게이트. 두 규정은
  독립이며 숫자는 재협상하지 않는다.

### Phase 3 — 제출 (예상 11-17 ~ 11-30)

제출 전 체크리스트(전부 ✔ 아니면 제출 안 함, 세션이 측정해 보고):

- [ ] 색인 30페이지 이상
- [ ] 자연 클릭 0이 아닌 날 7일 연속
- [ ] About·글 하단·JSON-LD의 peter.bae 표기 일치(라이브 확인)
- [ ] 홈 스니펫에 "Last reviewed" 없음, 라벨 22개, 허브 5개 라이브
- [ ] 코너스톤 5편 라이브, 계산 자산 포함
- [ ] 제출 후 심사 종료까지 구조 변경 동결

## 4. 오너가 할 일 (총 2회 클릭)

1. **PR #42 머지.** 이후 라이브 반영은 세션이 처리.
2. **제출 버튼.** Phase 3 게이트 충족 시 세션이 보고하면 AdSense에서 재심사 요청.

선택(각 2분, 안 해도 계획은 성립): Blogger 설정 → 크롤러 및 색인 생성 → 맞춤 robots 헤더 태그에서
아카이브·검색 페이지에 `noindex` 켜기. Blogger 프로필 표시명을 peter.bae로.

## 5. 리스크

- 사진은 스톡(오픈 라이선스)이지 1인칭 사진이 아니다. 기대 효과는 "전 글이 같은 그림체"라는 외관 획일성 완화까지이며,
  심사자가 1인칭 경험 부재를 이유로 거절하면 막을 수단이 없다. 그 경우 애드센스 경로를 접는다(규정대로).
- 스톡 사진의 라이선스 표기는 사진 아래 캡션으로 고정 노출한다(CC BY/BY-SA 조건). 캡션을 지우는 편집은 금지.
- Openverse 익명 한도(분 20·일 200)가 있어 글 1편당 검색 2~3회로 끝낸다. 맞는 사진이 없으면 SVG 유지.
- 11-16 클릭 100 미만으로 발행이 멈추면 Phase 1 잔여 슬롯이 사라진다. 그래서 코너스톤을 10월 안에 앞당긴다.
- 71편 재동기화와 라벨 교체로 Blogger 라벨 URL(`/search/label/…`)이 바뀐다. 검색 유입이 0이므로 실손은 없다.
- 허브 페이지 글 목록은 발행 시점 스냅샷이다. 새 글이 나올 때마다 `publish-pages`를 다시 돌려야 하며,
  Phase 1 발행 스크립트에 이 호출을 붙이는 것은 11-16 이후 기능 PR로 넘긴다. 그전까지는 세션이 수동 디스패치.
