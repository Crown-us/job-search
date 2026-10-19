"""Remove creative postings that landed in #dev-it, then let them be re-sent.

Deletes the bot's own messages whose job maps to a creative track, and clears
their delivery markers on both channels so the next run reposts them in #kreatif.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db, discord_sync
from jobhunter.score import _best_track

API = "https://discord.com/api/v10"
CREATIVE = {"marketing", "video_editor", "graphic_design", "social_media"}


def main(dry_run: bool) -> int:
    token, _ = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    channels = discord_sync.channel_ids()
    dev_id = channels[0]

    tracks = config.profile().get("tracks") or {}
    conn = db.connect()
    by_url = {row["url"]: row["id"] for row in conn.execute("SELECT id, url FROM jobs")}

    messages = discord_sync.fetch_messages(dev_id, token, limit=50)
    moved: list[str] = []
    for message in messages:
        for embed in message.get("embeds") or []:
            job_id = by_url.get(embed.get("url") or "")
            if not job_id:
                continue
            row = conn.execute(
                "SELECT title, department FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            best = _best_track(f"{row['title']} {row['department'] or ''}", tracks)
            if not best or best[1] not in CREATIVE:
                continue
            print(f"  pindah: {row['title'][:50]}  ({best[1]})")
            if not dry_run:
                status = requests.delete(
                    f"{API}/channels/{dev_id}/messages/{message['id']}",
                    headers=headers,
                    timeout=20,
                ).status_code
                print(f"    hapus dari dev-it -> {status}")
                conn.execute("DELETE FROM deliveries WHERE job_id = ?", (job_id,))
            moved.append(job_id)
            time.sleep(0.3)
            break

    if not dry_run:
        conn.commit()
    conn.close()
    print(f"\n{len(moved)} lowongan kreatif {'akan dipindah' if dry_run else 'dibersihkan'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
