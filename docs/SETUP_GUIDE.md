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
- **모니터링 루프**: 매주 월요일 조회수 스냅샷 수집 → 전주 대비 리포트 커밋 → **카카오톡 요약 전송**. 설정: **[docs/KAKAO_REPORT.md](KAKAO_REPORT.md)**
- 사람이 할 일은 "검색 유입 확보"(위)와 카카오톡 연결, 두 개의 1회성 설정뿐입니다.

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

## 정책 참고 사항 (중요)

- Google은 AI 생성 자체를 금지하지 않지만, 대량 저품질 콘텐츠는 스팸으로 판단합니다. 이 프로젝트는 고정 니치 + 편집 규칙(통계 날조 금지 등) + 절제된 발행 빈도(주 3회)로 설계되어 있지만, 발행물을 주기적으로 훑어보는 최소한의 품질 관리를 권장합니다.
- 무효 클릭(본인 광고 클릭 포함)은 애드센스 계정 정지 사유입니다.

## 참고: 예전 GitHub Pages 방식은 왜 없어졌나

이 프로젝트는 원래 커스텀 도메인 + GitHub Pages 정적 사이트로 설계됐었습니다 (`generator/build_site.py`, `templates/`, `static/`는 그 흔적으로 남아 있고, 지금은 로컬 미리보기 용도로만 쓸 수 있습니다 — `python generator/build_site.py` 후 `_site/index.html`을 열면 됩니다). 사용자가 이미 애드센스 연동이 진행 중인 Blogger 블로그를 보유하고 있다는 걸 확인한 뒤, 도메인 구매·DNS·소유권 인증 없이 곧바로 수익화를 시작할 수 있는 Blogger 경로로 전환했습니다.
