"""Generate cover letters for the best-fitting postings that do not have one yet.

Run: python scripts/make_letters.py --min-fit 75 --limit 6
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import analyze, config, db, letter


def main(argv: list[str]) -> int:
    min_fit = int(argv[argv.index("--min-fit") + 1]) if "--min-fit" in argv else 75
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 6

    profile = config.profile()
    out_dir = config.DATA_DIR / "letters"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = db.connect()
    rows = conn.execute(
        """
        SELECT j.*, a.fit FROM jobs j JOIN analyses a ON a.job_id = j.id
        WHERE a.fit >= ? ORDER BY a.fit DESC LIMIT ?
        """,
        (min_fit, limit),
    ).fetchall()

    made = 0
    for row in rows:
        job = dict(row)
        slug = re.sub(r"[^a-z0-9]+", "-", (job["company"] + "-" + job["title"]).lower()).strip("-")[:60]
        path = out_dir / f"{job['id'][:8]}-{slug}.md"
        if path.exists():
            print(f"  skip  {job['fit']:>3}  {job['title'][:44]} (sudah ada)")
            continue
        result = analyze.analyze(job, profile)
        text, engine = letter.build(job, profile, result)
        path.write_text(
            f"# {job['title']} - {job['company']}\n\n{job['url']}\n\n{text}\n", encoding="utf-8"
        )
        made += 1
        print(f"  buat  {job['fit']:>3}  {job['title'][:44]} [{engine}]")

    print(f"\n{made} surat baru di {out_dir}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
