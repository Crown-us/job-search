"""Print why a stored message looks empty: type, flags, webhook id, author."""

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
    messages = requests.get(
        f"{API}/channels/{channel_id}/messages",
        headers=headers,
        params={"limit": 5},
        timeout=20,
    ).json()
    for message in messages:
        print(
            f"id={message.get('id')} "
            f"type={message.get('type')} "
            f"flags={message.get('flags')} "
            f"author={(message.get('author') or {}).get('username')} "
            f"webhook={message.get('webhook_id')} "
            f"content={len(message.get('content') or '')} "
            f"embeds={len(message.get('embeds') or [])} "
            f"attachments={len(message.get('attachments') or [])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
