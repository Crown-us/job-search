"""Offline proof that a human reaction updates the right job status.

Feeds a synthetic message (with the real message id) into sync, so Discord is
never touched and no real status changes stick.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db, discord_sync


def main() -> int:
    conn = db.connect()
    row = conn.execute(
        "SELECT d.message_id, j.id, j.title, j.status FROM deliveries d "
        "JOIN jobs j ON j.id = d.job_id "
        "WHERE d.message_id IS NOT NULL ORDER BY d.sent_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        print("belum ada pesan per-job yang tercatat")
        conn.close()
        return 1

    message_id, job_id, title, original = row
    print("job   :", title[:50], f"({job_id[:8]}) status sekarang: {original}")
    print("pesan :", message_id)

    fake = [{
        "id": message_id,
        "embeds": [],
        "reactions": [
            {"emoji": {"name": "\u2705"}, "count": 2, "me": False},
        ],
    }]
    original_fetch = discord_sync.fetch_messages
    discord_sync.fetch_messages = lambda *a, **k: fake
    try:
        result = discord_sync.sync(limit=5, dry_run=False)
    finally:
        discord_sync.fetch_messages = original_fetch

    print("hasil :", result["changed"])

    after = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
    print("status sesudah sync:", after)
    conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (original, job_id))
    conn.commit()
    conn.close()
    print("status dikembalikan ke:", original)
    return 0 if after == "applied" else 1


if __name__ == "__main__":
    raise SystemExit(main())
