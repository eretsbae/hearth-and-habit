"""Shared KakaoTalk "메시지 나에게 보내기" client + encrypted token storage.

Kakao refresh tokens expire after ~60 days and get ROTATED when refreshed
with under ~30 days left, so unattended weekly use must persist the newest
refresh token somewhere. GitHub Actions can't update repository secrets with
the default token, and this repo is public — so the token lives in
.secrets/kakao_token.enc, AES-256 encrypted via openssl with a passphrase
that stays in the KAKAO_TOKEN_PASSPHRASE repository secret. The workflow
decrypts it, refreshes, and commits the re-encrypted file when Kakao rotates
the token.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import requests

AUTH_HOST = "https://kauth.kakao.com"
API_HOST = "https://kapi.kakao.com"

ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / ".secrets" / "kakao_token.enc"


def encrypt_token_file(data: dict, passphrase: str, path: Path = TOKEN_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt",
         "-pass", f"pass:{passphrase}", "-out", str(path)],
        input=json.dumps(data).encode(),
        check=True,
    )


def decrypt_token_file(passphrase: str, path: Path = TOKEN_FILE) -> dict:
    out = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-d",
         "-pass", f"pass:{passphrase}", "-in", str(path)],
        capture_output=True,
        check=True,
    )
    return json.loads(out.stdout)


def refresh_tokens(rest_api_key: str, refresh_token: str) -> dict:
    """Exchange the refresh token for a fresh access token. The response
    includes a new refresh_token only when Kakao decides to rotate it."""
    resp = requests.post(
        f"{AUTH_HOST}/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    if not resp.ok:
        raise SystemExit(
            f"ERROR: Kakao token refresh failed ({resp.status_code}): {resp.text.strip()}\n"
            "The stored refresh token may have fully expired (60-day limit). "
            "Re-run generator/kakao_auth.py locally to re-authorize."
        )
    return resp.json()


def send_to_self(access_token: str, text: str, link_url: str, button_title: str = "자세히 보기") -> None:
    """KakaoTalk '나에게 보내기'. Text template caps at ~200 chars — keep the
    message short and put detail behind the link button."""
    template = {
        "object_type": "text",
        "text": text[:200],
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": button_title,
    }
    resp = requests.post(
        f"{API_HOST}/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {access_token}"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=30,
    )
    if not resp.ok:
        raise SystemExit(
            f"ERROR: KakaoTalk send failed ({resp.status_code}): {resp.text.strip()}\n"
            "Check that the Kakao app has 카카오톡 메시지 enabled and the token "
            "was issued with the talk_message scope (re-run generator/kakao_auth.py)."
        )
