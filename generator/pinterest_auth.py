#!/usr/bin/env python3
"""One-time local helper: authorize the Pinterest app and store the token.

Setup steps are in docs/PINTEREST_SETUP.md. In short you need a Pinterest
developer app with a registered redirect URI and the pins:write scope.

Unlike the Blogger and Kakao helpers this does NOT spin up a localhost
listener: Pinterest requires an HTTPS redirect URI, so a local http://
callback can't be registered. Instead you approve in the browser, get
redirected to your registered URI, and paste the `code` value from the
address bar back here. The code is single-use and expires in minutes.

Credentials come from the environment when set, so nothing secret is typed
(a hidden getpass prompt hides typos too — a Korean IME or a console that
does not paste on Ctrl+V silently produces a wrong secret and Pinterest
answers 401 code 2):

    PINTEREST_APP_ID, PINTEREST_APP_SECRET, PINTEREST_TOKEN_PASSPHRASE

Anything missing is prompted for.

Run:
    python generator/pinterest_auth.py
"""

from __future__ import annotations

import getpass
import os
import urllib.parse
import webbrowser

import pinterest_client as pc


def main() -> int:
    print("Pinterest 인증 (docs/PINTEREST_SETUP.md 1~2단계를 먼저 끝내세요)\n")
    app_id = os.environ.get("PINTEREST_APP_ID", "").strip()
    if app_id:
        print(f"App ID (client id): {app_id}  (env PINTEREST_APP_ID)")
    else:
        app_id = input("App ID (client id): ").strip()
    app_secret = os.environ.get("PINTEREST_APP_SECRET", "").strip()
    if app_secret:
        print("App secret: (env PINTEREST_APP_SECRET)")
    else:
        app_secret = getpass.getpass("App secret: ").strip()
    redirect_uri = input("등록한 Redirect URI (앱 설정과 정확히 동일해야 함): ").strip()
    if not (app_id and app_secret and redirect_uri):
        print("App ID / secret / redirect URI가 모두 필요합니다.")
        return 1

    auth_url = (
        f"{pc.OAUTH_AUTHORIZE}?client_id={urllib.parse.quote(app_id)}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        f"&response_type=code&scope={urllib.parse.quote(pc.SCOPES)}"
    )
    print("\n아래 주소를 브라우저에서 열고 승인하세요:\n")
    print(auth_url)
    print()
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("승인하면 등록한 Redirect URI로 이동합니다. 그 페이지가 열리지 않아도 괜찮습니다 —")
    print("주소창의 ?code=... 부분에서 code 값만 복사하세요 (뒤에 &가 있으면 그 앞까지).\n")
    code = input("code 값 붙여넣기: ").strip()
    if not code:
        print("code가 필요합니다.")
        return 1
    if code.startswith("http"):  # user pasted the whole URL
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(code).query)
        code = (qs.get("code") or [""])[0]
        if not code:
            print("붙여넣은 URL에서 code를 찾지 못했습니다.")
            return 1
        print("(URL 전체에서 code를 자동 추출했습니다)")
    elif "&" in code or "?" in code:
        # "abc123&m=1" — Blogger appends &m=1 on mobile and it is easy to
        # drag-select along with the code. Everything after the code itself
        # makes Pinterest reject the grant (401, code 283).
        code = code.split("?")[-1].split("&")[0].removeprefix("code=")
        print("(code 뒤에 붙은 파라미터를 잘라냈습니다)")

    tokens = pc.exchange_code(app_id, app_secret, code, redirect_uri)
    if "refresh_token" not in tokens:
        print(f"응답에 refresh_token이 없습니다: {tokens}")
        return 1

    passphrase = os.environ.get("PINTEREST_TOKEN_PASSPHRASE", "").strip()
    if passphrase:
        print("\n토큰 파일 passphrase: (env PINTEREST_TOKEN_PASSPHRASE)")
    else:
        passphrase = getpass.getpass("\n토큰 파일 암호화에 쓸 passphrase (직접 정하세요): ").strip()
    if not passphrase:
        print("passphrase가 필요합니다.")
        return 1

    pc.save_tokens({"refresh_token": tokens["refresh_token"]}, passphrase)
    print(f"\n저장 완료: .secrets/{pc.TOKEN_FILE.name}")
    print("\n남은 일 (한 번만):")
    print("  1. GitHub 리포 → Settings → Secrets and variables → Actions에 등록:")
    print("       PINTEREST_APP_ID            = (위에서 입력한 App ID)")
    print("       PINTEREST_APP_SECRET        = (위에서 입력한 App secret)")
    print("       PINTEREST_TOKEN_PASSPHRASE  = (방금 정한 passphrase)")
    print("  2. 암호화된 토큰 파일 커밋:")
    print("       git add .secrets/pinterest_token.enc")
    print('       git commit -m "chore: add pinterest token" && git push')
    print("  3. Actions → 'Publish Pins to Pinterest' → Run workflow 로 첫 실행 확인")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
