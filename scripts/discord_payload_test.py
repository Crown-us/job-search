"""Post one real digest payload, inspect what Discord echoes back, then delete it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db, discord_notify


def main() -> int:
    url = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()
    conn = db.connect()
    rows = [dict(r) for r in conn.execute(
        "SELECT j.*, a.fit, a.gaps, a.strengths FROM jobs j "
        "LEFT JOIN analyses a ON a.job_id = j.id "
        "ORDER BY COALESCE(a.fit, j.score, 0) DESC LIMIT 1"
    )]
    conn.close()

    payload = discord_notify.build_payload(rows, 70)
    print("kirim:", json.dumps(payload, ensure_ascii=True)[:220], "...")

    resp = requests.post(url, params={"wait": "true"}, json=payload, timeout=20)
    print("status:", resp.status_code)
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    print("returned content:", repr((body.get("content") or "")[:80]))
    print("returned embeds :", len(body.get("embeds") or []))
    if body.get("embeds"):
        first = body["embeds"][0]
        print("embed title     :", first.get("title"))
        print("embed url       :", first.get("url"))
        print("embed fields    :", len(first.get("fields") or []))
    if not body.get("embeds"):
        print("RAW:", resp.text[:400])

    if body.get("id"):
        print("delete:", requests.delete(f"{url}/messages/{body['id']}", timeout=20).status_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
