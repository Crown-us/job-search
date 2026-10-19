"""POST one payload, then GET the very same message id and compare embeds."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db, discord_notify, discord_sync

API = "https://discord.com/api/v10"


def main() -> int:
    url = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()
    token, channel_id = discord_sync.credentials()

    conn = db.connect()
    rows = [dict(r) for r in conn.execute(
        "SELECT j.*, a.fit, a.gaps, a.strengths FROM jobs j "
        "LEFT JOIN analyses a ON a.job_id = j.id "
        "ORDER BY COALESCE(a.fit, j.score, 0) DESC LIMIT 2"
    )]
    conn.close()

    payload = discord_notify.build_payload(rows, 70)
    posted = requests.post(url, params={"wait": "true"}, json=payload, timeout=20).json()
    message_id = posted.get("id")
    print("POST status embeds:", len(posted.get("embeds") or []))
    print("POST channel_id   :", posted.get("channel_id"))
    print("POST message id   :", message_id)

    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    got = requests.get(
        f"{API}/channels/{posted.get('channel_id')}/messages/{message_id}",
        headers=headers,
        timeout=20,
    )
    print("GET by id status  :", got.status_code)
    if got.status_code == 200:
        body = got.json()
        print("GET embeds        :", len(body.get("embeds") or []))
        print("GET content len   :", len(body.get("content") or ""))
        print("GET keys          :", sorted(body.keys())[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
