"""Discord webhook delivery for the daily shortlist.

A webhook is a plain HTTPS endpoint: no bot, no OAuth, no gateway connection.
One POST with up to 10 embeds per message. Discord answers 204 on success and
429 with a JSON retry_after when the webhook is rate limited (30 calls/minute).

Setup is documented in README; the URL comes from .env as DISCORD_WEBHOOK_URL.
"""

from __future__ import annotations

import json
import time
from datetime import datetime

import requests

from . import config

COLOURS = {"good": 0x2F9E5F, "mid": 0xC8922A, "low": 0xB44D4D}
MAX_EMBEDS = 10


def _tone(fit: int | None) -> str:
    if fit is None:
        return "low"
    if fit >= 75:
        return "good"
    if fit >= 55:
        return "mid"
    return "low"


def _embed(row: dict) -> dict:
    fit = row.get("fit")
    gaps = [g for g in (row.get("gaps") or "").split("\n") if g.strip()][:2]
    strengths = [s for s in (row.get("strengths") or "").split("\n") if s.strip()][:1]

    fields = []
    if fit is not None:
        fields.append({"name": "fit", "value": str(fit), "inline": True})
    if row.get("score") is not None:
        fields.append({"name": "skor", "value": str(row["score"]), "inline": True})
    if row.get("source"):
        fields.append({"name": "sumber", "value": str(row["source"]), "inline": True})
    if gaps:
        fields.append({"name": "gap", "value": "\n".join(g[:90] for g in gaps)[:1024], "inline": False})
    if strengths:
        fields.append(
            {"name": "plus", "value": "\n".join(s[:90] for s in strengths)[:1024], "inline": False}
        )

    location = row.get("location") or ("Remote" if row.get("remote") else "lokasi tidak disebut")
    return {
        "title": (row.get("title") or "")[:240],
        "url": row.get("url") or "",
        "description": f"{row.get('company', '')} · {location}",
        "color": COLOURS[_tone(fit)],
        "fields": fields[:6],
        "footer": {"text": f"id {str(row.get('id', ''))[:8]} · python -m jobhunter letter {str(row.get('id', ''))[:8]}"},
    }


def build_payload(rows: list[dict], min_fit: int = 55) -> dict:
    today = datetime.now().strftime("%d %b %Y")
    header = f"**{len(rows)} lowongan layak dilihat** · {today} · fit ≥ {min_fit}"
    if not rows:
        header = f"Belum ada lowongan baru di atas fit {min_fit} · {today}"
    return {
        "username": "Job Hunter",
        "content": header,
        "embeds": [_embed(row) for row in rows[:MAX_EMBEDS]],
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


def send(
    payload: dict,
    webhook_url: str | None = None,
    timeout: int = 20,
    thread_name: str | None = None,
    attachments: list[tuple[str, bytes]] | None = None,
) -> tuple[bool, str]:
    env = config.env()
    url = (webhook_url or env.get("DISCORD_WEBHOOK_URL") or "").strip()
    if not url:
        return False, "DISCORD_WEBHOOK_URL belum diisi di .env"
    if not url.startswith("https://discord.com/api/webhooks/"):
        return False, "URL bukan webhook Discord yang valid (harus https://discord.com/api/webhooks/...)"

    # wait=true returns the message object (200) instead of 204, which gives us
    # the message id — useful later for reaction-based status.
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
        return False, f"koneksi gagal: {type(exc).__name__}"

    if resp.status_code in (200, 204):
        detail = f"terkirim ({len(payload.get('embeds') or [])} embed)"
        if attachments:
            detail += f", {len(attachments)} surat"
        if thread_name:
            detail += f", thread '{thread_name[:100]}'"
        return True, detail

    if resp.status_code == 429:
        try:
            retry_after = float(resp.json().get("retry_after", 1))
        except (json.JSONDecodeError, TypeError, ValueError):
            retry_after = 1.0
        time.sleep(min(retry_after, 5))
        retry = _post()
        if retry.status_code in (200, 204):
            return True, f"terkirim setelah rate limit ({retry_after:.1f}s)"

    detail = ""
    try:
        body = resp.json()
        detail = str(body.get("message") or body)[:160]
    except (json.JSONDecodeError, ValueError):
        detail = resp.text[:160]
    return False, f"HTTP {resp.status_code}: {detail}"


_ASCII_MAP = str.maketrans({"≥": ">=", "·": "-", "–": "-", "—": "-", "→": "->", "’": "'"})


def _ascii(text: str) -> str:
    """Terminal-safe preview: legacy Windows consoles are cp1252 and crash on ≥ and ·."""
    return text.translate(_ASCII_MAP)


def preview(payload: dict) -> str:
    """Human-readable dump for --dry-run."""
    lines = [_ascii(payload["content"])]
    for embed in payload["embeds"]:
        fields = " | ".join(
            f"{f['name']}={_ascii(f['value'].replace(chr(10), ', '))}" for f in embed["fields"]
        )
        lines.append(f"  - {_ascii(embed['title'])} ({_ascii(embed['description'])}) {fields}")
    return "\n".join(lines)
