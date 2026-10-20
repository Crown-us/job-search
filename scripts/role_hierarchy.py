"""Show role hierarchy: where the bot's role sits versus the picker roles."""

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
    guild_id = channel["guild_id"]

    me = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()
    member = requests.get(
        f"{API}/guilds/{guild_id}/members/{me['id']}", headers=headers, timeout=20
    ).json()
    my_roles = set(member.get("roles") or [])

    roles = requests.get(f"{API}/guilds/{guild_id}/roles", headers=headers, timeout=20).json()
    roles.sort(key=lambda r: r.get("position", 0), reverse=True)

    print("posisi role (atas = lebih tinggi):")
    for role in roles:
        mark = " <== bot" if role["id"] in my_roles else ""
        print(f"  {role.get('position'):>3}  {role['name'][:28]:<30}{mark}")

    my_pos = max((r.get("position", 0) for r in roles if r["id"] in my_roles), default=-1)
    need = ["Developer", "IT Support", "AI & Automation", "Marketing", "Desain", "Video"]
    blocked = [r["name"] for r in roles if r["name"] in need and r.get("position", 0) >= my_pos]
    print(f"\nrole bot di posisi {my_pos}")
    print("tidak bisa diberikan (di atas/ sama dengan bot):", blocked or "tidak ada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
