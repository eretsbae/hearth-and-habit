"""Shared KakaoTalk "메시지 나에게 보내기" client + encrypted token storage.

Kakao refresh tokens expire after ~60 days and get ROTATED when refreshed
with under ~30 days left, so unattended weekly use must persist the newest
refresh token somewhere. GitHub Actions can't update repository secrets with
the default token, and this repo is public — so the token lives in
.secrets/kakao_token.enc, encrypted (PBKDF2 + Fernet/AES via the
`cryptography` package, pure Python so it works on Windows too) with a
passphrase that stays in the KAKAO_TOKEN_PASSPHRASE repository secret. The
workflow decrypts it, refreshes, and commits the re-encrypted file when
Kakao rotates the token.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

import token_store

AUTH_HOST = "https://kauth.kakao.com"
API_HOST = "https://kapi.kakao.com"

ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / ".secrets" / "kakao_token.enc"

_HINT = "Re-create it with: python generator/kakao_auth.py"


def encrypt_token_file(data: dict, passphrase: str, path: Path = TOKEN_FILE) -> None:
    token_store.encrypt_token_file(data, passphrase, path)


def decrypt_token_file(passphrase: str, path: Path = TOKEN_FILE) -> dict:
    return token_store.decrypt_token_file(passphrase, path, _HINT)


def refresh_tokens(rest_api_key: str, refresh_token: str, client_secret: str = "") -> dict:
    """Exchange the refresh token for a fresh access token. The response
    includes a new refresh_token only when Kakao decides to rotate it.
    client_secret is required only when it is enabled on the app's REST API
    key in the Kakao console (KOE010 errors mean it's enabled but missing)."""
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    if client_secret:
        data["client_secret"] = client_secret
    resp = requests.post(f"{AUTH_HOST}/oauth/token", data=data, timeout=30)
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
