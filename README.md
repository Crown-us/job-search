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
| 2 | JD lengkap + gap analysis + cover letter | selesai (heuristik); LLM siap, tinggal API key |
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
python -m jobhunter enrich --min-score 60 # unduh JD penuh untuk shortlist
python -m jobhunter analyze --min-score 82   # gap analysis: CV vs JD
python -m jobhunter letter <id>           # draft cover letter, disimpan ke data/letters/
python -m jobhunter digest --open         # halaman HTML shortlist hari ini
python -m jobhunter digest --email        # sekaligus kirim lewat SMTP
python -m jobhunter stats
python -m jobhunter clean --dry-run       # lihat lowongan yang melanggar filter sekarang
python -m jobhunter clean                 # hapus dari database (status new/shortlist saja)
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

## Lowongan anonim ditolak

JobStreet menandai pengiklan tanpa identitas sebagai **"Private Advertiser"**.
Lowongan seperti itu tidak bisa diriset — tidak ada nama perusahaan, tidak ada
alamat, tidak ada jejak — dan di Indonesia pola ini sering dipakai untuk
lowongan abal-abal atau jebakan biaya administrasi. Karena itu ditolak di dua
tempat:

1. `filters.yaml` → `exclude_company_keywords` memuat `private advertiser`,
   `confidential`, `anonymous`, `undisclosed`, `tanpa nama`, `perusahaan rahasia`.
2. `require_company_name: true` membuang lowongan yang nama perusahaannya kosong
   atau "Unknown", termasuk kalau suatu saat sumber baru mengirim data cacat.

Filter berjalan **sebelum** insert, jadi lowongan anonim tidak pernah masuk
database lagi. Untuk membereskan yang sudah terlanjur tersimpan:

```powershell
python -m jobhunter clean --dry-run   # lihat dulu
python -m jobhunter clean             # hapus
```

`clean` hanya menyentuh status `new` dan `shortlist`; lowongan yang sudah
`applied` atau `interview` tidak dihapus karena itu riwayat lamaran.

Jalankan `python scripts/why_filtered.py` untuk melihat alasan penolakan tiap
baris (perusahaan, judul, lokasi, atau umur posting).

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

## JD penuh dan gap analysis

Board ID hanya mengirim teaser di hasil pencarian, jadi `enrich` mengambil
deskripsi asli dari halaman lowongan. Ekstraktornya membaca JSON-LD `JobPosting`
dulu, lalu jatuh ke blok `data-automation="jobAdDetails"` milik SEEK.

`analyze` membandingkan JD dengan `profile.yaml` dan mengeluarkan `fit` 0–100:

- **gelar** — JD minta S1/sarjana sementara CV D3 → gap, kecuali JD menyebut
  fresh graduate dipersilakan
- **pengalaman** — "min. 2 tahun" dibandingkan 17 bulan magang
- **teknologi** — hanya kata utuh: `java` tidak lagi cocok dengan `javascript`,
  dan `excel` cocok dengan "Microsoft Excel"

`letter` menyusun cover letter dari fakta CV: memilih magang yang paling relevan
dengan JD, menyebut stack yang diminta, dan menjawab gap gelar secara langsung.
Disimpan ke `data/letters/`.

## Mode LLM (opsional)

Salin `.env.example` menjadi `.env`, isi `LLM_API_KEY` (OpenAI-compatible:
OpenAI, DeepSeek, Groq, OpenRouter, Ollama). Tanpa key, `analyze` dan `letter`
tetap jalan dengan mesin heuristik; dengan key, keduanya memakai LLM dan
`engine` di output berubah dari `heuristic` menjadi `llm`.

## Digest harian (tanpa Telegram, tanpa HP)

`digest` menghasilkan satu file HTML mandiri di `data/digest/`: tanpa aset
eksternal, tanpa akun, jalan offline di browser mana pun. Isinya kartu per
lowongan — fit, gap, kelebihan, link lamaran, link surat yang sudah dibuat, dan
perintah untuk menandai status.

