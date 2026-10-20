"""Minimal Discord gateway bot that answers slash commands.

Only depends on `websockets`, which is already installed. Handles:
  - /cari kata:<kata> [hari:<n>] [remote:<true|false>]

The bot answers ephemeral (only the asker sees it), so the channel stays clean.
Run `python -m jobhunter bot --register` once to publish the commands, then
`python -m jobhunter bot` to keep it online.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
import time

import requests
import websockets

from . import config, db

API = "https://discord.com/api/v10"
GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

COMMANDS = [
    {
        "name": "cari",
        "description": "Cari lowongan di database Job Hunter",
        "options": [
            {
                "type": 3,
                "name": "kata",
                "description": "kata kunci: judul, perusahaan, atau teknologi",
                "required": True,
            },
            {
                "type": 4,
                "name": "hari",
                "description": "batas umur posting dalam hari (default 30)",
                "required": False,
                "min_value": 1,
                "max_value": 120,
            },
            {
                "type": 5,
                "name": "remote",
                "description": "hanya lowongan remote",
                "required": False,
            },
        ],
    }
]


def _token() -> str:
    return (config.env().get("DISCORD_BOT_TOKEN") or "").strip()


def _headers() -> dict:
    return {"Authorization": f"Bot {_token()}", "User-Agent": "jobhunter/0.1"}


def _guild_id() -> str:
    channel_id = (config.env().get("DISCORD_CHANNEL_ID") or "").strip()
    resp = requests.get(f"{API}/channels/{channel_id}", headers=_headers(), timeout=20)
    resp.raise_for_status()
    return resp.json()["guild_id"]


def register() -> int:
    """Publish slash commands to the guild (instant, unlike global commands)."""
    app = requests.get(f"{API}/applications/@me", headers=_headers(), timeout=20).json()
    app_id = app["id"]
    guild = _guild_id()
    resp = requests.put(
        f"{API}/applications/{app_id}/guilds/{guild}/commands",
        headers=_headers(),
        json=COMMANDS,
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        print("gagal daftar command:", resp.status_code, resp.text[:200])
        return 1
    names = [c["name"] for c in resp.json()]
    print(f"terdaftar di guild {guild}: {', '.join('/' + n for n in names)}")
    return 0


def _epoch(value: str | None) -> int | None:
    if not value:
        return None
    text = str(value).strip()
    if text.isdigit() and len(text) in (10, 13):
        return int(text) // (1000 if len(text) == 13 else 1)
    try:
        from datetime import datetime, timezone

        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return int(moment.timestamp())
    except ValueError:
        return None


def search(keyword: str, days: int = 30, remote_only: bool = False, limit: int = 5) -> list[dict]:
    conn = db.connect()
    sql = """
        SELECT j.id, j.title, j.company, j.location, j.url, j.salary, j.remote,
               j.posted_at, j.source, a.fit
        FROM jobs j LEFT JOIN analyses a ON a.job_id = j.id
        WHERE j.status IN ('new', 'shortlist')
          AND (j.title LIKE ? OR j.company LIKE ? OR j.department LIKE ?)
    """
    like = f"%{keyword}%"
    params: list = [like, like, like]
    if remote_only:
        sql += " AND j.remote = 1"
    sql += " ORDER BY COALESCE(a.fit, j.score, 0) DESC, j.first_seen DESC LIMIT ?"
    params.append(limit * 4)
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()

    cutoff = time.time() - days * 86400
    fresh = [r for r in rows if (_epoch(r["posted_at"]) or 0) >= cutoff or _epoch(r["posted_at"]) is None]
    return fresh[:limit]


PICKER_PATH = config.DATA_DIR / "role_picker.json"


def _picker() -> dict | None:
    try:
        return json.loads(PICKER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _apply_role(guild_id: str, user_id: str, role_id: str, add: bool) -> int:
    url = f"{API}/guilds/{guild_id}/members/{user_id}/roles/{role_id}"
    call = requests.put if add else requests.delete
    return call(url, headers=_headers(), timeout=15).status_code


def handle_reaction(event_type: str, data: dict) -> None:
    """Grant or revoke a picker role. Silent for anything else in the server."""
    picker = _picker()
    if not picker:
        return
    if data.get("channel_id") != picker.get("channel_id"):
        return
    if data.get("message_id") != picker.get("message_id"):
        return

    emoji = (data.get("emoji") or {}).get("name") or ""
    role_id = (picker.get("roles") or {}).get(emoji)
    if not role_id:
        return

    member = data.get("member") or {}
    if (member.get("user") or {}).get("bot"):
        return

    user_id = data.get("user_id")
    if not user_id:
        return

    add = event_type == "MESSAGE_REACTION_ADD"
    code = _apply_role(picker["guild_id"], user_id, role_id, add)
    action = "tambah" if add else "lepas"
    safe = role_id[-4:]
    print(f"{action} role ..{safe} untuk {user_id} -> {code}")
    if code == 403:
        print("  role bot harus di ATAS role target (Server Settings -> Roles)")


def _embed(row: dict) -> dict:
    posted = _epoch(row.get("posted_at"))
    lines = [f"**{row['company']}**", f"📍 {row['location'] or 'lokasi tidak disebut'}"]
    if posted:
        lines.append(f"🕒 <t:{posted}:R>")
    fields = []
    if row.get("salary"):
        fields.append({"name": "💰 Gaji", "value": str(row["salary"])[:150], "inline": True})
    if row.get("fit") is not None:
        fields.append({"name": "Fit", "value": str(row["fit"]), "inline": True})
    return {
        "title": (row["title"] or "")[:230],
        "url": row.get("url") or "",
        "description": "\n".join(lines),
        "color": 0x5865F2 if not row.get("remote") else 0x1ABC9C,
        "fields": fields[:3],
    }


def handle_command(data: dict) -> dict:
    options = {o["name"]: o.get("value") for o in data.get("options") or []}
    keyword = str(options.get("kata") or "").strip()
    days = int(options.get("hari") or 30)
    remote_only = bool(options.get("remote") or False)

    if len(keyword) < 2:
        return {"content": "Kata kunci minimal 2 huruf.", "flags": 64}

    rows = search(keyword, days=days, remote_only=remote_only)
    if not rows:
        return {
            "content": f"Tidak ada lowongan yang cocok dengan **{keyword}** dalam {days} hari terakhir.",
            "flags": 64,
        }

    header = f"**{len(rows)} lowongan** untuk `{keyword}`"
    if remote_only:
        header += " · remote saja"
    return {
        "content": header,
        "embeds": [_embed(row) for row in rows],
        "flags": 64,
    }


def _callback(interaction_id: str, token: str, payload: dict) -> None:
    url = f"{API}/interactions/{interaction_id}/{token}/callback"
    try:
        requests.post(url, json={"type": 4, "data": payload}, timeout=15)
    except requests.RequestException as exc:
        print("gagal jawab interaksi:", type(exc).__name__)


async def run() -> int:
    token = _token()
    if not token:
        print("DISCORD_BOT_TOKEN kosong")
        return 1

    backoff = 3
    while True:
        try:
            async with websockets.connect(GATEWAY_URL, max_size=2**24) as ws:
                hello = json.loads(await ws.recv())
                interval = hello["d"]["heartbeat_interval"] / 1000
                state = {"seq": None}
                stop = asyncio.Event()

                async def heartbeat() -> None:
                    while not stop.is_set():
                        await asyncio.sleep(interval)
                        await ws.send(json.dumps({"op": 1, "d": state["seq"]}))

                beat = asyncio.create_task(heartbeat())

                await ws.send(
                    json.dumps(
                        {
                            "op": 2,
                            "d": {
                                "token": token,
                                "intents": 1,  # GUILDS only; interactions need no privileged intent
                                "properties": {"os": "windows", "browser": "jobhunter", "device": "jobhunter"},
                            },
                        }
                    )
                )
                print("terhubung ke gateway, menunggu interaksi...")

                try:
                    async for raw in ws:
                        event = json.loads(raw)
                        if event.get("s") is not None:
                            state["seq"] = event["s"]
                        if event.get("op") == 1:
                            await ws.send(json.dumps({"op": 1, "d": state["seq"]}))
                            continue
                        if event.get("t") == "READY":
                            user = event["d"]["user"]
                            print(f"login sebagai {user['username']} ({user['id']})")
                        elif event.get("t") == "INTERACTION_CREATE":
                            interaction = event["d"]
                            if interaction.get("type") != 2:
                                continue
                            payload = handle_command(interaction.get("data") or {})
                            _callback(interaction["id"], interaction["token"], payload)
                            print(f"menjawab /{interaction['data'].get('name')}")
                        elif event.get("t") in ("MESSAGE_REACTION_ADD", "MESSAGE_REACTION_REMOVE"):
                            handle_reaction(event["t"], event["d"])
                finally:
                    stop.set()
                    beat.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await beat
        except KeyboardInterrupt:
            print("berhenti")
            return 0
        except Exception as exc:
            print(f"koneksi terputus: {type(exc).__name__}: {exc}; coba lagi {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue
        backoff = 3


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    if "--register" in argv:
        return register()
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
