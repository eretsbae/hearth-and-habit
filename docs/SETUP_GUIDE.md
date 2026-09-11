# 셋업 가이드 (처음부터 끝까지)

> **2026-07-03 업데이트**: 원래 계획이던 "커스텀 도메인 구매 + GitHub Pages 배포" 대신, 이미
> 보유 중인 **Blogger 블로그(peterpb.blogspot.com) + 진행 중이던 애드센스 계정**을 그대로
> 활용하는 방식으로 전환했습니다. 도메인 구매, DNS 설정, 도메인 소유권 인증이 전부 필요 없어져
> 훨씬 빠르게 시작할 수 있습니다. 전환 배경은 [blogger/SETUP.md](../blogger/SETUP.md) 참고.

이 문서만 따라 하면 됩니다. **사용자가 직접 해야 하는 일은 계정 승인/시크릿 등록뿐**이고, 나머지는 전부 자동입니다. 총 소요 시간: 약 25~35분.

---

## 1단계. 리포지토리 확인 ✅ 완료

`eretsbae/hearth-and-habit` 리포지토리에 프로젝트가 이미 올라가 있습니다: https://github.com/eretsbae/hearth-and-habit

## 2단계. Claude API 키 등록 (5분)

1. https://console.anthropic.com 접속 → 가입/로그인 → 결제수단 등록 후 소액 크레딧 충전
   - (선택) Settings에서 월 사용 한도를 걸어두면 안전합니다. 예상 비용은 월 $1~5 수준입니다.
2. API 키 발급 (`sk-ant-...`)
3. 리포지토리 → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `ANTHROPIC_API_KEY`
   - Value: 방금 발급받은 키

## 3단계. Blogger 연동 (25분, 최초 1회) ⭐ 핵심 단계

기존에 사용하시던 `peterpb.blogspot.com` 블로그를 그대로 발행 대상으로 씁니다. 두 부분으로 나뉩니다:

- **A. 디자인 적용** — Claude가 만든 웜톤 에디토리얼 CSS를 Blogger 테마에 붙여넣기 (5분)
- **B. 자동 발행 인증** — Google 계정이 자동화 앱에 "내 블로그에 글 올려도 됨"을 1회 승인 (15~20분)

**자세한 단계별 안내: [blogger/SETUP.md](../blogger/SETUP.md)**

