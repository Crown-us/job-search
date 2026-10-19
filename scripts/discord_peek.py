"""Peek at the configured channel: who posted, what embeds, and why matching fails."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db, discord_sync

API = "https://discord.com/api/v10"


def ascii_safe(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


def main() -> int:
    token, channel_id = discord_sync.credentials()
    if not token or not channel_id:
        print("kredensial belum lengkap")
        return 1
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}

    print("server + channel yang terlihat bot:")
    guilds = requests.get(f"{API}/users/@me/guilds", headers=headers, timeout=20).json()
    for guild in guilds if isinstance(guilds, list) else []:
        print(f"  server: {guild.get('name')} ({guild.get('id')})")
        channels = requests.get(
            f"{API}/guilds/{guild.get('id')}/channels", headers=headers, timeout=20
        ).json()
        for item in channels if isinstance(channels, list) else []:
            if item.get("type") in (0, 5):
                marker = " <== dipakai" if item.get("id") == channel_id else ""
                print(f"    #{item.get('name'):<24} {item.get('id')}{marker}")

    messages = discord_sync.fetch_messages(channel_id, token, limit=20)
    print(f"\n{len(messages)} pesan terakhir di channel terpilih:")
    for message in messages[:10]:
        embeds = message.get("embeds") or []
        author = (message.get("author") or {}).get("username", "?")
        first = embeds[0] if embeds else {}
        print(
            f"  [{author}] embeds={len(embeds)} "
            f"title={ascii_safe(str(first.get('title', '-'))[:40])} "
            f"url={str(first.get('url', '-'))[:60]}"
        )

    conn = db.connect()
    sample = [row[0] for row in conn.execute("SELECT url FROM jobs LIMIT 3")]
    conn.close()
    print("\ncontoh url di database:")
    for url in sample:
        print(f"  {url[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
