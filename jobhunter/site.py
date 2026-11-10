"""Public static job board: index.html (fonts from Google Fonts) plus jobs.json.

Only public fields leave the database: title, company, location, salary,
remote flag, source, dates, track and the original URL. Personal CV fit,
gaps, letters, statuses and score reasons are never written.

Design notes ("Maniak Kerja", job-app style after a Dribbble reference the owner picked,
ENERGY 2 / RHYTHM 1 / MOTION 2):
- night header with a pinned search strip, filter sidebar, card grid: the reader's one
  job is to narrow 300+ postings fast, so search and filters stay reachable
- pastel card tint encodes the track (Developer blue, Marketing peach, ...), not random
  decoration; one sky-blue accent marks "Baru" and focus
- Plus Jakarta Sans: geometric and friendly like the reference, made for Jakarta
- company initial in a circle stands in for logos we do not have
- cards rise in with a short stagger whenever the result set changes, so a filter
  change reads as "new results"; disabled under prefers-reduced-motion
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
    track = TRACK_LABEL.get(job["track"], job["track"])
    tags = [f"<li>{e(track)}</li>"]
    if job["remote"]:
        tags.append("<li>Remote</li>")
    tags.append(f"<li>via {e(job['source'])}</li>")
    pay = e(job["salary"]) if job["salary"] else "Gaji tidak disebut"
    pay_cls = "pay" if job["salary"] else "pay none"
    posted = _day(datetime.fromtimestamp(job["posted"], timezone.utc))
    mark = '<span class="new">Baru</span>' if job["new"] else ""
    initial = e((job["company"].strip(" .")[:1] or "?").upper())
    haystack = e(f"{job['title']} {job['company']} {job['location']}".lower(), quote=True)
    label = e(f"Lamar {job['title']} di {job['company']}", quote=True)
    return f"""
    <article class="ad t-{e(job['track'], quote=True)}" data-track="{e(job['track'], quote=True)}"
             data-remote="{int(job['remote'])}" data-pay="{int(bool(job['salary']))}"
             data-new="{int(job['new'])}" data-src="{e(job['source'], quote=True)}" data-text="{haystack}">
      <div class="tint">
        <div class="top"><span class="date">{posted}</span>{mark}</div>
        <p class="co">{e(job['company'])}</p>
        <div class="head"><h2>{e(job['title'])}</h2><span class="mono" aria-hidden="true">{initial}</span></div>
        <ul class="tags">{''.join(tags)}</ul>
      </div>
      <div class="row">
        <div><p class="{pay_cls}">{pay}</p><p class="where">{where}</p></div>
        <a class="apply" href="{e(job['url'], quote=True)}" rel="noopener nofollow" aria-label="{label}">Lamar</a>
      </div>
    </article>"""


FONTS = "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"

CSS = """
:root {
  --bg: #eef0f4; --surface: #ffffff; --ink: #121316; --muted: #545968; --line: #d9dce4;
  --night: #111214; --night-2: #1c1d22; --night-line: #34363e; --night-ink: #f4f5f7; --night-muted: #a9aebb;
  --accent: #8cc8ff; --accent-ink: #0b1a2a;
  --font: "Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0d0e11; --surface: #17181c; --ink: #eceef2; --muted: #a9aebb; --line: #2c2f36; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0d0e11; --surface: #17181c; --ink: #eceef2; --muted: #a9aebb; --line: #2c2f36; color-scheme: dark;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 var(--font); }
a, button, select, label[for], label:has(input[type=checkbox]), input[type=checkbox] { cursor: pointer; }
a { color: inherit; }
:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
.in-wrap { max-width: 80rem; margin: 0 auto; padding: 0 16px; }

/* Header: night bar, the search strip below it stays pinned while scrolling */
.topbar { background: var(--night); color: var(--night-ink); }
.topbar .in-wrap { display: flex; align-items: center; justify-content: space-between; gap: 8px 20px;
  flex-wrap: wrap; padding-top: 16px; padding-bottom: 6px; }
.brand { font-weight: 700; font-size: 1.25rem; letter-spacing: -0.01em; margin: 0; }
.edition { color: var(--night-muted); font-size: .85rem; margin: 0; flex: 1; }
.theme { font: 600 .85rem var(--font); color: var(--night-ink); background: transparent;
  border: 1px solid var(--night-line); border-radius: 999px; min-height: 44px; padding: 0 16px; }
.theme:hover { border-color: var(--night-ink); }
.theme:active { transform: translateY(1px); }
/* The whole header stays pinned; the sidebar pins right under it (--hdr is set by JS) */
#top { position: sticky; top: 0; z-index: 5; }
.searchbar { background: var(--night); color: var(--night-ink); border-bottom: 1px solid var(--night-line); }
.searchbar .in-wrap { display: flex; align-items: flex-end; gap: 10px; padding-top: 10px; padding-bottom: 16px; }
#search { flex: 1; min-width: 0; }
.search { display: block; font-size: .85rem; color: var(--night-muted); }
.search span { display: block; margin-bottom: 6px; }
.search .box { position: relative; display: block; }
.search svg { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); width: 20px; height: 20px;
  color: var(--night-muted); pointer-events: none; }