이 단계가 끝나면 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` 세 개의 시크릿이 리포지토리에 등록되어 있어야 합니다.

## 4단계. 첫 실행 (5분)

1. 리포지토리 **Actions 탭** → 왼쪽 **"Generate & Publish Post"** 선택 → **Run workflow** 클릭
2. 몇 분 뒤 완료되면:
   - 새 글 1편이 Claude로 생성되어 `content/posts/`에 커밋됨
   - 기존에 준비되어 있던 시드 글 3편 + 새 글이 **한 번에 peterpb.blogspot.com에 발행**됨 (최초 실행이라 미발행 상태였던 글이 전부 올라감 — 이후로는 회차마다 새 글만 올라갑니다)
3. https://peterpb.blogspot.com 접속해서 확인

## 완료. 이후 자동으로 일어나는 일

- **매주 월/수/금** GitHub Actions가 자동 실행되어: Claude가 새 글 1편(본문 + 일러스트) 작성 → 리포에 커밋 → Blogger에 자동 게시
- 대기 주제가 5개 미만이 되면 Claude가 고정된 5개 필러(주택관리/청소·정리/에너지절약/주방/마당) 안에서만 새 주제를 자동 보충 — 트렌드에 흔들리지 않는 니치 유지
- 애드센스 광고는 이미 Blogger ↔ 애드센스 연동이 되어 있다면 **별도 코드 작업 없이** Blogger의 "수익" 탭 설정을 그대로 따릅니다

## 사용자가 이후에 할 일 (선택)

- 애드센스 대시보드에서 **사이트 연결**을 마무리하세요 (캡처에서 보이던 마지막 단계) — adsense.google.com → 사이트 → peterpb.blogspot.com 연결 확인
- **검색 유입 확보 (5분, 권장)**: Blogger 설정에서 Search Console 연결 + 사이트맵 제출 — 새 글이 검색에 뜨는 속도가 빨라집니다. 자세한 절차: [blogger/SETUP.md의 D 섹션](../blogger/SETUP.md#d-트래픽-확보-검색-유입-극대화-5분--지속-자동)
- 가끔 발행된 글을 훑어보며 품질 확인 (애드센스 정책 준수에 도움)

## 수익 극대화 (트래픽 × RPM)

애드센스 수익은 결국 **트래픽 × RPM**입니다. 이 프로젝트가 두 축에서 자동으로 하고 있는 것:

- **RPM 쪽**: 품질 게이트(발행 전 이중 검증)로 얇은/획일적 콘텐츠를 걸러내 애드센스 콘텐츠 정책 위반으로 인한 계정 리스크를 낮춥니다.
- **트래픽 쪽 (발행 시 전부 자동)**:
  - **양방향 내부 링크** — 새 글에 같은 필러 기존 글로 가는 "Keep reading" 링크가 붙고, 발행 시 **기존 글들의 링크 블록도 갱신**되어 새 글을 가리킵니다. 세션당 페이지뷰(=광고 노출)와 토픽 권위 신호가 함께 올라갑니다.
  - **구조화 데이터(JSON-LD)** — 글마다 Article + FAQ 스키마를 삽입해 구글 검색에서 리치 결과(질문 펼침 등) 노출 자격을 얻습니다. 같은 순위라도 클릭률이 높아집니다.
  - **이미지 alt 텍스트** — 일러스트에 묘사형 alt를 자동 부여(이미지 검색 유입 + 품질 신호).
  - **계절 인식 발행** — 계절성 주제(`season_months`)는 검색 수요가 뛰기 4주+ 전에 우선 발행되고, 철 지난 주제는 대기합니다.
  - **검색 스니펫 첫 문단** — 글 도입 1~2문장이 검색 결과 설명문 역할을 하도록 생성 규칙에 포함. (Blogger의 meta description API 필드는 반영이 불안정해 의도적으로 쓰지 않습니다.)
- **Pinterest 게시**: 글마다 세로형 핀 이미지(1000×1500)를 자동 생성합니다. 검색 색인이 아직 안 잡힌 신규 사이트가 실제 방문자와 외부 링크를 확보하는 가장 빠른 경로입니다. 설정: **[docs/PINTEREST_SETUP.md](PINTEREST_SETUP.md)**
  - ⚠️ **API 자동 게시는 아직 꺼져 있습니다** — 개발자 앱이 Pinterest의 trial access 승인 대기 중(2026-09 기준 2개월째)이고, 승인 전에는 App secret이 안 나와 OAuth 자체가 불가능합니다. 대신 **`generator/make_bulk_csv.py`로 벌크 업로드 CSV를 만들어 올립니다** — Pinterest 비즈니스 계정의 "콘텐츠 가져오기"는 한 번에 최대 200핀을 받고 API 권한이 필요 없습니다. 2026-09-01에 첫 4핀으로 검증 완료. 올린 뒤에는 `pinterest_publish.py --mark-pinned`로 기록해야 승인 후 중복 게시를 막습니다.
- **모니터링 루프**: 매주 월요일 조회수 스냅샷 수집 → 전주 대비 리포트 커밋 → **카카오톡 요약 전송**. 설정: **[docs/KAKAO_REPORT.md](KAKAO_REPORT.md)**
- 사람이 할 일은 "검색 유입 확보"(위), 카카오톡 연결, 그리고 Pinterest 승인이 날 때까지의 수동 핀 게시입니다.

---

## 문제 해결

| 증상 | 해결 |
|---|---|
| Actions "Generate new post" 단계 실패 | `ANTHROPIC_API_KEY` 시크릿 확인, 콘솔 크레딧 잔액 확인 |
| Actions "Publish to Blogger" 단계 실패 (401/403) | `GOOGLE_REFRESH_TOKEN` 등이 정확한지 확인. `generator/blogger_auth.py`를 다시 실행해 새 토큰 발급 |
| `get_access_token` 단계에서 `400 Client Error` (`oauth2.googleapis.com/token`) | OAuth 동의 화면이 "테스트" 상태면 refresh token이 7일 뒤 자동 만료됩니다. `blogger/SETUP.md`의 B-5 참고 — Google Cloud Console에서 앱을 "게시(Publish)"하면 재발 방지, 아니면 `blogger_auth.py`로 토큰을 재발급해 `GOOGLE_REFRESH_TOKEN` 시크릿을 갱신하세요. 이미 생성된 글은 리포에 남아 있으니 재인증 후 다음 실행에서 자동으로 발행됩니다 |
| 이미지가 블로그에서 깨져 보임 | raw.githubusercontent.com 반영에 수십 초~수 분 지연이 있을 수 있음. 잠시 후 새로고침 |
| 디자인이 하나도 안 바뀜 | `blogger/custom-css.css`를 정확히 Customize → Advanced → Add CSS에 붙여넣었는지, 저장을 눌렀는지 확인 |
| 광고가 하나도 안 보임 | 애드센스 승인 여부와 Blogger "수익" 탭에서 광고가 켜져 있는지 확인 |

## 애드센스 "가치가 별로 없는 콘텐츠" 탈락 대응 (2026-07-17)

1차 심사에서 "Low value content"로 탈락했다. 원인 분석과 조치:

| 격차 | 조치 | 상태 |
|---|---|---|
| About/Contact/Privacy/Terms 페이지가 라이브에 없었음 | `generator/blogger_pages.py` + "Publish Static Pages" 워크플로우로 게시 | 자동화됨 |
| Contact의 플레이스홀더 이메일(`@example`) | 댓글 기반 연락 안내로 교체 | 완료 |
| 글 12편·운영 2주 (볼륨/연령 부족) | 발행 주기 주3회→주5회(월~금)로 한시 상향, 30편 도달까지 | 진행 중 |
| 페이지가 내비게이션에 노출 안 됨 | Blogger → 레이아웃 → **"페이지(Pages)" 가젯** 추가 (수동 1회) | 사용자 작업 |

**재검토 요청 (2026-09-01 제출 완료)**: 아래 조건이 모두 갖춰진 것을 확인한 뒤 요청했다.
같은 상태로 재심사하면 다시 탈락하고 심사 주기(1~2주)만 소모되므로, 조건 미충족 상태에서
누르지 않는 것이 핵심이었다.

- [x] 발행 글 25~30편 이상 — 제출 시점 43편
- [x] 4개 정적 페이지 라이브 + 내비게이션 노출 — 페이지 게시는 "Publish Static Pages"
      (2026-07-19), 페이지 가젯은 상단 "페이지 목록" + 사이드바 양쪽에 추가
- [x] Search Console 색인 시작 — **40페이지 색인 완료** (8월 초부터 상승, 그 전에는 전량
      `검색됨 - 현재 색인이 생성되지 않음`이었다)
- [x] 애드센스 사이트 연결 확인 — 홈 화면이 "모든 단계를 완료했습니다" 상태
- [x] 애드센스 → 사이트 → "문제를 수정했음을 확인합니다" 체크 → 검토 요청

**심사 중 주의**: 결과는 보통 1~2주 걸린다. 그동안 사이트 구조를 크게 바꾸거나 글을 대량
삭제하지 말 것 — 심사 중 상태가 흔들리면 불리하다. 발행은 평소대로 계속하면 된다.

> 참고: Search Console의 "색인이 생성되지 않은 페이지"가 42개로 잡히는데, Blogger는
> 라벨·아카이브·페이지네이션 URL을 대량으로 만들고 구글이 그걸 의도적으로 색인하지
> 않는다. 글 본문이 색인되고 있으면 정상이므로 이 숫자 자체는 문제가 아니다.

## 커스텀 도메인 전환 — hearth-habit.com (2026-09-11)

### 왜 바꿨나

거절 이력이 위 표보다 훨씬 많다. AdSense 메일 기준 **"가치가 별로 없는 콘텐츠" 거절 5회**:
07-16, 07-30, 08-05, 08-19, 09-11. 즉 2주 간격으로 재심사를 눌렀고 그 사이 사이트는 거의
그대로였다. 글 51편·2,000단어급·정적 페이지·색인은 이미 통과 수준이라 콘텐츠를 더 쌓는
건 답이 아니다. 남은 변수는 (1) blogspot 서브도메인 자체의 낮은 신뢰, (2) 30일 조회 88의
트래픽 부재, (3) 반복 제출 이력. 커스텀 도메인은 애드센스에 **새 사이트**로 등록되어
(3)을 끊고 (1)을 없앤다. 리포 쪽은 이미 반영됐다:

- `config/site.yml`: `blog_url` → `https://www.hearth-habit.com`, `blog_id` 고정
- `config/topics.yml`: 49개 `blogger_url` 을 새 도메인으로 치환 (경로는 Blogger가 그대로 유지)
- `generator/blogger_publish.py --relink-all` + 워크플로우 **Relink Posts to Current Domain**:
  라이브 글 전체의 "Keep reading"/허브 링크를 새 도메인으로 재작성

