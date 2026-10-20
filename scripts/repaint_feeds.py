"""Wipe the bot's messages from every feed channel and clear their markers.

Used after a visual redesign so old and new cards do not sit side by side.

Run: python scripts/repaint_feeds.py [--dry-run]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db, discord_sync

API = "https://discord.com/api/v10"


def main(dry_run: bool) -> int:
    token, _ = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    bot_id = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()["id"]

    conn = db.connect()
    for cid in discord_sync.channel_ids():
        info = requests.get(f"{API}/channels/{cid}", headers=headers, timeout=20).json()
        messages = discord_sync.fetch_messages(cid, token, limit=100)
        mine = [m for m in messages if (m.get("author") or {}).get("id") == bot_id]
        print(f"#{info.get('name')}: {len(mine)} pesan bot")
        if dry_run:
            continue
        for message in mine:
            status = requests.delete(
                f"{API}/channels/{cid}/messages/{message['id']}", headers=headers, timeout=20
            ).status_code
            print(f"  hapus {message['id']} -> {status}")
            time.sleep(0.3)
        removed = conn.execute("DELETE FROM deliveries WHERE channel = ?", (cid,)).rowcount
        conn.commit()
        print(f"  {removed} penanda direset")

    conn.close()
    print("dry run" if dry_run else "selesai")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
