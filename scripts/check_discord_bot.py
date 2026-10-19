"""Verify Discord bot credentials without printing the token.

Run: python scripts/check_discord_bot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db, discord_sync

API = "https://discord.com/api/v10"


def main() -> int:
    token, channel_id = discord_sync.credentials()
    print(f"token: {'terisi' if token else 'KOSONG'} ({len(token)} chars)")
    print(f"channel id: {channel_id or 'KOSONG'}")

    if not token or not channel_id:
        print("\n-> isi DISCORD_BOT_TOKEN dan DISCORD_CHANNEL_ID di .env")
        return 1

    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}

    me = requests.get(f"{API}/users/@me", headers=headers, timeout=20)
    if me.status_code != 200:
        print(f"\n-> token ditolak: HTTP {me.status_code}")
        return 1
    bot = me.json()
    print(f"bot: {bot.get('username')}#{bot.get('discriminator', '0')} (id {bot.get('id')})")

    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20)
    if channel.status_code != 200:
        print(f"\n-> channel tidak bisa dibuka: HTTP {channel.status_code}")
        if channel_id == bot.get("id"):
            print("   yang diisi adalah ID bot, bukan ID channel")
        print("   berikut channel yang bisa dilihat bot:\n")
        guilds = requests.get(f"{API}/users/@me/guilds", headers=headers, timeout=20).json()
        if not isinstance(guilds, list):
            print("   gagal membaca daftar server:", guilds)
            return 1
        for guild in guilds:
            print(f"   server: {guild.get('name')} (id {guild.get('id')})")
            channels = requests.get(
                f"{API}/guilds/{guild.get('id')}/channels", headers=headers, timeout=20
            ).json()
            if not isinstance(channels, list):
                print("     tidak bisa membaca channel")
                continue
            for item in channels:
                if item.get("type") in (0, 5):  # text + announcement
                    print(f"     #{item.get('name'):<28} id {item.get('id')}")
        print("\n   salin id channel yang benar ke DISCORD_CHANNEL_ID")
        return 1
    data = channel.json()
    print(f"channel: #{data.get('name')} (type {data.get('type')})")

    try:
        messages = discord_sync.fetch_messages(channel_id, token, limit=50)
    except Exception as exc:
        print(f"\n-> gagal membaca pesan: {exc}")
        return 1

    print(f"pesan terbaca: {len(messages)}")

    conn = db.connect()
    urls = {row[0] for row in conn.execute("SELECT url FROM jobs")}
    conn.close()

    matched = 0
    reacted = 0
    for message in messages:
        embeds = message.get("embeds") or []
        if any((e.get("url") or "") in urls for e in embeds):
            matched += 1
            if message.get("reactions"):
                reacted += 1
    print(f"pesan lowongan yang cocok dengan database: {matched}")
    print(f"di antaranya punya reaksi: {reacted}")
    print(f"\nlegenda: {discord_sync.legend()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
