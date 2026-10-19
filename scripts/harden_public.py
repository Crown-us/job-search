"""Prepare the server for public visitors without leaking personal data.

1. delete the digest messages that have cover letters attached
2. lock #lowongan so only the bot/owner can post (read-only for everyone)
3. create a PRIVAT category hidden from @everyone and move the pipeline there
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, db, discord_sync

API = "https://discord.com/api/v10"

VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
READ_MESSAGE_HISTORY = 1 << 16
ADD_REACTIONS = 1 << 6


def main(dry_run: bool) -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}

    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    guild_id = channel.get("guild_id")
    guild = requests.get(f"{API}/guilds/{guild_id}", headers=headers, timeout=20).json()
    owner_id = guild.get("owner_id")
    me = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()
    bot_id = me["id"]

    # 1. delete digest messages that carry letters
    conn = db.connect()
    rows = conn.execute(
        "SELECT job_id, message_id FROM deliveries WHERE channel='discord' AND message_id IS NOT NULL"
    ).fetchall()
    print(f"pesan digest dengan surat: {len(rows)}")
    for job_id, message_id in rows:
        if dry_run:
            print(f"  [dry] hapus {message_id} (job {job_id[:8]})")
            continue
        status = requests.delete(
            f"{API}/channels/{channel_id}/messages/{message_id}", headers=headers, timeout=20
        ).status_code
        print(f"  hapus {message_id} -> {status}")
        time.sleep(0.3)
    if not dry_run:
        conn.execute("DELETE FROM deliveries WHERE channel='discord'")
        conn.commit()

    # 2. read-only public feed: deny Send Messages to @everyone, then re-allow
    #    it explicitly for the bot and the owner (channel overwrites beat roles).
    if dry_run:
        print("\n[dry] #lowongan: @everyone read-only, bot + owner tetap bisa kirim")
    else:
        steps = [
            (guild_id, 0, "0", str(SEND_MESSAGES)),
            (bot_id, 1, str(SEND_MESSAGES), "0"),
            (owner_id, 1, str(SEND_MESSAGES), "0"),
        ]
        for target, kind, allow, deny in steps:
            resp = requests.put(
                f"{API}/channels/{channel_id}/permissions/{target}",
                headers=headers,
                json={"type": kind, "allow": allow, "deny": deny},
                timeout=20,
            )
            print(f"  overwrite {target} -> {resp.status_code}")

    # 3. private category
    existing = requests.get(f"{API}/guilds/{guild_id}/channels", headers=headers, timeout=20).json()
    private_cat = next(
        (c for c in existing if c.get("type") == 4 and c.get("name", "").lower() == "privat"), None
    )
    if private_cat:
        cat_id = private_cat["id"]
        print(f"kategori PRIVAT sudah ada ({cat_id})")
    elif dry_run:
        cat_id = None
        print("[dry] buat kategori PRIVAT (tersembunyi dari @everyone)")
    else:
        overwrites = [
            {"id": guild_id, "type": 0, "allow": "0", "deny": str(VIEW_CHANNEL)},
            {"id": owner_id, "type": 1, "allow": str(VIEW_CHANNEL | READ_MESSAGE_HISTORY), "deny": "0"},
            {"id": bot_id, "type": 1, "allow": str(VIEW_CHANNEL | SEND_MESSAGES | READ_MESSAGE_HISTORY), "deny": "0"},
        ]
        resp = requests.post(
            f"{API}/guilds/{guild_id}/channels",
            headers=headers,
            json={"name": "PRIVAT", "type": 4, "permission_overwrites": overwrites},
            timeout=20,
        )
        if resp.status_code in (200, 201):
            cat_id = resp.json()["id"]
            print(f"kategori PRIVAT dibuat ({cat_id})")
        else:
            print("gagal buat kategori:", resp.status_code, resp.text[:140])
            cat_id = None

    pipeline = next((c for c in existing if c.get("name") == "pipeline" and c.get("type") == 0), None)
    if pipeline and cat_id:
        if dry_run:
            print("[dry] pindahkan #pipeline ke kategori PRIVAT")
        else:
            moved = requests.patch(
                f"{API}/channels/{pipeline['id']}",
                headers=headers,
                json={"parent_id": cat_id},
                timeout=20,
            )
            print(f"#pipeline -> PRIVAT: {moved.status_code}")
            time.sleep(0.5)
            for overwrite in (
                {"id": guild_id, "type": 0, "allow": "0", "deny": str(VIEW_CHANNEL)},
                {"id": owner_id, "type": 1, "allow": str(VIEW_CHANNEL | SEND_MESSAGES | READ_MESSAGE_HISTORY), "deny": "0"},
                {"id": bot_id, "type": 1, "allow": str(VIEW_CHANNEL | SEND_MESSAGES | READ_MESSAGE_HISTORY), "deny": "0"},
            ):
                requests.put(
                    f"{API}/channels/{pipeline['id']}/permissions/{overwrite['id']}",
                    headers=headers,
                    json=overwrite,
                    timeout=20,
                )
            print("permission #pipeline dikunci")

    if not dry_run:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