.search input { width: 100%; font: 500 1rem var(--font); color: var(--night-ink); background: var(--night-2);
  border: 1px solid var(--night-line); border-radius: 14px; min-height: 52px; padding: 0 16px 0 48px; }
.search input::placeholder { color: #8f94a3; }
.search input:hover { border-color: var(--night-muted); }

/* Body: filter sidebar + card grid */
.shell { display: grid; grid-template-columns: 15.5rem minmax(0, 1fr); gap: 32px; padding-top: 28px; padding-bottom: 24px; }
#aside { position: sticky; top: calc(var(--hdr, 180px) + 20px); align-self: start;
  max-height: calc(100vh - var(--hdr, 180px) - 36px); overflow-y: auto; overscroll-behavior: contain;
  padding-right: 6px; scrollbar-width: thin; }
.done { display: none; }
.promo { background: var(--night); color: var(--night-ink); border: 1px solid var(--night-line); border-radius: 22px; padding: 20px; margin-bottom: 24px; }
.promo h2 { font-size: 1.3rem; line-height: 1.2; margin: 0 0 8px; }
.promo p { font-size: .9rem; color: var(--night-muted); margin: 0 0 16px; }
.pill-link { display: inline-flex; align-items: center; min-height: 44px; padding: 0 18px; border-radius: 999px;
  background: var(--accent); color: var(--accent-ink); font-weight: 600; font-size: .9rem; text-decoration: none; }
.pill-link:hover { background: #b3dbff; }
.side-h { font-size: 1.15rem; margin: 0 0 12px; }
fieldset { border: 0; padding: 0; margin: 0 0 18px; min-width: 0; }
legend { font-size: .8rem; font-weight: 600; color: var(--muted); padding: 0; margin-bottom: 4px; }
.opt { display: flex; align-items: center; gap: 10px; min-height: 40px; font-size: .92rem; }
.opt input { width: 18px; height: 18px; margin: 0; accent-color: var(--ink); flex: none; }
.opt small { margin-left: auto; color: var(--muted); font-size: .8rem; }
.ghost { font: 600 .9rem var(--font); color: var(--ink); background: transparent; border: 1px solid var(--line);
  border-radius: 999px; min-height: 44px; padding: 0 18px; }
.ghost:hover { border-color: var(--ink); }
.ghost:active { transform: translateY(1px); }

.res-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
.res-head h1 { font-size: clamp(1.5rem, 3vw, 2rem); font-weight: 600; letter-spacing: -0.01em; margin: 0; }
.total { border: 1px solid var(--line); border-radius: 999px; padding: 2px 12px; font-weight: 600; font-size: .95rem; }
.sort { margin-left: auto; color: var(--muted); font-size: .85rem; }
.count { flex-basis: 100%; margin: 0; color: var(--muted); font-size: .9rem; }
.toggle { display: none; font: 600 .95rem var(--font); color: var(--night-ink); background: var(--night-2);
  border: 1px solid var(--night-line); border-radius: 14px; min-height: 52px; padding: 0 16px; flex: none; }
.toggle:hover { border-color: var(--night-muted); }
.toggle:active { transform: translateY(1px); }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(16.5rem, 1fr)); gap: 18px; }
.ad { position: relative; display: flex; flex-direction: column; background: var(--surface);
  border: 1px solid var(--line); border-radius: 22px; padding: 8px;
  transition: transform .15s ease, border-color .15s ease; }
