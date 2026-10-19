"""Reset the Discord channel to a clean state.

Deletes every message authored by the "Job Hunter" webhook, then clears the
delivery markers so the same postings can be sent again in the new format.

Only touches messages the webhook itself created; other members' messages and
system messages are left alone.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db, discord_sync

API = "https://discord.com/api/v10"


def main(dry_run: bool = False) -> int:
    token, channel_id = discord_sync.credentials()
    webhook = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()
    if not token or not channel_id or not webhook:
        print("kredensial belum lengkap")
        return 1

    messages = discord_sync.fetch_messages(channel_id, token, limit=100)
    targets = [
        m for m in messages
        if (m.get("author") or {}).get("username") == "Job Hunter"
    ]
    print(f"{len(targets)} pesan webhook ditemukan di channel")

    deleted = 0
    for message in targets:
        label = f"{message.get('id')} type={message.get('type')}"
        if dry_run:
            print("  akan hapus", label)
            continue
        status = requests.delete(f"{webhook}/messages/{message['id']}", timeout=20).status_code
        print(f"  hapus {label} -> {status}")
        if status in (200, 204):
            deleted += 1
        time.sleep(0.4)

    if dry_run:
        return 0

    conn = db.connect()
    before = conn.execute("SELECT COUNT(*) FROM deliveries WHERE channel = 'discord'").fetchone()[0]
    conn.execute("DELETE FROM deliveries WHERE channel = 'discord'")
    conn.commit()
    conn.close()
    print(f"\n{deleted} pesan dihapus, {before} penanda kirim direset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
