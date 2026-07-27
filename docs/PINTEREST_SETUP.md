# Pinterest 자동 게시 설정 (최초 1회, 약 15분)

설정이 끝나면 **매일 22:43 UTC에 핀 3개씩 자동 게시**됩니다. 글이 발행되면 핀 이미지도
자동 생성되므로, 이후 사람이 할 일은 없습니다.

> **왜 Pinterest인가**: Search Console이 모든 글을 `검색됨 - 현재 색인이 생성되지 않음`으로
> 표시합니다. 차단이 아니라 **외부 링크가 하나도 없어서** 구글이 크롤링 우선순위를 안 주는
> 상태입니다. 핀은 (1) 크롤 가능한 외부 링크가 되고 (2) 도메인 권위와 무관하게 실제 방문자를
> 데려옵니다. 홈·생활 니치에서 신규 사이트가 쓸 수 있는 가장 빠른 채널입니다.

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

> **Trial access로 충분합니다.** 새 앱은 "Trial access" 상태로 시작하는데, 이는 *앱 소유자
> 본인 계정*에 대한 호출만 허용한다는 뜻입니다. 우리가 하려는 일(내 보드에 내 핀 올리기)이
> 정확히 여기 해당하므로 별도 심사 신청이 필요 없습니다.

## 3단계. 로컬에서 1회 인증 (5분)

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

## 수동으로 올리고 싶을 때

자동화를 쓰지 않거나 추가로 더 올리고 싶다면 `content/pins/PINS.md`에 글마다
핀 이미지 경로 / 보드 / 연결 URL / 복사용 설명문이 정리되어 있습니다.

## 문제 해결

| 증상 | 해결 |
|---|---|
| `code exchange failed` | Redirect URI가 앱 설정과 글자 하나까지 같은지 확인. code는 1회용이고 몇 분 내 만료되므로 새로 발급받아 즉시 사용 |
| `pin creation failed` + 권한 관련 메시지 | 앱 scope에 `pins:write`가 있는지, Pinterest 계정이 비즈니스 계정인지 확인 |
| `token refresh failed` | refresh token 만료(약 1년) 또는 앱 접근 취소. `python generator/pinterest_auth.py` 재실행 후 토큰 파일 다시 커밋 |
| 핀은 생성됐는데 이미지가 안 보임 | 핀 이미지는 raw.githubusercontent.com에서 제공됩니다. 리포가 public인지 확인 |
| 보드가 중복 생성됨 | 보드는 **이름**으로 매칭합니다. Pinterest에서 보드 이름을 바꿨다면 `config/topics.yml`의 필러 이름과 다시 맞춰주세요 |
