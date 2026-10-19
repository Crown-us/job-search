"""Decode what the bot is actually allowed to do in its guild."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import discord_sync

API = "https://discord.com/api/v10"

PERMS = {
    "ADMINISTRATOR": 1 << 3,
    "VIEW_CHANNEL": 1 << 10,
    "SEND_MESSAGES": 1 << 11,
    "MANAGE_MESSAGES": 1 << 13,
    "MANAGE_CHANNELS": 1 << 4,
    "MANAGE_ROLES": 1 << 28,
    "MANAGE_GUILD": 1 << 5,
    "READ_MESSAGE_HISTORY": 1 << 16,
    "ADD_REACTIONS": 1 << 6,
    "EMBED_LINKS": 1 << 14,
    "ATTACH_FILES": 1 << 15,
    "KICK_MEMBERS": 1 << 1,
    "BAN_MEMBERS": 1 << 2,
    "MENTION_EVERYONE": 1 << 17,
    "CREATE_PUBLIC_THREADS": 1 << 35,
    "CREATE_PRIVATE_THREADS": 1 << 36,
    "MANAGE_THREADS": 1 << 34,
}


def main() -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}

    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    guild_id = channel.get("guild_id")
    print(f"server: {guild_id}  channel: #{channel.get('name')}")

    guild = requests.get(
        f"{API}/guilds/{guild_id}", headers=headers, params={"with_counts": "true"}, timeout=20
    ).json()
    print(f"nama server : {guild.get('name')}")
    print(f"owner id    : {guild.get('owner_id')}")
    print(f"jumlah anggota (perkiraan): {guild.get('approximate_member_count')}")

    me = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()
    member = requests.get(
        f"{API}/guilds/{guild_id}/members/{me['id']}", headers=headers, timeout=20
    )
    if member.status_code != 200:
        print("tidak bisa membaca member bot:", member.status_code)
        return 1
    roles = member.json().get("roles") or []

    all_roles = requests.get(f"{API}/guilds/{guild_id}/roles", headers=headers, timeout=20).json()
    everyone = next((r for r in all_roles if r.get("name") == "@everyone"), {})

    bits = int(everyone.get("permissions") or 0)
    for role in all_roles:
        if role.get("id") in roles:
            bits |= int(role.get("permissions") or 0)

    print(f"role bot: {len(roles)} | admin: {bool(bits & PERMS['ADMINISTRATOR'])}\n")
    allowed, denied = [], []
    for name, bit in PERMS.items():
        (allowed if bits & bit else denied).append(name)

    print("BOLEH:")
    for name in allowed:
        print("  +", name)
    print("\nTIDAK BOLEH:")
    for name in denied:
        print("  -", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
