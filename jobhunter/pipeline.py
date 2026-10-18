"""Collect -> filter -> dedupe -> store."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from . import config, db
from .model import Job
from .sources import ADAPTERS, BOARD_SOURCES, FEED_SOURCES, QUERY_SOURCES
from .sources.base import SOURCE_PRIORITY


def _lower(value) -> str:
    return (value or "").lower()


def _posted_within(posted_at: str, max_days: int) -> bool:
    """Unparseable or missing dates pass: better to show an old job than drop a new one."""
    if not max_days or not posted_at:
        return True
    text = str(posted_at).strip()
    moment: datetime | None = None
    if text.isdigit() and len(text) in (10, 13):
        value = int(text) / (1000 if len(text) == 13 else 1)
        moment = datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return True
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - moment <= timedelta(days=max_days)


def passes_filters(job: Job, flt: dict) -> bool:
    title = _lower(job.title)
    if any(_lower(k) in title for k in flt.get("exclude_title_keywords") or []):
        return False
    if any(_lower(k) in _lower(job.company) for k in flt.get("exclude_company_keywords") or []):
        return False

    must = [_lower(k) for k in flt.get("must_have_any") or []]
    if must:
        blob = " ".join([title, _lower(job.department), _lower(job.description)])
        if not any(k in blob for k in must):
            return False

    allow = [_lower(k) for k in flt.get("location_allow") or []]
    if allow and not job.remote:
        location = _lower(job.location)
        if location and not any(k in location for k in allow):
            return False

    if flt.get("remote_only") and not job.remote:
        return False

    return _posted_within(job.posted_at, int(flt.get("max_age_days") or 0))


def _preferred(a: Job, b: Job) -> bool:
    """True when a should replace b for the same cross-source fingerprint."""
    pa, pb = SOURCE_PRIORITY.get(a.source, 9), SOURCE_PRIORITY.get(b.source, 9)
    if pa != pb:
        return pa < pb
    if bool(a.salary) != bool(b.salary):
        return bool(a.salary)
    return len(a.description) > len(b.description)


def dedupe(jobs: list[Job]) -> list[Job]:
    best: dict[str, Job] = {}
    for job in jobs:
        current = best.get(job.fingerprint)
        if current is None or _preferred(job, current):
            best[job.fingerprint] = job
    return list(best.values())


def run_discover(
    sources: list[str] | None = None,
    full: bool = False,
    per_board_limit: int = 0,
    total_limit: int = 0,
    apply_filters: bool = True,
    dry_run: bool = False,
) -> dict:
    cfg = config.companies()
    searches = config.searches()
    flt = config.filters()

    wanted = sources or [name for name in ADAPTERS if cfg.get(name) or searches.get(name)]
    fetched = 0
    kept: list[Job] = []
    by_source: dict[str, int] = {}
    errors: list[str] = []

    for name in wanted:
        adapter = ADAPTERS.get(name)
        if adapter is None:
            errors.append(f"{name}: unknown source")
            continue

        count = 0
        if name in QUERY_SOURCES:
            spec = searches.get(name) or {}
            keywords = spec.get("keywords") or []
            pages = int(spec.get("pages") or 1)
            calls = [(kw, page) for kw in keywords for page in range(1, pages + 1)]
        elif name in BOARD_SOURCES:
            calls = [(token, 0) for token in (cfg.get(name) or [])]
        elif name in FEED_SOURCES:
            calls = [("", 0)]
        else:
            calls = []

        for token, page in calls:
            try:
                if name in QUERY_SOURCES:
                    batch = adapter(token, page=page, full=full)
                else:
                    batch = adapter(token, full=full)
            except Exception as exc:  # one dead board must not kill the run
                errors.append(f"{name}:{token or '-'} p{page}: {type(exc).__name__}: {exc}")
                continue
            if per_board_limit:
                batch = batch[:per_board_limit]
            fetched += len(batch)
            count += len(batch)
            kept.extend(batch)
        by_source[name] = count

    matched = [job for job in kept if passes_filters(job, flt)] if apply_filters else kept
    unique = dedupe(matched)
    unique.sort(key=lambda j: (SOURCE_PRIORITY.get(j.source, 9), j.company.lower(), j.title.lower()))
    if total_limit:
        unique = unique[:total_limit]

    result = {
        "fetched": fetched,
        "matched": len(matched),
        "unique": len(unique),
        "inserted": 0,
        "known": 0,
        "by_source": by_source,
        "errors": errors,
        "jobs": unique,
    }

    if not dry_run:
        conn = db.connect()
        run_id = db.start_run(conn)
        inserted, known = db.upsert(conn, [job.as_row() for job in unique])
        db.finish_run(
            conn, run_id,
            fetched=fetched, inserted=inserted, kept=len(unique),
            sources=",".join(wanted), note="; ".join(errors[:5]),
        )
        conn.close()
        result["inserted"] = inserted
        result["known"] = known

    return result
