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
4. 웹사이트 항목에 `https://www.hearth-habit.com` 입력 (2026-09-11 커스텀 도메인 전환 후 갱신할 것)

> (선택, 권장) 설정 → **도메인 및 계정 연결 → 클레임**에서 블로그 도메인을 클레임하면
> 핀에 사이트 정보가 붙고 노출에 유리합니다. HTML 태그 방식으로 클레임하며, Blogger →
> 테마 → HTML 편집에서 `<head>` 안에 태그를 넣으면 됩니다. 커스텀 도메인은 클레임
> 이후 사이트 소유 표시가 붙으므로 도메인 전환 뒤 `hearth-habit.com`으로 다시 클레임하세요.
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

> **Trial access로는 실제 핀을 만들 수 없습니다 (2026-09-13 실측).** 이 프로젝트의
> 앱(ID 1594725)은 2026-06에 신청해 2026-09-13에 Trial access를 받았고, 그날 바로
> 워크플로를 돌려보니 `POST /pins`가 **403 code 29: "Apps with Trial access may not
> create Pins in production — use API Sandbox"** 로 거절됐습니다. Trial은 읽기 +
> sandbox 쓰기까지이고, 실제 프로필에 핀을 만들려면 **Standard access**가 필요합니다.
>
> **다음 단계**: 개발자 포털 → 내 앱 → **업그레이드** 버튼으로 Standard access를
> 신청하세요. 데모 영상 촬영 대본과 신청서 답변은 [PINTEREST_STANDARD_ACCESS.md](PINTEREST_STANDARD_ACCESS.md). 신청서에는 용도("내 블로그 글의 핀을 내 보드에 자동 게시"), 앱이 실제로
> 호출하는 엔드포인트(boards list, pins create), 데이터 저장 방식(핀 ID만 리포에 기록)을
> 적으면 됩니다. 심사 중에도 3~5단계는 그대로 유효하고, 승인되는 순간 워크플로가
> 자동으로 핀을 올리기 시작합니다(코드 변경 불필요).
>
> 그때까지는 아래 "승인 대기 중에 할 일"의 **CSV 경로가 정식 경로**입니다.

## 3단계. 로컬에서 1회 인증 (5분)

> **선행 조건**: 앱이 trial access 승인을 받아 App secret이 포털(내 앱 → 관리)에
> 표시되어야 합니다. (2026-09-13 승인 완료.)

본인 컴퓨터에서:

```bash
cd hearth-and-habit
git pull
pip install -r requirements.txt
python generator/pinterest_auth.py
```

1. App ID / App secret / Redirect URI 입력 (2단계에서 등록한 것과 **정확히 동일**하게)
   - 환경변수 `PINTEREST_APP_ID`, `PINTEREST_APP_SECRET`, `PINTEREST_TOKEN_PASSPHRASE`가 있으면 묻지 않고 그 값을 씁니다.
     secret 프롬프트는 입력이 안 보여 오타를 잡을 수 없으니, 가능하면 env로 넣으세요.
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

> Standard access가 나오기 전까지는 이 CSV 경로가 정식 경로입니다. 워크플로는 매일
> 돌지만 Trial access라 핀을 만들지 못하고 경고만 남깁니다. **Standard access가 승인된
> 뒤에는 CSV를 올리지 마세요** — 워크플로가 같은 글을 다시 올립니다.

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

### CSV 배치 루틴 (콘텐츠 가져오기)

낱개로 올리는 대신 Pinterest 설정 → **콘텐츠 가져오기**에 CSV를 넣는 방식입니다.
Standard access가 승인될 때까지는 이 루틴이 실제 게시 경로이며, **다음 파일은 자동으로
만들어집니다.** 사람이 할 일은 업로드와 기록뿐입니다.

```bash
git pull origin main                                 # bulk-upload/pinsNN.csv 가 내려옴
#   → Pinterest 설정 → 콘텐츠 가져오기 → bulk-upload/pinsNN.csv 업로드
#   → 보드에서 핀이 실제로 생성됐는지 확인
python generator/pinterest_publish.py --mark-pinned pinsNN   # 기록 + 다음 파일 생성
git add config/topics.yml bulk-upload
git commit -m "chore: record pinsNN, prepare next batch"
git push origin main
```

- `bulk-upload/`는 **커밋 대상**입니다. 다음 CSV는 `git pull`로 받고, 직접 생성할 필요가
  없습니다.
