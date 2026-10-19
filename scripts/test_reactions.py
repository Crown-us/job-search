"""Prove reactions are readable without the Message Content intent.

The bot adds a reaction, we read the message back, then remove it again.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db, discord_sync

API = "https://discord.com/api/v10"
EMOJI = "✅"


def main() -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}

    conn = db.connect()
    row = conn.execute(
        "SELECT message_id FROM deliveries WHERE message_id IS NOT NULL ORDER BY sent_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        print("belum ada message_id tersimpan")
        return 1
    message_id = row[0]
    print("message:", message_id)

    encoded = quote(EMOJI)
    add = requests.put(
        f"{API}/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me",
        headers=headers,
        timeout=20,
    )
    print("tambah reaksi:", add.status_code)
    time.sleep(1.5)

    got = requests.get(
        f"{API}/channels/{channel_id}/messages/{message_id}", headers=headers, timeout=20
    )
    print("baca pesan   :", got.status_code)
    if got.status_code == 200:
        body = got.json()
        reactions = body.get("reactions") or []
        names = [
            ((r.get("emoji") or {}).get("name") or "?") for r in reactions
        ]
        names = [n.encode("ascii", "replace").decode("ascii") for n in names]
        print("reactions    :", len(reactions), names)
        print("embeds       :", len(body.get("embeds") or []))
        print("content len  :", len(body.get("content") or ""))
        if reactions:
            print("\n-> reaksi TERBACA tanpa intent. sync akan jalan.")
        else:
            print("\n-> reactions kosong: intent tetap perlu dinyalakan.")

    remove = requests.delete(
        f"{API}/channels/{channel_id}/messages/{message_id}/reactions/{encoded}/@me",
        headers=headers,
        timeout=20,
    )
    print("hapus reaksi :", remove.status_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
