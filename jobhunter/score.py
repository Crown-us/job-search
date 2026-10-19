"""Heuristic scorer v1 — profile-aware, no API key needed.

Reads profile.yaml: four career tracks, boost words, avoid words. Picks the best
matching track for each posting and explains the number. The LLM scorer planned
for phase 2 keeps this exact (score, reasons) contract, so the rest of the
pipeline will not change when it lands.
"""

from __future__ import annotations

import re

from . import config, db

ID_HINTS = (
    "indonesia", "jakarta", "malang", "surabaya", "bandung", "yogyakarta",
    "jogja", "bali", "denpasar", "semarang", "kediri", "sleman",
)
ENTRY_HINTS = (
    "junior", "intern", "internship", "associate", "entry level",
    "fresh graduate", "magang", "trainee", "graduate",
)
US_ONLY = re.compile(
    r"\bremote\s*[-–(]?\s*(usa|u\.s\.a?\.?|us|united states|canada|uk|emea)\b|\bus\s+only\b|"
    r"\bmust be (located|based) in the (us|united states)\b",
    re.I,
)
# On-site roles in these cities need US work authorization just as surely.
US_CITY = re.compile(
    r"\b(new york|san francisco|seattle|austin|boston|chicago|denver|los angeles|"
    r"san diego|atlanta|miami|dallas|houston|phoenix|portland|foster city|nyc|"
    r"palo alto|mountain view|menlo park|sunnyvale|bellevue|toronto|vancouver|"
    r"london|dublin|berlin|amsterdam|paris|madrid|warsaw|stockholm|zurich|tel aviv)\b",
    re.I,
)
YEARS = re.compile(r"\b([3-9]|1[0-9])\+?\s*years?\b", re.I)


_KW_CACHE: dict[str, re.Pattern[str]] = {}


def _kw_pattern(needle: str) -> re.Pattern[str]:
    """Word-ish boundary so 'ai' does not match inside 'desain'."""
    pattern = _KW_CACHE.get(needle)
    if pattern is None:
        pattern = re.compile(
            r"(?<![\w+#.])" + re.escape(needle.strip()) + r"(?![\w+#])", re.I
        )
        _KW_CACHE[needle] = pattern
    return pattern


def _hits(text: str, needles) -> list[str]:
    return [str(n) for n in needles if n and _kw_pattern(str(n)).search(text)]


def _best_track(headline: str, tracks: dict) -> tuple[float, str, list[str], list[str]] | None:
    """Match on title + department only.

    Full descriptions mention AI/prompt/automation in passing, so scoring them
    makes a Customer Experience role look like an engineering role.
    """
    best = None
    for name, spec in tracks.items():
        keywords = spec.get("keywords") or []
        title_hits = _hits(headline, keywords)
        if not title_hits:
            continue
        if best is None or len(title_hits) > len(best[2]):
            best = (float(len(title_hits)), name, title_hits, [])
    return best


def score_one(job: dict, profile: dict) -> tuple[int, list[str]]:
    title = " ".join([job.get("title") or "", job.get("department") or ""])
    location = job.get("location") or ""
    description = job.get("description") or ""

    score = 50
    reasons: list[str] = []

    best = _best_track(title, profile.get("tracks") or {})
    if best:
        _, name, title_hits, _ = best
        score += min(27, 9 * len(title_hits))
        reasons.append(f"track {name}")
        reasons.append("judul: " + ", ".join(title_hits[:4]))
    else:
        score -= 12
        reasons.append("judul tidak cocok track mana pun (-12)")

    avoid = _hits(title, profile.get("avoid_keywords") or [])
    if avoid:
        score -= min(20, 10 * len(avoid))
        reasons.append("hindari: " + ", ".join(avoid[:4]))

    years = YEARS.search(title) or YEARS.search(description[:1200])
    if years:
        score -= 8
        reasons.append(f"minta {years.group(0)} pengalaman (-8)")

    if job.get("remote"):
        score += 4
        reasons.append("remote")
    if _hits(location, ID_HINTS):
        score += 10
        reasons.append("lokasi Indonesia")
    elif US_ONLY.search(location) or US_ONLY.search(description[:600]) or US_CITY.search(location):
        score -= 18
        reasons.append("kemungkinan butuh izin kerja US/EU (-18)")

    if _hits(title, ENTRY_HINTS):
        score += 8
        reasons.append("level entry")

    if job.get("salary"):
        score += 3
        reasons.append("ada gaji")

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
