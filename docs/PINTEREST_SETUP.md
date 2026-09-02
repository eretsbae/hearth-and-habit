# Pinterest 자동 게시 설정 (최초 1회)

설정이 끝나면 **매일 22:43 UTC에 핀 3개씩 자동 게시**됩니다. 글이 발행되면 핀 이미지도
자동 생성되므로, 이후 사람이 할 일은 없습니다.

> **손이 가는 시간은 15분이지만, 전체는 그보다 오래 걸립니다.** 2단계의 앱이 Pinterest의
> **trial access 승인**을 받아야 3단계로 넘어갈 수 있고, 그 대기가 몇 주씩 걸립니다.
> 승인을 기다리는 동안 채널을 놀리지 않는 방법은 아래 **[승인 대기 중에 할
> 일](#승인-대기-중에-할-일-또는-수동으로-더-올리고-싶을-때)**에 있습니다.

> **왜 Pinterest인가**: 원래 이유는 색인이었습니다 — Search Console이 모든 글을
> `검색됨 - 현재 색인이 생성되지 않음`으로 표시했고, 차단이 아니라 **외부 링크가 하나도
> 없어서** 구글이 크롤링 우선순위를 안 주는 상태였습니다.
>
> **그 문제는 해소됐습니다** (2026-09-01 기준 40페이지 색인). 하지만 핀은 계속 올릴
> 가치가 있습니다: 색인은 검색 노출의 전제일 뿐이고, 신규 도메인이 실제 순위를 얻기까지는
> 몇 달이 걸립니다. 핀은 도메인 권위와 무관하게 그 사이의 방문자를 데려오고, 외부 링크로
> 남습니다.

---

## 1단계. Pinterest 비즈니스 계정 (3분)

개인 계정이어도 **비즈니스 계정으로 전환**해야 API를 쓸 수 있습니다. 무료입니다.

1. https://www.pinterest.com 로그인
2. 우측 상단 프로필 → **설정 → 계정 관리**
3. **"비즈니스 계정으로 전환"** (이미 비즈니스면 건너뛰기)
4. 웹사이트 항목에 `https://peterpb.blogspot.com` 입력

> (선택, 권장) 설정 → **도메인 및 계정 연결 → 클레임**에서 블로그 도메인을 클레임하면
> 핀에 사이트 정보가 붙고 노출에 유리합니다. blogspot 서브도메인은 HTML 태그 방식으로
> 클레임 가능하며, Blogger → 테마 → HTML 편집에서 `<head>` 안에 태그를 넣으면 됩니다.
> 클레임 없이도 자동 게시는 동작하므로 나중에 하셔도 됩니다.

## 2단계. 개발자 앱 만들기 (5분)

1. https://developers.pinterest.com/apps/ 접속 (1단계와 같은 계정)
2. **"Create app"** 클릭
   - App name: 아무거나 (예: `hearth-habit-publisher`)
   - 용도/설명: "Automatically publishes my own blog's pins to my own boards"
3. 생성 후 앱 상세 화면에서 아래를 설정합니다:
   - **Redirect URI 등록** — Pinterest는 **HTTPS만** 허용하므로 `http://localhost`는 안 됩니다.
     소유한 주소가 없다면 `https://peterpb.blogspot.com/` 를 그대로 넣으세요.
     (실제로 그 페이지가 뭔가를 처리할 필요는 없습니다. 승인 후 주소창의 `code` 값만
     복사해 쓰기 때문입니다.)
   - **Scopes** — `boards:read`, `boards:write`, `pins:read`, `pins:write`, `user_accounts:read`
4. **App ID**와 **App secret**을 복사해 둡니다.

> ⚠️ **Trial access는 자동으로 주어지지 않습니다 — 승인 심사를 거칩니다.**
> Trial access가 허용하는 범위(*앱 소유자 본인 계정*에 대한 호출)는 우리 용도와 정확히
> 맞으므로 그 위 단계인 **standard access 심사는 필요 없습니다.** 하지만 trial access
> 자체가 Pinterest의 승인 대기열을 통과해야 하고, 이 대기열이 길게는 몇 주씩 밀립니다
> (Pinterest가 2026-06-17에 지연을 공식 인정). **이 프로젝트의 앱은 2026-08 기준
> 2개월째 대기 중입니다.**
>
> 승인 전에는 **포털이 App secret을 보여주지 않습니다.** OAuth 코드 교환에 secret이
> 필수라서, 3단계를 시작하는 것 자체가 불가능합니다.
>
> 대기가 2주를 넘으면 [Pinterest Business Community](https://community.pinterest.biz/)의
> Developers 카테고리에 **App ID를 명시한 스레드**를 올려 리뷰를 요청하세요 (그게 이
> 포럼의 관행이고, 실제로 그렇게 풀립니다). **App secret은 절대 올리지 마세요.**
> 답이 없으면 같은 스레드에 답글로만 bump하세요 — 새 스레드는 뒤로 밀립니다.
>
> 승인을 기다리는 동안에는 아래 "승인 대기 중에 할 일"을 보세요. 자동화 없이도
> 채널은 굴릴 수 있습니다.

## 3단계. 로컬에서 1회 인증 (5분)

> **선행 조건**: 앱이 trial access **승인**을 받아 App secret이 포털에 표시되어야
> 합니다. 아직 `pending`이라면 이 단계는 진행할 수 없습니다 — 2단계의 경고를 보세요.

본인 컴퓨터에서:

```bash
cd hearth-and-habit
git pull
pip install -r requirements.txt
python generator/pinterest_auth.py
```

1. App ID / App secret / Redirect URI 입력 (2단계에서 등록한 것과 **정확히 동일**하게)
2. 브라우저가 열리면 Pinterest 승인 → 등록한 Redirect URI로 이동합니다
   - 그 페이지가 에러여도 상관없습니다. **주소창을 보세요.**
   - `...?code=abc123...` 에서 **code 값**을 복사 (주소 전체를 붙여넣어도 자동으로 추출합니다)
3. 터미널에 code 붙여넣기
4. 토큰 파일 암호화용 **passphrase**를 직접 정해서 입력 (기억해두세요)

완료되면 `.secrets/pinterest_token.enc`가 생성됩니다.

## 4단계. 시크릿 등록 + 토큰 커밋 (2분)

1. GitHub 리포 → **Settings → Secrets and variables → Actions**:
   - `PINTEREST_APP_ID` = App ID
   - `PINTEREST_APP_SECRET` = App secret
   - `PINTEREST_TOKEN_PASSPHRASE` = 3단계에서 정한 passphrase
2. 토큰 파일 커밋:
   ```bash
   git add .secrets/pinterest_token.enc
   git commit -m "chore: add pinterest token"
   git push
   ```

## 5단계. 동작 확인

**Actions 탭 → "Publish Pins to Pinterest" → Run workflow** (limit은 기본 3)

성공하면 로그에 이렇게 찍힙니다:

```
17 post(s) awaiting a pin; publishing 3 this run.
  created board: Home Maintenance & Repairs
Pinning: Furnace Filter Basics: ...
  -> pin 1234567890 on 'Home Maintenance & Repairs'
```

Pinterest 프로필에서 보드와 핀이 생겼는지 확인하세요. 첫 실행 때 **필러 5개에 해당하는
보드가 자동 생성**됩니다 (Home Maintenance & Repairs / Cleaning & Organization /
Energy & Utility Savings / Kitchen & Food Habits / Yard & Outdoor Basics).

---

## 동작 방식

- **하루 3개씩만** 올립니다. Pinterest는 꾸준한 활동을 선호하고, 신규 계정이 한 번에
  수십 개를 쏟아내면 스팸으로 취급합니다. 현재 밀린 17개는 약 6일에 걸쳐 소진됩니다.
- **보드를 번갈아 사용**합니다. 매 실행마다 서로 다른 필러에서 하나씩 뽑아 올립니다.
- **중복 게시 없음** — 게시된 핀 ID가 `config/topics.yml`에 기록되고, 핀 하나 올릴 때마다
  즉시 저장되므로 중간에 오류가 나도 이미 올린 것이 다시 올라가지 않습니다.
- **토큰 자동 갱신** — Pinterest refresh token은 약 1년 유효하고, 갱신 시 교체되면
  워크플로우가 재암호화해 자동 커밋합니다.

## 승인 대기 중에 할 일 (또는 수동으로 더 올리고 싶을 때)

승인은 우리가 통제할 수 없지만, 핀 이미지는 글이 발행될 때마다 이미 자동 생성되고
있습니다. 백로그를 쌓아두지 말고 손으로 올리세요 — AdSense 심사에 필요한 외부 링크와
실제 유입도 여기서 나옵니다.

1. **보드 5개를 먼저 만드세요** — `config/topics.yml`의 필러 이름과 **똑같이**,
   **공개** 상태로. 이름이 같아야 나중에 API가 켜졌을 때 기존 보드를 그대로 쓰고
   중복 생성하지 않습니다.
2. `content/pins/PINS.md`에 글마다 핀 이미지 경로 / 보드 / 연결 URL / 복사용 설명문이
   정리되어 있습니다. 이미지는 `content/pins/` 폴더에 있습니다.
3. **하루 3~5개씩**만. 신규 계정이 몰아 올리면 스팸으로 취급됩니다.
4. 올린 뒤에는 **반드시 기록하세요.** 이걸 빠뜨리면 나중에 API가 켜졌을 때 같은 글을
   중복 게시합니다:

   ```bash
   python generator/pinterest_publish.py --mark-pinned SLUG [SLUG ...]
   git add config/topics.yml content/pins/PINS.md
   git commit -m "chore: record manually pinned posts" && git push
   ```

   슬러그는 `PINS.md`의 이미지 경로(`content/pins/<슬러그>.png`)에서 그대로 가져오면
   됩니다. `make_bulk_csv.py`는 배치마다 이 명령을 슬러그까지 채워서 출력하므로 그대로
   복사하면 됩니다.

   > **Windows PowerShell 주의**: `--mark-pinned`는 **반드시 한 줄로** 붙여넣으세요.
   > bash의 줄바꿈 문자 `\`는 PowerShell에서 동작하지 않고(PowerShell은 백틱 `` ` ``),
   > 그대로 인자로 넘어가 `ERROR: no published post found for: \`로 실패합니다. 이때
   > 파일은 저장되지 않으니 다시 실행하면 됩니다. `&&`도 Windows PowerShell 5.1에서는
   > 안 되므로 `git commit`과 `git push`를 각각 실행하세요.

   기록을 빠뜨리면 승인 후 API가 같은 글을 다시 올립니다. 반대로 **업로드 전에** 찍으면
   그 글이 큐에서 영영 빠지므로, 업로드가 끝난 뒤에 실행하세요.

## 문제 해결

| 증상 | 해결 |
|---|---|
| 앱이 `pending` 상태에서 안 넘어감 / App secret이 안 보임 | trial access 승인 대기입니다. 2주 넘었으면 커뮤니티 포럼에 App ID를 적어 리뷰 요청 (2단계 경고 참고). 그동안은 "승인 대기 중에 할 일"로 수동 게시 |
| 워크플로우는 매일 성공인데 핀이 안 올라감 | 로그에 `Pinterest not configured — skipping send`가 있으면 미설정 상태입니다. 실행 요약(Summary)에도 경고가 뜹니다. 4단계의 시크릿 3개와 `.secrets/pinterest_token.enc` 커밋 여부를 확인하세요 |
| 포털에서 발급한 30일짜리 토큰을 쓰고 싶음 | 쓸 수 없습니다. 이 파이프라인은 **refresh token**으로 매 실행마다 access token을 재발급합니다. 포털 버튼으로 받은 토큰에는 refresh token이 없어 `pinterest_auth.py`가 거부하고, 한 달 뒤 죽습니다. 3단계의 OAuth 플로우로 받으세요 |
| `code exchange failed` | Redirect URI가 앱 설정과 글자 하나까지 같은지 확인. code는 1회용이고 몇 분 내 만료되므로 새로 발급받아 즉시 사용 |
| `pin creation failed` + 권한 관련 메시지 | 앱 scope에 `pins:write`가 있는지, Pinterest 계정이 비즈니스 계정인지 확인 |
| `token refresh failed` | refresh token 만료(약 1년) 또는 앱 접근 취소. `python generator/pinterest_auth.py` 재실행 후 토큰 파일 다시 커밋 |
| 핀은 생성됐는데 이미지가 안 보임 | 핀 이미지는 raw.githubusercontent.com에서 제공됩니다. 리포가 public인지 확인 |
| 보드가 중복 생성됨 | 보드는 **이름**으로 매칭합니다. Pinterest에서 보드 이름을 바꿨다면 `config/topics.yml`의 필러 이름과 다시 맞춰주세요 |
