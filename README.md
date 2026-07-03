# Hearth & Habit 🏠

**북미 시장 타겟 Google AdSense 수익형 자동 블로그** — Claude가 글과 일러스트를 생성하고, GitHub Actions가 상시 가동하며, GitHub Pages가 무료로 호스팅합니다.

> 니치: **Home & Practical Living** (주택 관리 · 청소/정리 · 에너지 절약 · 주방 습관 · 마당 관리)
> 애드센스 RPM이 높은 evergreen 분야이며, 고정된 5개 필러(pillar) 구조로 주제 드리프트를 원천 차단합니다.

## 작동 방식

```
매주 월/수/금 (GitHub Actions cron)
  └─> Claude가 주제 큐에서 다음 글 작성 (글 + SVG 일러스트 1~2장)
       └─> content/에 커밋
            └─> 정적 사이트 빌드 (Python + Jinja2)
                 └─> GitHub Pages 자동 배포
                      └─> AdSense 자동 광고 게재
```

- **주제 큐** (`config/topics.yml`): 5개 필러 안의 evergreen 주제 40여 개가 미리 큐잉되어 있고, 큐가 부족해지면 Claude가 **필러 범위 안에서만** 자동 보충합니다. 트렌드 API를 쓰지 않으므로 주제가 중구난방으로 흔들리지 않습니다.
- **디자인**: 웜톤 에디토리얼 테마 (라이트/다크 자동 지원). 게시물 히어로 이미지는 Claude가 그리는 플랫 스타일 SVG.
- **애드센스**: `config/site.yml`에 게시자 ID만 넣으면 head 스크립트 + `ads.txt`가 자동 삽입됩니다.

## 사용자가 해야 할 일 (전부 5단계, 이후는 완전 자동)

1. **새 리포지토리 생성 후 이 폴더를 이전** — `bash scripts/migrate_to_new_repo.sh <새 리포 URL>`
2. **GitHub Pages 켜기** — Settings → Pages → Source: *GitHub Actions*
3. **Anthropic API 키 등록** — Settings → Secrets → Actions → `ANTHROPIC_API_KEY`
4. **도메인 구매 & 연결** (애드센스 승인에 사실상 필수, 연 $10 내외)
5. **애드센스 가입/승인 후** `config/site.yml`에 게시자 ID 입력

→ 자세한 단계별 안내: **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)**
→ 콘텐츠 전략과 드리프트 방지 설계: **[docs/CONTENT_STRATEGY.md](docs/CONTENT_STRATEGY.md)**

## 로컬 테스트

```bash
pip install -r requirements.txt

# 사이트 빌드 (API 불필요)
python generator/build_site.py
# → _site/index.html 을 브라우저로 열기

# 생성 파이프라인 점검 (API 호출 없이 더미 글 생성)
python generator/generate_post.py --dry-run

# 실제 글 1개 생성
ANTHROPIC_API_KEY=sk-ant-... python generator/generate_post.py
```

## 프로젝트 구조

```
config/site.yml          사이트/애드센스/생성 설정 ([사용자 입력] 항목 참고)
config/topics.yml        고정 필러 + 주제 큐 (드리프트 방지의 핵심)
generator/generate_post.py  Claude 글+SVG 생성
generator/build_site.py     정적 사이트 빌드
templates/, static/      블로그 디자인 (Jinja2 + CSS)
content/posts/           생성된 글 (Markdown)
content/images/          생성된 SVG 일러스트
content/pages/           About / Privacy / Terms / Contact (애드센스 필수 페이지)
.github/workflows/       자동 생성·배포 파이프라인
```

## 운영 비용

| 항목 | 비용 |
|---|---|
| 호스팅 (GitHub Pages) | 무료 |
| 자동화 (GitHub Actions) | 무료 (public repo) |
| 도메인 | ~$10/년 |
| Claude API (주 3회 생성) | 대략 월 $1~3 수준 |
