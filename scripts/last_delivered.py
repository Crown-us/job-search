"""Show the most recent deliveries: message id, job id, title, letter availability."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db


def main() -> int:
    letters = config.DATA_DIR / "letters"
    conn = db.connect()
    rows = conn.execute(
        "SELECT d.message_id, j.id, j.title, j.company FROM deliveries d "
        "JOIN jobs j ON j.id = d.job_id WHERE d.channel='discord' "
        "ORDER BY d.sent_at DESC, d.rowid DESC LIMIT 8"
    ).fetchall()
    for message_id, job_id, title, company in rows:
        has = bool(list(letters.glob(f"{job_id[:8]}-*.md"))) if letters.exists() else False
        print(f"{job_id[:8]}  surat={'ada ' if has else 'TIDAK'}  {title[:48]:<50} {company[:24]}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
