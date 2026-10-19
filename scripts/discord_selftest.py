"""Send one minimal message, print what Discord returns, then delete it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config


def main() -> int:
    url = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()
    if not url:
        print("webhook kosong")
        return 1

    payload = {
        "content": "selftest",
        "embeds": [{"title": "selftest", "description": "embed uji", "color": 0x2F9E5F}],
    }
    resp = requests.post(url, params={"wait": "true"}, json=payload, timeout=20)
    print("status:", resp.status_code)
    try:
        body = resp.json()
    except json.JSONDecodeError:
        print("body bukan json:", resp.text[:200])
        return 1

    print("returned content:", repr(body.get("content")))
    print("returned embeds :", len(body.get("embeds") or []))
    print("message id      :", body.get("id"))

    message_id = body.get("id")
    if message_id:
        delete = requests.delete(f"{url}/messages/{message_id}", timeout=20)
        print("delete status   :", delete.status_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
