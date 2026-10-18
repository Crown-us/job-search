"""Heuristic scorer v0.

Ranks a posting against profile.yaml without any API key. Fast, explainable, and
good enough to cut 106 rows down to the ten worth reading. The LLM scorer in the
next phase replaces the number but keeps this same (score, reasons) shape.
"""

from __future__ import annotations

import re

from . import config, db

ID_HINTS = (
    "indonesia", "jakarta", "malang", "surabaya", "bandung",
    "yogyakarta", "jogja", "bali", "denpasar", "semarang",
)
ENTRY_HINTS = ("junior", "intern", "internship", "associate", "entry level", "fresh graduate", "magang", "trainee")
US_ONLY = re.compile(
    r"\bremote\s*[-–(]\s*(usa|u\.s\.|us|united states|canada|uk|emea)\b|\bus\s+only\b|"
    r"\bmust be (located|based) in the (us|united states)\b",
    re.I,
)
SENIORITY_TRAP = re.compile(r"\b([5-9]|1[0-9])\+?\s*years\b", re.I)


def _hits(text: str, needles: tuple[str, ...] | list[str]) -> list[str]:
    low = text.lower()
    return [n for n in needles if n and n.lower() in low]


def score_one(job: dict, profile: dict) -> tuple[int, list[str]]:
    title = job.get("title") or ""
    location = job.get("location") or ""
    department = job.get("department") or ""
    description = job.get("description") or ""
    blob = " ".join([title, department, description])
    score = 50
    reasons: list[str] = []

    boosts = [_h for _h in (profile.get("boost_keywords") or []) if _h]
    title_hits = _hits(title, boosts)
    body_hits = [k for k in _hits(blob, boosts) if k not in title_hits]
    if title_hits:
        score += min(24, 8 * len(title_hits))
        reasons.append("match di judul: " + ", ".join(title_hits[:4]))
    if body_hits:
        score += min(12, 3 * len(body_hits))
        reasons.append("match di deskripsi: " + ", ".join(body_hits[:4]))

    if job.get("remote"):
        score += 4
        reasons.append("remote")

    if _hits(location, ID_HINTS):
        score += 10
        reasons.append("lokasi Indonesia")
    elif US_ONLY.search(location) or US_ONLY.search(description[:600]):
        score -= 18
        reasons.append("kemungkinan butuh work authorization US/UK (-18)")

    entry = _hits(title, ENTRY_HINTS)
    if entry:
        score += 8
        reasons.append("level entry/junior")

    years = SENIORITY_TRAP.search(blob)
    if years:
        score -= 10
        reasons.append(f"minta pengalaman {years.group(0)} (-10)")

    if job.get("salary"):
        score += 3
        reasons.append("ada info gaji")

    return max(0, min(100, score)), reasons


def score_jobs(rescore: bool = False, limit: int = 0) -> int:
    profile = config.profile()
    conn = db.connect()
    sql = "SELECT * FROM jobs"
    if not rescore:
        sql += " WHERE score IS NULL"
    sql += " ORDER BY first_seen DESC"
    rows = [dict(r) for r in conn.execute(sql).fetchall()]
    if limit:
        rows = rows[:limit]

    for row in rows:
        value, reasons = score_one(row, profile)
        conn.execute(
            "UPDATE jobs SET score=?, score_reason=? WHERE id=?",
            (value, "; ".join(reasons), row["id"]),
        )
    conn.commit()
    conn.close()
    return len(rows)
