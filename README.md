# Hearth & Habit 🏠

**북미 시장 타겟 Google AdSense 수익형 자동 블로그** — Claude가 글과 일러스트를 생성하고, GitHub Actions가 상시 가동하며, [peterpb.blogspot.com](https://peterpb.blogspot.com)(Blogger, 기존 애드센스 연동 계정)에 자동 게시합니다.

> 니치: **Home & Practical Living** (주택 관리 · 청소/정리 · 에너지 절약 · 주방 습관 · 마당 관리)
> 애드센스 RPM이 높은 evergreen 분야이며, 고정된 5개 필러(pillar) 구조로 주제 드리프트를 원천 차단합니다.

## 작동 방식

```
매주 월/수/금 (GitHub Actions cron)
  └─> Claude가 주제 큐에서 다음 글 작성 (글 + SVG 일러스트 1~2장)
       └─> content/에 커밋·푸시 (이미지는 raw.githubusercontent.com 로 서빙)
            └─> Blogger API v3로 peterpb.blogspot.com에 자동 게시
                 └─> 이미 연동된 AdSense 계정이 광고 게재
```

- **주제 큐** (`config/topics.yml`): 5개 필러 안의 evergreen 주제 40여 개가 미리 큐잉되어 있고, 큐가 부족해지면 Claude가 **필러 범위 안에서만** 자동 보충합니다. 트렌드 API를 쓰지 않으므로 주제가 중구난방으로 흔들리지 않습니다.
- **디자인**: 웜톤 에디토리얼 테마를 Blogger 커스텀 CSS(`blogger/custom-css.css`)로 적용. 게시물 히어로 이미지는 Claude가 그리는 플랫 스타일 SVG.
- **애드센스**: 도메인·ads.txt·스크립트 삽입이 전혀 필요 없습니다 — 이미 Blogger ↔ 애드센스가 연동되어 있어 Blogger의 "수익" 탭 설정을 그대로 따릅니다.

## 사용자가 해야 할 일 (전부 4단계, 이후는 완전 자동)

1. ~~새 리포지토리 생성~~ ✅ 완료 (`eretsbae/hearth-and-habit`)
2. **Anthropic API 키 등록** — Settings → Secrets → Actions → `ANTHROPIC_API_KEY`
3. **Blogger 연동** — 디자인 CSS 적용 + Google OAuth 1회 인증 ([blogger/SETUP.md](blogger/SETUP.md))
4. **Actions에서 수동 1회 실행** → 이후 매주 월/수/금 완전 자동

→ 자세한 단계별 안내: **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)**
→ 콘텐츠 전략과 드리프트 방지 설계: **[docs/CONTENT_STRATEGY.md](docs/CONTENT_STRATEGY.md)**
→ Blogger 연동 상세 가이드: **[blogger/SETUP.md](blogger/SETUP.md)**

## 로컬 테스트

```bash
pip install -r requirements.txt

# 생성 파이프라인 점검 (API 호출 없이 더미 글 생성)
python generator/generate_post.py --dry-run

# 실제 글 생성 (Claude API 호출)
ANTHROPIC_API_KEY=sk-ant-... python generator/generate_post.py

# 생성된 글 중 아직 Blogger에 안 올라간 것들을 실제로 게시
GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... GOOGLE_REFRESH_TOKEN=... \
  python generator/blogger_publish.py

# (선택/레거시) 정적 사이트로 로컬 미리보기만 하고 싶을 때
python generator/build_site.py   # _site/index.html 을 브라우저로 열기
```

## 프로젝트 구조

```
config/site.yml             사이트/Blogger/생성 설정 ([사용자 입력] 항목 참고)
config/topics.yml           고정 필러 + 주제 큐 (드리프트 방지의 핵심, blogger_url 기록됨)
generator/generate_post.py  Claude 글+SVG 생성 (content/에 저장)
generator/blogger_publish.py  Blogger API로 실제 게시
generator/blogger_auth.py   최초 1회 로컬 OAuth 인증 헬퍼
generator/build_site.py     (레거시) 정적 사이트 빌드 — 로컬 미리보기 전용
blogger/custom-css.css      Blogger 테마에 붙여넣는 디자인 CSS
blogger/SETUP.md            Blogger 연동 상세 가이드
content/posts/               생성된 글 (Markdown)
content/images/               생성된 SVG 일러스트 (Blogger 글의 이미지 소스)
content/pages/                About / Privacy / Terms / Contact (참고용, Blogger 페이지로는 별도 등록 필요시 사용)
.github/workflows/           자동 생성·발행 파이프라인
```

## 운영 비용

| 항목 | 비용 |
|---|---|
| 호스팅 (Blogger) | 무료 |
| 자동화 (GitHub Actions) | 무료 (public repo) |
| 이미지 호스팅 (GitHub raw) | 무료 |
| Claude API (주 3회 생성) | 대략 월 $1~5 수준 |
