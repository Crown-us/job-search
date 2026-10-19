"""List every channel in the guild with type and category."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import discord_sync

API = "https://discord.com/api/v10"
TYPES = {0: "text", 2: "voice", 4: "category", 5: "announcement", 13: "stage", 15: "forum"}


def main() -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    guild_id = channel.get("guild_id")
    channels = requests.get(f"{API}/guilds/{guild_id}/channels", headers=headers, timeout=20).json()
    parents = {c["id"]: c["name"] for c in channels if c.get("type") == 4}
    for item in sorted(channels, key=lambda c: (c.get("position", 0), c.get("name", ""))):
        parent = parents.get(item.get("parent_id"), "-")
        print(
            f"  {TYPES.get(item.get('type'), item.get('type')):<10} "
            f"#{item.get('name'):<22} id={item.get('id')} kategori={parent}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
