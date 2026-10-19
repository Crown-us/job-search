"""Set up the Job Hunter channel structure, then move the webhook into it.

Idempotent: existing channels with the same name are reused, so running it twice
is safe. Needs MANAGE_CHANNELS on the bot.

Run: python scripts/setup_server.py --dry-run
     python scripts/setup_server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import config, discord_sync

API = "https://discord.com/api/v10"

CATEGORY = "JOB HUNTER"
CHANNELS = [
    ("lowongan", "tempat digest otomatis"),
    ("pipeline", "ringkasan status lamaran"),
]


def parse_webhook(url: str) -> tuple[str, str] | None:
    parts = url.rstrip("/").split("/")
    if len(parts) < 2 or "webhooks" not in parts:
        return None
    index = parts.index("webhooks")
    try:
        return parts[index + 1], parts[index + 2]
    except IndexError:
        return None


def main(dry_run: bool) -> int:
    token, channel_id = discord_sync.credentials()
    webhook_url = (config.env().get("DISCORD_WEBHOOK_URL") or "").strip()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}

    channel = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    guild_id = channel.get("guild_id")
    if not guild_id:
        print("tidak bisa menemukan server dari channel id")
        return 1

    existing = requests.get(f"{API}/guilds/{guild_id}/channels", headers=headers, timeout=20).json()
    if not isinstance(existing, list):
        print("gagal membaca channel:", existing)
        return 1
    by_name = {str(c.get("name", "")).lower(): c for c in existing}
    print(f"server {guild_id}: {len(existing)} channel sekarang")

    # 1. category
    category_id = None
    if CATEGORY.lower() in by_name:
        category_id = by_name[CATEGORY.lower()]["id"]
        print(f"  kategori '{CATEGORY}' sudah ada")
    elif dry_run:
        print(f"  [dry] buat kategori '{CATEGORY}'")
    else:
        resp = requests.post(
            f"{API}/guilds/{guild_id}/channels",
            headers=headers,
            json={"name": CATEGORY, "type": 4},
            timeout=20,
        )
        if resp.status_code not in (200, 201):
            print("  gagal buat kategori:", resp.status_code, resp.text[:120])
            return 1
        category_id = resp.json()["id"]
        print(f"  kategori '{CATEGORY}' dibuat ({category_id})")

    # 2. text channels
    target_id = None
    for name, topic in CHANNELS:
        if name.lower() in by_name:
            found = by_name[name.lower()]
            print(f"  #{name} sudah ada ({found['id']})")
            if name == "lowongan":
                target_id = found["id"]
            continue
        if dry_run:
            print(f"  [dry] buat #{name} - {topic}")
            continue
        body = {"name": name, "type": 0, "topic": topic}
        if category_id:
            body["parent_id"] = category_id
        resp = requests.post(
            f"{API}/guilds/{guild_id}/channels", headers=headers, json=body, timeout=20
        )
        if resp.status_code not in (200, 201):
            print(f"  gagal buat #{name}:", resp.status_code, resp.text[:140])
            return 1
        created = resp.json()["id"]
        print(f"  #{name} dibuat ({created})")
        if name == "lowongan":
            target_id = created

    # 3. move the webhook
    hook = parse_webhook(webhook_url)
    if not hook:
        print("\nwebhook tidak terbaca dari .env")
        return 1
    webhook_id, webhook_token = hook
    if not target_id:
        print("\n#lowongan belum ada, webhook tidak dipindah")
        return 1

    current = requests.get(f"{API}/webhooks/{webhook_id}/{webhook_token}", timeout=20)
    current_channel = current.json().get("channel_id") if current.status_code == 200 else None
    if current_channel == target_id:
        print(f"\nwebhook sudah ada di #lowongan ({target_id})")
    elif dry_run:
        print(f"\n[dry] pindahkan webhook dari {current_channel} ke #lowongan ({target_id})")
    else:
        moved = requests.patch(
            f"{API}/webhooks/{webhook_id}/{webhook_token}",
            json={"channel_id": target_id},
            timeout=20,
        )
        if moved.status_code != 200:
            print("\n gagal pindah webhook:", moved.status_code, moved.text[:140])
            return 1
        print(f"\nwebhook dipindah ke #lowongan ({target_id})")

    # 4. point .env at the new channel
    env_path = config.ROOT / ".env"
    if not dry_run and env_path.exists():
        text = env_path.read_text(encoding="utf-8")
        lines = []
        found = False
        for line in text.splitlines():
            if line.startswith("DISCORD_CHANNEL_ID="):
                lines.append(f"DISCORD_CHANNEL_ID={target_id}")
                found = True
            else:
                lines.append(line)
        if not found:
            lines.append(f"DISCORD_CHANNEL_ID={target_id}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f".env: DISCORD_CHANNEL_ID -> {target_id}")

    if dry_run:
        print("\ndry run: tidak ada perubahan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