.ad:hover { transform: translateY(-2px); border-color: var(--muted); }
.ad:focus-within { outline: 3px solid var(--accent); outline-offset: 2px; }
.tint { background: var(--tint); border-radius: 16px; padding: 14px 14px 16px; flex: 1;
  --tag-line: color-mix(in srgb, var(--ink) 35%, transparent); }
.t-fullstack { --tint: #dbe8ff; } .t-it_support { --tint: #d4f1e7; } .t-ai_junior { --tint: #e6dcfb; }
.t-admin_data { --tint: #e9e7e1; } .t-marketing { --tint: #ffe0c9; } .t-video_editor { --tint: #ffdae8; }
.t-graphic_design { --tint: #fdeeb4; } .t-social_media { --tint: #d6f0cc; }
:root[data-theme="dark"] .tint { background: color-mix(in srgb, var(--tint) 24%, var(--surface)); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .tint { background: color-mix(in srgb, var(--tint) 24%, var(--surface)); }
}
.top { display: flex; align-items: center; gap: 6px; margin-bottom: 14px; }
.date { background: var(--surface); border-radius: 999px; padding: 4px 12px; font-size: .8rem; font-weight: 500; }
.new { background: var(--accent); color: var(--accent-ink); border-radius: 999px; padding: 4px 10px;
  font-size: .78rem; font-weight: 700; }
.co { font-size: .85rem; font-weight: 500; margin: 0 0 2px; overflow-wrap: anywhere; }
.head { display: flex; align-items: flex-start; gap: 12px; }
.head h2 { flex: 1; font-size: 1.2rem; line-height: 1.25; font-weight: 600; margin: 0; overflow-wrap: anywhere; }
.mono { flex: none; display: grid; place-items: center; width: 38px; height: 38px; border-radius: 50%;
  background: var(--ink); color: var(--surface); font-weight: 700; font-size: 1rem; }
.tags { list-style: none; display: flex; flex-wrap: wrap; gap: 6px; padding: 0; margin: 16px 0 0; }
.tags li { border: 1px solid var(--tag-line); border-radius: 999px; padding: 2px 10px; font-size: .76rem; font-weight: 500; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 8px 6px; }
.row p { margin: 0; overflow-wrap: anywhere; }
.pay { font-weight: 700; font-size: .92rem; }
.pay.none { font-weight: 500; color: var(--muted); }
.where { color: var(--muted); font-size: .8rem; }
.apply { flex: none; display: inline-flex; align-items: center; min-height: 44px; padding: 0 20px; border-radius: 999px;
  background: var(--ink); color: var(--surface); font-weight: 600; font-size: .9rem; text-decoration: none; }
.apply::after { content: ""; position: absolute; inset: 0; border-radius: 22px; }
.apply:focus-visible { outline: none; }
.ad:hover .apply { background: color-mix(in srgb, var(--ink) 82%, var(--accent)); }

/* Cards rise in, staggered, whenever the filter result changes */
@keyframes rise { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
.ad.in { animation: rise .38s cubic-bezier(.2, .7, .3, 1) both; }

.empty { grid-column: 1 / -1; padding: 32px 4px; }
.empty p { margin: 0 0 14px; font-size: 1.05rem; max-width: 36rem; }

footer { border-top: 1px solid var(--line); }
.foot { display: grid; grid-template-columns: 3fr 2fr; gap: 24px; padding-top: 28px; padding-bottom: 48px; }
footer h2 { font-size: 1.15rem; margin: 0 0 8px; }
footer p { margin: 0 0 10px; max-width: 40rem; color: var(--muted); }
.stamp { font-size: .85rem; }

@media (max-width: 860px) {
  .shell { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .promo { display: none; }
  #aside { position: static; max-height: none; overflow: visible; padding: 0; }
  /* Filter opens as a sheet under the pinned header; elevated because it covers the cards */
  #side { display: none; position: fixed; z-index: 6; top: calc(var(--hdr, 160px) + 8px); left: 16px; right: 16px;
    max-height: calc(100vh - var(--hdr, 160px) - 24px); overflow-y: auto; overscroll-behavior: contain;
    border: 1px solid var(--line); border-radius: 22px; padding: 16px; background: var(--surface);
    box-shadow: 0 18px 40px rgba(0, 0, 0, .28); }
  #side.open { display: block; }
  .toggle { display: inline-flex; align-items: center; }
  .done { display: inline-flex; align-items: center; margin-left: 8px; background: var(--ink); color: var(--surface);
    border-color: var(--ink); }
  .sort { display: none; }
  .foot { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .grid { grid-template-columns: minmax(0, 1fr); }
  .edition { display: none; }
  .topbar .in-wrap { padding-top: 10px; padding-bottom: 2px; }
  .theme { min-height: 40px; }
  .search span:first-child { margin-bottom: 4px; }
  .searchbar .in-wrap { padding-bottom: 12px; }
}
@media (max-height: 520px) {
  #top, #aside { position: static; max-height: none; overflow: visible; }
  #side { top: 16px; max-height: calc(100vh - 32px); }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; } .ad:hover { transform: none; }
}
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
      side = document.getElementById('side'), toggle = document.getElementById('toggle'),
      total = document.getElementById('total'), count = document.getElementById('count'),
      empty = document.getElementById('empty'), bar = document.getElementById('top'),
      ads = Array.prototype.slice.call(document.querySelectorAll('.ad')), all = ads.length;
  if (!all) return;
  form.hidden = false; q.disabled = false; toggle.hidden = false;
  function pad() {
    var pinned = getComputedStyle(bar).position === 'sticky';
    root.style.setProperty('--hdr', (pinned ? bar.offsetHeight : 0) + 'px');
    root.style.scrollPaddingTop = (pinned ? bar.offsetHeight + 8 : 0) + 'px';
  }
  pad(); addEventListener('resize', pad);
  function checked(name) {
    return Array.prototype.slice.call(form.querySelectorAll('input[name="' + name + '"]:checked'))
      .map(function (i) { return i.value; });
  }
  function apply() {
    var words = q.value.toLowerCase().split(/\\s+/).filter(Boolean),
        tracks = checked('track'), srcs = checked('src'), flags = checked('flag'), shown = 0;
    ads.forEach(function (ad) {
      var d = ad.dataset;
      var ok = (!tracks.length || tracks.indexOf(d.track) !== -1)
        && (!srcs.length || srcs.indexOf(d.src) !== -1)
        && (flags.indexOf('remote') === -1 || d.remote === '1')
        && (flags.indexOf('pay') === -1 || d.pay === '1')
        && (flags.indexOf('new') === -1 || d.new === '1')
        && words.every(function (w) { return d.text.indexOf(w) !== -1; });
      ad.hidden = !ok;
      ad.classList.remove('in');
      if (ok) {
        if (shown < 12) { void ad.offsetWidth; ad.style.animationDelay = (shown * 45) + 'ms'; ad.classList.add('in'); }
        shown++;
      }
    });
    total.textContent = shown;
    count.textContent = shown === all ? all + ' lowongan, urut dari yang terbaru'
      : 'Menampilkan ' + shown + ' dari ' + all + ' lowongan';
    empty.hidden = shown !== 0;
    var active = tracks.length + srcs.length + flags.length;
    toggle.textContent = active ? 'Filter (' + active + ')' : 'Filter';
  }
  function reset() { form.reset(); q.value = ''; apply(); q.focus(); }
  form.addEventListener('change', apply);
  q.addEventListener('input', apply);
  document.getElementById('search').addEventListener('submit', function (e) { e.preventDefault(); apply(); });
  document.getElementById('reset').addEventListener('click', reset);
  document.getElementById('reset-side').addEventListener('click', reset);
  function setOpen(open, refocus) {
    side.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    if (!open && refocus) toggle.focus();
  }
  toggle.addEventListener('click', function () { setOpen(!side.classList.contains('open')); });
  document.getElementById('done').addEventListener('click', function () { setOpen(false, true); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && side.classList.contains('open')) setOpen(false, true);
  });
  apply();
})();
"""


def _options(name: str, items: list[tuple[str, str, int]]) -> str:
    e = html.escape
    return "".join(
        f'<label class="opt"><input type="checkbox" name="{name}" value="{e(v, quote=True)}"> {e(text)}'
        f'<small>{n}</small></label>' for v, text, n in items)


def render(jobs: list[dict], name: str, now: datetime | None = None) -> str:
    now = (now or datetime.now(timezone.utc)).astimezone(WIB)
    e = html.escape
    edition = f"{DAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]} {now.year}"
    tracks = [(t, TRACK_LABEL[t], sum(1 for j in jobs if j["track"] == t)) for t in TRACK_LABEL]
    tracks = [t for t in tracks if t[2]]
    sources = sorted({j["source"] for j in jobs})
    sources = [(s, s, sum(1 for j in jobs if j["source"] == s)) for s in sources]
    fresh = sum(1 for j in jobs if j["new"])
    flags = [("remote", "Hanya remote", sum(1 for j in jobs if j["remote"])),
             ("pay", "Ada info gaji", sum(1 for j in jobs if j["salary"])),
             ("new", "Baru, 2 hari terakhir", fresh)]
    if jobs:
        tally = f"{len(jobs)} lowongan, urut dari yang terbaru"
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<style>{CSS}</style>
</head>
<body>
<header id="top">
  <div class="topbar"><div class="in-wrap">
    <p class="brand">{e(name)}</p>
    <p class="edition">Edisi {edition}. Diperbarui tiap pagi.</p>
    <button type="button" class="theme" id="theme" aria-pressed="false" hidden>Mode gelap</button>
  </div></div>
  <div class="searchbar" id="searchbar"><div class="in-wrap">
    <form id="search" role="search">
      <label class="search" for="q"><span>Cari judul, perusahaan, atau kota</span>
        <span class="box">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          <input id="q" type="search" autocomplete="off" placeholder="contoh: laravel surabaya" disabled>
        </span>
      </label>
    </form>
    <button type="button" class="toggle" id="toggle" aria-expanded="false" aria-controls="side" hidden>Filter</button>
  </div></div>
</header>
<div class="in-wrap shell">
  <aside id="aside">
    <section class="promo">
      <h2>Awas penipuan</h2>
      <p>Perusahaan yang sah tidak meminta biaya untuk melamar. Ada yang minta transfer? Jangan dibayar.</p>
      <a class="pill-link" href="#cara-kerja">Cara kerja papan ini</a>
    </section>
    <div id="side">
      <form id="filters" hidden>
        <h2 class="side-h">Filter</h2>
        <fieldset><legend>Bidang</legend>{_options("track", tracks)}</fieldset>
        <fieldset><legend>Lowongan</legend>{_options("flag", flags)}</fieldset>
        <fieldset><legend>Sumber</legend>{_options("src", sources)}</fieldset>
        <button type="button" class="ghost" id="reset-side">Hapus filter</button>
        <button type="button" class="ghost done" id="done">Selesai</button>
      </form>
    </div>
  </aside>
  <main>
    <div class="res-head">
      <h1>Lowongan terbaru</h1>
      <span class="total" id="total">{len(jobs)}</span>
      <span class="sort">Urut: terbaru</span>
      <p class="count" id="count" aria-live="polite">{tally}</p>
    </div>
    <div class="grid">
      <div class="empty" id="empty" hidden>
        <p>Tidak ada lowongan yang cocok. Coba kata kunci yang lebih pendek atau kurangi filter.</p>
        <button type="button" class="ghost" id="reset">Hapus semua filter</button>
      </div>
      {body}
    </div>
  </main>
</div>
<footer id="cara-kerja"><div class="in-wrap foot">
  <section>
    <h2>Cara kerja papan ini</h2>
    <p>Setiap pagi skrip menarik lowongan dari JobStreet, Kalibrr, dan halaman karier perusahaan, lalu
    membuang duplikat, posting lebih dari 30 hari, dan iklan yang tidak menyebut nama perusahaan
    (misalnya "Private Advertiser"). Tombol Lamar membawa kamu ke halaman aslinya; lamar di sana.</p>
    <p class="stamp">Terakhir diperbarui {now:%d-%m-%Y %H:%M} WIB.</p>
  </section>
  <section>
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
