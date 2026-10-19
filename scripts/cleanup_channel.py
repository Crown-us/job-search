"""Delete the Job Hunter webhook messages from a specific channel.

Used to tidy the old #general after the webhook moved to #lowongan.

Run: python scripts/cleanup_channel.py <channel_id>
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, discord_sync

API = "https://discord.com/api/v10"


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python scripts/cleanup_channel.py <channel_id>")
        return 1
    target = argv[0]
    token, _ = discord_sync.credentials()
    webhook = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()

    messages = discord_sync.fetch_messages(target, token, limit=100)
    targets = [m for m in messages if (m.get("author") or {}).get("username") == "Job Hunter"]
    print(f"{len(targets)} pesan webhook di channel {target}")

    for message in targets:
        status = requests.delete(f"{webhook}/messages/{message['id']}", timeout=20).status_code
        print(f"  hapus {message['id']} -> {status}")
        time.sleep(0.4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
