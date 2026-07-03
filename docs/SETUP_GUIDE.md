# 셋업 가이드 (처음부터 끝까지)

이 문서만 따라 하면 됩니다. **사용자가 직접 해야 하는 일은 계정/결제가 필요한 부분뿐**이고, 나머지는 전부 자동입니다. 총 소요 시간: 약 30~40분 (+ 애드센스 승인 대기 수일~수주).

---

## 1단계. 새 리포지토리로 이전 (5분)

GitHub 앱 권한 제한으로 리포 생성 자체는 사용자가 클릭해야 합니다.

1. https://github.com/new 접속
2. Repository name: `hearth-and-habit`
3. **Public** 선택 (GitHub Pages 무료 호스팅 조건), **README 추가 체크 해제** (빈 리포여야 함)
4. Create repository 클릭
5. 로컬 터미널에서 이 폴더로 이동 후:

```bash
bash scripts/migrate_to_new_repo.sh https://github.com/<내계정>/hearth-and-habit.git
```

## 2단계. GitHub Pages + API 키 설정 (5분)

새 리포지토리에서:

1. **Settings → Pages** → "Build and deployment" → Source를 **GitHub Actions**로 변경
2. **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `ANTHROPIC_API_KEY`
   - Value: https://console.anthropic.com 에서 발급한 API 키 (`sk-ant-...`)
3. **Actions 탭** → 왼쪽 "Deploy Site" → **Run workflow** 클릭

몇 분 뒤 `https://<내계정>.github.io/hearth-and-habit` 에서 시드 글 3개가 올라간 블로그가 열립니다.

> 이 시점부터 자동화는 이미 돌아갑니다: 매주 월/수/금 Claude가 새 글을 쓰고 배포합니다.
> `config/site.yml`의 `fallback_url`을 실제 Pages 주소로 수정해 두세요.

## 3단계. 커스텀 도메인 연결 (15분 + DNS 전파 대기)

**왜 필요한가:** AdSense는 `*.github.io` 같은 서브도메인 사이트를 신규 등록할 수 없습니다. 본인 소유 도메인이 사실상 필수입니다 (연 $10 내외).

1. 도메인 구매: [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/) (원가 판매, 추천) 또는 Namecheap, Porkbun
   - 추천 도메인 예시: `hearthandhabit.com` 또는 유사한 .com
2. DNS 설정 (구매처의 DNS 관리 화면에서):
   - `A` 레코드 4개 — 호스트 `@`, 값:
     `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `CNAME` 레코드 — 호스트 `www`, 값 `<내계정>.github.io`
3. GitHub 리포 → **Settings → Pages → Custom domain**에 도메인 입력, 확인 후 **Enforce HTTPS** 체크
4. `config/site.yml`의 `custom_domain`에 도메인 입력 (예: `hearthandhabit.com`) 후 커밋/푸시
   → 빌드 시 `CNAME` 파일이 자동 생성되고 모든 URL이 새 도메인 기준으로 바뀝니다.

## 4단계. Google Search Console 등록 (10분)

애드센스 승인과 검색 유입 모두에 중요합니다.

1. https://search.google.com/search-console 접속 → 속성 추가 → 도메인 또는 URL 접두어
2. HTML 태그 인증을 선택했다면 `content="..."` 값을 복사해서
   `config/site.yml`의 `google_site_verification`에 붙여넣고 커밋/푸시 → 재배포 후 인증 확인
3. 인증 후 **Sitemaps** 메뉴에 `sitemap.xml` 제출 (자동 생성되어 있음)

## 5단계. Google AdSense 신청 및 연결 (10분 + 심사 대기)

**신청 타이밍:** 글이 15~20개 이상 쌓인 뒤 신청하는 것이 승인률이 높습니다. 주 3회 자동 발행 기준 약 4~6주 후입니다. 필수 페이지(About, Privacy Policy, Terms, Contact)는 이미 포함되어 있습니다.

1. https://adsense.google.com 접속 → 구글 계정으로 가입 → 사이트에 본인 도메인 입력
2. AdSense가 주는 확인 코드는 **이미 자동 처리됩니다**: `config/site.yml`의 `adsense.publisher_id`에 `ca-pub-XXXXXXXXXXXXXXXX`를 입력하고 커밋/푸시하면, 모든 페이지 head에 AdSense 스크립트가 삽입되고 `ads.txt`도 자동 생성됩니다. AdSense 화면에서 "코드가 설치되었는지 확인"을 누르세요.
3. 심사 통과 후 AdSense 대시보드에서 **자동 광고(Auto ads)를 켜세요** — 별도 코드 수정 없이 광고가 게재됩니다.
4. 수익 지급을 위해 AdSense에 주소 인증(PIN 우편), 세금 정보(W-8BEN, 한국 거주자), 은행 계좌를 등록하세요.

## 끝. 이후에 사용자가 할 일

**없습니다.** 시스템이 알아서:
- 월/수/금 새 글 작성 + 일러스트 생성 + 배포
- 주제 큐가 5개 미만이 되면 필러 범위 안에서 자동 보충
- sitemap/RSS/ads.txt 갱신

가끔 해주면 좋은 것 (선택):
- 월 1회 Search Console에서 유입 키워드 확인
- 발행된 글을 훑어보고 어색한 부분 수정 (품질 관리는 승인 유지에 도움됨)
- 발행 빈도 조절: `.github/workflows/generate-and-publish.yml`의 `cron` 수정

---

## 문제 해결

| 증상 | 해결 |
|---|---|
| Actions에서 생성 실패 | Secrets에 `ANTHROPIC_API_KEY`가 정확한지, 콘솔 크레딧 잔액 확인 |
| 사이트가 안 열림 | Settings → Pages Source가 "GitHub Actions"인지 확인 |
| 도메인 연결 안 됨 | DNS 전파는 최대 24~48시간 소요. `dig <도메인>`으로 A 레코드 확인 |
| 광고가 안 나옴 | 승인 완료 여부 + AdSense 대시보드에서 자동 광고 ON 확인. 승인 직후엔 수 시간 걸릴 수 있음 |

## 알아두어야 할 정책 사항 (중요)

- Google은 **AI 생성 자체를 금지하지 않지만**, "검색 순위 조작만을 목적으로 한 대량 생산 콘텐츠"는 스팸으로 봅니다. 이 프로젝트는 (1) 고정 니치, (2) 실용적 정확성 위주의 편집 규칙, (3) 적당한 발행 빈도(주 3회)로 설계되어 있지만, **발행물을 주기적으로 훑어보며 품질을 관리하는 것이 승인과 수익 유지에 실질적으로 중요합니다.**
- 애드센스 승인 전 최소 요건: 충분한 콘텐츠(통상 15개+ 글), 필수 페이지, 본인 소유 도메인, 만 18세 이상.
- 무효 클릭(본인 클릭 포함)은 계정 정지 사유입니다. 본인 사이트 광고를 클릭하지 마세요.
