"""Create the #remote feed channel, read-only for @everyone."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import discord_sync

API = "https://discord.com/api/v10"
SEND_MESSAGES = 1 << 11
VIEW_CHANNEL = 1 << 10


def main(dry_run: bool) -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    guild_id = channel.get("guild_id")
    parent_id = channel.get("parent_id")
    guild = requests.get(f"{API}/guilds/{guild_id}", headers=headers, timeout=20).json()
    owner_id = guild.get("owner_id")
    bot_id = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()["id"]

    existing = requests.get(f"{API}/guilds/{guild_id}/channels", headers=headers, timeout=20).json()
    found = next((c for c in existing if c.get("name") == "remote"), None)
    if found:
        print(f"#remote sudah ada: {found['id']}")
        return 0

    overwrites = [
        {"id": guild_id, "type": 0, "allow": "0", "deny": str(SEND_MESSAGES)},
        {"id": owner_id, "type": 1, "allow": str(SEND_MESSAGES), "deny": "0"},
        {"id": bot_id, "type": 1, "allow": str(SEND_MESSAGES), "deny": "0"},
    ]
    body = {
        "name": "remote",
        "type": 0,
        "topic": "lowongan remote dari Remotive, Jobicy, Himalayas, RemoteOK",
        "permission_overwrites": overwrites,
    }
    if parent_id:
        body["parent_id"] = parent_id

    if dry_run:
        print("[dry] buat #remote")
        return 0

    resp = requests.post(
        f"{API}/guilds/{guild_id}/channels", headers=headers, json=body, timeout=20
    )
    if resp.status_code not in (200, 201):
        print("gagal:", resp.status_code, resp.text[:160])
        return 1
    print(f"#remote dibuat: {resp.json()['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
