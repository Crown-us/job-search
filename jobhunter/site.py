"""Public static job board: one self-contained index.html plus jobs.json.

Only public fields leave the database: title, company, location, salary,
remote flag, source, dates, track and the original URL. Personal CV fit,
gaps, letters, statuses and score reasons are never written.

Design notes (classified-ads board, ENERGY 1 / RHYTHM 1 / MOTION 1):
- paper + ink palette with one accent (stamp red) reserved for the "Baru" mark,
  because "new since yesterday" is the one state a daily reader scans for
- serif titles for the newspaper voice, system sans for dense meta lines
- double rule under the masthead is the repeated identity motif
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
    meta = [e(job["company"]), where]
    facts = [TRACK_LABEL.get(job["track"], job["track"])]
    if job["remote"]:
        facts.append("Remote")
    if job["salary"]:
        facts.append(job["salary"])
    posted = _day(datetime.fromtimestamp(job["posted"], timezone.utc))
    mark = '<span class="new">Baru</span> ' if job["new"] else ""
    haystack = e(f"{job['title']} {job['company']} {job['location']}".lower(), quote=True)
    return f"""
    <article class="ad" data-track="{e(job['track'], quote=True)}" data-remote="{int(job['remote'])}"
             data-text="{haystack}">
      <h2>{mark}<a href="{e(job['url'], quote=True)}" rel="noopener nofollow">{e(job['title'])}</a></h2>
      <p class="who">{' · '.join(meta)}</p>
      <p class="facts">{' · '.join(e(f) for f in facts)}</p>
      <p class="src">via {e(job['source'])}, diposting {posted}</p>
    </article>"""


CSS = """
:root {
  --paper: #f3eee3; --ink: #1c1b18; --muted: #565248; --rule: #bdb5a3;
  --accent: #a4231b; --field: #fbf8f1;
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #1a1916; --ink: #ece6d8; --muted: #b0a998; --rule: #45413a;
    --accent: #f08a7a; --field: #23221e; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #1a1916; --ink: #ece6d8; --muted: #b0a998; --rule: #45413a;
  --accent: #f08a7a; --field: #23221e; color-scheme: dark;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.5 var(--sans); }
a, button, select, label[for], input[type=checkbox] { cursor: pointer; }
a { color: inherit; text-underline-offset: 3px; }
a:hover { text-decoration-thickness: 2px; }
:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
.wrap { max-width: 46rem; margin: 0 auto; padding: 0 16px; }
header.mast { padding: 28px 0 0; }
.mast-top { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.mast h1 { font: 700 clamp(2.2rem, 8vw, 3.4rem)/1 var(--serif); margin: 0; letter-spacing: -0.01em; }
.edition { color: var(--muted); font-size: .95rem; margin: 10px 0 12px; }
.rule { border: 0; border-top: 3px solid var(--ink); margin: 0; }
.rule + .rule { border-top-width: 1px; margin-top: 3px; }
.lede { font: 1.1rem/1.5 var(--serif); margin: 16px 0 0; max-width: 38rem; }
.theme { font: inherit; font-size: .9rem; color: var(--ink); background: transparent;
  border: 1px solid var(--rule); border-radius: 4px; min-height: 44px; padding: 0 14px; }
.theme:hover { border-color: var(--ink); }
.theme:active { transform: translateY(1px); }
form.filters { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; margin: 24px 0 8px;
  padding: 16px 0; border-bottom: 1px solid var(--rule); }
.field { display: flex; flex-direction: column; gap: 4px; font-size: .9rem; color: var(--muted); }
.field.wide { grid-column: 1 / -1; }
.field input, .field select { font: inherit; font-size: 1rem; color: var(--ink); background: var(--field);
  border: 1px solid var(--rule); border-radius: 4px; min-height: 44px; padding: 0 10px; }
.field input:hover, .field select:hover { border-color: var(--muted); }
.check { align-self: end; display: flex; align-items: center; gap: 10px; min-height: 44px; color: var(--ink); font-size: 1rem; }
.check input { width: 20px; height: 20px; accent-color: var(--ink); margin: 0; }
.count { margin: 12px 0 0; color: var(--muted); font-size: .95rem; }
.ad { padding: 18px 0; border-bottom: 1px solid var(--rule); }
.ad h2 { font: 700 1.25rem/1.3 var(--serif); margin: 0 0 6px; overflow-wrap: anywhere; }
.ad h2 a { display: inline; padding: 4px 0; }
.ad p { margin: 2px 0; overflow-wrap: anywhere; }
.who { font-weight: 600; }
.facts { color: var(--ink); }
.src { color: var(--muted); font-size: .9rem; }
.new { font: 700 .8rem/1 var(--sans); color: var(--accent); border: 1.5px solid currentColor;
  border-radius: 3px; padding: 2px 5px; vertical-align: 3px; margin-right: 4px; }
.empty { padding: 32px 0; }
.empty p { margin: 0 0 12px; font: 1.1rem/1.5 var(--serif); }
.reset { font: inherit; color: var(--paper); background: var(--ink); border: 1px solid var(--ink);
  border-radius: 4px; min-height: 44px; padding: 0 16px; }
.reset:hover { opacity: .88; }
.reset:active { transform: translateY(1px); }
footer { margin: 40px 0 48px; color: var(--muted); font-size: .95rem; }
footer h2 { font: 700 1.15rem/1.3 var(--serif); color: var(--ink); margin: 20px 0 8px; }
footer p { margin: 0 0 10px; max-width: 38rem; }
.warn { color: var(--ink); }
@media (max-width: 520px) {
  form.filters { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
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

    return f"""<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(name)}: lowongan kerja terverifikasi, {now.day} {MONTHS[now.month - 1]} {now.year}</title>
<meta name="description" content="Lowongan developer, IT, data, dan kreatif dari JobStreet, Kalibrr, dan board perusahaan. Pengiklan tanpa nama perusahaan tidak dimuat. Diperbarui harian.">
<style>{CSS}</style>
</head>
<body>
<header class="mast"><div class="wrap">
  <div class="mast-top">
    <h1>{e(name)}</h1>
    <button type="button" class="theme" id="theme" aria-pressed="false" hidden>Mode gelap</button>
  </div>
  <p class="edition">Edisi {edition} · {tally}</p>
  <hr class="rule"><hr class="rule">
  <p class="lede">Lowongan developer, IT, data, dan kreatif yang dikumpulkan setiap pagi dari JobStreet,
  Kalibrr, dan board karier perusahaan. Iklan tanpa nama perusahaan tidak dimuat.</p>
</div></header>
<main class="wrap">
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
  <div class="empty" id="empty" hidden>
    <p>Tidak ada lowongan yang cocok dengan filter ini. Coba kata kunci yang lebih pendek atau pilih semua bidang.</p>
    <button type="button" class="reset" id="reset">Hapus semua filter</button>
  </div>
  {body}
</main>
<footer class="wrap">
  <hr class="rule"><hr class="rule">
  <h2>Cara kerja papan ini</h2>
  <p>Setiap pagi skrip menarik lowongan dari JobStreet, Kalibrr, dan halaman karier perusahaan, lalu
  membuang duplikat, posting lebih dari 30 hari, dan iklan yang tidak menyebut nama perusahaan
  (misalnya "Private Advertiser"). Judul lowongan membawa kamu ke halaman aslinya; lamar di sana.</p>
  <p class="warn">Perusahaan yang sah tidak meminta biaya untuk melamar. Kalau ada yang meminta transfer
  untuk "biaya administrasi", "pelatihan", atau "seragam", jangan dibayar.</p>
  <p>Terakhir diperbarui {now:%d-%m-%Y %H:%M} WIB.</p>
</footer>
<script>{JS}</script>
</body>
</html>
"""


def build(out_dir: Path | None = None, name: str = "Job Hunter", min_score: int = 60,
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
