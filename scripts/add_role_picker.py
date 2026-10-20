"""Create the role-picker roles, channel, and message.

Idempotent: existing roles are reused by name, an existing channel is reused, and
the picker message is only posted when the channel is empty. The resulting
message id is written to data/role_picker.json so the bot knows what to watch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, discord_sync

API = "https://discord.com/api/v10"
SEND_MESSAGES = 1 << 11
EMBED_LINKS = 1 << 14
VIEW_CHANNEL = 1 << 10
ADD_REACTIONS = 1 << 6


def main(dry_run: bool) -> int:
    spec = yaml.safe_load((config.CONFIG_DIR / "roles.yaml").read_text(encoding="utf-8"))
    token, anchor = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}

    channel = requests.get(f"{API}/channels/{anchor}", headers=headers, timeout=20).json()
    guild_id = channel["guild_id"]
    guild = requests.get(f"{API}/guilds/{guild_id}", headers=headers, timeout=20).json()
    owner_id = guild["owner_id"]
    bot_id = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()["id"]

    existing_roles = requests.get(
        f"{API}/guilds/{guild_id}/roles", headers=headers, timeout=20
    ).json()
    by_name = {r["name"].lower(): r for r in existing_roles}

    mapping: dict[str, str] = {}
    for entry in spec["roles"]:
        name = entry["name"]
        role = by_name.get(name.lower())
        if role:
            mapping[entry["emoji"]] = role["id"]
            print(f"role '{name}' sudah ada ({role['id']})")
            continue
        if dry_run:
            print(f"[dry] buat role '{name}'")
            continue
        resp = requests.post(
            f"{API}/guilds/{guild_id}/roles",
            headers=headers,
            json={"name": name, "color": int(entry["color"], 16), "mentionable": True, "hoist": False},
            timeout=20,
        )
        if resp.status_code not in (200, 201):
            print(f"gagal buat role '{name}':", resp.status_code, resp.text[:140])
            return 1
        mapping[entry["emoji"]] = resp.json()["id"]
        print(f"role '{name}' dibuat ({resp.json()['id']})")

    channels = requests.get(f"{API}/guilds/{guild_id}/channels", headers=headers, timeout=20).json()
    picker = next((c for c in channels if c.get("type") == 0 and c.get("name") == spec["channel"]), None)
    if picker is None:
        if dry_run:
            print(f"[dry] buat #{spec['channel']}")
            return 0
        overwrites = [
            {"id": guild_id, "type": 0, "allow": "0", "deny": str(SEND_MESSAGES)},
            {"id": owner_id, "type": 1, "allow": str(SEND_MESSAGES), "deny": "0"},
            {"id": bot_id, "type": 1, "allow": str(SEND_MESSAGES | EMBED_LINKS | ADD_REACTIONS), "deny": "0"},
        ]
        resp = requests.post(
            f"{API}/guilds/{guild_id}/channels",
            headers=headers,
            json={
                "name": spec["channel"],
                "type": 0,
                "topic": "pilih role sesuai bidangmu",
                "permission_overwrites": overwrites,
            },
            timeout=20,
        )
        if resp.status_code not in (200, 201):
            print("gagal buat channel:", resp.status_code, resp.text[:160])
            return 1
        picker = resp.json()
        print(f"#{spec['channel']} dibuat ({picker['id']})")

    messages = discord_sync.fetch_messages(picker["id"], token, limit=5)
    if messages:
        print("picker sudah ada pesan; tidak diposting ulang")
        message_id = messages[0]["id"]
    else:
        if dry_run:
            print("[dry] kirim pesan picker")
            return 0
        lines = "\n".join(f"{emoji}  **{entry['name']}**" for emoji, entry in zip(mapping, spec["roles"]))
        payload = {
            "embeds": [
                {
                    "title": spec["title"],
                    "description": spec["description"] + "\n\n" + lines,
                    "color": 0x5865F2,
                    "footer": {"text": "klik emoji → dapat role · klik lagi → lepas"},
                }
            ]
        }
        resp = requests.post(
            f"{API}/channels/{picker['id']}/messages", headers=headers, json=payload, timeout=20
        )
        if resp.status_code not in (200, 201):
            print("gagal kirim picker:", resp.status_code, resp.text[:160])
            return 1
        message_id = resp.json()["id"]
        print("pesan picker dikirim:", message_id)

    # Reactions are added idempotently: PUT on an existing reaction is a no-op.
    for emoji in mapping:
        status = requests.put(
            f"{API}/channels/{picker['id']}/messages/{message_id}/reactions/{requests.utils.quote(emoji)}/@me",
            headers=headers,
            timeout=20,
        ).status_code
        safe = emoji.encode("ascii", "replace").decode("ascii")
        print(f"  reaksi {safe} -> {status}")

    state = {
        "guild_id": guild_id,
        "channel_id": picker["id"],
        "message_id": message_id,
        "roles": mapping,
    }
    path = config.DATA_DIR / "role_picker.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"state ditulis ke {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
