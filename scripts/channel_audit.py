"""Show what is actually in each feed channel, with the track the scorer assigns."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db, discord_sync
from jobhunter.score import _best_track

API = "https://discord.com/api/v10"


def main() -> int:
    token, _ = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    tracks = config.profile().get("tracks") or {}

    conn = db.connect()
    by_url = {row["url"]: dict(row) for row in conn.execute("SELECT id, url, title, department FROM jobs")}
    conn.close()

    for cid in discord_sync.channel_ids():
        info = requests.get(f"{API}/channels/{cid}", headers=headers, timeout=20).json()
        messages = discord_sync.fetch_messages(cid, token, limit=50)
        print(f"\n#{info.get('name')} ({len(messages)} pesan)")
        for message in messages:
            for embed in message.get("embeds") or []:
                url = embed.get("url") or ""
                job = by_url.get(url)
                title = embed.get("title") or (job or {}).get("title") or "?"
                department = (job or {}).get("department") or ""
                best = _best_track(f"{title} {department}", tracks)
                track = best[1] if best else "(tidak cocok)"
                print(f"  {track:<14} {title[:56]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
