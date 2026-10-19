"""Delete empty messages left behind by earlier failed sends.

Only touches messages authored by "Job Hunter" that have neither content nor
embeds nor attachments, so real digests are never removed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, discord_sync

API = "https://discord.com/api/v10"


def main(dry_run: bool = False) -> int:
    token, channel_id = discord_sync.credentials()
    webhook = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()
    if not token or not channel_id or not webhook:
        print("kredensial belum lengkap")
        return 1

    messages = discord_sync.fetch_messages(channel_id, token, limit=100)
    removed = 0
    for message in messages:
        author = (message.get("author") or {}).get("username")
        if author != "Job Hunter":
            continue
        empty = not (message.get("content") or "")
        if not empty or (message.get("embeds") or []) or (message.get("attachments") or []):
            continue
        if dry_run:
            print(f"  akan hapus {message['id']}")
        else:
            status = requests.delete(f"{webhook}/messages/{message['id']}", timeout=20).status_code
            print(f"  hapus {message['id']} -> {status}")
        removed += 1

    print(f"{removed} pesan kosong {'ditemukan' if dry_run else 'dihapus'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