Tiga cara memakainya:

1. **Manual** — `python -m jobhunter digest --open`, atau klik dua kali
   `daily.cmd` yang menjalankan discover → enrich → analyze → digest sekaligus.
2. **Terjadwal** — Windows Task Scheduler, aksi: jalankan `daily.cmd`.
   Tidak perlu PowerShell execution policy karena ini file `.cmd`.
3. **Email** — isi `SMTP_HOST/PORT/USER/PASS/DIGEST_TO` di `.env` (Gmail pakai
   App Password), lalu `python -m jobhunter digest --email`. Berguna saat HP
   sedang tidak bisa dipakai; email tetap bisa dibuka dari PC.

Alternatif lain kalau nanti butuh notifikasi: Discord webhook (butuh server
Discord, tidak butuh HP) atau Windows toast. Yang butuh nomor HP aktif —
Telegram, WhatsApp — sebaiknya ditunda sampai HP hidup.

## Notifikasi desktop

`python -m jobhunter toast --min-fit 75` memunculkan notifikasi berisi jumlah
lowongan baru plus dua teratas. Ada dua mesin, dipilih otomatis:

1. **toast native** (`Windows.UI.Notifications`). Tampil di pojok kanan bawah,
   masuk Action Center, ada suara. Butuh **AppUserModelID** yang dikenali
   Windows. Proses yang tidak punya *package identity* — termasuk skrip Python
   biasa — ditolak dengan `0x80073D54`.
2. **balloon** (`System.Windows.Forms.NotifyIcon`). Tampilan lebih lama, tidak
   masuk Action Center, tapi tidak butuh registrasi apa pun.

`--mode auto` (default) mencoba toast dulu lalu jatuh ke balloon, dan melaporkan
mesin mana yang dipakai. `--mode toast` / `--mode balloon` memaksa satu mesin.

Untuk mengaktifkan toast native, daftarkan AppID sekali dari PowerShell biasa
(bukan dari dalam sandbox, yang memblokir registry):

```powershell
$p = 'HKCU:\SOFTWARE\Classes\AppUserModelId\JobHunter.Toast'
New-Item -Path $p -Force
Set-ItemProperty -Path $p -Name DisplayName -Value 'Job Hunter'
Set-ItemProperty -Path $p -Name ShowInSettings -Value 1 -Type DWord
```

lalu isi `TOAST_APP_ID=JobHunter.Toast` di `.env`.

Batas yang tidak bisa dilanggar: toast tidak bisa diklik untuk membuka URL tanpa
COM activator terdaftar, tidak muncul kalau PC mati, dan ditelan Focus Assist
tanpa pesan error. Karena itu digest HTML tetap menjadi tempat kerja, toast
hanya pengingat.

## Discord webhook

`python -m jobhunter discord --min-fit 60` mengirim shortlist ke channel Discord
sebagai satu pesan: header jumlah lowongan + maksimal 10 embed (judul jadi link,
fit, skor, sumber, gap, plus). Warna embed mengikuti fit: hijau >= 75, kuning >= 55,
merah di bawahnya.

Setup, sekali saja, tanpa bot dan tanpa nomor HP:

1. Daftar/masuk Discord lewat browser atau aplikasi desktop - registrasi cukup email.
2. Buat server pribadi: `+` di sidebar -> Create My Own -> beri nama.
3. Server Settings -> **Integrations** -> **Webhooks** -> **New Webhook**.
4. Pilih channel, beri nama "Job Hunter", lalu **Copy Webhook URL**.
5. Isi `.env`: `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...`

Uji tanpa mengirim: `python -m jobhunter discord --dry-run` mencetak isi pesan.
Hapus `--dry-run` untuk benar-benar mengirim.

Tiga mode pengiriman:

