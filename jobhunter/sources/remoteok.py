"""RemoteOK public API. Needs a browser-ish user agent or it answers 403."""

from __future__ import annotations

from ..model import Job
from .base import get_json, strip_html


def fetch(token: str = "", full: bool = False) -> list[Job]:
    data = get_json("https://remoteok.com/api")
    if not isinstance(data, list):
        return []
    jobs: list[Job] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("position"):
            continue  # first element is the legal notice
        low, high = item.get("salary_min") or 0, item.get("salary_max") or 0
        salary = f"${low:,} - ${high:,}" if low and high else ""
        jobs.append(
            Job(
                source="remoteok",
                company=item.get("company", ""),
                title=item.get("position", ""),
                url=item.get("url") or item.get("apply_url") or "",
                location=item.get("location") or "Remote",
                remote=True,
                salary=salary,
                department=", ".join(item.get("tags") or []),
                description=strip_html(item.get("description")) if full else "",
                posted_at=item.get("date") or "",
                external_id=str(item.get("id", "")),
            )
        )
    return jobs
