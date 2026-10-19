"""Split the feed: #lowongan becomes #dev-it, and a new #kreatif is created.

Both stay read-only for @everyone; the bot and the owner keep posting rights.
Renaming keeps the existing channel id, so the five digest messages already there
are preserved and the webhook/bot target does not change.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, discord_sync

API = "https://discord.com/api/v10"

VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
READ_MESSAGE_HISTORY = 1 << 16


def main(dry_run: bool) -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}

    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    guild_id = channel.get("guild_id")
    parent_id = channel.get("parent_id")
    guild = requests.get(f"{API}/guilds/{guild_id}", headers=headers, timeout=20).json()
    owner_id = guild.get("owner_id")
    me = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()
    bot_id = me["id"]

    # 1. rename the current feed
    if channel.get("name") == "dev-it":
        print("#dev-it sudah ada, skip rename")
        dev_id = channel_id
    elif dry_run:
        dev_id = channel_id
        print(f"[dry] rename #{channel.get('name')} -> #dev-it")
    else:
        resp = requests.patch(
            f"{API}/channels/{channel_id}", headers=headers, json={"name": "dev-it"}, timeout=20
        )
        print(f"rename -> #dev-it: {resp.status_code}")
        dev_id = channel_id

    existing = requests.get(f"{API}/guilds/{guild_id}/channels", headers=headers, timeout=20).json()
    kreatif = next((c for c in existing if c.get("name") == "kreatif"), None)

    overwrites = [
        {"id": guild_id, "type": 0, "allow": "0", "deny": str(SEND_MESSAGES)},
        {"id": owner_id, "type": 1, "allow": str(SEND_MESSAGES), "deny": "0"},
        {"id": bot_id, "type": 1, "allow": str(SEND_MESSAGES), "deny": "0"},
    ]

    if kreatif:
        kreatif_id = kreatif["id"]
        print(f"#kreatif sudah ada ({kreatif_id})")
    elif dry_run:
        kreatif_id = None
        print("[dry] buat #kreatif di kategori yang sama, read-only untuk @everyone")
    else:
        body = {
            "name": "kreatif",
            "type": 0,
            "topic": "lowongan marketing, desain, video, dan social media",
            "permission_overwrites": overwrites,
        }
        if parent_id:
            body["parent_id"] = parent_id
        resp = requests.post(
            f"{API}/guilds/{guild_id}/channels", headers=headers, json=body, timeout=20
        )
        if resp.status_code not in (200, 201):
            print("gagal buat #kreatif:", resp.status_code, resp.text[:140])
            return 1
        kreatif_id = resp.json()["id"]
        print(f"#kreatif dibuat ({kreatif_id})")

    # 2. make sure the new channel is not writable by everyone
    if kreatif_id and not dry_run:
        for target, kind, allow, deny in [
            (guild_id, 0, "0", str(SEND_MESSAGES)),
            (bot_id, 1, str(SEND_MESSAGES), "0"),
            (owner_id, 1, str(SEND_MESSAGES), "0"),
        ]:
            status = requests.put(
                f"{API}/channels/{kreatif_id}/permissions/{target}",
                headers=headers,
                json={"type": kind, "allow": allow, "deny": deny},
                timeout=20,
            ).status_code
            print(f"  overwrite {target} -> {status}")

    print(f"\nDEV_IT_ID={dev_id}")
    print(f"KREATIF_ID={kreatif_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
