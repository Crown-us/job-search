"""Check whether the bot has the privileged Message Content intent enabled."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import discord_sync

API = "https://discord.com/api/v10"
GATEWAY_MESSAGE_CONTENT = 1 << 18
GATEWAY_MESSAGE_CONTENT_LIMITED = 1 << 19


def main() -> int:
    token, _ = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    resp = requests.get(f"{API}/applications/@me", headers=headers, timeout=20)
    if resp.status_code != 200:
        print("gagal membaca aplikasi:", resp.status_code, resp.text[:120])
        return 1

    app = resp.json()
    flags = int(app.get("flags") or 0)
    print("aplikasi:", app.get("name"), f"(id {app.get('id')})")
    print("flags   :", flags)
    print("MESSAGE_CONTENT        :", bool(flags & GATEWAY_MESSAGE_CONTENT))
    print("MESSAGE_CONTENT_LIMITED:", bool(flags & GATEWAY_MESSAGE_CONTENT_LIMITED))

    enabled = bool(flags & (GATEWAY_MESSAGE_CONTENT | GATEWAY_MESSAGE_CONTENT_LIMITED))
    if enabled:
        print("\n-> intent aktif. Kalau pesan masih kosong, tunggu 1-2 menit lalu ulangi.")
    else:
        print("\n-> intent BELUM aktif.")
        print("   Developer Portal -> aplikasi -> Bot -> Privileged Gateway Intents")
        print("   nyalakan MESSAGE CONTENT INTENT -> Save Changes")
        print("   (bot tidak perlu di-restart untuk REST; toggle-nya yang penting)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
