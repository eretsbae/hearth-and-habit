"""Encrypted OAuth-token storage shared by the Kakao and Pinterest clients.

Both services hand out refresh tokens that must survive between unattended
workflow runs, and both rotate them often enough that "just put it in a
repository secret" fails — GitHub Actions cannot update its own secrets with
the default token. So the token lives in the repo as .secrets/<name>.enc,
encrypted with a passphrase that stays in a repository secret; the workflow
decrypts it, refreshes, and commits the re-encrypted file when the provider
rotates the token.

PBKDF2 + Fernet from `cryptography` — pure Python, so this behaves the same
on the user's Windows machine and on the Ubuntu runner (an earlier version
shelled out to the openssl binary and crashed on Windows).

The on-disk format is unchanged from when this lived in kakao_client.py, so
tokens encrypted by older versions still decrypt.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
SECRETS_DIR = ROOT / ".secrets"

_MAGIC = b"HHKT1"  # file format marker + version (kept for backward compatibility)
_SALT_LEN = 16
_PBKDF2_ITERATIONS = 600_000


def _fernet(passphrase: str, salt: bytes) -> Fernet:
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, _PBKDF2_ITERATIONS)
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_token_file(data: dict, passphrase: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(_SALT_LEN)
    token = _fernet(passphrase, salt).encrypt(json.dumps(data).encode())
    path.write_bytes(_MAGIC + salt + token)


def decrypt_token_file(passphrase: str, path: Path, recreate_hint: str = "") -> dict:
    if not path.exists():
        raise SystemExit(f"ERROR: {path} not found. {recreate_hint}".rstrip())
    raw = path.read_bytes()
    if not raw.startswith(_MAGIC):
        raise SystemExit(
            f"ERROR: {path} is not in the expected format (bad header). {recreate_hint}".rstrip()
        )
    salt = raw[len(_MAGIC):len(_MAGIC) + _SALT_LEN]
    token = raw[len(_MAGIC) + _SALT_LEN:]
    return json.loads(_fernet(passphrase, salt).decrypt(token))
