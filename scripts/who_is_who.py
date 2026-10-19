"""Who owns the server, and who else is in it."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import discord_sync

API = "https://discord.com/api/v10"


def main() -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    guild_id = channel.get("guild_id")

    guild = requests.get(
        f"{API}/guilds/{guild_id}", headers=headers, params={"with_counts": "true"}, timeout=20
    ).json()
    owner_id = guild.get("owner_id")
    print(f"server     : {guild.get('name')} ({guild_id})")
    print(f"anggota    : {guild.get('approximate_member_count')}")
    print(f"owner id   : {owner_id}")

    owner = requests.get(f"{API}/users/{owner_id}", headers=headers, timeout=20).json()
    print(f"owner      : {owner.get('username')}#{owner.get('discriminator', '0')}")

    members = requests.get(
        f"{API}/guilds/{guild_id}/members", headers=headers, params={"limit": 20}, timeout=20
    )
    if members.status_code == 200:
        print("member:")
        for member in members.json():
            user = member.get("user") or {}
            print(f"  - {user.get('username')} (bot={user.get('bot', False)})")
    else:
        print("member list butuh GUILD_MEMBERS intent:", members.status_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
