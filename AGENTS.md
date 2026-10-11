# hearth-and-habit — 에이전트 지침

북미 타겟 Home & Practical Living 자동 블로그. Claude Code 세션이 글+SVG 를 쓰고 GitHub Actions 가 www.hearth-habit.com(Blogger) 에 자동 게시한다.

## 글 생성은 Claude Code 토큰으로 (2026-10-11 오너 지시)
- 정기 글은 오너 PC 예약 작업 `hearth_publish_mwf`(월/수/금 20:43 KST, `scripts/claude-publish.ps1`)가 headless `claude -p` 로 쓴다. 세션은 `generator/CLAUDE_RUN.md` 를 따르고 `generator/claude_post.py finalize` 로 main 에 커밋한다. `generate-and-publish.yml`(22:17 KST)은 **게시 전용**이고, 새 글이 없으면 실패해 ci-alerts 이슈가 뜬다.
- **Anthropic API 크레딧을 쓰는 경로는 쓰지 않는다**: `generate_post.py`, `enrich_post.py`, `enrich-posts.yml`, `quality-preview.yml`. 기존 글 보강·수정도 Claude Code 세션(하위 에이전트 + WebSearch/WebFetch)으로 하고 `python generator/check_post.py <slug>` 로 검사한다.
- 실행 로그: `logs/claude-publish/`(git 제외). 예약 등록·해제: `scripts/register-claude-publish.ps1 [-Unregister]`. 사람용 상세는 `README.md`, `docs/SETUP_GUIDE.md`, `docs/CONTENT_STRATEGY.md`, `blogger/SETUP.md` — 필요한 절만 grep 으로 읽는다.

## 원격이 정본
- 운영 커밋은 GitHub Actions 봇이 `main` 에 직접 올린다(글 생성·Pinterest·주간 리포트). **상태를 판단하기 전에 반드시 `git fetch origin` 후 `origin/main` 기준으로 본다.** 로컬 클론은 뒤처져 있는 것이 정상이다.
- `main` 에 쓰는 워크플로우는 `concurrency: repo-write` 그룹 하나를 공유하고 push 직전 rebase 한다. 이 규칙을 깨는 워크플로우를 추가하지 않는다(`config/topics.yml` 이 통째로 다시 쓰이므로 동시 실행 시 게시 기록이 유실되어 중복 게시된다).

## 하지 말 것
- 비밀값(`ANTHROPIC_API_KEY`, `GOOGLE_*`, Pinterest·Kakao 토큰)은 GitHub Secrets 와 로컬 `.secrets/`·`.env`·`generator/token.json` 에만. 코드·문서·커밋에 값을 쓰지 않는다.
- 워크플로우 cron·일정과 Blogger/AdSense 설정은 사용자가 명시적으로 승인한 경우에만 바꾼다. 발행은 주 3회(월/수/금)이고, 계속·중단은 `docs/SETUP_GUIDE.md` "중단 기준" 절의 숫자(2026-11-16·2027-01-18 점검)대로 판단한다 — 점검일에 기준을 재협상하지 않는다.
- 주제는 `config/topics.yml` 의 5개 필러 안에서만. 트렌드 API·외부 주제 소스를 붙이지 않는다(드리프트 방지가 설계 핵심).
- 글 속 수치·안전 기준(식품안전, 곰팡이 면적, 락스 혼합, 전기요금 단가 등)은 `config/facts.yml` 과 일치시킨다. 값을 바꾸면 그 값을 인용한 글도 같이 고친다.
- `content/` 의 게시된 글·이미지는 Blogger 가 raw URL 로 참조한다. 이름 변경·삭제는 `retire-posts.yml` 절차로만.
- 게시된 글(`content/posts`)을 고쳐 main 에 머지하면 `sync-posts.yml` 이 바뀐 글만 라이브에 PATCH 한다(Blogger 편집기 수정분은 덮어씀). 로컬 확인은 `python generator/blogger_publish.py --sync-content SLUG --dry-run`.

## 로컬 실행·검증
```
pip install -r requirements.txt
python generator/claude_post.py next                 # 다음 주제·각도·내부 링크 목록 (API 없음)
python generator/check_post.py <slug>                # 글 결정적 검사 (API 없음)
python generator/generate_post.py --dry-run          # (API 경로, 크레딧 소진으로 미사용) 파이프라인 점검
python generator/blogger_publish.py                  # 미게시 글 발행 (GOOGLE_* 필요)
python generator/build_site.py                       # (레거시) 정적 미리보기 _site/
```

## 구조
`config/site.yml` 사이트·생성 설정 · `config/topics.yml` 필러+주제 큐+게시 URL 기록 · `config/facts.yml` 사실 기준표(프롬프트·크리틱에 주입) · `generator/` 생성·발행·Pinterest·Kakao 스크립트(`prompts.py` 가 글 프롬프트, `research.py` 가 집필 전 웹 리서치, `enrich_post.py` 가 기존 글 재작성) · `data/research/` 글별 근거 문서 · `content/posts|images|pages` 산출물 · `blogger/custom-css.css` 테마 · `.github/workflows/` generate-and-publish · pinterest-publish · publish-pages · relink-posts · retire-posts · sync-posts · weekly-report · enrich-posts(기존 글 재작성 → PR) · quality-preview(커밋 없는 미리보기) · prune-branches(머지 끝난 브랜치 자동 삭제 — 수동 정리 불필요).

## 보고 원칙
- 결론 먼저, 근거는 경로·커밋 해시로. 도구의 성공 응답은 게시 성공의 증거가 아니다 — Blogger URL 또는 Actions 로그로 확인하고, 못 하면 "미검증".
- 관측과 해석을 분리한다.
