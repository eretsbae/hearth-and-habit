"""Pinterest API v5 client — OAuth refresh, boards, and pin creation.

Why Pinterest: Search Console reports every post as "Discovered - currently
not indexed" because the site has no inbound links anywhere on the web. Pins
are real crawlable links AND send actual readers, and Pinterest ranks pins
without caring about domain authority — the one channel a three-week-old
blogspot can compete in today.

Access model: a Pinterest developer app starts in "Trial access", which is
limited to the app owner's own account. That is exactly this use case
(posting our own pins to our own boards), so no app review is needed.

Token storage follows the same encrypted-file pattern as Kakao — see
token_store.py for why repository secrets alone don't work.
"""

from __future__ import annotations

import base64
from pathlib import Path

import requests

import token_store

API = "https://api.pinterest.com/v5"
OAUTH_AUTHORIZE = "https://www.pinterest.com/oauth/"
OAUTH_TOKEN = f"{API}/oauth/token"

SCOPES = "boards:read,boards:write,pins:read,pins:write,user_accounts:read"

TOKEN_FILE = token_store.SECRETS_DIR / "pinterest_token.enc"
_HINT = "Re-create it with: python generator/pinterest_auth.py"


def load_tokens(passphrase: str) -> dict:
    return token_store.decrypt_token_file(passphrase, TOKEN_FILE, _HINT)


def save_tokens(data: dict, passphrase: str) -> None:
    token_store.encrypt_token_file(data, passphrase, TOKEN_FILE)


def _basic_auth(app_id: str, app_secret: str) -> str:
    raw = f"{app_id}:{app_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def exchange_code(app_id: str, app_secret: str, code: str, redirect_uri: str) -> dict:
    resp = requests.post(
        OAUTH_TOKEN,
        headers={"Authorization": _basic_auth(app_id, app_secret),
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        timeout=30,
    )
    if not resp.ok:
        raise SystemExit(
            f"ERROR: Pinterest code exchange failed ({resp.status_code}): {resp.text.strip()}\n"
            "Check that the redirect URI matches the one registered on the app exactly, "
            "and that the code was pasted whole and hasn't already been used "
            "(each code works once and expires within minutes)."
        )
    return resp.json()


def refresh_access_token(app_id: str, app_secret: str, refresh_token: str) -> dict:
    resp = requests.post(
        OAUTH_TOKEN,
        headers={"Authorization": _basic_auth(app_id, app_secret),
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=30,
    )
    if not resp.ok:
        raise SystemExit(
            f"ERROR: Pinterest token refresh failed ({resp.status_code}): {resp.text.strip()}\n"
            "Pinterest refresh tokens last about a year; if this one expired or was "
            f"revoked, {_HINT}"
        )
    return resp.json()


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def list_boards(access_token: str) -> list[dict]:
    boards, bookmark = [], None
    while True:
        params = {"page_size": 100}
        if bookmark:
            params["bookmark"] = bookmark
        resp = requests.get(f"{API}/boards", params=params,
                            headers=_auth_headers(access_token), timeout=30)
        if not resp.ok:
            raise SystemExit(f"ERROR: could not list boards ({resp.status_code}): {resp.text[:300]}")
        payload = resp.json()
        boards.extend(payload.get("items", []))
        bookmark = payload.get("bookmark")
        if not bookmark:
            return boards


def create_board(access_token: str, name: str, description: str) -> dict:
    resp = requests.post(
        f"{API}/boards",
        json={"name": name, "description": description[:500], "privacy": "PUBLIC"},
        headers=_auth_headers(access_token), timeout=30,
    )
    if not resp.ok:
        raise SystemExit(f"ERROR: could not create board '{name}' ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def ensure_board(access_token: str, name: str, description: str, cache: dict) -> str:
    """Board id for `name`, creating the board on first use. `cache` is the
    name->id map from list_boards() and is updated in place."""
    if name in cache:
        return cache[name]
    board = create_board(access_token, name, description)
    cache[name] = board["id"]
    print(f"  created board: {name}")
    return board["id"]


def create_pin(access_token: str, board_id: str, title: str, description: str,
               link: str, image_url: str) -> dict:
    """Create a pin from a publicly reachable image URL.

    We pass the raw.githubusercontent.com URL of the committed pin PNG rather
    than uploading bytes — Pinterest fetches it itself, so there's no
    multipart upload path to maintain.
    """
    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:500],
        "link": link,
        "media_source": {"source_type": "image_url", "url": image_url},
    }
    resp = requests.post(f"{API}/pins", json=payload,
                         headers=_auth_headers(access_token), timeout=60)
    if not resp.ok:
        raise SystemExit(
            f"ERROR: pin creation failed ({resp.status_code}): {resp.text[:400]}\n"
            "If this says the app lacks permission, confirm the app has pins:write "
            "and that Trial access covers your own account."
        )
    return resp.json()
