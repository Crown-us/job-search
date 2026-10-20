"""Print the rendered embed of the newest message in a feed channel."""

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
    messages = discord_sync.fetch_messages(channel_id, token, limit=3)
    if not messages:
        print("tidak ada pesan")
        return 0
    message = messages[-1] if len(messages) > 1 else messages[0]
    content = (message.get("content") or "").encode("ascii", "replace").decode("ascii")
    print("content:", content)
    for embed in message.get("embeds") or []:
        print(json.dumps({
            "author": embed.get("author"),
            "title": embed.get("title"),
            "description": embed.get("description"),
            "color": hex(embed.get("color") or 0),
            "fields": embed.get("fields"),
            "footer": embed.get("footer"),
            "timestamp": embed.get("timestamp"),
        }, indent=1, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
