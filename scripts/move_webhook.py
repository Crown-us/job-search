"""Move the webhook, printing the actual API response instead of trusting status."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, discord_sync

API = "https://discord.com/api/v10"


def main(argv: list[str]) -> int:
    target = argv[0] if argv else ""
    token, _ = discord_sync.credentials()
    webhook_url = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()
    parts = webhook_url.rstrip("/").split("/")
    index = parts.index("webhooks")
    wid, wtoken = parts[index + 1], parts[index + 2]

    before = requests.get(f"{API}/webhooks/{wid}/{wtoken}", timeout=20).json()
    print("sebelum:", before.get("channel_id"))

    resp = requests.patch(
        f"{API}/webhooks/{wid}/{wtoken}",
        json={"channel_id": target},
        timeout=20,
    )
    print("status :", resp.status_code)
    try:
        body = resp.json()
        print("sesudah:", body.get("channel_id"))
        if body.get("channel_id") != target:
            print("body:", {k: body.get(k) for k in ("id", "name", "channel_id", "guild_id")})
    except Exception:
        print("body:", resp.text[:200])

    # also check whether the bot can manage webhooks in the target channel
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    channel = requests.get(f"{API}/channels/{target}", headers=headers, timeout=20).json()
    overwrites = channel.get("permission_overwrites") or []
    print(f"overwrites di #{channel.get('name')}: {len(overwrites)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
