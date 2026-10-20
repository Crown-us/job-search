"""Try to raise the bot's role above the picker roles.

Discord only lets a bot assign roles that sit below its own highest role. A bot
usually cannot move its own role, so this may legitimately fail — in that case
the owner has to drag it in Server Settings -> Roles.
"""

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
    bot_role = member["roles"][0]

    roles = requests.get(f"{API}/guilds/{guild_id}/roles", headers=headers, timeout=20).json()
    top = max((r.get("position", 0) for r in roles), default=0)
    print(f"posisi tertinggi sekarang: {top}")

    resp = requests.patch(
        f"{API}/guilds/{guild_id}/roles/{bot_role}",
        headers=headers,
        json={"position": top + 2},
        timeout=20,
    )
    print("patch:", resp.status_code, resp.text[:160] if resp.status_code >= 400 else "")

    if resp.status_code >= 400:
        print(
            "\nBot tidak bisa menaikkan role-nya sendiri.\n"
            "Di Discord: Server Settings -> Roles -> tarik 'Lokers' ke ATAS role\n"
            "'Developer', 'IT Support', 'AI & Automation', 'Marketing', 'Desain', 'Video'."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