- **satu pesan berisi banyak kartu** (`--limit 8`) — paling ringkas, tapi reaksi
  tidak bisa menunjuk kartu tertentu karena reaksi menempel ke pesan.
- **`--thread`** — pesan masuk ke thread baru bernama `Lowongan 19 Oct`, jadi
  channel utama tetap bersih.
- **`--per-job`** — satu pesan per lowongan. Ini yang dipakai `daily.cmd`, karena
  setiap pesan menyimpan message id-nya sehingga reaksi ✅ hanya mengubah job itu.

`--attach-letters` melampirkan cover letter `.md`; pada `--per-job` surat ikut ke
pesan lowongannya masing-masing.

```
python -m jobhunter discord --only-new --limit 5 --min-fit 75 --per-job --attach-letters
```

## Reaksi jadi status lamaran

`python -m jobhunter sync` membaca reaksi di channel dan mengubah status:

| Reaksi | Status |
|---|---|
| ✅ | applied |
| 🔖 | shortlist |
| ❌ | skipped |
| 📅 | interview |
| 🏆 | offer |

Mapping-nya lewat **message id yang disimpan saat mengirim** (kolom
`deliveries.message_id`), bukan dengan membaca isi pesan. Ini penting: bot tanpa
privileged **Message Content intent** tetap menerima metadata dan reaksi, tapi
`content`/`embeds`/`attachments` dikosongkan Discord. Karena kita mencocokkan
lewat id, sync tetap jalan tanpa intent tersebut.

Kalau ingin pesan juga terbaca lengkap lewat API (misal untuk debugging),
nyalakan **MESSAGE CONTENT INTENT** di Developer Portal → Bot → Privileged
Gateway Intents, lalu `python scripts/check_message_intent.py` untuk memastikan
flag-nya sudah aktif.

Tingkat lanjutan yang **belum** dibuat, sengaja: reaksi ✅ untuk menandai
`applied` butuh bot token, undangan bot ke server, dan proses polling REST
(`GET /channels/{id}/messages/{mid}/reactions/...`). Tombol interaktif lebih
berat lagi karena butuh endpoint publik atau koneksi gateway. Keduanya baru
layak kalau tracking lewat CLI sudah terasa mengganggu - selama masih di depan
PC, `python -m jobhunter status <id> applied` lebih cepat.

Catatan:

- Webhook URL itu **kredensial**. Siapa pun yang memegangnya bisa memposting ke
  channel itu. Jangan di-commit - `.env` sudah masuk `.gitignore`.
- Batas Discord: 10 embed per pesan, sekitar 30 request per menit per webhook.
  Kode menangani `429` dengan menunggu `retry_after` lalu mengirim sekali lagi.
- Pesan webhook tidak bisa dijadikan tombol interaktif tanpa aplikasi terdaftar;
  karena itu tiap embed hanya berisi link ke lowongan.
- `daily.cmd` sudah memanggil langkah ini sebagai langkah 6; kalau URL kosong,
  ia hanya mencetak peringatan dan lanjut.
- `--only-new` melewati lowongan yang sudah pernah dikirim ke channel itu. Setiap
  pengiriman dicatat di tabel `deliveries` (job_id, channel, sent_at), jadi
  menjalankan perintah dua kali tidak memposting hal yang sama.
- Saat filter ini pertama kali dipakai, database masih punya backlog: semua
  lowongan lama di atas ambang akan dikirim bertahap. Naikkan `--min-fit` atau
  kecilkan `--limit` kalau channel terasa ramai; `daily.cmd` memakai
  `--limit 5 --min-fit 75`.
- `python scripts/delivery_state.py` menunjukkan berapa yang sudah terkirim dan
  berapa yang masih tersisa.

## Batasan yang disengaja

- Tidak menyentuh LinkedIn (ToS + cepat kena restrict).
- Tidak auto-submit lamaran.
- Tanpa API key pun tetap jalan.
