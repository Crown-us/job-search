"""Public static job board: index.html (fonts from Google Fonts) plus jobs.json.

Only public fields leave the database: title, company, location, salary,
remote flag, source, dates, track and the original URL. Personal CV fit,
gaps, letters, statuses and score reasons are never written.

Design notes ("Maniak Kerja", loud tabloid / classifieds, ENERGY 3 / RHYTHM 2 / MOTION 1):
- palette: newsprint paper + ink, tabloid red for the nameplate and the scam
  warning (brand + danger), yellow marker reserved for "baru" (headline count and
  the sticker on fresh ads), because new-since-yesterday is what a daily reader scans for
- Anton (condensed, all caps) is the tabloid nameplate/headline voice; Libre Franklin
  is a Franklin Gothic revival, the classic newspaper gothic, for dense ad text
- halftone dots on the red nameplate and hard offset ink shadows on hover are the
  print motif; boxed ads in auto-fill columns read as a classifieds page
- tracks are black section kickers, not per-track colours, to keep the palette at
  paper/ink/red + one yellow accent
- the full list is server-rendered; JavaScript only filters it, so the page
  works without JS and has no loading or fetch-error state to show
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, db
from . import score as scoring
from .discord_notify import SOURCE_LABEL, _epoch

TRACK_LABEL = {
    "fullstack": "Developer",
    "it_support": "IT Support",
    "ai_junior": "AI & Data",
    "admin_data": "Admin & Data Entry",
    "marketing": "Marketing",
    "video_editor": "Video Editor",
    "graphic_design": "Desain Grafis",
    "social_media": "Social Media",
}

MONTHS = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
          "Agustus", "September", "Oktober", "November", "Desember"]
DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
WIB = timezone(timedelta(hours=7))
NEW_HOURS = 48


def _salary(value: str) -> str:
    """Drop placeholder salaries such as Kalibrr's bare '1' flag."""
    text = (value or "").strip()
    if not text or re.fullmatch(r"\d{1,3}", text) or text.lower() in {"true", "false", "none"}:
        return ""
    return text[:80]


def _day(moment: datetime) -> str:
    local = moment.astimezone(WIB)
    return f"{local.day} {MONTHS[local.month - 1][:3]} {local.year}"


