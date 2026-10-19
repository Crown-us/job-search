"""Group stored postings by career track and show the best of each.

Run: python scripts/track_report.py [--per-track 5]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db
from jobhunter.score import _best_track


def main(argv: list[str]) -> int:
    per_track = 5
    if "--per-track" in argv:
        per_track = int(argv[argv.index("--per-track") + 1])

    profile = config.profile()
    tracks = profile.get("tracks") or {}
    labels = {name: (spec.get("label") or name) for name, spec in tracks.items()}

    conn = db.connect()
    rows = conn.execute(
        """
        SELECT j.title, j.company, j.location, j.source, j.score, j.status, a.fit
        FROM jobs j LEFT JOIN analyses a ON a.job_id = j.id
        WHERE j.status IN ('new', 'shortlist')
        ORDER BY COALESCE(a.fit, j.score, 0) DESC
        """
    ).fetchall()
    conn.close()

    groups: dict[str, list] = {name: [] for name in tracks}
    groups["lainnya"] = []

    for row in rows:
        headline = f"{row['title']} {''}"
        best = _best_track(headline, tracks)
        key = best[1] if best else "lainnya"
        groups.setdefault(key, []).append(row)

    for name, label in labels.items():
        items = groups.get(name) or []
        print(f"\n{label.upper()}  ({len(items)})")
        if not items:
            print("  (kosong)")
            continue
        for row in items[:per_track]:
            fit = row["fit"]
            marker = f"fit {fit}" if fit is not None else f"skor {row['score']}"
            print(f"  {marker:<9} {row['title'][:44]:<46} {row['company'][:22]:<24} {row['location'][:20]}")

    other = groups.get("lainnya") or []
    print(f"\nLAINNYA  ({len(other)}) - tidak cocok track mana pun")
    for row in other[:3]:
        print(f"  skor {row['score']:<4} {row['title'][:52]:<54} {row['company'][:20]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
