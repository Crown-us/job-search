"""Where does the webhook actually post, and can the bot read that channel?"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, discord_sync

API = "https://discord.com/api/v10"


def main() -> int:
    token, channel_id = discord_sync.credentials()
    webhook_url = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()
    parts = webhook_url.rstrip("/").split("/")
    index = parts.index("webhooks")
    wid, wtoken = parts[index + 1], parts[index + 2]

    hook = requests.get(f"{API}/webhooks/{wid}/{wtoken}", timeout=20).json()
    print("webhook channel_id:", hook.get("channel_id"))
    print("env channel_id    :", channel_id)
    print("sama?             :", hook.get("channel_id") == channel_id)

    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    print("\nchannel name      :", channel.get("name"))
    print("parent_id         :", channel.get("parent_id"))
    print("permission overwrites:")
    for ow in channel.get("permission_overwrites") or []:
        print("  ", ow.get("type"), ow.get("id"), "allow", ow.get("allow"), "deny", ow.get("deny"))

    msgs = requests.get(
        f"{API}/channels/{channel_id}/messages", headers=headers, params={"limit": 10}, timeout=20
    )
    print("\nGET messages:", msgs.status_code, "count:", len(msgs.json()) if msgs.status_code == 200 else msgs.text[:120])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
