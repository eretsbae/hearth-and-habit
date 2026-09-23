# hearth-and-habit — 에이전트 지침

북미 타겟 Home & Practical Living 자동 블로그. Claude 가 글+SVG 를 생성하고 GitHub Actions 가 www.hearth-habit.com(Blogger) 에 자동 게시한다. 사람용 상세는 `README.md`, `docs/SETUP_GUIDE.md`, `docs/CONTENT_STRATEGY.md`, `blogger/SETUP.md` — 필요한 절만 grep 으로 읽는다.

## 원격이 정본
- 운영 커밋은 GitHub Actions 봇이 `main` 에 직접 올린다(글 생성·Pinterest·주간 리포트). **상태를 판단하기 전에 반드시 `git fetch origin` 후 `origin/main` 기준으로 본다.** 로컬 클론은 뒤처져 있는 것이 정상이다.
- `main` 에 쓰는 워크플로우는 `concurrency: repo-write` 그룹 하나를 공유하고 push 직전 rebase 한다. 이 규칙을 깨는 워크플로우를 추가하지 않는다(`config/topics.yml` 이 통째로 다시 쓰이므로 동시 실행 시 게시 기록이 유실되어 중복 게시된다).

## 하지 말 것
- 비밀값(`ANTHROPIC_API_KEY`, `GOOGLE_*`, Pinterest·Kakao 토큰)은 GitHub Secrets 와 로컬 `.secrets/`·`.env`·`generator/token.json` 에만. 코드·문서·커밋에 값을 쓰지 않는다.
- 워크플로우 cron·일정과 Blogger/AdSense 설정은 사용자가 명시적으로 승인한 경우에만 바꾼다. 생성 편수 상향은 `generate-and-publish.yml` 주석의 조건(30편 도달·애드센스 승인)을 따른다.
- 주제는 `config/topics.yml` 의 5개 필러 안에서만. 트렌드 API·외부 주제 소스를 붙이지 않는다(드리프트 방지가 설계 핵심).
- `content/` 의 게시된 글·이미지는 Blogger 가 raw URL 로 참조한다. 이름 변경·삭제는 `retire-posts.yml` 절차로만.

## 로컬 실행·검증
```
pip install -r requirements.txt
python generator/generate_post.py --dry-run          # API 호출 없이 파이프라인 점검
python generator/generate_post.py                    # 실제 생성 (ANTHROPIC_API_KEY 필요)
python generator/blogger_publish.py                  # 미게시 글 발행 (GOOGLE_* 필요)
python generator/build_site.py                       # (레거시) 정적 미리보기 _site/
```

## 구조
`config/site.yml` 사이트·생성 설정 · `config/topics.yml` 필러+주제 큐+게시 URL 기록 · `generator/` 생성·발행·Pinterest·Kakao 스크립트(`prompts.py` 가 글 프롬프트) · `content/posts|images|pages` 산출물 · `blogger/custom-css.css` 테마 · `.github/workflows/` generate-and-publish · pinterest-publish · publish-pages · relink-posts · retire-posts · weekly-report.

## 보고 원칙
- 결론 먼저, 근거는 경로·커밋 해시로. 도구의 성공 응답은 게시 성공의 증거가 아니다 — Blogger URL 또는 Actions 로그로 확인하고, 못 하면 "미검증".
- 관측과 해석을 분리한다.
