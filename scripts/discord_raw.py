"""Dump the raw JSON of the newest (non-bot) webhook messages in the channel."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import discord_sync

API = "https://discord.com/api/v10"


def main() -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    messages = requests.get(
        f"{API}/channels/{channel_id}/messages",
        headers=headers,
        params={"limit": 20},
        timeout=20,
    ).json()

    for message in messages:
        author = (message.get("author") or {})
        if author.get("username") != "Job Hunter":
            continue
        print("=" * 70)
        print("id            :", message.get("id"))
        print("webhook_id    :", message.get("webhook_id"))
        print("content       :", repr((message.get("content") or "")[:120]))
        print("embeds        :", len(message.get("embeds") or []))
        print("attachments   :", len(message.get("attachments") or []))
        print("flags         :", message.get("flags"))
        print("keys          :", sorted(message.keys()))
        if message.get("embeds"):
            print("first embed   :", json.dumps(message["embeds"][0], ensure_ascii=True)[:400])
        break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
