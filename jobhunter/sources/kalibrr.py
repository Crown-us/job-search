"""Kalibrr job board search API.

Kalibrr exposes is_open_to_fresh_grads / work_experience, which matters a lot for
a fresh graduate, so it gets folded into the stored description when full=True.
"""

from __future__ import annotations

from ..model import Job
from .base import extract_job_description, get_json, strip_html

ENDPOINT = "https://www.kalibrr.com/kjs/job_board/search"


def _location(item: dict) -> str:
    if item.get("is_work_from_home"):
        return "Remote"
    loc = item.get("google_location") or {}
    if isinstance(loc, dict):
        for key in ("formatted_address", "address", "name"):
            if loc.get(key):
                return str(loc[key])[:120]
        components = loc.get("address_components") or {}
        if isinstance(components, dict):
            joined = ", ".join(str(v) for v in components.values() if v)
            if joined:
                return joined[:120]
    text = str(loc)
    return "" if text == "{}" else text[:120]


def fetch(keyword: str = "", page: int = 1, full: bool = False, limit: int = 20) -> list[Job]:
    params = {"limit": limit, "offset": max(0, (page - 1) * limit)}
    if keyword:
        params["text"] = keyword  # 'q' and 'search_text' are ignored by this API
    data = get_json(ENDPOINT, **params)

    jobs: list[Job] = []
    for item in data.get("jobs") or []:
        job_id = str(item.get("id", ""))
        slug = item.get("slug") or ""
        url = f"https://www.kalibrr.com/jobs/{job_id}" + (f"/{slug}" if slug else "")
        tags = []
        if item.get("is_open_to_fresh_grads"):
            tags.append("open to fresh grads")
        if item.get("work_experience"):
            tags.append(f"experience: {item['work_experience']}")
        description = strip_html(item.get("description")) if full else " | ".join(tags)
        jobs.append(
            Job(
                source="kalibrr",
                company=item.get("company_name") or "Kalibrr",
                title=item.get("name", ""),
                url=url,
                location=_location(item),
                remote=bool(item.get("is_work_from_home")),
                salary=item.get("salary_shown") or "",
                department=" | ".join(
                    str(x) for x in (item.get("function"), item.get("tenure")) if x
                ),
                description=description,
                posted_at=item.get("activation_date") or "",
                external_id=job_id,
            )
        )
    return jobs


def fetch_detail(url: str) -> str:
    from .base import SESSION

    resp = SESSION.get(url, headers={"Accept": "text/html"}, timeout=30)
    resp.raise_for_status()
    return extract_job_description(resp.text)
