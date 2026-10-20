"""Create the welcome area: a pinned-style intro channel plus the rules.

Read-only for @everyone; only the bot and the owner can post.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import discord_sync

API = "https://discord.com/api/v10"
SEND_MESSAGES = 1 << 11
VIEW_CHANNEL = 1 << 10
EMBED_LINKS = 1 << 14
READ_MESSAGE_HISTORY = 1 << 16
MANAGE_MESSAGES = 1 << 13

CATEGORY = "MULAI DI SINI"
CHANNEL = "selamat-datang"

INTRO = {
    "title": "👋 Selamat datang di Pencari Loker",
    "description": (
        "Kumpulan lowongan **Indonesia + remote**, disaring tiap hari.\n\n"
        "**Kenapa beda:**\n"
        "• Lowongan tanpa nama perusahaan (*Private Advertiser*) kami buang — "
        "tidak bisa diriset dan sering jadi jebakan\n"
        "• Dikurasi, bukan scrape mentah: 3–5 lowongan per hari per channel\n"
        "• Gratis, tanpa link afiliasi, tanpa biaya pendaftaran"
    ),
    "color": 0x5865F2,
    "fields": [
        {"name": "📥 Feed harian", "value": "**#dev-it** — developer, IT support\n**#kreatif** — marketing, desain, video, sosmed\n**#remote** — lowongan global", "inline": False},
        {"name": "🔍 Cari cepat", "value": "`/cari kata:laravel`\n`/cari kata:desain hari:60`\n`/cari kata:python remote:true`", "inline": False},
        {"name": "✅ Menandai lamaran", "value": "Klik reaksi di pesan lowongan:\n✅ sudah dilamar · 🔖 simpan · ❌ skip · 📅 interview", "inline": False},
    ],
}

RULES = {
    "title": "📋 Aturan",
    "description": (
        "1. **Tanpa nama perusahaan = tidak diposting.** Berlaku untuk semua member.\n"
        "2. **No spam, no DM massal.** Promosi, jualan jasa, dan tawaran \"kerja online\" tanpa perusahaan jelas akan dihapus.\n"
        "3. **No link afiliasi / referral.** Termasuk shortlink yang menyembunyikan tujuan.\n"
        "4. **Lowongan harus jelas:** posisi, lokasi, dan cara melamar.\n"
        "5. **Hormati sesama.** Ini tempat bantu-membantu, bukan debat.\n\n"
        "Pelanggaran berulang = dikeluarkan tanpa pemberitahuan."
    ),
    "color": 0xE67E22,
}


def main(dry_run: bool) -> int:
    token, channel_id = discord_sync.credentials()
    headers = {"Authorization": f"Bot {token}", "User-Agent": "jobhunter/0.1"}
    anchor = requests.get(f"{API}/channels/{channel_id}", headers=headers, timeout=20).json()
    guild_id = anchor["guild_id"]
    guild = requests.get(f"{API}/guilds/{guild_id}", headers=headers, timeout=20).json()
    owner_id = guild["owner_id"]
    bot_id = requests.get(f"{API}/users/@me", headers=headers, timeout=20).json()["id"]

    existing = requests.get(f"{API}/guilds/{guild_id}/channels", headers=headers, timeout=20).json()
    category = next((c for c in existing if c.get("type") == 4 and c.get("name") == CATEGORY), None)
    channel = next((c for c in existing if c.get("type") == 0 and c.get("name") == CHANNEL), None)

    if dry_run:
        print(f"[dry] kategori '{CATEGORY}': {'ada' if category else 'buat'}")
        print(f"[dry] #{CHANNEL}: {'ada' if channel else 'buat'}")
        print("[dry] kirim pesan sambutan + aturan")
        return 0

    if category is None:
        resp = requests.post(
            f"{API}/guilds/{guild_id}/channels",
            headers=headers,
            json={"name": CATEGORY, "type": 4},
            timeout=20,
        )
        if resp.status_code not in (200, 201):
            print("gagal buat kategori:", resp.status_code, resp.text[:160])
            return 1
        category = resp.json()
        print(f"kategori dibuat: {category['id']}")

    overwrites = [
        {"id": guild_id, "type": 0, "allow": "0", "deny": str(SEND_MESSAGES)},
        {"id": owner_id, "type": 1, "allow": str(SEND_MESSAGES), "deny": "0"},
        {"id": bot_id, "type": 1, "allow": str(SEND_MESSAGES | EMBED_LINKS), "deny": "0"},
    ]

    if channel is None:
        body = {
            "name": CHANNEL,
            "type": 0,
            "topic": "mulai dari sini: cara pakai dan aturan",
            "parent_id": category["id"],
            "permission_overwrites": overwrites,
        }
        resp = requests.post(
            f"{API}/guilds/{guild_id}/channels", headers=headers, json=body, timeout=20
        )
        if resp.status_code not in (200, 201):
            print("gagal buat channel:", resp.status_code, resp.text[:160])
            return 1
        channel = resp.json()
        print(f"#{CHANNEL} dibuat: {channel['id']}")

    # put the welcome category above the feeds
    requests.patch(
        f"{API}/channels/{category['id']}", headers=headers, json={"position": 0}, timeout=20
    )

    messages = discord_sync.fetch_messages(channel["id"], token, limit=5)
    if messages:
        print("channel sudah berisi pesan, sambutan tidak dikirim ulang")
        return 0

    payload = {
        "content": (
            "**Gratis, dikurasi, tanpa lowongan anonim.** "
            "Baca 30 detik di bawah, lalu pilih feed-mu."
        ),
        "embeds": [INTRO, RULES],
        "allowed_mentions": {"parse": []},
    }
    resp = requests.post(
        f"{API}/channels/{channel['id']}/messages", headers=headers, json=payload, timeout=20
    )
    print("pesan sambutan:", resp.status_code)
    if resp.status_code not in (200, 201):
        print(resp.text[:180])
    print(f"selesai: #{CHANNEL} = {channel['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--dry-run" in sys.argv))
