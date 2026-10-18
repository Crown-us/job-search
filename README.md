# Job Hunter

Otomasi cari kerja: tarik lowongan dari board publik → filter → dedupe → skor →
(berikutnya) digest Telegram + cover letter.

Bukan auto-apply. Yang dikerjakan robot adalah bagian yang bikin capek: nyisir
ribuan posting jadi 10 yang layak dibaca.

## Status

| Fase | Isi | Status |
|---|---|---|
| 1 | Discovery: 5 adapter sumber, SQLite, filter, dedupe lintas sumber | selesai |
| 2 | Skoring LLM (CV vs JD) + gap analysis + cover letter | belum — nunggu CV |
| 3 | Digest Telegram + dashboard Streamlit + tracker follow-up | belum |
| 4 | Autofill lamaran (Playwright, submit tetap manual) | opsional |

Skor saat ini pakai heuristik kata kunci (tanpa API key). Fase 2 mengganti
angkanya dengan penilaian LLM terhadap CV asli, tapi bentuk outputnya sama.

## Pakai

```powershell
python -m jobhunter discover              # tarik, filter, dedupe, skor
python -m jobhunter discover --dry-run    # lihat hasil tanpa nulis DB
python -m jobhunter list --min-score 60   # yang layak dibaca
python -m jobhunter list --search python
python -m jobhunter stats
python -m jobhunter status <id> applied   # pipeline: new/shortlist/applied/interview/offer/rejected/skipped
python -m jobhunter probe                 # cek board mana yang masih hidup
python -m jobhunter score --rescore       # hitung ulang setelah profile.yaml diedit
```

## Struktur

```
config/
  companies.yaml   board yang dipoll (token per ATS)
  filters.yaml     hard filter: judul, lokasi, umur posting
  profile.yaml     profil lo — bahan bakar skoring
data/jobs.db       SQLite: jobs + runs
jobhunter/
  model.py         Job + canonical URL + fingerprint
  db.py            schema, upsert, dedupe
  pipeline.py      collect -> filter -> dedupe
  score.py         heuristik v0 (ganti LLM di fase 2)
  cli.py           argparse + tampilan
  sources/         greenhouse, ashby, lever, workable, remoteok, hackernews
```

## Sumber: apa yang hidup per 2026-10-19

Hasil `probe`, ini yang penting buat nanti nambah sumber:

- **Greenhouse** — paling produktif. 20 board hidup, ~3.600 posting. Stripe 731,
  Anthropic 655, Datadog/Cloudflare 433, MongoDB 401.
- **Ashby** — 7 board hidup (Ramp 167, ElevenLabs 156, Vanta 85).
- **Lever** — semua token kandidat mati. Perusahaan Indonesia hampir tidak ada
  yang pakai Lever.
- **Workable** — semua kandidat kosong.
- **RemoteOK** — jalan, tapi butuh User-Agent browser (default 403).
- **HN Who is Hiring** — jalan via Algolia, tapi parsing-nya kasar.

**Temuan penting:** coverage Indonesia masih tipis. Cuma Xendit (Greenhouse, 25
posting). Glints, JobStreet, Kalibrr, Dealls tidak pakai ATS publik — mereka SPA
dengan API internal sendiri, jadi butuh adapter khusus (fase 3). Ini yang bikin
"dua-duanya" belum seimbang: global sudah, lokal belum.

## Dedupe

Dua lapis:

1. `id` = SHA1 dari URL yang sudah dibersihkan dari parameter tracking
   (`utm_*`, `gh_src`, `ref`, dst). Posting yang sama tidak dobel walau di-scrape
   berkali-kali.
2. `fingerprint` = SHA1 dari `company|title|location` yang dinormalisasi.
   Lowongan yang di-repost di beberapa board jadi satu baris; yang menang adalah
   board dengan prioritas tertinggi (ATS > agregator), lalu yang punya gaji.

Terbukti di run kedua: `fetched 960, match 107, unique 106, new 0, seen 106`.

## Config

`filters.yaml` — sengaja agresif buang senioritas (`senior`, `lead`, `manager`,
`5+ years`) karena profilnya junior. Kalau hasilnya terlalu sempit, longgarkan
`exclude_title_keywords`.

`profile.yaml` — masih draft dari yang lo ceritakan. Bagian `experience`,
`projects`, dan `education.year` perlu diisi dari CV. Skor heuristik membaca
`boost_keywords`; skor LLM nanti membaca seluruh file.

## Batasan yang disengaja

- Tidak menyentuh LinkedIn (ToS + cepat kena restrict).
- Tidak auto-submit lamaran. Kalau nanti dibuat, bentuknya autofill + konfirmasi.
- Tanpa API key pun tetap jalan.
