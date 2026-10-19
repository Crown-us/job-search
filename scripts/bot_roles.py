"""Print the bot's roles by name, so permission edits target the right one."""

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

    me = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()
    member = requests.get(
        f"{API}/guilds/{guild_id}/members/{me['id']}", headers=headers, timeout=20
    ).json()
    role_ids = set(member.get("roles") or [])

    roles = requests.get(f"{API}/guilds/{guild_id}/roles", headers=headers, timeout=20).json()
    print(f"bot: {me.get('username')} ({me.get('id')})")
    print("role yang dipegang bot:")
    for role in sorted(roles, key=lambda r: r.get("position", 0), reverse=True):
        if role.get("id") in role_ids:
            flags = []
            if role.get("managed"):
                flags.append("managed/integration")
            if int(role.get("permissions") or 0) & (1 << 3):
                flags.append("ADMIN")
            print(f"  - {role.get('name')}  id={role.get('id')} {' '.join(flags)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
