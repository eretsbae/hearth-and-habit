#!/usr/bin/env python3
"""One-time LOCAL helper: authorize this app against your Google account and
print the credentials to store as GitHub Actions secrets.

Run this on your own computer — NOT in CI. It opens a browser window for you
to log in with the Google account that owns peterpb.blogspot.com and approve
access.

Prerequisites (one-time, in Google Cloud Console):
  1. https://console.cloud.google.com -> create a project (any name).
  2. APIs & Services -> Library -> enable "Blogger API v3".
  3. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID.
     - If prompted, configure the OAuth consent screen first (External,
       add yourself as a test user is enough — this app is only used by you).
     - Application type: "Desktop app".
  4. Download the JSON and save it as generator/client_secret.json
     (this path is already in .gitignore — it will never be committed).
     No JSON? Newer Google Cloud clients only show the secret once. Just run
     the script: it asks for the client ID and a client secret instead (use
     "Add secret" on the client's page to get a fresh one; keep the old one
     enabled, since the GitHub secret still uses it).

Usage:
    pip install google-auth-oauthlib
    python generator/blogger_auth.py
"""

from __future__ import annotations

import getpass
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# webmasters.readonly lets weekly_report.py read Search Console queries/pages.
# Tokens minted before it was added keep working for Blogger; the report just
# skips the Search Console section until this script is re-run.
SCOPES = [
    "https://www.googleapis.com/auth/blogger",
    "https://www.googleapis.com/auth/webmasters.readonly",
]
ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET_FILE = ROOT / "generator" / "client_secret.json"


def client_config() -> tuple[dict, bool]:
    """(OAuth client config, came_from_file). Without client_secret.json, ask
    for the two values instead of making the user hand-write the JSON."""
    if CLIENT_SECRET_FILE.exists():
        return json.loads(CLIENT_SECRET_FILE.read_text()), True
    print(f"{CLIENT_SECRET_FILE} not found - enter the OAuth client values instead.")
    print("(Google Cloud -> Google Auth Platform -> Clients -> your Desktop client)")
    client_id = input("Client ID: ").strip()
    secret = getpass.getpass("Client secret (hidden; paste with right-click): ").strip()
    if not client_id or not secret:
        raise SystemExit("Both the client ID and the client secret are required.")
    return {"installed": {
        "client_id": client_id,
        "client_secret": secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}, False


def main() -> int:
    config, from_file = client_config()
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    # prompt=consent: always show the consent screen so Google returns a new
    # refresh token that carries every scope in SCOPES, even for an account
    # that already authorized an older, Blogger-only version of this app.
    creds = flow.run_local_server(port=0, prompt="consent")
    installed = config["installed"]

    print("\n" + "=" * 72)
    print("Authorization complete. Update these GitHub repository secrets")
    print("(Settings -> Secrets and variables -> Actions):")
    print("=" * 72)
    print(f"GOOGLE_CLIENT_ID     = {installed['client_id']}")
    if from_file:
        print(f"GOOGLE_CLIENT_SECRET = {installed['client_secret']}")
    else:
        print("GOOGLE_CLIENT_SECRET = (unchanged if the old secret is still enabled;")
        print("                        otherwise the secret you just typed)")
    print(f"GOOGLE_REFRESH_TOKEN = {creds.refresh_token}")
    print("=" * 72)
    if not creds.refresh_token:
        print("\nWARNING: no refresh_token was returned. Go to")
        print("https://myaccount.google.com/permissions , remove access for this")
        print("app, and run this script again to force a fresh consent.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
