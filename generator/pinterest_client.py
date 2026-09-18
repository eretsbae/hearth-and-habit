"""Pinterest API v5 client — OAuth refresh, boards, and pin creation.

Why Pinterest: Search Console reports every post as "Discovered - currently
not indexed" because the site has no inbound links anywhere on the web. Pins
are real crawlable links AND send actual readers, and Pinterest ranks pins
without caring about domain authority — the one channel a three-week-old
blogspot can compete in today.

Access model (verified live 2026-09-13): "Trial access" lets the app read
production data and create pins ONLY against the API sandbox
(api-sandbox.pinterest.com), which never touches the real profile. A
production POST /pins returns 403 code 29. Creating real pins needs
*Standard* access, requested with the "Upgrade" button on the app page and
reviewed by Pinterest. Trial access itself took 2026-06 -> 2026-09-13 to be
granted. Until Standard access lands, pins go up through the bulk-CSV route
(make_bulk_csv.py), which is the working path, not a fallback.

Token storage follows the same encrypted-file pattern as Kakao — see
token_store.py for why repository secrets alone don't work.
"""

from __future__ import annotations

import base64
from pathlib import Path

import requests

import token_store

API_PRODUCTION = "https://api.pinterest.com/v5"
# Trial-access apps may create pins only here. Same OAuth token, same request
# shapes, but nothing created lands on the real profile — it exists so an app
# can be exercised (and demoed for the Standard-access review) before it is
# allowed to write to production.
API_SANDBOX = "https://api-sandbox.pinterest.com/v5"
API = API_PRODUCTION
OAUTH_AUTHORIZE = "https://www.pinterest.com/oauth/"
OAUTH_TOKEN = f"{API_PRODUCTION}/oauth/token"
# The sandbox does not accept production access tokens (401 "Authentication
# failed", seen 2026-09-13). It has its own token endpoint, and the developer
# portal can also mint a 30-day sandbox token directly (app page -> Manage).
OAUTH_TOKEN_SANDBOX = f"{API_SANDBOX}/oauth/token"


def use_sandbox() -> None:
    """Route every data call (boards, pins, user account) at the sandbox."""
    global API
    API = API_SANDBOX

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
        body = resp.text.strip()
        try:
            parsed = resp.json()
        except ValueError:
            parsed = None
        err_code = parsed.get("code") if isinstance(parsed, dict) else None
        if resp.status_code == 401 and err_code == 2:
            # Pinterest rejected the Basic auth header itself (observed 2026-09-18:
            # a mistyped App secret gives code 2; a bad/reused code gives code 283).
            hint = ("Pinterest rejected the App ID / App secret pair, not the code. "
                    "Set PINTEREST_APP_ID and PINTEREST_APP_SECRET in the environment "
                    "so nothing is typed, and check the secret was not regenerated on "
                    "the developer portal.")
        else:
            hint = ("Check that the redirect URI matches the one registered on the app "
                    "exactly, and that the code was pasted whole and hasn't already been "
                    "used (each code works once and expires within minutes).")
        raise SystemExit(
            f"ERROR: Pinterest code exchange failed ({resp.status_code}): {body}\n{hint}"
        )
    return resp.json()


def refresh_access_token(app_id: str, app_secret: str, refresh_token: str,
                         sandbox: bool = False) -> dict:
    resp = requests.post(
        OAUTH_TOKEN_SANDBOX if sandbox else OAUTH_TOKEN,
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


def get_user_account(access_token: str) -> dict:
    """The authenticated account: username, account_type, profile URL."""
    resp = requests.get(f"{API}/user_account", headers=_auth_headers(access_token), timeout=30)
    if not resp.ok:
        raise SystemExit(f"ERROR: could not read user account ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def list_boards(access_token: str) -> list[dict]:
    boards, bookmark = [], None
    while True:
        # privacy=ALL: secret/protected boards count too, and the sandbox
        # has been seen to hide boards from the default listing while still
        # rejecting a create for the same name (code 58).
        params = {"page_size": 100, "privacy": "ALL"}
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


class BoardNameTaken(SystemExit):
    """POST /boards refused with code 58: a board with this name exists but
    the listing did not return it (seen on the sandbox, 2026-09-18)."""


def create_board(access_token: str, name: str, description: str) -> dict:
    resp = requests.post(
        f"{API}/boards",
        json={"name": name, "description": description[:500], "privacy": "PUBLIC"},
        headers=_auth_headers(access_token), timeout=30,
    )
    if resp.status_code == 400 and '"code":58' in resp.text.replace(" ", ""):
        raise BoardNameTaken(f"ERROR: could not create board '{name}' (400): {resp.text[:300]}")
    if not resp.ok:
        raise SystemExit(f"ERROR: could not create board '{name}' ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def board_key(name: str) -> str:
    """Case- and whitespace-insensitive board name, for matching boards that
    were created by hand against the pillar names in topics.yml."""
    return " ".join(name.split()).casefold()


def board_index(boards: list[dict]) -> dict[str, str]:
    """board_key(name) -> id for the boards list_boards() returned."""
    return {board_key(b["name"]): b["id"] for b in boards}


def ensure_board(access_token: str, name: str, description: str, cache: dict) -> str:
    """Board id for `name`, creating the board on first use. `cache` is the
    board_index() map and is updated in place.

    The five pillar boards were created by hand during the months the API was
    pending, so the lookup must find them however Pinterest normalised the
    name; creating a near-duplicate board would split each pillar's pins
    across two boards."""
    key = board_key(name)
    if key in cache:
        return cache[key]
    try:
        board = create_board(access_token, name, description)
    except BoardNameTaken:
        if API != API_SANDBOX:
            raise
        # Sandbox only: the hidden board cannot be addressed, so demo on a
        # visibly-named twin rather than abort the recording. The listing
        # stays empty run after run, so the twin from a previous run collides
        # too; fall through to a timestamped name in that case.
        import datetime
        stamp = datetime.datetime.now().strftime("%m%d-%H%M")
        base = name
        for name in (f"{base} (sandbox)", f"{base} (sandbox {stamp})"):
            print(f"  sandbox hides an existing '{base}' board; trying '{name}'")
            try:
                board = create_board(access_token, name, description)
                break
            except BoardNameTaken:
                continue
        else:
            raise SystemExit(f"ERROR: sandbox refuses every name for '{base}' (code 58)")
    cache[key] = board["id"]
    print(f"  created board: {name}")
    return board["id"]


class TrialAccessOnly(SystemExit):
    """Pinterest refused a production write because the app only has Trial
    access (HTTP 403, code 29). Trial access can read production data but may
    only *create* pins against the sandbox host, which never reaches the real
    profile. Production pin creation needs Standard access, requested with
    the "Upgrade" button on the app page."""


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
    if resp.status_code == 403 and '"code":29' in resp.text.replace(" ", ""):
        raise TrialAccessOnly(resp.text[:300])
    if not resp.ok:
        raise SystemExit(
            f"ERROR: pin creation failed ({resp.status_code}): {resp.text[:400]}\n"
            "If this says the app lacks permission, confirm the app has pins:write."
        )
    return resp.json()
