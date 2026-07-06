# Blogger 연동 셋업 (peterpb.blogspot.com)

이 문서는 `docs/SETUP_GUIDE.md`의 3단계에서 참조하는 상세 가이드입니다.

## A. 테마 디자인 적용 (5분)

1. Blogger 관리 화면(blogger.com) 접속 → 좌측 메뉴 **테마(Theme)**
2. 상단의 **테마 갈아입히기** 또는 테마 갤러리에서 **Soho**(또는 다른 미니멀/반응형 테마) 선택 → 적용
   - Soho를 권장하는 이유: 넓은 여백, 단순한 그리드 구조라 커스텀 CSS가 깨질 확률이 낮습니다.
3. **맞춤설정(Customize)** 클릭 → 왼쪽 메뉴 **고급(Advanced)** → 스크롤 맨 아래 **CSS 추가**
4. 이 폴더의 `custom-css.css` 파일 전체 내용을 복사해서 붙여넣고 **저장**
5. 블로그 주소(peterpb.blogspot.com)를 열어 반영 확인. 색상/폰트가 웜톤 에디토리얼 스타일로 바뀌어 있으면 성공입니다.

문제가 생기면 Customize 화면에서 CSS 박스를 비우고 저장하면 즉시 원상 복구됩니다 (테마 자체는 건드리지 않으므로 안전합니다).

## B. Blogger API 자동 발행 인증 (10~15분, 최초 1회만)

자동화 워크플로우가 여러분 대신 글을 올리려면, 여러분의 Google 계정이 "이 앱이 내 Blogger에 글을 올려도 좋다"고 1회 승인해야 합니다. 이후로는 완전 자동입니다.

### B-1. Google Cloud 프로젝트 생성 + API 활성화

1. https://console.cloud.google.com 접속 (Blogger와 같은 구글 계정으로 로그인)
2. 상단 프로젝트 선택 → **새 프로젝트** → 이름 아무거나 (예: `hearth-habit-automation`) → 만들기
3. 좌측 메뉴 **API 및 서비스 → 라이브러리** → "Blogger API v3" 검색 → **사용 설정**

### B-2. OAuth 동의 화면 + 클라이언트 ID 발급

1. **API 및 서비스 → OAuth 동의 화면**
   - User Type: **외부(External)** 선택 → 만들기
   - 앱 이름: 아무거나 (예: `Hearth Habit Publisher`), 사용자 지원 이메일/개발자 연락처: 본인 이메일
   - 범위(Scopes) 단계는 건너뛰어도 됩니다
   - **테스트 사용자**에 본인 구글 계정 이메일 추가 (필수 — 안 하면 로그인 시 차단됨)
2. **API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID**
   - 애플리케이션 유형: **데스크톱 앱**
   - 이름: 아무거나 → 만들기
3. 생성된 클라이언트의 **JSON 다운로드** 클릭

### B-3. 로컬에서 1회 인증 실행

다운로드한 JSON 파일을 리포지토리를 클론한 본인 컴퓨터의 `generator/client_secret.json` 경로에 저장한 뒤:

```bash
cd hearth-and-habit
pip install -r requirements.txt
python generator/blogger_auth.py
```

브라우저가 열리며 구글 로그인 화면이 나옵니다. Blogger를 소유한 계정으로 로그인하고 권한을 승인하세요. ("Google에서 앱을 확인하지 않았습니다" 경고가 나오면 **고급 → (앱 이름)으로 이동(안전하지 않음)** 클릭 — 본인이 만든 앱이라 안전합니다.)

완료되면 터미널에 아래 3줄이 출력됩니다:

```
GOOGLE_CLIENT_ID     = ...
GOOGLE_CLIENT_SECRET = ...
GOOGLE_REFRESH_TOKEN = ...
```

### B-4. GitHub 시크릿 등록

리포지토리 → **Settings → Secrets and variables → Actions → New repository secret** 에서 위 3개를 각각 등록하세요:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

(`ANTHROPIC_API_KEY`도 등록되어 있어야 합니다 — `docs/SETUP_GUIDE.md` 2단계 참고)

`generator/client_secret.json`은 `.gitignore`에 등록되어 있어 실수로 커밋되지 않습니다. 인증이 끝났다면 로컬에서 삭제해도 무방합니다.

## C. 동작 확인

**Actions 탭 → "Generate & Publish Post" → Run workflow** 로 수동 실행해 보세요. 성공하면:
1. 새 글이 `content/posts/`에 커밋되고
2. 기존에 준비된 시드 글 3편 + 새 글이 한꺼번에 peterpb.blogspot.com에 발행되고 (최초 1회는 미발행 상태였던 글이 모두 올라갑니다)
3. `config/topics.yml`의 각 항목에 `blogger_url`이 기록됩니다

블로그 주소에서 바로 확인 가능합니다.

## D. 트래픽 확보 (검색 유입 극대화, 5분 + 지속 자동)

애드센스 수익 = 트래픽 × RPM 이라, 글 품질 다음으로 중요한 건 검색 유입입니다. Blogger의
`customMetaData`(검색 설명) API 필드는 커뮤니티에서 반영이 안 된다는 보고가 많아 신뢰할 수 없는
것으로 확인되어, 이 프로젝트는 대신 아래처럼 **직접 통제 가능한 부분**에 집중합니다.

### D-1. 자동으로 이미 되는 것 (코드 레벨)

- **내부 링크(관련 글)**: `generator/blogger_publish.py`가 발행할 때마다 같은 필러(카테고리)의
  기존 발행 글 링크를 본문 하단에 자동으로 붙입니다 ("Keep reading"). 방문자가 한 번에 여러
  페이지를 보게 되어 세션당 광고 노출이 늘고, 같은 주제를 서로 링크하는 사이트는 구글이 그
  분야의 "토픽 권위"를 더 쳐줍니다.
- **필러 허브 링크**: 각 글 하단에 Blogger가 라벨(label)마다 자동으로 만들어주는 아카이브 페이지
  (`/search/label/<필러 이름>`)로 가는 링크도 함께 붙습니다 — 별도 페이지 제작 없이 카테고리
  허브 역할을 합니다.
- **자동 sitemap**: Blogger 블로그는 별도 설정 없이 `/sitemap.xml`을 자동 생성합니다.

### D-2. 최초 1회만 사람이 할 일 (5분)

1. Blogger 관리 화면 → **설정(Settings) → 크롤링 및 색인 생성(Crawling and indexing)**
   - "커스텀 robots.txt 사용"은 켤 필요 없음(기본값으로 충분)
   - **Search Console** 항목에서 "지금 연결(Connect now)" 클릭 → Google Search Console에
     `peterpb.blogspot.com`이 URL 접두어 속성으로 자동 등록됩니다 (도메인 소유권 인증 불필요,
     Blogger 소유 계정으로 로그인만 하면 됨)
2. Search Console에 등록되면 사이트맵(`sitemap.xml`)을 제출해 새 글이 더 빨리 색인됩니다 —
   Search Console → **Sitemaps** → `sitemap.xml` 입력 후 제출 (한 번만 하면 이후 새 글은 자동
   포함됩니다)
3. (선택) 몇 주 후 Search Console **실적(Performance)** 탭에서 어떤 필러가 검색 유입이 많은지
   확인 — 잘 되는 필러 비중을 `config/topics.yml`에서 늘리는 식으로 반영 가능
   (`docs/CONTENT_STRATEGY.md`의 성장 로드맵 참고)
