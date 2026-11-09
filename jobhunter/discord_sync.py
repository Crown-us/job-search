"""Poll reactions and save application status per Discord user.

Read reactor identities with pagination; never mutate the owner's CLI status.
Only messages recorded as one-job deliveries are eligible for tracking.
"""

from __future__ import annotations

import requests

from . import config, db

API = "https://discord.com/api/v10"

# What each reaction means. Keys are the emoji `name` field Discord returns.
EMOJI_STATUS = {
    "✅": "applied",
    "🔖": "shortlist",
    "❌": "skipped",
    "📅": "interview",
    "🏆": "offer",
}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}


def credentials() -> tuple[str, str]:
    env = config.env()
    return (
        (env.get("DISCORD_BOT_TOKEN") or "").strip(),
        (env.get("DISCORD_CHANNEL_ID") or "").strip(),
    )


def channel_ids() -> list[str]:
    """Every feed channel: main, creative, and remote, when configured."""
    env = config.env()
    keys = ("DISCORD_CHANNEL_ID", "DISCORD_CHANNEL_KREATIF", "DISCORD_CHANNEL_REMOTE")
    return [value for key in keys if (value := (env.get(key) or "").strip())]


def fetch_messages(channel_id: str, token: str, limit: int = 50) -> list[dict]:
    resp = requests.get(
        f"{API}/channels/{channel_id}/messages",
        headers=_headers(token),
        params={"limit": min(limit, 100)},
        timeout=25,
    )
    if resp.status_code == 401:
        raise PermissionError("token bot ditolak (401) - cek DISCORD_BOT_TOKEN")
    if resp.status_code == 403:
        raise PermissionError(
            "bot tidak punya akses channel (403) - pastikan permission View Channels + Read Message History"
        )
    if resp.status_code == 404:
        raise LookupError("channel tidak ditemukan (404) - cek DISCORD_CHANNEL_ID")
    resp.raise_for_status()
    return resp.json()


def reactions_of(message: dict) -> list[str]:
    """Emoji names reacted to by a human, from the message's own reactions array."""
    names = []
    for reaction in message.get("reactions") or []:
        count = int(reaction.get("count") or 0)
        if count <= 0:
            continue
        # `me` is the bot itself; a bot-only reaction should not change anything.
        if reaction.get("me") and count == 1:
            continue
        name = ((reaction.get("emoji") or {}).get("name") or "").strip()
        if name:
            names.append(name)
    return names


def fetch_reactors(channel_id: str, message_id: str, emoji: str, token: str) -> list[dict]:
    """Read every reactor, including messages with more than 100 reactions."""
    from urllib.parse import quote

    users = []
    after = None
    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after
        resp = requests.get(
            f"{API}/channels/{channel_id}/messages/{message_id}/reactions/{quote(emoji, safe='')}",
            headers=_headers(token), params=params, timeout=25,
        )
        resp.raise_for_status()
        batch = resp.json()
        users.extend(u for u in batch if not u.get("bot"))
        if len(batch) < 100:
            return users
        after = batch[-1]["id"]


def sync(limit: int = 50, dry_run: bool = False) -> dict:
    token, channel_id = credentials()
    if not token or not channel_id:
        return {"ok": False, "error": "DISCORD_BOT_TOKEN / DISCORD_CHANNEL_ID belum diisi di .env", "changed": []}

    conn = db.connect()
    changed = []
    scanned = 0
    # Multiple reactions have a stable precedence; REST does not give their time.
    priority = {"shortlist": 1, "applied": 2, "skipped": 3, "interview": 4, "offer": 5}
    pending = {}
    try:
        jobs = {r["id"]: dict(r) for r in conn.execute("SELECT id,title FROM jobs")}
        for channel in channel_ids():
            mapping = db.delivery_by_message(conn, channel)
            if channel == channel_id:
                mapping = {**db.delivery_by_message(conn, "discord"), **mapping}
            messages = fetch_messages(channel, token, limit)
            scanned += len(messages)
            for message in messages:
                job_id = mapping.get(str(message.get("id")))
                if job_id not in jobs:
                    continue
                for emoji in reactions_of(message):
                    status = EMOJI_STATUS.get(emoji)
                    if not status:
                        continue
                    for user in fetch_reactors(channel, str(message["id"]), emoji, token):
                        if user.get("bot") or not user.get("id"):
                            continue
                        key = (str(user["id"]), job_id)
                        if priority[status] > priority.get(pending.get(key), 0):
                            pending[key] = status
        for (user_id, job_id), status in pending.items():
            previous = conn.execute(
                "SELECT status FROM user_job_status WHERE user_id=? AND job_id=?", (user_id, job_id)
            ).fetchone()
            if previous and previous[0] == status:
                continue
            changed.append((user_id, job_id, jobs[job_id]["title"], status))
            if not dry_run:
                conn.execute(
                    "INSERT INTO user_job_status (user_id,job_id,status,updated_at) VALUES (?,?,?,?) "
                    "ON CONFLICT(user_id,job_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at",
                    (user_id, job_id, status, db.utcnow()),
                )
        if not dry_run:
            conn.commit()
        return {"ok": True, "error": "", "changed": changed, "scanned": scanned}
    except (requests.RequestException, PermissionError, LookupError) as exc:
        conn.rollback()
        return {"ok": False, "error": f"sinkronisasi gagal: {type(exc).__name__}", "changed": [], "scanned": scanned}
    finally:
        conn.close()


def legend() -> str:
    return " | ".join(f"{emoji} = {status}" for emoji, status in EMOJI_STATUS.items())