### 사용자가 할 일 (순서대로)

**1. DNS (도메인 등록업체 관리 화면)**

| 타입 | 호스트 | 값 |
|---|---|---|
| CNAME | `www` | `ghs.google.com` |
| CNAME | *(Blogger가 알려주는 고유 문자열)* | *(Blogger가 알려주는 `gv-....dv.googlehosted.com`)* |
| A | `@` | `216.239.32.21` |
| A | `@` | `216.239.34.21` |
| A | `@` | `216.239.36.21` |
| A | `@` | `216.239.38.21` |

두 번째 CNAME 값은 아래 2번에서 Blogger가 "설정을 확인할 수 없습니다" 오류와 함께
보여준다. 그걸 복사해서 넣고 다시 저장하면 통과된다. Cloudflare를 쓴다면 프록시(주황
구름)는 **끄고** DNS only 로 둔다 — 켜두면 Blogger 인증서 발급이 실패한다.

**2. Blogger → 설정 → 게시 → 맞춤 도메인**
- `www.hearth-habit.com` 입력 → 저장 (오류 메시지에서 CNAME 값 복사 → 1번에 추가 → 재저장)
- **도메인 리디렉션** 켜기 (hearth-habit.com → www)
- **HTTPS 사용 가능**·**HTTPS 리디렉션** 둘 다 켜기 (인증서 발급에 수 분~수 시간)
- 확인: `https://www.hearth-habit.com` 과 `https://hearth-habit.com` 둘 다 블로그가 뜨고,
  `https://peterpb.blogspot.com/2026/09/...` 글 주소가 새 도메인의 같은 경로로 넘어가면 완료

