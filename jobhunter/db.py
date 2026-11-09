"""SQLite store: upsert by canonical id, dedupe by fingerprint, track pipeline status."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import db_path
from .model import utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    source      TEXT NOT NULL,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    location    TEXT DEFAULT '',
    remote      INTEGER DEFAULT 0,
    salary      TEXT DEFAULT '',
    department  TEXT DEFAULT '',
    description TEXT DEFAULT '',
    posted_at   TEXT DEFAULT '',
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    score       INTEGER,
    score_reason TEXT DEFAULT '',
    status      TEXT DEFAULT 'new',
    notes       TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    fetched     INTEGER DEFAULT 0,
    inserted    INTEGER DEFAULT 0,
    kept        INTEGER DEFAULT 0,
    sources     TEXT DEFAULT '',
    note        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS analyses (
    job_id    TEXT PRIMARY KEY,
    fit       INTEGER,
    verdict   TEXT DEFAULT '',
    gaps      TEXT DEFAULT '',
    strengths TEXT DEFAULT '',
    engine    TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    job_id   TEXT NOT NULL,
    channel  TEXT NOT NULL,
    sent_at  TEXT NOT NULL,
    PRIMARY KEY (job_id, channel)
);

CREATE TABLE IF NOT EXISTS user_job_status (
    user_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, job_id)
);
"""

FIELDS = (
    "id", "fingerprint", "source", "company", "title", "url", "location",
    "remote", "salary", "department", "description", "posted_at", "last_seen",
)


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that CREATE TABLE IF NOT EXISTS cannot add to an existing table."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(deliveries)")}
    if "message_id" not in columns:
        conn.execute("ALTER TABLE deliveries ADD COLUMN message_id TEXT")
    conn.commit()


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def upsert(conn: sqlite3.Connection, rows: list[dict]) -> tuple[int, int]:
    """Insert new postings, refresh last_seen on known ones. Returns (inserted, known)."""
    known = {
        r[0] for r in conn.execute(
            f"SELECT id FROM jobs WHERE id IN ({','.join('?' * len(rows))})", [r["id"] for r in rows]
        )
    } if rows else set()
    now = utcnow()
    sql = f"""
    INSERT INTO jobs ({','.join(FIELDS)}, first_seen, status)
    VALUES ({','.join('?' * len(FIELDS))}, ?, 'new')
    ON CONFLICT(id) DO UPDATE SET
        last_seen   = excluded.last_seen,
        location    = excluded.location,
        remote      = excluded.remote,
        salary      = CASE WHEN jobs.salary = '' THEN excluded.salary ELSE jobs.salary END,
        description = CASE WHEN jobs.description = '' THEN excluded.description ELSE jobs.description END,
        posted_at   = CASE WHEN jobs.posted_at = '' THEN excluded.posted_at ELSE jobs.posted_at END
    """
    conn.executemany(sql, [[r[f] for f in FIELDS] + [now] for r in rows])
    conn.commit()
    return len(rows) - len(known), len(known)


def start_run(conn: sqlite3.Connection) -> int:
    cur = conn.execute("INSERT INTO runs (started_at) VALUES (?)", (utcnow(),))
    conn.commit()
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, **kw) -> None:
    conn.execute(
        "UPDATE runs SET finished_at=?, fetched=?, inserted=?, kept=?, sources=?, note=? WHERE id=?",
        (
            utcnow(), kw.get("fetched", 0), kw.get("inserted", 0), kw.get("kept", 0),
            kw.get("sources", ""), kw.get("note", ""), run_id,
        ),
    )
    conn.commit()


def save_analysis(conn: sqlite3.Connection, job_id: str, result: dict) -> None:
    conn.execute(
        """INSERT INTO analyses (job_id, fit, verdict, gaps, strengths, engine, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(job_id) DO UPDATE SET
             fit=excluded.fit, verdict=excluded.verdict, gaps=excluded.gaps,
             strengths=excluded.strengths, engine=excluded.engine, created_at=excluded.created_at""",
        (
            job_id,
            result.get("fit"),
            result.get("verdict", ""),
            "\n".join(result.get("gaps") or []),
            "\n".join(result.get("strengths") or []),
            result.get("engine", ""),
            utcnow(),
        ),
    )
    conn.commit()


def delivered_ids(conn: sqlite3.Connection, channel: str) -> set[str]:
    """Ids already pushed to a channel, so daily runs do not repost the same jobs."""
    return {row[0] for row in conn.execute(
        "SELECT job_id FROM deliveries WHERE channel = ?", (channel,)
    )}


def record_deliveries(
    conn: sqlite3.Connection,
    job_ids: list[str],
    channel: str,
    message_id: str | None = None,
) -> None:
    now = utcnow()
    conn.executemany(
        """INSERT INTO deliveries (job_id, channel, sent_at, message_id)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(job_id, channel) DO UPDATE SET
             sent_at = excluded.sent_at,
             message_id = COALESCE(excluded.message_id, deliveries.message_id)""",
        [(job_id, channel, now, message_id) for job_id in job_ids],
    )
    conn.commit()


def delivery_by_message(conn: sqlite3.Connection, channel: str) -> dict[str, str]:
    """message_id -> job_id, so reactions can be mapped without reading message content."""
    return {
        str(row[0]): row[1]
        for row in conn.execute(
            "SELECT message_id, job_id FROM deliveries WHERE channel = ? AND message_id IS NOT NULL",
            (channel,),
        )
    }
