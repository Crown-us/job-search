# Job Hunter

Otomasi cari kerja: tarik lowongan dari board publik → filter → dedupe → skor →
(berikutnya) gap analysis, cover letter, dan digest Telegram.

Bukan auto-apply. Yang dikerjakan robot adalah bagian yang bikin capek: nyisir
1.340 posting jadi 22 yang layak dibaca.

## Status

| Fase | Isi | Status |
|---|---|---|
| 1 | Discovery: 8 adapter (4 ATS global, 2 board ID, 2 feed), SQLite, filter, dedupe | selesai |
| 1b | Profil dari CV asli + skoring heuristik berbasis track | selesai |
| 2 | Skoring LLM (CV vs JD penuh) + gap analysis + cover letter | belum |
| 3 | Digest Telegram + dashboard Streamlit + tracker follow-up | belum |
| 4 | Autofill lamaran (Playwright, submit tetap manual) | opsional |

## Angka run terakhir (2026-10-19)

```
fetched 1.340   match filter 407   unique 276   new 8   seen 268
jobstreet 320 | greenhouse 728 | ashby 232 | kalibrr 60
database: 280 posting (jobstreet 133, greenhouse 79, kalibrr 41, ashby 27)
shortlist skor >= 70: 22 lowongan
```

## Pakai

```powershell
python -m jobhunter discover              # tarik, filter, dedupe, skor
python -m jobhunter discover --dry-run    # lihat hasil tanpa nulis DB
python -m jobhunter list --min-score 70   # yang layak dibaca
python -m jobhunter list --search laravel
python -m jobhunter stats
python -m jobhunter score --rescore       # setelah profile.yaml diedit
python -m jobhunter status <id> applied   # new/shortlist/applied/interview/offer/rejected/skipped
python -m jobhunter probe                 # cek board ATS mana yang masih hidup
```

## Struktur

```
config/
  companies.yaml   board ATS yang dipoll (token per perusahaan)
  searches.yaml    kata kunci untuk board ID (JobStreet, Kalibrr)
  filters.yaml     hard filter: judul, senioritas, lokasi, umur posting
  profile.yaml     profil Kevin — bahan bakar skoring
data/jobs.db       SQLite: jobs + runs
scripts/           probe API, ekstrak teks CV, purge per sumber
jobhunter/
  model.py         Job + canonical URL + fingerprint
  db.py            schema, upsert, dedupe
  pipeline.py      collect -> filter -> dedupe
  score.py         heuristik v1 berbasis track
  cli.py           argparse + tampilan
  sources/         greenhouse, ashby, lever, workable, jobstreet, kalibrr, remoteok, hackernews
```

## Sumber: temuan per 2026-10-19

| Sumber | Status | Volume | Catatan |
|---|---|---|---|
| Greenhouse | hidup | 20 board, ~3.600 | Stripe 731, Anthropic 655, Datadog 433 |
| Ashby | hidup | 7 board | Ramp 167, ElevenLabs 156, Vanta 85 |
| **JobStreet** | **hidup** | **1.482 untuk "developer"** | wajib `id.jobstreet.com` + `siteKey=ID-Main`; host `.co.id` diam-diam balikin lowongan Australia |
| **Kalibrr** | **hidup** | ~143 per 8 kata kunci | wajib parameter `text=`; `q`/`search` diabaikan dan hasilnya jadi feed satu perusahaan |
| Lever | mati | 0 | 18 token kandidat, semua 404 |
| Workable | mati | 0 | semua kosong |
| RemoteOK | hidup | feed | butuh User-Agent browser |
| HN Who is Hiring | hidup | feed | parsing kasar |

Tiga jebakan yang sudah dipetakan: JobStreet `.co.id` → Australia, Kalibrr tanpa
`text=` → feed Ruangguru, Glints → 404 di semua endpoint `/api/v1`.

## Dedupe

1. `id` = SHA1 dari URL yang dibersihkan dari parameter tracking.
2. `fingerprint` = SHA1 dari `company|title|location`. Lowongan yang di-repost di
   beberapa board jadi satu baris; ATS menang atas agregator, lalu yang ada gajinya.

## Skoring (heuristik v1)

`score.py` membaca `profile.yaml`:

- **track** — `fullstack`, `it_support`, `ai_junior`, `admin_data`; dicocokkan ke
  **judul saja**. Deskripsi penuh menyebut "AI/prompt/automation" secara sambil
  lalu, jadi kalau ikut dinilai, lowongan Customer Experience ikut naik.
- **penalti** — kata `avoid_keywords` di judul, `3+ years` di JD, dan lowongan
  on-site di kota AS/EU (butuh izin kerja).
- **bonus** — lokasi Indonesia, level entry, remote, ada info gaji.

Skor 0–100 plus alasan yang bisa dibaca (`score_reason`). LLM nanti mengganti
angkanya tapi mempertahankan bentuk output ini.

## Batasan yang disengaja

- Tidak menyentuh LinkedIn (ToS + cepat kena restrict).
- Tidak auto-submit lamaran.
- Tanpa API key pun tetap jalan.