**3. 같은 화면에서 신뢰 신호 정리 (5분)**
- 설정 → 기본 → **언어: English (United States)** — 현재 "홈" 등 한국어 UI 문자열이 영어
  미국 타겟 블로그에 섞여 노출됨
- 설정 → 사용자 프로필 → 표시 이름 `PeterPyGrowth` → **Hearth & Habit Editorial**, 소개는 영어 한 줄
- 설정 → 수익 → **맞춤 ads.txt 사용** 켜고 아래 한 줄 저장 (현재 `/ads.txt` 가 200이지만 빈 파일):
  ```
  google.com, pub-8417752841954578, DIRECT, f08c47fec0942fa0
  ```
- 레이아웃 → 가젯 추가 → **연락처 양식**을 사이드바에 추가 (댓글 기반 연락처 보완)

**4. GitHub Actions (도메인이 실제로 열린 뒤)**
- **Relink Posts to Current Domain** 워크플로우 1회 실행 → 글 안 내부 링크가 새 도메인 직결
- **Publish Static Pages** 워크플로우 1회 실행 → About/Contact/Privacy/Terms 의 상호 링크가
  새 도메인 페이지 URL로 재작성됨 (Blogger API가 돌려주는 URL을 그대로 쓰므로 자동)

**5. Search Console**
- 새 속성 추가: **도메인** 유형으로 `hearth-habit.com` (DNS TXT 인증 — 1번 화면에 TXT 1개 추가)
- 사이트맵 제출: `https://www.hearth-habit.com/sitemap.xml`
- 기존 `peterpb.blogspot.com` 속성은 삭제하지 말고 **설정 → 주소 변경** 으로 새 속성에 연결
  (색인 신호 승계)
