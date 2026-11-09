"""Inspect/update bot-owned welcome and manual-job guide. No mass mentions."""
import json
import sys
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobhunter import config, discord_sync

WELCOME = "1561911081948151808"
MANUAL = "1562114975248416788"

def main():
    token, anchor = discord_sync.credentials()
    session = requests.Session()
    session.headers.update({"Authorization": f"Bot {token}"})
    def call(method, path, **kwargs):
        r = session.request(method, "https://discord.com/api/v10" + path, timeout=25, **kwargs)
        if not r.ok:
            raise RuntimeError(f"{method} {path}: HTTP {r.status_code}")
        return r.json() if r.content else None
    me = call("GET", "/users/@me")
    channel = call("GET", f"/channels/{anchor}")
    commands = call("GET", f"/applications/{me['id']}/guilds/{channel['guild_id']}/commands")
    print("Bot:", me['username'], "| commands:", [c['name'] for c in commands])
    own = {}
    for cid in (WELCOME, MANUAL):
        messages = call("GET", f"/channels/{cid}/messages", params={"limit": 100})
        own[cid] = [m for m in messages if m.get("author", {}).get("id") == me['id']]
        print("Channel", cid, "bot messages:", [{"id": m['id'], "content": m.get('content', '')[:250], "titles": [e.get('title') for e in m.get('embeds', [])]} for m in own[cid]])
    if '--apply' not in sys.argv:
        return
    intro = {
        "title": "👋 Selamat datang di Pencari Loker",
        "description": "Cari kerja bareng, mulai dari sini:\n\n**1. Pilih bidang** di <#1561911782480683080> — klik emoji buat ambil role, klik lagi buat lepas.\n**2. Buka feed** <#1561725081095250023> buat dev/IT, <#1561730155158966363> buat kreatif, atau <#1561733022368407623> buat remote.\n**3. Cari sendiri** pakai `/cari kata:laravel` atau `/cari kata:desain hari:60`. Hasilnya cuma terlihat oleh lo.\n\nPunya info loker? Bagikan di <#1562114975248416788>.",
        "color": 0x5865F2,
    }
    tracking = {
        "title": "🔖 Tandai progres lamaran lo",
        "description": "Tambahkan reaksi ke pesan bot yang berisi satu lowongan:\n✅ sudah dilamar · 🔖 simpan · ❌ skip · 📅 interview · 🏆 dapat offer\n\nStatus disimpan **per akun Discord**, jadi nggak mengubah progres anggota lain. Emoji reaksinya tetap terlihat anggota channel.\nStatus diperbarui saat admin menjalankan sinkronisasi atau pipeline harian — belum langsung saat diklik. Setelah sync, `/cari` menyembunyikan lowongan yang sudah lo tindak lanjuti; yang disimpan tetap muncul.\n\nPakai satu reaksi status. Kalau ganti, hapus yang lama. Jika beberapa tetap ada, urutannya: offer → interview → skip → applied → simpan. Menghapus semua reaksi tidak mereset status terakhir.",
        "color": 0x2F9E5F,
    }
    welcome = next((m for m in own[WELCOME] if any('Selamat datang' in e.get('title','') for e in m.get('embeds', []))), None)
    preserved = [e for e in (welcome or {}).get('embeds', []) if 'Aturan' in e.get('title','')]
    payloads = {WELCOME: {"content": "**Mulai dari pilih bidang, lalu cari lowongan yang cocok.**", "embeds": [intro, tracking] + preserved}, MANUAL: {"content": "📌 **Format berbagi lowongan**\nSalin format ini biar gampang dibaca:\n```\nPerusahaan:\nPosisi:\nLokasi + onsite/hybrid/remote:\nGaji: (kalau belum ada, tulis tidak dicantumkan)\nJenis kerja: full-time/kontrak/magang/freelance\nSyarat utama:\nCara melamar + link resmi:\nDeadline: (atau tidak dicantumkan)\nSumber + tanggal info:\n```\nPastikan perusahaan dan tujuan link jelas. Kalau sudah tutup, edit postingan lo dan tambahkan **[DITUTUP]**."}}
    backup = config.DATA_DIR / 'server-layout' / 'guides-before.json'
    if not backup.exists():
        backup.write_text(json.dumps(own, ensure_ascii=False, indent=2), encoding='utf-8')
    for cid, payload in payloads.items():
        payload['allowed_mentions'] = {'parse': []}
        previous = welcome if cid == WELCOME else next((m for m in own[cid] if 'Format berbagi lowongan' in m.get('content','')), None)
        if previous:
            result = call('PATCH', f"/channels/{cid}/messages/{previous['id']}", json=payload)
        else:
            result = call('POST', f"/channels/{cid}/messages", json=payload)
        saved = call('GET', f"/channels/{cid}/messages/{result['id']}")
        assert saved.get('content') == payload['content']
        print('Verified guide:', f"https://discord.com/channels/{channel['guild_id']}/{cid}/{result['id']}")

if __name__ == '__main__':
    main()
