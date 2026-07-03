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

Usage:
    pip install google-auth-oauthlib
    python generator/blogger_auth.py
"""

from __future__ import annotations

import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/blogger"]
ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET_FILE = ROOT / "generator" / "client_secret.json"


def main() -> int:
    if not CLIENT_SECRET_FILE.exists():
        print(f"Missing {CLIENT_SECRET_FILE}")
        print("Download OAuth client credentials (Desktop app type) from")
        print("Google Cloud Console and save them at that exact path, then re-run this script.")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    client_config = json.loads(CLIENT_SECRET_FILE.read_text())["installed"]

    print("\n" + "=" * 72)
    print("Authorization complete. Save these three values as GitHub repository")
    print("secrets (Settings -> Secrets and variables -> Actions -> New secret):")
    print("=" * 72)
    print(f"GOOGLE_CLIENT_ID     = {client_config['client_id']}")
    print(f"GOOGLE_CLIENT_SECRET = {client_config['client_secret']}")
    print(f"GOOGLE_REFRESH_TOKEN = {creds.refresh_token}")
    print("=" * 72)
    if not creds.refresh_token:
        print("\nWARNING: no refresh_token was returned. This usually means this")
        print("Google account already authorized this app before. Go to")
        print("https://myaccount.google.com/permissions , remove access for this")
        print("app, and run this script again to force a fresh consent.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