def select_jobs(min_score: int = 60, max_age_days: int = 30, now: datetime | None = None) -> list[dict]:
    """Fresh, named, track-matched postings ranked newest first."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=max_age_days)).timestamp()
    tracks = config.profile().get("tracks") or {}
    conn = db.connect()
    rows = [dict(r) for r in conn.execute(
        "SELECT id, source, company, title, url, location, remote, salary, department, "
        "posted_at, first_seen FROM jobs"
    )]
    conn.close()

    picked = []
    for row in rows:
        company = (row.get("company") or "").strip()
        if not company or company.lower() == "unknown":
            continue
        best = scoring._best_track(f"{row.get('title') or ''} {row.get('department') or ''}", tracks)
        if not best:
            continue
        posted = _epoch(row.get("posted_at")) or _epoch(row.get("first_seen"))
        if posted is None or posted < cutoff:
            continue
        if scoring.public_score(row) < min_score:
            continue
        # "Baru" follows the posting date when the board gives one, so a backlog
        # pulled in for the first time is not passed off as fresh.
        fresh_since = _epoch(row.get("posted_at")) or _epoch(row.get("first_seen")) or posted
        picked.append({
            "id": row["id"][:12],
            "title": (row.get("title") or "").strip(),
            "company": company,
            "location": (row.get("location") or "").strip() or ("Remote" if row.get("remote") else ""),
            "remote": bool(row.get("remote")),
            "salary": _salary(row.get("salary") or ""),
            "source": SOURCE_LABEL.get(row.get("source") or "", row.get("source") or ""),
            "track": best[1],
            "url": row.get("url") or "",
            "posted": posted,
            "new": now.timestamp() - fresh_since <= NEW_HOURS * 3600,
        })
    picked.sort(key=lambda j: j["posted"], reverse=True)
    return picked


def _entry(job: dict) -> str:
    e = html.escape
    where = e(job["location"][:90]) if job["location"] else "Lokasi tidak disebut"
    kicker = TRACK_LABEL.get(job["track"], job["track"])
    tags = []
    if job["remote"]:
        tags.append('<span class="tag">Remote</span>')
    pay = f'<p class="pay">{e(job["salary"])}</p>' if job["salary"] else ""
    posted = _day(datetime.fromtimestamp(job["posted"], timezone.utc))
    mark = '<span class="new">Baru</span>' if job["new"] else ""
    haystack = e(f"{job['title']} {job['company']} {job['location']}".lower(), quote=True)
    return f"""
    <article class="ad" data-track="{e(job['track'], quote=True)}" data-remote="{int(job['remote'])}"
             data-text="{haystack}">
      {mark}
      <p class="kicker"><span>{e(kicker)}</span>{''.join(tags)}</p>
      <h2><a href="{e(job['url'], quote=True)}" rel="noopener nofollow">{e(job['title'])}</a></h2>
      <p class="who">{e(job['company'])}</p>
      <p class="where">{where}</p>
      {pay}
      <p class="src">via {e(job['source'])}, diposting {posted}</p>
    </article>"""


FONTS = ("https://fonts.googleapis.com/css2?family=Anton&"
         "family=Libre+Franklin:wght@400;600;800&display=swap")

CSS = """
:root {
  --paper: #f2ebdb; --card: #fbf7ee; --ink: #15120d; --muted: #554d40; --rule: #b9ad97;
  --red: #c4161c; --red-text: #a8121a; --marker: #ffd43b; --marker-ink: #15120d;
  --display: "Anton", Impact, "Arial Narrow Bold", sans-serif;
  --news: "Libre Franklin", "Franklin Gothic Medium", system-ui, sans-serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #16130f; --card: #201c16; --ink: #f1e9d8; --muted: #bdb3a1; --rule: #4d463b;
    --red-text: #ff7a6e; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #16130f; --card: #201c16; --ink: #f1e9d8; --muted: #bdb3a1; --rule: #4d463b;
  --red-text: #ff7a6e; color-scheme: dark;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.5 var(--news); }
a, button, select, label[for], input[type=checkbox] { cursor: pointer; }
a { color: inherit; text-underline-offset: 3px; }
:focus-visible { outline: 3px solid var(--red); outline-offset: 2px; }
.wrap { max-width: 74rem; margin: 0 auto; padding: 0 16px; }

/* Nameplate: tabloid red band; the halftone dots are the newsprint motif. */
.nameplate { background-color: var(--red); color: #fff;
  background-image: radial-gradient(rgba(0,0,0,.22) 1.1px, transparent 1.6px);
  background-size: 7px 7px; border-bottom: 6px solid var(--ink); }
.np { display: flex; justify-content: space-between; align-items: center; gap: 12px 20px;
  flex-wrap: wrap; padding: 18px 16px 14px; }
.np h1 { font: 400 clamp(3rem, 13vw, 7.5rem)/.9 var(--display); margin: 0; text-transform: uppercase;
  letter-spacing: .01em; text-shadow: 3px 3px 0 #15120d; }
.np .motto { font: 800 .95rem/1.3 var(--news); margin: 8px 0 0; }
.nameplate :focus-visible { outline-color: #fff; }
.theme { font: 600 .9rem var(--news); color: #fff; background: transparent; border: 2px solid #fff;
  min-height: 44px; padding: 0 14px; }
.theme:hover { background: #fff; color: var(--red); }
.theme:active { transform: translateY(1px); }
.dateline { border-bottom: 1px solid var(--ink); font-size: .9rem; font-weight: 600; }
.dateline .wrap { padding-top: 8px; padding-bottom: 8px; }

/* Lead: the one headline per edition; yellow marker = "baru" everywhere. */
.lead { padding-top: 28px; padding-bottom: 8px; }
.headline { font: 400 clamp(2rem, 7vw, 4.2rem)/1.02 var(--display); text-transform: uppercase;
  margin: 0; max-width: 24ch; }
mark { background: var(--marker); color: var(--marker-ink); padding: 0 .12em;
  box-decoration-break: clone; -webkit-box-decoration-break: clone; }
.deck { font-size: 1.1rem; margin: 14px 0 0; max-width: 40rem; }

/* Sticky filter strip */
.panel { position: sticky; top: 0; z-index: 3; background: var(--paper);
  margin-top: 24px; padding-bottom: 10px; border-bottom: 3px solid var(--ink); }
form.filters { display: grid; grid-template-columns: 2fr 1fr auto; gap: 10px 14px; align-items: end;
  margin: 0; padding: 14px 0 0; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: .9rem; font-weight: 600; color: var(--ink); }
.field input, .field select { font: inherit; font-weight: 400; font-size: 1rem; color: var(--ink);
  background: var(--card); border: 2px solid var(--ink); border-radius: 0; min-height: 44px; padding: 0 10px; }
.field input:hover, .field select:hover { background: var(--paper); }
.check { display: flex; align-items: center; gap: 10px; min-height: 44px; font-weight: 600; }
.check input { width: 20px; height: 20px; accent-color: var(--red); margin: 0; }
.count { margin: 10px 0 0; font-weight: 600; font-size: .95rem; }

/* Classified boxes in newspaper columns */
.ads { display: grid; grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr)); gap: 18px;
  padding: 22px 0 8px; }
.ad { position: relative; display: flex; flex-direction: column; background: var(--card);
  border: 2px solid var(--ink); padding: 14px 16px 12px;
  transition: transform .12s ease, box-shadow .12s ease; }
.ad:hover, .ad:focus-within { transform: translate(-2px, -2px); box-shadow: 5px 5px 0 var(--ink); }
.kicker { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 10px; }
.kicker span { background: var(--ink); color: var(--paper); font-size: .75rem; font-weight: 800;
  text-transform: uppercase; letter-spacing: .03em; padding: 2px 7px; }
.kicker .tag { background: transparent; color: var(--ink); border: 1.5px solid var(--ink); padding: 1px 6px; }
.ad h2 { font: 800 1.2rem/1.2 var(--news); margin: 0 0 8px; overflow-wrap: anywhere; }
.ad h2 a { text-decoration: none; }
.ad h2 a::after { content: ""; position: absolute; inset: 0; }
.ad h2 a:focus-visible { outline: none; }
.ad:focus-within { outline: 3px solid var(--red); outline-offset: 2px; }
.ad:hover h2 a { text-decoration: underline; text-decoration-thickness: 2px; }
.ad p { margin: 0; overflow-wrap: anywhere; }
.who { font-weight: 600; }
.where { color: var(--muted); font-size: .95rem; }
.pay { color: var(--red-text); font-weight: 800; margin-top: 6px !important; }
.src { color: var(--muted); font-size: .82rem; margin-top: auto !important; padding-top: 10px; }
.new { position: absolute; top: -12px; right: 10px; transform: rotate(4deg);
  background: var(--marker); color: var(--marker-ink); border: 2px solid var(--marker-ink);
  font: 400 1rem/1 var(--display); text-transform: uppercase; letter-spacing: .04em; padding: 4px 9px; }

.empty { padding: 32px 0; }
.ads > .empty { grid-column: 1 / -1; }
.empty p { margin: 0 0 12px; font-size: 1.15rem; font-weight: 600; max-width: 40rem; }
.reset { font: 800 1rem var(--news); color: var(--paper); background: var(--ink); border: 2px solid var(--ink);
  min-height: 44px; padding: 0 16px; }
.reset:hover { background: var(--red); border-color: var(--red); color: #fff; }
.reset:active { transform: translateY(1px); }

footer { margin: 40px 0 0; padding: 0 0 48px; border-top: 6px solid var(--ink); }
.foot { display: grid; grid-template-columns: 3fr 2fr; gap: 24px; padding-top: 22px; }
footer h2 { font: 400 1.6rem/1.1 var(--display); text-transform: uppercase; margin: 0 0 10px; }
footer p { margin: 0 0 10px; max-width: 40rem; }
.warn { border: 3px solid var(--red); padding: 14px 16px; align-self: start; }
.warn h2 { color: var(--red-text); }
.stamp { color: var(--muted); font-size: .9rem; }

@media (max-width: 720px) {
  form.filters { grid-template-columns: 1fr auto; }
  .field.wide { grid-column: 1 / -1; }
  .foot { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  form.filters { gap: 8px 12px; padding-top: 10px; }
  .panel { padding-bottom: 8px; }
  .lead { padding-top: 20px; }
}
@media (max-height: 520px) { .panel { position: static; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } .ad:hover { transform: none; } }
"""

JS = """
(function () {
  var root = document.documentElement, btn = document.getElementById('theme');
  function current() {
    var set = root.getAttribute('data-theme');
    if (set) return set;
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  function label() {
    var dark = current() === 'dark';
    btn.textContent = dark ? 'Mode terang' : 'Mode gelap';
    btn.setAttribute('aria-pressed', String(dark));
  }
  try { var saved = localStorage.getItem('jh-theme'); if (saved) root.setAttribute('data-theme', saved); } catch (e) {}
  btn.hidden = false; label();
  btn.addEventListener('click', function () {
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('jh-theme', next); } catch (e) {}
    label();
  });

  var form = document.getElementById('filters'), q = document.getElementById('q'),
      track = document.getElementById('track'), remote = document.getElementById('remote'),
      count = document.getElementById('count'), empty = document.getElementById('empty'),
      ads = Array.prototype.slice.call(document.querySelectorAll('.ad')), total = ads.length;
  if (!total) return;
  form.hidden = false;
  var panel = document.getElementById('panel');
  function pad() { root.style.scrollPaddingTop = (getComputedStyle(panel).position === 'sticky' ? panel.offsetHeight + 8 : 0) + 'px'; }
  pad(); addEventListener('resize', pad);
  function apply() {
    var words = q.value.toLowerCase().split(/\\s+/).filter(Boolean), shown = 0;
    ads.forEach(function (ad) {
      var ok = (!track.value || ad.dataset.track === track.value)
        && (!remote.checked || ad.dataset.remote === '1')
        && words.every(function (w) { return ad.dataset.text.indexOf(w) !== -1; });
      ad.hidden = !ok; if (ok) shown++;
    });
    count.textContent = shown === total ? total + ' lowongan' : 'Menampilkan ' + shown + ' dari ' + total + ' lowongan';
    empty.hidden = shown !== 0;
  }
  form.addEventListener('submit', function (e) { e.preventDefault(); apply(); });
  [q, track, remote].forEach(function (el) { el.addEventListener('input', apply); el.addEventListener('change', apply); });
  document.getElementById('reset').addEventListener('click', function () {
    q.value = ''; track.value = ''; remote.checked = false; apply(); q.focus();
  });
})();
"""


def render(jobs: list[dict], name: str, now: datetime | None = None) -> str:
    now = (now or datetime.now(timezone.utc)).astimezone(WIB)
    e = html.escape
    edition = f"{DAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]} {now.year}"
    present = [t for t in TRACK_LABEL if any(j["track"] == t for j in jobs)]
    options = "".join(f'<option value="{t}">{e(TRACK_LABEL[t])}</option>' for t in present)
    fresh = sum(1 for j in jobs if j["new"])
    if jobs:
        tally = f"{len(jobs)} lowongan"
        tally += f", {fresh} diposting dalam 2 hari terakhir" if fresh else ""
        body = "".join(_entry(j) for j in jobs)
    else:
        tally = "Belum ada lowongan"
        body = """
    <div class="empty"><p>Edisi ini belum memuat lowongan. Data diperbarui setiap pagi;
    kalau halaman ini masih kosong besok, pengambilan data sedang bermasalah.</p></div>"""

    if jobs:
        headline = (f"<mark>{fresh} lowongan baru</mark> dalam 2 hari terakhir" if fresh
                    else f"{len(jobs)} lowongan masih dibuka")
    else:
        headline = "Edisi ini masih kosong"

    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(name)}: lowongan kerja terverifikasi, {now.day} {MONTHS[now.month - 1]} {now.year}</title>
<meta name="description" content="Lowongan developer, IT, data, dan kreatif dari JobStreet, Kalibrr, dan board perusahaan. Pengiklan tanpa nama perusahaan tidak dimuat. Diperbarui harian.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>{CSS}</style>
</head>
<body>
<header class="mast">
  <div class="nameplate"><div class="wrap np">
    <div>
      <h1>{e(name)}</h1>
      <p class="motto">Loker harian. Yang ngiklan wajib sebut nama perusahaan.</p>
    </div>
    <button type="button" class="theme" id="theme" aria-pressed="false" hidden>Mode gelap</button>
  </div></div>
  <div class="dateline"><div class="wrap">Edisi {edition} · Terbit tiap pagi</div></div>
  <div class="wrap lead">
    <p class="headline">{headline}</p>
    <p class="deck">Dikumpulkan dari JobStreet, Kalibrr, dan halaman karier perusahaan. Iklan tanpa nama
    perusahaan dibuang, jadi setiap lowongan di sini jelas siapa yang buka. Klik judulnya untuk melamar
    di halaman aslinya.</p>
  </div>
</header>
<main class="wrap">
  <div class="panel" id="panel">
  <form class="filters" id="filters" role="search" hidden>
    <label class="field wide" for="q">Cari judul, perusahaan, atau kota
      <input id="q" type="search" autocomplete="off" placeholder="contoh: laravel surabaya">
    </label>
    <label class="field" for="track">Bidang
      <select id="track"><option value="">Semua bidang</option>{options}</select>
    </label>
    <label class="check" for="remote"><input id="remote" type="checkbox"> Hanya remote</label>
  </form>
  <p class="count" id="count" aria-live="polite">{tally}</p>
  </div>
  <div class="empty" id="empty" hidden>
    <p>Tidak ada lowongan yang cocok dengan filter ini. Coba kata kunci yang lebih pendek atau pilih semua bidang.</p>
    <button type="button" class="reset" id="reset">Hapus semua filter</button>
  </div>
  <div class="ads">{body}</div>
</main>
<footer><div class="wrap foot">
  <section>
    <h2>Cara kerja papan ini</h2>
    <p>Setiap pagi skrip menarik lowongan dari JobStreet, Kalibrr, dan halaman karier perusahaan, lalu
    membuang duplikat, posting lebih dari 30 hari, dan iklan yang tidak menyebut nama perusahaan
    (misalnya "Private Advertiser"). Judul lowongan membawa kamu ke halaman aslinya; lamar di sana.</p>
    <p class="stamp">Terakhir diperbarui {now:%d-%m-%Y %H:%M} WIB.</p>
  </section>
  <section class="warn">
    <h2>Awas penipuan</h2>
    <p>Perusahaan yang sah tidak meminta biaya untuk melamar. Kalau ada yang meminta transfer
    untuk "biaya administrasi", "pelatihan", atau "seragam", jangan dibayar.</p>
  </section>
</div></footer>
<script>{JS}</script>
</body>
</html>
"""


def build(out_dir: Path | None = None, name: str = "Maniak Kerja", min_score: int = 60,
          max_age_days: int = 30) -> tuple[Path, int]:
    out = out_dir or (config.DATA_DIR / "site")
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    jobs = select_jobs(min_score=min_score, max_age_days=max_age_days, now=now)
    (out / "index.html").write_text(render(jobs, name, now), encoding="utf-8")
    (out / "jobs.json").write_text(
        json.dumps({"updated": now.isoformat(), "jobs": jobs}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return out / "index.html", len(jobs)
