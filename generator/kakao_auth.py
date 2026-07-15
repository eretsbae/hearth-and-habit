#!/usr/bin/env python3
"""One-time local helper: authorize KakaoTalk 나에게 보내기 and store the token.

Prerequisites (see docs/KAKAO_REPORT.md for screenshots-level detail):
  1. https://developers.kakao.com → 내 애플리케이션 → 애플리케이션 추가
  2. 앱 설정 → 플랫폼 → Web 플랫폼 등록 (사이트 도메인: http://localhost:8765)
  3. 제품 설정 → 카카오 로그인 → 활성화 ON,
     Redirect URI에 http://localhost:8765 등록
  4. 제품 설정 → 카카오 로그인 → 동의항목 →
     "카카오톡 메시지 전송(talk_message)" 사용 설정
  5. 앱 키 중 "REST API 키"를 복사

Run:
    python generator/kakao_auth.py

It opens a browser for Kakao login/consent, catches the redirect locally,
exchanges the code for tokens, and writes .secrets/kakao_token.enc encrypted
with a passphrase you choose. Afterwards register two GitHub Actions secrets:
    KAKAO_REST_API_KEY      (the REST API key)
    KAKAO_TOKEN_PASSPHRASE  (the passphrase you chose)
and commit the .secrets/kakao_token.enc file.
"""

from __future__ import annotations

import getpass
import http.server
import threading
import urllib.parse
import webbrowser

import requests

from kakao_client import AUTH_HOST, TOKEN_FILE, encrypt_token_file

REDIRECT_URI = "http://localhost:8765"
PORT = 8765

_code_holder: dict = {}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _code_holder["code"] = (qs.get("code") or [None])[0]
        _code_holder["error"] = (qs.get("error") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>인증 완료 — 터미널로 돌아가세요.</h2>".encode())

    def log_message(self, *args):  # silence request logging
        pass


def main() -> int:
    rest_key = input("Kakao REST API 키: ").strip()
    if not rest_key:
        print("REST API 키가 필요합니다.")
        return 1
    client_secret = input(
        "클라이언트 시크릿 (콘솔의 REST API 키에서 '사용함'인 경우만 입력, 아니면 Enter): "
    ).strip()

    server = http.server.HTTPServer(("localhost", PORT), _Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    auth_url = (
        f"{AUTH_HOST}/oauth/authorize?client_id={rest_key}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        "&response_type=code&scope=talk_message"
    )
    print(f"\n브라우저에서 Kakao 로그인/동의를 진행하세요:\n{auth_url}\n")
    webbrowser.open(auth_url)
    thread.join(timeout=300)

    if _code_holder.get("error") or not _code_holder.get("code"):
        print(f"인증 실패: {_code_holder.get('error') or 'no code received (timeout?)'}")
        return 1

    data = {
        "grant_type": "authorization_code",
        "client_id": rest_key,
        "redirect_uri": REDIRECT_URI,
        "code": _code_holder["code"],
    }
    if client_secret:
        data["client_secret"] = client_secret
    resp = requests.post(f"{AUTH_HOST}/oauth/token", data=data, timeout=30)
    resp.raise_for_status()
    tokens = resp.json()
    if "refresh_token" not in tokens:
        print(f"토큰 응답에 refresh_token이 없습니다: {tokens}")
        return 1

    passphrase = getpass.getpass("토큰 파일 암호화에 쓸 passphrase (직접 정하세요): ").strip()
    if not passphrase:
        print("passphrase가 필요합니다.")
        return 1

    encrypt_token_file(
        {"refresh_token": tokens["refresh_token"], "client_secret": client_secret}, passphrase
    )
    print(f"\n저장 완료: {TOKEN_FILE.relative_to(TOKEN_FILE.parents[1])}")
    print("\n남은 일 (한 번만):")
    print("  1. GitHub 리포 → Settings → Secrets and variables → Actions에 등록:")
    print("       KAKAO_REST_API_KEY      = (위에서 입력한 REST API 키)")
    print("       KAKAO_TOKEN_PASSPHRASE  = (방금 정한 passphrase)")
    print("  2. 암호화된 토큰 파일 커밋:")
    print("       git add .secrets/kakao_token.enc && git commit -m 'chore: add kakao token' && git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
