"""Normalized job record shared by every source adapter."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING = re.compile(
    r"^(utm_|gh_src$|lever-|ref$|source$|trk|fbclid|gclid|mc_cid|mc_eid)", re.I
)


def clean(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def canonical_url(url: str | None) -> str:
    """Strip tracking params and trailing slashes so the same posting hashes once."""
    url = (url or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower() or "https", parts.netloc.lower(), path, urlencode(query), "")
    )


def key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class Job:
    source: str
    company: str
    title: str
    url: str
    location: str = ""
    remote: bool = False
    salary: str = ""
    department: str = ""
    description: str = ""
    posted_at: str = ""
    external_id: str = ""

    def __post_init__(self) -> None:
        self.company = clean(self.company) or "Unknown"
        self.title = clean(self.title)
        self.location = clean(self.location)
        self.url = canonical_url(self.url)

    @property
    def id(self) -> str:
        basis = self.url or f"{self.source}:{self.external_id}:{self.company}:{self.title}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    @property
    def fingerprint(self) -> str:
        """Cross-source identity: same role re-posted on another board collapses to one."""
        basis = f"{key(self.company)}|{key(self.title)}|{key(self.location)}"
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    def as_row(self) -> dict:
        return {
            "id": self.id,
            "fingerprint": self.fingerprint,
            "source": self.source,
            "company": self.company,
            "title": self.title,
            "url": self.url,
            "location": self.location,
            "remote": int(bool(self.remote)),
            "salary": self.salary,
            "department": self.department,
            "description": self.description,
            "posted_at": self.posted_at,
            "last_seen": utcnow(),
        }
