"""Read emoji reactions on the Discord shortlist and update job status.

Uses only the REST API with a bot token — no gateway, no discord.py, no
long-running process. One GET returns recent channel messages, and each message
already carries a `reactions` array with counts, so no per-emoji requests.

Polling this every few minutes (or on demand) is enough: reactions are not
real-time critical.
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


def sync(limit: int = 50, dry_run: bool = False) -> dict:
    token, channel_id = credentials()
    if not token or not channel_id:
        return {
            "ok": False,
            "error": "DISCORD_BOT_TOKEN / DISCORD_CHANNEL_ID belum diisi di .env",
            "changed": [],
        }

    try:
        messages = fetch_messages(channel_id, token, limit)
    except (PermissionError, LookupError) as exc:
        return {"ok": False, "error": str(exc), "changed": []}
    except requests.RequestException as exc:
        return {"ok": False, "error": f"koneksi gagal: {type(exc).__name__}", "changed": []}

    conn = db.connect()
    by_url = {
        row["url"]: dict(row)
        for row in conn.execute("SELECT id, url, title, status FROM jobs")
    }

    changed: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for message in messages:
        for embed in message.get("embeds") or []:
            job = by_url.get(embed.get("url") or "")
            if job is None or job["id"] in seen:
                continue
            for emoji in reactions_of(message):
                status = EMOJI_STATUS.get(emoji)
                if not status or status == job["status"]:
                    continue
                changed.append((job["id"], job["title"], status))
                seen.add(job["id"])
                if not dry_run:
                    conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job["id"]))
                break

    if not dry_run:
        conn.commit()
    conn.close()
    return {"ok": True, "error": "", "changed": changed, "scanned": len(messages)}


def legend() -> str:
    return " | ".join(f"{emoji} = {status}" for emoji, status in EMOJI_STATUS.items())
