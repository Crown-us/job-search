"""Discord webhook delivery for the daily shortlist.

A webhook is a plain HTTPS endpoint: no bot, no OAuth, no gateway connection.
One POST with up to 10 embeds per message. Discord answers 204 on success,
200 when `wait=true` (which also returns the message id), and 429 with a JSON
retry_after when the webhook is rate limited (30 calls/minute).

Setup is documented in README; the URL comes from .env as DISCORD_WEBHOOK_URL.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import config

COLOURS = {"good": 0x2F9E5F, "mid": 0xC8922A, "low": 0xB44D4D}
MAX_EMBEDS = 10

SOURCE_LABEL = {
    "jobstreet": "JobStreet",
    "kalibrr": "Kalibrr",
    "greenhouse": "Greenhouse",
    "ashby": "Ashby",
    "lever": "Lever",
    "workable": "Workable",
    "remoteok": "RemoteOK",
    "remotive": "Remotive",
    "jobicy": "Jobicy",
    "himalayas": "Himalayas",
    "arbeitnow": "Arbeitnow",
    "hackernews": "Hacker News",
}

# Emoji + colour per career track, so a glance is enough to tell the feed apart.
TRACK_STYLE = {
    "fullstack": ("💻", 0x5865F2),
    "it_support": ("🛠️", 0x2F9E5F),
    "ai_junior": ("🤖", 0xEB459E),
    "admin_data": ("🗂️", 0xFEE75C),
    "marketing": ("📣", 0xE67E22),
    "video_editor": ("🎬", 0x9B59B6),
    "graphic_design": ("🎨", 0xE91E63),
    "social_media": ("📱", 0x1ABC9C),
}

REACTION_HELP = "✅ applied · 🔖 simpan · ❌ skip · 📅 interview"
REACTION_HELP_SYNC = REACTION_HELP + " — jalankan `jobhunter sync`"


def _tone(fit: int | None) -> str:
    if fit is None:
        return "low"
    if fit >= 75:
        return "good"
    if fit >= 55:
        return "mid"
    return "low"


def _bot_configured() -> bool:
    return bool((config.env().get("DISCORD_BOT_TOKEN") or "").strip())


def _track_of(row: dict) -> str:
    """Best-matching track name, or '' when nothing matches."""
    from .score import _best_track

    tracks = config.profile().get("tracks") or {}
    headline = f"{row.get('title') or ''} {row.get('department') or ''}"
    best = _best_track(headline, tracks)
    return best[1] if best else ""


def _epoch(value: str | None) -> int | None:
    """Turn the various posted_at formats into a unix timestamp for Discord."""
    if not value:
        return None
    text = str(value).strip()
    if text.isdigit() and len(text) in (10, 13):
        return int(text) // (1000 if len(text) == 13 else 1)
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return int(moment.replace(tzinfo=timezone.utc).timestamp())
    return int(moment.timestamp())


def _embed(row: dict, public: bool = False) -> dict:
    fit = row.get("fit")
    gaps = [g for g in (row.get("gaps") or "").split("\n") if g.strip()][:2]
    strengths = [s for s in (row.get("strengths") or "").split("\n") if s.strip()][:1]

    track = _track_of(row)
    emoji, track_colour = TRACK_STYLE.get(track, ("📌", 0x95A5A6))
    location = row.get("location") or ("Remote" if row.get("remote") else "lokasi tidak disebut")
    company = row.get("company") or "Perusahaan tidak disebut"
    source = str(row.get("source") or "")

    lines = [f"**{company}**", f"📍 {location}"]
    posted = _epoch(row.get("posted_at"))
    if posted:
        lines.append(f"🕒 diposting <t:{posted}:R>")

    fields = []
    if public:
        if row.get("salary"):
            fields.append({"name": "💰 Gaji", "value": str(row["salary"])[:200], "inline": True})
        fields.append({"name": "🏷️ Tipe", "value": "Remote" if row.get("remote") else "On-site", "inline": True})
    else:
        if fit is not None:
            fields.append({"name": "Fit", "value": str(fit), "inline": True})
        if row.get("score") is not None:
            fields.append({"name": "Skor", "value": str(row["score"]), "inline": True})
        if row.get("salary"):
            fields.append({"name": "💰 Gaji", "value": str(row["salary"])[:200], "inline": True})
        if gaps:
            fields.append({"name": "❗ Gap", "value": "\n".join(g[:90] for g in gaps)[:1024], "inline": False})
        if strengths:
            fields.append(
                {"name": "✅ Plus", "value": "\n".join(s[:90] for s in strengths)[:1024], "inline": False}
            )

    embed = {
        "author": {"name": f"{SOURCE_LABEL.get(source, source or 'Job Hunter')}"},
        "title": f"{emoji} {(row.get('title') or '')[:230]}",
        "url": row.get("url") or "",
        "description": "\n".join(lines),
        "color": track_colour if public else COLOURS[_tone(fit)],
        "fields": fields[:6],
        "footer": {"text": f"Job Hunter · {track or 'lainnya'} · id {str(row.get('id', ''))[:8]}"},
    }
    return embed


def build_single(row: dict, public: bool = False) -> dict:
    """One job per message, so a reaction on it means that job and only that job."""
    fit = row.get("fit")
    location = row.get("location") or ("Remote" if row.get("remote") else "lokasi tidak disebut")
    source = SOURCE_LABEL.get(str(row.get("source") or ""), "Job Hunter")
    if public:
        header = f"🆕 **{source}** · {location}"
    elif fit is not None:
        header = f"**fit {fit}** · skor {row.get('score')} · {location}"
    else:
        header = f"**skor {row.get('score')}** · {location}"
    if _bot_configured():
        header += "\n" + REACTION_HELP
    return {
        "username": "Job Hunter",
        "content": header,
        "embeds": [_embed(row, public)],
        "allowed_mentions": {"parse": []},
    }


def build_payload(rows: list[dict], min_fit: int = 55, public: bool = False) -> dict:
    today = datetime.now().strftime("%d %b %Y")
    if public:
        header = f"**{len(rows)} lowongan baru** · {today}"
    else:
        header = f"**{len(rows)} lowongan layak dilihat** · {today} · fit ≥ {min_fit}"
    if not rows:
        header = f"Belum ada lowongan baru · {today}" if public else (
            f"Belum ada lowongan baru di atas fit {min_fit} · {today}"
        )

    # Only advertise reactions when a bot is configured to read them back;
    # otherwise the emoji would be decoration that lies.
    if _bot_configured():
        header += "\n" + REACTION_HELP_SYNC

    return {
        "username": "Job Hunter",
        "content": header,
        "embeds": [_embed(row, public) for row in rows[:MAX_EMBEDS]],
        "allowed_mentions": {"parse": []},
    }


def letter_files(rows: list[dict], limit: int = 5) -> list[tuple[str, bytes]]:
    """Generated cover letters for these postings, ready to attach to the message."""
    folder = config.DATA_DIR / "letters"
    if not folder.exists():
        return []
    payloads: list[tuple[str, bytes]] = []
    for row in rows:
        matches = sorted(folder.glob(f"{str(row.get('id', ''))[:8]}-*.md"))
        if matches:
            payloads.append((matches[0].name, matches[0].read_bytes()))
        if len(payloads) >= limit:
            break
    return payloads


API = "https://discord.com/api/v10"


def _send_as_bot(
    payload: dict,
    token: str,
    channel_id: str,
    attachments: list[tuple[str, bytes]] | None,
    timeout: int,
) -> tuple[bool, str, str | None]:
    """POST /channels/{id}/messages. Bot messages can be deleted by the bot itself."""
    url = f"{API}/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    body = {k: v for k, v in payload.items() if k != "username"}

    try:
        if attachments:
            files = {
                f"files[{index}]": (name, data)
                for index, (name, data) in enumerate(attachments)
            }
            resp = requests.post(
                url,
                headers=headers,
                data={"payload_json": json.dumps(body)},
                files=files,
                timeout=timeout,
            )
        else:
            resp = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.RequestException as exc:
        return False, f"koneksi gagal: {type(exc).__name__}", None

    if resp.status_code in (200, 201):
        detail = f"terkirim ({len(payload.get('embeds') or [])} embed)"
        message_id = None
        try:
            data = resp.json()
            raw_id = data.get("id")
            message_id = str(raw_id) if raw_id else None
            detail += f" | id {message_id}"
        except (json.JSONDecodeError, ValueError):
            pass
        if attachments:
            detail += f", {len(attachments)} surat"
        return True, detail, message_id

    detail = ""
    try:
        body_err = resp.json()
        detail = str(body_err.get("message") or body_err)[:160]
    except (json.JSONDecodeError, ValueError):
        detail = resp.text[:160]
    return False, f"HTTP {resp.status_code}: {detail}", None


def send(
    payload: dict,
    webhook_url: str | None = None,
    timeout: int = 20,
    thread_name: str | None = None,
    attachments: list[tuple[str, bytes]] | None = None,
    channel_id: str | None = None,
) -> tuple[bool, str, str | None]:
    """Returns (ok, detail, message_id). message_id is None unless wait=true replied.

    Posts as the bot when DISCORD_BOT_TOKEN is configured (messages it owns can
    be deleted later without Manage Messages); otherwise falls back to the
    webhook, which needs no bot at all. `channel_id` overrides the .env target.
    """
    env = config.env()
    bot_token = (env.get("DISCORD_BOT_TOKEN") or "").strip()
    bot_channel = (channel_id or env.get("DISCORD_CHANNEL_ID") or "").strip()

    if bot_token and bot_channel:
        return _send_as_bot(payload, bot_token, bot_channel, attachments, timeout)

    url = (webhook_url or env.get("DISCORD_WEBHOOK_URL") or "").strip()
    if not url:
        return False, "DISCORD_WEBHOOK_URL / bot belum diisi di .env", None
    if not url.startswith("https://discord.com/api/webhooks/"):
        return False, "URL bukan webhook Discord yang valid", None

    params: dict[str, str] = {"wait": "true"}
    if thread_name:
        params["thread_name"] = thread_name[:100]

    def _post() -> requests.Response:
        if attachments:
            files = {
                f"files[{index}]": (name, data)
                for index, (name, data) in enumerate(attachments)
            }
            return requests.post(
                url,
                params=params,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=timeout,
            )
        return requests.post(url, params=params, json=payload, timeout=timeout)

    try:
        resp = _post()
    except requests.RequestException as exc:
        return False, f"koneksi gagal: {type(exc).__name__}", None

    if resp.status_code in (200, 204):
        detail = f"terkirim ({len(payload.get('embeds') or [])} embed)"
        message_id: str | None = None
        if resp.status_code == 200:
            try:
                body = resp.json()
                raw_id = body.get("id")
                message_id = str(raw_id) if raw_id else None
                detail += f" | id {message_id}"
            except (json.JSONDecodeError, ValueError):
                detail += " | respons bukan json"
        if attachments:
            detail += f", {len(attachments)} surat"
        if thread_name:
            detail += f", thread '{thread_name[:100]}'"
        return True, detail, message_id

    if resp.status_code == 429:
        try:
            retry_after = float(resp.json().get("retry_after", 1))
        except (json.JSONDecodeError, TypeError, ValueError):
            retry_after = 1.0
        time.sleep(min(retry_after, 5))
        retry = _post()
        if retry.status_code in (200, 204):
            return True, f"terkirim setelah rate limit ({retry_after:.1f}s)", None

    detail = ""
    try:
        body = resp.json()
        detail = str(body.get("message") or body)[:160]
    except (json.JSONDecodeError, ValueError):
        detail = resp.text[:160]
    return False, f"HTTP {resp.status_code}: {detail}", None


_ASCII_MAP = str.maketrans({"≥": ">=", "·": "-", "–": "-", "—": "-", "→": "->", "’": "'"})


def _ascii(text: str) -> str:
    """Terminal-safe preview: legacy Windows consoles are cp1252 and crash on ≥ and ·."""
    out = text.translate(_ASCII_MAP)
    return out.encode("ascii", "replace").decode("ascii")


def preview(payload: dict) -> str:
    """Human-readable dump for --dry-run."""
    lines = [_ascii(payload["content"])]
    for embed in payload["embeds"]:
        fields = " | ".join(
            f"{f['name']}={_ascii(f['value'].replace(chr(10), ', '))}" for f in embed["fields"]
        )
        lines.append(f"  - {_ascii(embed['title'])} ({_ascii(embed['description'])}) {fields}")
    return "\n".join(lines)