- 다음 파일이 생기는 규칙(`make_bulk_csv.py --auto`):
  - 아직 기록되지 않은 배치가 있으면 아무것도 만들지 않습니다(한 번에 한 파일만 대기).
    그 배치의 CSV가 폴더에 없으면 `config/topics.yml` 기록으로 같은 파일을 다시 만듭니다.
  - 모든 배치가 기록됐고 대기 글이 있으면 다음 `pinsNN.csv`(최대 4핀)를 만들고
    각 글에 `pinterest_batch: pinsNN`을 찍습니다. 대기 글이 4개 미만이면 채워질 때까지
    기다리되, 가장 오래된 글이 게시 후 7일을 넘기면 그 수만으로 만듭니다(새 글은 주 3편이라
    글마다 1핀짜리 파일을 올리는 것보다 주 1회 꽉 찬 파일이 낫습니다).
  - API가 실제 핀을 하나라도 만든 뒤(Standard access 승인)에는 더 이상 만들지 않습니다.
- 실행 시점 두 곳: `--mark-pinned pinsNN` 직후(그 자리에서 다음 파일 생성), 그리고 매일
  도는 `pinterest-publish.yml`(새 글이 올라왔거나 로컬에서 커밋을 빠뜨린 경우를 메움).
  워크플로우가 파일을 만들면 실행 요약(Summary)에 📌 배치 준비됨이 뜹니다.
- 기록 전에는 그 배치 글이 API 경로에서도 제외됩니다(`held back` 로그). 승인 후 CSV를
  올리지 않고 API에 맡기려면 `config/topics.yml`에서 해당 `pinterest_batch:` 줄을 지우세요.
- 파일명은 `pins09.csv` 형식이고, 번호는 폴더의 `pinsNN.csv`(하이픈 있는 `pins-NN.csv`도
  인식)와 `topics.yml`의 `pinterest_batch` 중 가장 큰 번호 다음부터 이어집니다.
- 수동 생성(`--per-file`, `--limit`, `--start`, `--include-assigned`)도 그대로 됩니다.
  `--auto` 없이 만든 파일도 커밋하세요.

## 문제 해결

| 증상 | 해결 |
|---|---|
| 앱이 `pending` 상태에서 안 넘어감 / App secret이 안 보임 | trial access 승인 대기입니다. 2주 넘었으면 커뮤니티 포럼에 App ID를 적어 리뷰 요청 (2단계 경고 참고). 그동안은 "승인 대기 중에 할 일"로 수동 게시 |
| 워크플로우는 매일 성공인데 핀이 안 올라감 | 로그에 `Pinterest not configured — skipping send`가 있으면 미설정 상태입니다. 실행 요약(Summary)에도 경고가 뜹니다. 4단계의 시크릿 3개와 `.secrets/pinterest_token.enc` 커밋 여부를 확인하세요 |
| 포털에서 발급한 30일짜리 토큰을 쓰고 싶음 | 쓸 수 없습니다. 이 파이프라인은 **refresh token**으로 매 실행마다 access token을 재발급합니다. 포털 버튼으로 받은 토큰에는 refresh token이 없어 `pinterest_auth.py`가 거부하고, 한 달 뒤 죽습니다. 3단계의 OAuth 플로우로 받으세요 |
| `code exchange failed` + `"code":2` | App ID/secret 쌍이 거부된 것입니다(code 자체의 문제가 아님). secret 프롬프트에 오타가 들어갔거나(한글 IME, 붙여넣기 실패) 포털에서 secret을 재생성한 경우. `PINTEREST_APP_ID`/`PINTEREST_APP_SECRET`을 env로 넣고 재실행 |
| `code exchange failed` (그 외) | Redirect URI가 앱 설정과 글자 하나까지 같은지 확인. code는 1회용이고 몇 분 내 만료되므로 새로 발급받아 즉시 사용 |
| `pin creation failed` + 권한 관련 메시지 | 앱 scope에 `pins:write`가 있는지, Pinterest 계정이 비즈니스 계정인지 확인 |
| `token refresh failed` | refresh token 만료(약 1년) 또는 앱 접근 취소. `python generator/pinterest_auth.py` 재실행 후 토큰 파일 다시 커밋 |
| 핀은 생성됐는데 이미지가 안 보임 | 핀 이미지는 raw.githubusercontent.com에서 제공됩니다. 리포가 public인지 확인 |
| 보드가 중복 생성됨 | 보드는 **이름**으로 매칭합니다. Pinterest에서 보드 이름을 바꿨다면 `config/topics.yml`의 필러 이름과 다시 맞춰주세요 |
