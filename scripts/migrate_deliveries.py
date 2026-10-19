"""Move delivery markers from the generic 'discord' key to the dev-it channel id.

Needed once after splitting the feed, so --only-new keeps knowing what was
already posted to the main channel.

Run: python scripts/migrate_deliveries.py <dev_channel_id>
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import db


def main(argv: list[str]) -> int:
    target = argv[0] if argv else ""
    if not target:
        print("usage: python scripts/migrate_deliveries.py <channel_id>")
        return 1
    conn = db.connect()
    before = conn.execute("SELECT COUNT(*) FROM deliveries WHERE channel = 'discord'").fetchone()[0]
    conn.execute("UPDATE deliveries SET channel = ? WHERE channel = 'discord'", (target,))
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM deliveries WHERE channel = ?", (target,)).fetchone()[0]
    conn.close()
    print(f"{before} penanda dipindah ke {target} (total {after})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