- Bing 웹마스터 도구에도 같은 사이트맵 등록 (Search Console 가져오기 기능으로 1분)

**6. 애드센스**
- 사이트 → **새 사이트** → `hearth-habit.com` 추가. 기존 `peterpb.blogspot.com` 항목은 그대로 둔다
  (삭제해도 이득 없음, 리다이렉트 대상이므로 유지)
- Blogger → 수익 탭에서 애드센스 연결이 새 도메인으로 잡혀 있는지 확인
- **검토 요청은 아직 누르지 않는다.** 조건(아래)이 모두 갖춰지면 1회만 누른다

### 재심사 게이트 (셋 다 충족 전엔 제출 금지)

- [ ] Search Console 새 속성에서 **색인 30페이지 이상** (도메인 전환 후 보통 2~4주)
- [ ] Search Console 실적에서 **자연 클릭이 0이 아닌 날이 연속** 기록됨
- [ ] 위 3번 신뢰 신호 정리 + 4번 워크플로우 2개 실행 완료

거절되면 **최소 30일** 뒤에 재제출. 2주 간격 반복은 다시 하지 않는다.

### 그동안 콘텐츠 쪽 (2단계, 별도 작업)

- 발행 주기 주5회 → 주2회로 하향 (`generate-and-publish.yml` cron). 양은 충분하고 더 쌓는 건
  "scaled content" 신호가 된다
- 근접 중복 쌍 통합 후 Blogger 맞춤 리디렉션: furnace filter 2편, running toilet 2편,
  caulk 2편, 온도조절기/환기구 3편
- 필러당 코너스톤 가이드 1편(2,500단어+, 원본 표 포함) 추가

## 정책 참고 사항 (중요)

- Google은 AI 생성 자체를 금지하지 않지만, 대량 저품질 콘텐츠는 스팸으로 판단합니다. 이 프로젝트는 고정 니치 + 편집 규칙(통계 날조 금지 등) + 절제된 발행 빈도(주 3회)로 설계되어 있지만, 발행물을 주기적으로 훑어보는 최소한의 품질 관리를 권장합니다.
- 무효 클릭(본인 광고 클릭 포함)은 애드센스 계정 정지 사유입니다.

## 참고: 예전 GitHub Pages 방식은 왜 없어졌나

이 프로젝트는 원래 커스텀 도메인 + GitHub Pages 정적 사이트로 설계됐었습니다 (`generator/build_site.py`, `templates/`, `static/`는 그 흔적으로 남아 있고, 지금은 로컬 미리보기 용도로만 쓸 수 있습니다 — `python generator/build_site.py` 후 `_site/index.html`을 열면 됩니다). 사용자가 이미 애드센스 연동이 진행 중인 Blogger 블로그를 보유하고 있다는 걸 확인한 뒤, 도메인 구매·DNS·소유권 인증 없이 곧바로 수익화를 시작할 수 있는 Blogger 경로로 전환했습니다.
