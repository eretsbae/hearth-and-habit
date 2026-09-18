# Pinterest Standard access 신청 — 데모 영상 촬영 대본과 신청서 답변

Trial access는 sandbox에만 핀을 만들 수 있어(2026-09-13 실측, 403 code 29) 실제 게시에는
Standard access가 필요합니다. 신청 폼은 **데모 영상(필수)** 과 **정보 검토** 두 부분입니다.
Pinterest가 영상에서 보겠다고 명시한 것은 딱 두 가지입니다:

1. 앱이 Pinterest 사용자를 **어떻게 인증**하는지 (OAuth 동의 화면)
2. 사용자가 쓰게 될 **메인 Pinterest 기능** (우리 경우: 내 글의 핀을 내 보드에 생성)

Trial 앱은 sandbox로 시연하라는 게 Pinterest의 공식 안내이므로, 핀 생성은
`--sandbox`로 보여주면 됩니다. 실제 프로필에 핀이 생기지 않아도 심사에는 문제없습니다.

---

## 0. 촬영 전 준비 (10분, 녹화 전에 끝낼 것)

```powershell
cd C:\workspace\hearth-and-habit
git pull origin main
. .\generator\pinterest_env.ps1
```

- `pinterest_env.ps1`은 App ID, App secret, passphrase, sandbox 토큰을 **프롬프트로** 받습니다.
  값은 프롬프트에 붙여넣으세요(우클릭 또는 Ctrl+V). 클립보드를 직접 읽지 않으므로 명령을 복사한 뒤
  값을 복사해도 됩니다. 입력이 끝나면 각 값의 길이(sandbox 토큰은 `pina_` 접두어까지)를 보여주고,
  Enter를 누르면 화면을 지웁니다. secret이 영상에 남으면 안 되므로 **녹화 시작 전에** 끝내세요.
  앞의 점과 공백(`. .\`)이 빠지면 env가 창에 남지 않으니 그대로 입력합니다.
- **sandbox 토큰**: sandbox는 프로덕션 access token을 받지 않습니다(401 code 2). 개발자 포털 → 내 앱 →
  **Generate Access Tokens**에서 환경을 **Sandbox**로 선택하고 Generate token → 복사 아이콘(30일 유효).
  `--sandbox`는 이 값을 우선 쓰고, 없으면 sandbox 토큰 엔드포인트로 발급을 시도합니다.
- `pinterest_auth.py`와 `pinterest_publish.py` 모두 이 env를 읽으므로 장면 2에서 secret을 타이핑할 일이
  없습니다. 숨김 프롬프트에 직접 타이핑하면 오타(한글 IME 등)를 알 수 없고, Pinterest는 401 code 2로
  거부합니다. env는 PowerShell 창마다 따로이므로 새 창을 열면 다시 실행해야 합니다.
- 리허설로 아래 두 명령이 오류 없이 도는지 먼저 확인:
  ```powershell
  python generator/pinterest_publish.py --whoami
  python generator/pinterest_publish.py --sandbox --limit 1
  ```
- Pinterest 웹 언어를 **영어**로 바꿔두면(설정 → 계정 관리 → 언어) 심사자가 동의 화면을 읽을 수 있습니다. 촬영 후 되돌리면 됩니다.
- 화면 구성: 왼쪽 브라우저(Pinterest 로그인 상태), 오른쪽 PowerShell. 글꼴 크게(터미널 16pt 이상).
- 녹화 도구: **캡처 도구(Snipping Tool) 화면 녹화** `Win + Shift + R` → 세 창이 다 들어가게 영역 드래그 → 시작.
  결과는 `동영상\화면 녹화\*.mp4`. Xbox 게임 바(`Win + Alt + R`)는 활성 창 하나만 잡아서 브라우저·터미널·메모장을
  함께 찍을 수 없습니다. 캡처 도구에 비디오 모드가 없으면 PowerPoint 삽입 → 화면 녹화, 또는 OBS의 디스플레이 캡처.
- 구형 PowerShell 콘솔은 창 안을 **클릭하면 선택 모드**(제목이 "선택 관리자:"로 바뀜)에 들어가 출력이 멈춥니다.
  녹화 전 `Esc`로 풀고, 촬영 중에는 터미널 위에 마우스를 올려놓기만 하고 클릭하지 마세요.
- 길이 목표 **2~4분**. 편집 없이 한 번에 찍어도 됩니다. 실수하면 처음부터 다시.

---

## 1. 촬영 대본 (장면 · 화면 · 캡션/보이스오버)

보이스오버는 선택입니다. 말하기 싫으면 각 장면의 영어 문장을 PowerShell에 `Write-Host`로
찍거나 메모장에 띄워 두면 캡션 역할을 합니다.

### 장면 1 — 앱 소개 (0:00–0:20)
- 화면: `https://www.hearth-habit.com/` 홈 → Pinterest 개발자 포털(`developers.pinterest.com` → 내 앱)의
  **앱 페이지**. 앱 이름과 app ID 1594725가 영어 UI로 보입니다.
  (GitHub 리포 README는 한국어이고 Pinterest 언급이 없어 심사자에게 도움이 되지 않으니 보여주지 않습니다.
  리포를 꼭 보이고 싶으면 Actions 탭의 "Publish Pins to Pinterest" 워크플로가 대안입니다.)
- 말/캡션: *"This is Hearth & Habit Publisher, app ID 1594725. It is a private, single-user tool. It posts pins for articles on my own blog, hearth-habit.com, to boards on my own Pinterest account. There are no other users."*

### 장면 2 — 인증 (0:20–1:20)
- 화면: PowerShell에서
  ```powershell
  python generator/pinterest_auth.py
  ```
  App ID와 secret은 0절에서 넣은 env를 자동으로 읽습니다(secret은 화면에 나오지 않음).
  Redirect URI `https://www.hearth-habit.com/`만 입력.
- 브라우저가 열리면 **Pinterest OAuth 동의 화면**을 2~3초 그대로 보여준 뒤 승인(Allow).
- 리다이렉트된 주소창(`https://www.hearth-habit.com/?code=...`)을 보여주고 주소 전체를 복사해 터미널에 붙여넣기 → passphrase 입력 → `저장 완료`.
- 말/캡션: *"Authentication uses the standard Pinterest OAuth 2.0 authorization-code flow with scopes boards:read, boards:write, pins:read, pins:write, user_accounts:read. I approve the app on Pinterest's consent screen, Pinterest redirects to my registered URI with a code, and the app exchanges it for tokens. The refresh token is stored encrypted; nothing else about the account is stored."*

### 장면 3 — 인증 확인 (1:20–1:40)
- 화면:
  ```powershell
  python generator/pinterest_publish.py --whoami
  ```
  → `Authenticated as: username ... account_type BUSINESS`.
- 말/캡션: *"The token now identifies my account through GET /v5/user_account."*

### 장면 4 — 메인 기능: 핀 생성 (1:40–2:50)
- 화면:
  ```powershell
  python generator/pinterest_publish.py --sandbox --limit 2
  ```
  출력 순서대로 마우스를 **올려놓기만** 해서(클릭 금지, 위 선택 모드 참고) 짚기: `SANDBOX MODE` 배너 → `Boards on this account: 5` 와 보드 이름 → `Pinning: <글 제목>` → `-> sandbox pin <id> on '<board>'` 와 link/title.
- 말/캡션: *"This is the app's only write operation. For each new article it picks the board that matches the article's category from GET /v5/boards, then calls POST /v5/pins with the article's title, description, the article URL as the link, and a pin image hosted on GitHub. Because the app is on Trial access, this run uses the API sandbox; in production the exact same code runs once a day from GitHub Actions and creates at most three pins."*

### 장면 5 — 운영 방식과 결과물 (2:50–3:30)
- 화면 A: GitHub → Actions → "Publish Pins to Pinterest" 최근 실행 → 요약(step summary). 일일 스케줄이 보이면 좋습니다.
- 화면 B: `config/topics.yml`에서 `pinterest_pin_id:` 줄 몇 개.
- 화면 C: Pinterest 프로필(`kr.pinterest.com/qo5928`)의 보드 5개와 기존 핀들.
- 말/캡션: *"The scheduler is a GitHub Actions cron job. After each pin is created, the app records only the pin ID next to the article so the same article is never pinned twice. These boards and pins are what the result looks like; the earlier ones were uploaded by hand with Pinterest's bulk-import CSV while the app waited for API access."*

### 장면 6 — 마무리 (3:30–3:45)
- 말/캡션: *"Summary: one user, my own account, my own content. Endpoints used: user_account, boards list and create, pins create. Data stored: encrypted refresh token and pin IDs. No user data is collected, shared, or sold."*
- 캡처 도구의 정지 버튼으로 녹화 종료 → 저장.

---

## 2. 촬영 후

재인증(장면 2)을 했으므로 토큰 파일이 새로 생겼습니다. 커밋해야 워크플로가 새 토큰을 씁니다:

```powershell
git add .secrets/pinterest_token.enc
git commit -m "chore: refresh pinterest token"
git pull --rebase origin main
git push origin main
```

Pinterest 언어를 다시 한국어로 돌려놓고, 영상 파일을 폼에 업로드합니다.

---

## 3. "정보 검토" 답변 (영어, 그대로 붙여넣기)

폼 문항 문구는 바뀔 수 있으니 가장 가까운 칸에 넣으세요.

**App name / description**
> Hearth & Habit Publisher — a private, single-user automation that publishes Pins for articles on my own blog (https://www.hearth-habit.com) to boards on my own Pinterest Business account (@qo5928). The app owner is the only user.

**Use case / what the app does**
> Each weekday my blog publishes one home-care article with a 1000×1500 pin image. Once a day a scheduled job (GitHub Actions) reads the list of articles that do not yet have a Pin, picks the board matching the article's category, and creates one Pin per article (title, description, link to the article, image URL). It creates at most 3 Pins per day. It never reads, modifies, or deletes other users' content and never posts to boards it does not own.

**Pinterest features / endpoints used**
> GET /v5/user_account (verify the authenticated account) · GET /v5/boards (find the board for a category) · POST /v5/boards (create a category board once if missing) · POST /v5/pins (create the Pin). Scopes: boards:read, boards:write, pins:read, pins:write, user_accounts:read.

**How users authenticate**
> Standard OAuth 2.0 authorization-code flow against https://www.pinterest.com/oauth/ with redirect URI https://www.hearth-habit.com/. The refresh token is stored encrypted (PBKDF2 + Fernet) in a private repository; the passphrase lives only in GitHub Actions secrets. Tokens are refreshed via POST /v5/oauth/token.

**Data collected / stored / shared**
> The only Pinterest data stored is the ID of each Pin the app itself created, kept next to the article record to prevent duplicate Pins. No user data, analytics, or content from other accounts is collected, stored, shared, or sold. Deleting the repository secret revokes the app's access.

**Number of users / audience**
> 1 (the app owner). Not distributed. No public-facing UI.

**Platform**
> Server-side Python script run by GitHub Actions (Linux). Source: https://github.com/eretsbae/hearth-and-habit

**Website / privacy policy**
> https://www.hearth-habit.com/ · https://www.hearth-habit.com/p/privacy-policy.html
> (개인정보 페이지 주소는 Blogger → 페이지에서 실제 URL을 확인해 넣으세요.)

**Why Standard access is needed**
> Trial access allows Pin creation only in the API sandbox. The app is complete and verified end-to-end (OAuth, board lookup, sandbox Pin creation, daily scheduling); Standard access is required only so the same POST /v5/pins call can create Pins on the production account.

---

## 4. 심사에서 자주 걸리는 것 (피하기)

- 동의 화면을 안 보여줌 → 장면 2에서 **Allow 누르기 전에** 화면을 2~3초 멈춰 두세요.
- 영상에 secret이나 토큰이 노출 → 준비 단계에서 env로 넣고 `cls`. `pinterest_auth.py`는 secret을 가립니다.
- "누가 쓰는 앱인지" 불분명 → 장면 1과 6에서 *single user, my own account* 를 말로 반복.
- 신청서와 영상의 엔드포인트가 불일치 → 위 답변의 엔드포인트 목록이 코드와 정확히 같습니다(`generator/pinterest_client.py`).
