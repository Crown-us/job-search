"""Public static job board: index.html (fonts from Google Fonts) plus jobs.json.

Only public fields leave the database: title, company, location, salary,
remote flag, source, dates, track and the original URL. Personal CV fit,
gaps, letters, statuses and score reasons are never written.

Design notes ("Maniak Kerja", ENERGY 2 / RHYTHM 1 / MOTION 2):
- dense list + detail panel (the Glints/Wellfound pattern Indonesian job seekers
  already know): a reader scans 300+ postings, so one row per posting shows title,
  company, city, salary and age at a glance; the detail panel holds the rest
- pinned night header with search, pinned filter sidebar, pinned detail panel
- city is the first filter because location decides most applications; the free-form
  board locations are mapped onto a fixed city list (_place)
- pastel tint encodes the track in the small track tag and the selected row; one
  sky-blue accent marks "Baru" and focus
- Plus Jakarta Sans: geometric and friendly, made for Jakarta
- rows rise in with a short stagger whenever the result set changes; the detail panel
  fades on change; both off under prefers-reduced-motion
- the list is server-rendered with titles linking to the original posting, so it
  works without JS; JavaScript adds filtering and the detail panel
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


PER = [
    (r"\s*(?:per\s+month|/\s*month|/\s*mo|per\s+bulan)\b", "/bulan"),
    (r"\s*(?:per\s+hour|/\s*hour|/\s*hr)\b", "/jam"),
    (r"\s*(?:per\s+(?:year|annum)|/\s*year|/\s*yr)\b", "/tahun"),
    (r"\s*per\s+task\b", "/tugas"),
]


def _juta(value: int) -> str:
    text = f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _salary(value: str) -> str:
    """Drop placeholder salaries, then shorten to Indonesian reading: 'Rp 4,5–5,8 jt/bulan'."""
    text = (value or "").replace("\xa0", " ").strip()
    if not text or re.fullmatch(r"\d{1,3}", text) or text.lower() in {"true", "false", "none"}:
        return ""
    per = ""
    for pattern, short in PER:
        if re.search(pattern, text, re.I):
            per = short
            text = re.sub(pattern, "", text, flags=re.I).strip()
    amounts = re.findall(r"Rp\s*([\d.,]+)", text)
    if amounts and text.startswith("Rp"):
        values = [int(re.sub(r"[.,]", "", a) or 0) for a in amounts]
        if values and all(v >= 1_000_000 for v in values):
            parts = list(dict.fromkeys(_juta(v) for v in values))
            text = "Rp " + "–".join(parts) + " jt"
        else:
            parts = list(dict.fromkeys(f"{v:,}".replace(",", ".") for v in values))
            text = "Rp " + "–".join(parts)
    else:
        pair = re.fullmatch(r"(.+?)\s*[-–]\s*(.+)", text)
        if pair and pair.group(1).replace("USD", "").strip() == pair.group(2).replace("USD", "").strip():
            text = pair.group(1).strip()
    return (text + per)[:80]


GENDER_TAG = re.compile(r"\s*\((?:[mfwdx](?:\s*/\s*[mfwdx])+|all\s+genders?)\)", re.I)
KEEP_CAPS = {"HTML", "HRIS", "SAAS", "DEVOPS", "QA/QC", "SPV", "B2B", "B2C", "UI/UX"}


def _cap(word: str) -> str:
    for i, ch in enumerate(word):
        if ch.isalpha():
            return word[:i] + ch.upper() + word[i + 1:].lower()
    return word


def _title(value: str) -> str:
    """Drop '(m/f/d)' style tags and soften ALL-CAPS titles, keeping short acronyms."""
    text = GENDER_TAG.sub("", value or "").strip()
    words = text.split()
    shouting = [w for w in words if w.isupper() and len(re.sub(r"\W", "", w)) >= 4]
    if len(shouting) >= 2:
        text = " ".join(_cap(w) if w in shouting and w.strip("()") not in KEEP_CAPS else w for w in words)
    return text


# (key, label, tokens) in priority order; suburbs before Jakarta so "BSD ... Jakarta" style
# addresses land on the more specific city.
CITIES = [
    ("tangerang", "Tangerang", ("tangerang", "bsd city", "serpong")),
    ("bekasi", "Bekasi", ("bekasi", "cikarang")),
    ("depok", "Depok", ("depok",)),
    ("bogor", "Bogor", ("bogor",)),
    ("bandung", "Bandung", ("bandung", "cimahi")),
    ("surabaya", "Surabaya", ("surabaya", "sidoarjo", "gresik")),
    ("semarang", "Semarang", ("semarang",)),
    ("yogyakarta", "Yogyakarta", ("yogyakarta", "jogja", "bantul", "sleman")),
    ("bali", "Bali", ("bali", "denpasar", "badung", "kuta", "gianyar", "seminyak", "ubud")),
    ("batam", "Batam", ("batam",)),
    ("malang", "Malang", ("malang",)),
    ("medan", "Medan", ("medan",)),
    ("makassar", "Makassar", ("makassar",)),
    ("solo", "Solo", ("surakarta", "solo,")),
    ("jakarta", "Jakarta", ("jakarta", "cengkareng", "kalideres", "kelapa gading", "penjaringan", "cakung",
                            "grogol", "tanjung priok", "kebayoran", "kuningan", "sunter", "tebet")),
]
AREA_ID = {
    "south jakarta": "Jakarta Selatan", "west jakarta": "Jakarta Barat", "north jakarta": "Jakarta Utara",
    "east jakarta": "Jakarta Timur", "central jakarta": "Jakarta Pusat", "south tangerang": "Tangerang Selatan",
    "south denpasar": "Denpasar Selatan", "west denpasar": "Denpasar Barat",
}
REGION_ID = {"yogyakarta special region": "Yogyakarta", "west java": "Jawa Barat", "east java": "Jawa Timur",
             "central java": "Jawa Tengah", "riau islands": "Kepulauan Riau", "banten": "Banten"}
ABROAD = ("united states", "canada", "united kingdom", "poland", "mexico", "germany", "apac", "emea", "latam",
          "europe", "usa", "uk", "philippines", "singapore", "malaysia", "india")
STANDALONE = {"sidoarjo", "gresik", "surakarta", "cimahi", "sleman", "bantul"}
GLOBAL = ("remote", "anywhere", "worldwide", "any state")
CITY_ORDER = [c[0] for c in CITIES] + ["remote", "abroad", "other"]
CITY_LABEL = {**{c[0]: c[1] for c in CITIES}, "remote": "Remote", "abroad": "Luar Indonesia",
              "other": "Kota lain"}


def _place(location: str, remote: bool) -> tuple[str, str]:
    """(city key, short display) from a free-form board location."""
    raw = re.sub(r"\s+", " ", location or "").strip()
    low = raw.lower()
    for key, label, tokens in CITIES:
        if any(t in low for t in tokens):
            first = raw.split(",")[0].strip()
            junk = (not first or re.search(r"\d", first) or len(first) > 28
                    or re.match(r"(jl\.?|jalan|head office|gdg\.?|gedung|rt\b)", first, re.I))
            area = AREA_ID.get(first.lower(), REGION_ID.get(first.lower(), first))
            if junk or area.lower() == label.lower():
                return key, label
            if label.lower() in area.lower() or area.lower() in STANDALONE:
                return key, area
            return key, f"{area}, {label}"
    if remote or any(g in low for g in GLOBAL):
        where = re.sub(r"(?i)\bremote\b[\s,:-]*|[\s,:-]*\bremote\b", "", raw).strip(" ,-;")
        where = where.split(";")[0].strip()
        return "remote", f"Remote, {where}" if where and len(where) <= 30 and "job" not in where.lower() else "Remote"
    if any(re.search(rf"\b{re.escape(a)}\b", low) for a in ABROAD):
        return "abroad", raw[:40]
    if not raw:
        return "other", "Lokasi tidak disebut"
    region = REGION_ID.get(raw.split(",")[-1].strip().lower())
    first = raw.split(",")[0].strip()
    if region:
        return "other", region
    if re.search(r"\d", first) or re.match(r"(jl\.?|jalan|gdg\.?|gedung|rt\b)", first, re.I):
        return "other", "Kota lain"
    return "other", raw[:40]


def _ago(posted: float, now: datetime) -> str:
    days = max(0, int((now.timestamp() - posted) // 86400))
    if days == 0:
        return "Hari ini"
    if days == 1:
        return "Kemarin"
    if days < 7:
        return f"{days} hari lalu"
    if days < 30:
        return f"{days // 7} minggu lalu"
    return _day(datetime.fromtimestamp(posted, timezone.utc))


def _excerpt(text: str, limit: int = 420) -> str:
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    plain = re.sub(r"\s+", " ", plain).strip()
    if len(plain) <= limit:
        return plain
    cut = plain[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return cut + "…"


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
        "SELECT id, source, company, title, url, location, remote, salary, department, description, "
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
        location = re.sub(r"\s+", " ", row.get("location") or "").strip()
        remote = bool(row.get("remote"))
        city, place = _place(location, remote)
        picked.append({
            "id": row["id"][:12],
            "title": _title((row.get("title") or "").strip()),
            "company": company,
            "location": location or ("Remote" if remote else ""),
            "city": city,
            "place": place,
            "remote": remote,
            "salary": _salary(row.get("salary") or ""),
            "source": SOURCE_LABEL.get(row.get("source") or "", row.get("source") or ""),
            "track": best[1],
            "url": row.get("url") or "",
            "posted": posted,
            "new": now.timestamp() - fresh_since <= NEW_HOURS * 3600,
            "excerpt": _excerpt(row.get("description") or ""),
        })
    picked.sort(key=lambda j: j["posted"], reverse=True)
    return picked


def _entry(job: dict, now: datetime) -> str:
    e = html.escape
    track = TRACK_LABEL.get(job["track"], job["track"])
    posted_at = datetime.fromtimestamp(job["posted"], timezone.utc)
    ago = _ago(job["posted"], now)
    new = '<span class="new">Baru</span>' if job["new"] else ""
    pay = (f'<span class="pay">{e(job["salary"])}</span>' if job["salary"]
           else '<span class="pay none">Gaji tidak disebut</span>')
    meta = [f'<span class="co">{e(job["company"])}</span>', e(job["place"])]
    if job["remote"] and job["city"] != "remote":
        meta.append("Remote")
    facts = [("Lokasi", e(job["location"][:160]) or "Tidak disebut"),
             ("Gaji", e(job["salary"]) or "Tidak disebut"),
             ("Bidang", e(track))]
    if job["remote"]:
        facts.append(("Kerja", "Remote"))
    facts += [("Diposting", f"{_day(posted_at)} ({ago.lower()})"), ("Sumber", e(job["source"]))]
    dl = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)
    excerpt = (f'<p class="d-sub">Cuplikan iklan</p><p class="desc">{e(job["excerpt"])}</p>'
               if job["excerpt"] else "")
    haystack = e(f"{job['title']} {job['company']} {job['location']} {job['place']}".lower(), quote=True)
    jid = e(job["id"], quote=True)
    return f"""
    <article class="job t-{e(job['track'], quote=True)}" data-track="{e(job['track'], quote=True)}"
             data-city="{e(job['city'], quote=True)}" data-remote="{int(job['remote'])}"
             data-pay="{int(bool(job['salary']))}" data-new="{int(job['new'])}"
             data-src="{e(job['source'], quote=True)}" data-text="{haystack}">
      <div class="job-row">
        <h2 class="job-title"><a class="pick" href="{e(job['url'], quote=True)}" rel="noopener nofollow">{e(job['title'])}</a></h2>
        <time class="ago" datetime="{posted_at.date().isoformat()}">{ago}</time>
        <p class="meta">{' · '.join(meta)}</p>
        <p class="tags">{pay}<span class="trk">{e(track)}</span>{new}</p>
      </div>
      <div class="more" id="more-{jid}">
        <div class="d-head">
          <p class="tags"><span class="trk">{e(track)}</span>{new}</p>
          <p class="d-title">{e(job['title'])}</p>
          <p class="d-co">{e(job['company'])}</p>
        </div>
        <dl class="facts">{dl}</dl>
        {excerpt}
        <a class="apply" href="{e(job['url'], quote=True)}" rel="noopener nofollow">Lamar di {e(job['source'])}</a>
        <p class="scam">Perusahaan yang sah tidak meminta biaya untuk melamar. Ada yang minta transfer? Jangan dibayar.</p>
      </div>
    </article>"""


FONTS = "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"

CSS = """
:root {
  --bg: #eef0f4; --surface: #ffffff; --ink: #121316; --muted: #545968; --line: #dcdfe6; --hover: #f5f6f9;
  --night: #111214; --night-2: #1c1d22; --night-line: #34363e; --night-ink: #f4f5f7; --night-muted: #a9aebb;
  --accent: #8cc8ff; --accent-ink: #0b1a2a;
  --font: "Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0d0e11; --surface: #17181c; --ink: #eceef2; --muted: #a9aebb; --line: #2c2f36; --hover: #1e1f24;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0d0e11; --surface: #17181c; --ink: #eceef2; --muted: #a9aebb; --line: #2c2f36; --hover: #1e1f24;
  color-scheme: dark;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 var(--font); }
a, button, select, label:has(input[type=checkbox]), input[type=checkbox] { cursor: pointer; }
a { color: inherit; }
:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
.in-wrap { max-width: 86rem; margin: 0 auto; padding: 0 16px; }

/* Header stays pinned; sidebar and detail pin right under it (--hdr is set by JS) */
#top { position: sticky; top: 0; z-index: 5; }
.topbar { background: var(--night); color: var(--night-ink); }
.topbar .in-wrap { display: flex; align-items: center; justify-content: space-between; gap: 8px 20px;
  flex-wrap: wrap; padding-top: 14px; padding-bottom: 4px; }
.brand { font-weight: 700; font-size: 1.25rem; letter-spacing: -0.01em; margin: 0; }
.edition { color: var(--night-muted); font-size: .85rem; margin: 0; flex: 1; }
.theme { font: 600 .85rem var(--font); color: var(--night-ink); background: transparent;
  border: 1px solid var(--night-line); border-radius: 999px; min-height: 44px; padding: 0 16px; }
.theme:hover { border-color: var(--night-ink); }
.theme:active { transform: translateY(1px); }
.searchbar { background: var(--night); color: var(--night-ink); border-bottom: 1px solid var(--night-line); }
.searchbar .in-wrap { display: flex; align-items: flex-end; gap: 10px; padding-top: 8px; padding-bottom: 14px; }
#search { flex: 1; min-width: 0; }
.search { display: block; font-size: .85rem; color: var(--night-muted); }
.search > span:first-child { display: block; margin-bottom: 6px; }
.search .box { position: relative; display: block; }
.search svg { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); width: 20px; height: 20px;
  color: var(--night-muted); pointer-events: none; }
.search input { width: 100%; font: 500 1rem var(--font); color: var(--night-ink); background: var(--night-2);
  border: 1px solid var(--night-line); border-radius: 14px; min-height: 50px; padding: 0 16px 0 48px; }
.search input::placeholder { color: #8f94a3; }
.search input:hover { border-color: var(--night-muted); }
.toggle { display: none; font: 600 .95rem var(--font); color: var(--night-ink); background: var(--night-2);
  border: 1px solid var(--night-line); border-radius: 14px; min-height: 50px; padding: 0 16px; flex: none; }
.toggle:hover { border-color: var(--night-muted); }
.toggle:active { transform: translateY(1px); }

/* Body: filters | list | detail */
.shell { display: grid; grid-template-columns: 14.5rem minmax(0, 1fr); gap: 28px; padding-top: 24px; padding-bottom: 24px; }
.js .shell { grid-template-columns: 14.5rem minmax(0, 1fr) 26rem; }
.pinned { position: sticky; top: calc(var(--hdr, 170px) + 20px); align-self: start;
  max-height: calc(100vh - var(--hdr, 170px) - 36px); overflow-y: auto; overscroll-behavior: contain;
  scrollbar-width: thin; }
#aside { padding-right: 6px; }
.side-h { font-size: 1.1rem; margin: 0 0 10px; }
fieldset { border: 0; padding: 0; margin: 0 0 16px; min-width: 0; }
legend { font-size: .8rem; font-weight: 600; color: var(--muted); padding: 0; margin-bottom: 2px; }
.opt { display: flex; align-items: center; gap: 10px; min-height: 36px; font-size: .92rem; }
.opt input { width: 18px; height: 18px; margin: 0; accent-color: var(--ink); flex: none; }
.opt small { margin-left: auto; color: var(--muted); font-size: .8rem; }
.ghost { font: 600 .9rem var(--font); color: var(--ink); background: transparent; border: 1px solid var(--line);
  border-radius: 999px; min-height: 44px; padding: 0 18px; }
.ghost:hover { border-color: var(--ink); }
.ghost:active { transform: translateY(1px); }
.done { display: none; }

.res-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.res-head h1 { font-size: clamp(1.4rem, 2.6vw, 1.85rem); font-weight: 600; letter-spacing: -0.01em; margin: 0; }
.total { border: 1px solid var(--line); border-radius: 999px; padding: 1px 12px; font-weight: 600; font-size: .95rem; }
.sort { margin-left: auto; color: var(--muted); font-size: .85rem; }
.count { flex-basis: 100%; margin: 0; color: var(--muted); font-size: .9rem; }

/* Dense list: one posting per row, track colour lives in the small track tag */
.list { background: var(--surface); border: 1px solid var(--line); border-radius: 20px; overflow: hidden; }
.job { position: relative; border-top: 1px solid var(--line); }
.list > .job:first-of-type, .list > .empty + .job { border-top: 0; }
.job-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 16px; padding: 14px 18px; }
.job:hover .job-row { background: var(--hover); }
.job.sel .job-row, .job.open .job-row { background: color-mix(in srgb, var(--tint) 45%, var(--surface)); }
.job-title { font-size: 1.02rem; line-height: 1.3; font-weight: 600; margin: 0; overflow-wrap: anywhere; }
.pick { font: inherit; color: inherit; background: none; border: 0; padding: 0; text-align: left; text-decoration: none; }
.pick::after { content: ""; position: absolute; inset: 0; }
.pick:focus-visible { outline: none; }
.job:has(.pick:focus-visible) { outline: 3px solid var(--accent); outline-offset: -3px; }
.ago { color: var(--muted); font-size: .8rem; white-space: nowrap; padding-top: 2px; }
.meta { grid-column: 1 / -1; margin: 0; font-size: .88rem; color: var(--muted); overflow-wrap: anywhere; }
.meta .co { color: var(--ink); font-weight: 500; }
.tags { grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; margin: 6px 0 0; }
.pay { font-weight: 700; font-size: .9rem; margin-right: 4px; }
.pay.none { font-weight: 500; color: var(--muted); }
.trk { background: var(--tint); color: #121316; border-radius: 999px; padding: 2px 10px; font-size: .76rem; font-weight: 600; }
.new { background: var(--accent); color: var(--accent-ink); border-radius: 999px; padding: 2px 10px; font-size: .76rem; font-weight: 700; }
.t-fullstack { --tint: #dbe8ff; } .t-it_support { --tint: #d4f1e7; } .t-ai_junior { --tint: #e6dcfb; }
.t-admin_data { --tint: #e9e7e1; } .t-marketing { --tint: #ffe0c9; } .t-video_editor { --tint: #ffdae8; }
.t-graphic_design { --tint: #fdeeb4; } .t-social_media { --tint: #d6f0cc; }
:root[data-theme="dark"] .job.sel .job-row, :root[data-theme="dark"] .job.open .job-row {
  background: color-mix(in srgb, var(--tint) 16%, var(--surface)); }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .job.sel .job-row, :root:not([data-theme="light"]) .job.open .job-row {
    background: color-mix(in srgb, var(--tint) 16%, var(--surface)); }
}

/* Detail: hidden in the row, shown inline (narrow) or copied into the side panel (wide) */
.more { display: none; position: relative; z-index: 1; padding: 4px 18px 18px; }
.job.open .more { display: block; background: color-mix(in srgb, var(--tint) 18%, var(--surface)); }
.job.open .more .d-head { display: none; }
#detail { background: var(--surface); border: 1px solid var(--line); border-radius: 20px; padding: 22px; }
#detail .tags { margin: 0 0 12px; }
.d-title { font-size: 1.4rem; line-height: 1.25; font-weight: 700; margin: 0 0 4px; overflow-wrap: anywhere; }
.d-co { font-weight: 500; margin: 0 0 18px; }
.facts { margin: 0 0 18px; display: grid; gap: 10px; }
.facts div { display: grid; grid-template-columns: 6.5rem minmax(0, 1fr); gap: 12px; }
.facts dt { color: var(--muted); font-size: .85rem; }
.facts dd { margin: 0; font-size: .92rem; overflow-wrap: anywhere; }
.d-sub { font-size: .8rem; font-weight: 600; color: var(--muted); margin: 0 0 4px; }
.desc { font-size: .9rem; margin: 0 0 18px; color: var(--ink); }
.apply { display: flex; align-items: center; justify-content: center; min-height: 48px; border-radius: 999px;
  background: var(--ink); color: var(--surface); font-weight: 600; text-decoration: none; }
.apply:hover { background: color-mix(in srgb, var(--ink) 82%, var(--accent)); }
.scam { font-size: .82rem; color: var(--muted); margin: 14px 0 0; }
.d-empty { color: var(--muted); margin: 0; }
@keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.job.in { animation: rise .32s cubic-bezier(.2, .7, .3, 1) both; }
#detail.fade > * { animation: rise .25s ease both; }

.empty { padding: 28px 18px; }
.empty p { margin: 0 0 14px; font-size: 1.05rem; max-width: 36rem; }

footer { border-top: 1px solid var(--line); }
.foot { display: grid; grid-template-columns: 3fr 2fr; gap: 24px; padding-top: 28px; padding-bottom: 48px; }
footer h2 { font-size: 1.15rem; margin: 0 0 8px; }
footer p { margin: 0 0 10px; max-width: 40rem; color: var(--muted); }
.stamp { font-size: .85rem; }

@media (max-width: 1179px) {
  .js .shell, .shell { grid-template-columns: 14.5rem minmax(0, 1fr); }
  #detail { display: none; }
}
@media (max-width: 860px) {
  .js .shell, .shell { grid-template-columns: minmax(0, 1fr); gap: 0; }
  #aside { position: static; max-height: none; overflow: visible; padding: 0; }
  /* Filter opens as a sheet under the pinned header; elevated because it covers the list */
  #side { display: none; position: fixed; z-index: 6; top: calc(var(--hdr, 150px) + 8px); left: 16px; right: 16px;
    max-height: calc(100vh - var(--hdr, 150px) - 24px); overflow-y: auto; overscroll-behavior: contain;
    border: 1px solid var(--line); border-radius: 22px; padding: 16px; background: var(--surface);
    box-shadow: 0 18px 40px rgba(0, 0, 0, .28); }
  #side.open { display: block; }
  .opt { min-height: 44px; }
  .toggle { display: inline-flex; align-items: center; }
  .done { display: inline-flex; align-items: center; margin-left: 8px; background: var(--ink); color: var(--surface);
    border-color: var(--ink); }
  .sort { display: none; }
  .foot { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .edition { display: none; }
  .topbar .in-wrap { padding-top: 10px; padding-bottom: 2px; }
  .theme { min-height: 40px; }
  .search > span:first-child { margin-bottom: 4px; }
  .searchbar .in-wrap { padding-bottom: 12px; }
  .job-row { padding: 12px 14px; }
  .more { padding: 4px 14px 16px; }
  .facts div { grid-template-columns: 5.5rem minmax(0, 1fr); }
}
@media (max-height: 520px) {
  #top, .pinned { position: static; max-height: none; overflow: visible; }
  #side { top: 16px; max-height: calc(100vh - 32px); }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
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
      detail = document.getElementById('detail'), wide = matchMedia('(min-width: 1180px)'),
      jobs = Array.prototype.slice.call(document.querySelectorAll('.job')), all = jobs.length, chosen = null;
  if (!all) return;
  root.classList.add('js');
  form.hidden = false; q.disabled = false; toggle.hidden = false; detail.hidden = false;
  function pad() {
    var pinned = getComputedStyle(bar).position === 'sticky';
    root.style.setProperty('--hdr', (pinned ? bar.offsetHeight : 0) + 'px');
    root.style.scrollPaddingTop = (pinned ? bar.offsetHeight + 8 : 0) + 'px';
  }
  pad(); addEventListener('resize', pad);

  // Titles are links to the original posting; with JS they become buttons that open the detail.
  jobs.forEach(function (job) {
    var link = job.querySelector('.pick'), b = document.createElement('button');
    b.type = 'button'; b.className = 'pick'; b.textContent = link.textContent;
    b.setAttribute('aria-expanded', 'false');
    link.parentNode.replaceChild(b, link);
    b.addEventListener('click', function () { choose(job, true); });
  });
  function controls() {
    jobs.forEach(function (job) {
      job.querySelector('.pick').setAttribute('aria-controls', wide.matches ? 'detail' : job.querySelector('.more').id);
    });
  }
  function mark(job, on) {
    job.classList.toggle('sel', on && wide.matches);
    job.querySelector('.pick').setAttribute('aria-expanded', String(on));
  }
  function choose(job, byUser) {
    if (wide.matches) {
      if (chosen) mark(chosen, false);
      chosen = job; mark(job, true);
      detail.innerHTML = job.querySelector('.more').innerHTML;
      detail.className = 'pinned t-' + job.dataset.track;
      void detail.offsetWidth; detail.classList.add('fade');
      if (byUser) detail.scrollTop = 0;
    } else {
      var open = !job.classList.contains('open');
      job.classList.toggle('open', open); mark(job, open);
    }
  }
  function sync() {
    if (!wide.matches || (chosen && !chosen.hidden)) return;
    for (var i = 0; i < all; i++) { if (!jobs[i].hidden) { choose(jobs[i], false); return; } }
    if (chosen) mark(chosen, false);
    chosen = null;
    detail.innerHTML = '<p class="d-empty">Tidak ada lowongan yang cocok dengan filter ini.</p>';
  }
  wide.addEventListener('change', function () {
    jobs.forEach(function (job) { job.classList.remove('open', 'sel'); mark(job, false); });
    chosen = null; controls(); sync(); pad();
  });

  function checked(name) {
    return Array.prototype.slice.call(form.querySelectorAll('input[name="' + name + '"]:checked'))
      .map(function (i) { return i.value; });
  }
  function apply() {
    var words = q.value.toLowerCase().split(/\\s+/).filter(Boolean), cities = checked('city'),
        tracks = checked('track'), srcs = checked('src'), flags = checked('flag'), shown = 0;
    jobs.forEach(function (job) {
      var d = job.dataset;
      var ok = (!cities.length || cities.indexOf(d.city) !== -1)
        && (!tracks.length || tracks.indexOf(d.track) !== -1)
        && (!srcs.length || srcs.indexOf(d.src) !== -1)
        && (flags.indexOf('remote') === -1 || d.remote === '1')
        && (flags.indexOf('pay') === -1 || d.pay === '1')
        && (flags.indexOf('new') === -1 || d.new === '1')
        && words.every(function (w) { return d.text.indexOf(w) !== -1; });
      job.hidden = !ok;
      job.classList.remove('in');
      if (ok) {
        if (shown < 14) { void job.offsetWidth; job.style.animationDelay = (shown * 30) + 'ms'; job.classList.add('in'); }
        shown++;
      }
    });
    total.textContent = shown;
    count.textContent = shown === all ? all + ' lowongan, urut dari yang terbaru'
      : 'Menampilkan ' + shown + ' dari ' + all + ' lowongan';
    empty.hidden = shown !== 0;
    var active = cities.length + tracks.length + srcs.length + flags.length;
    toggle.textContent = active ? 'Filter (' + active + ')' : 'Filter';
    sync();
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
  controls(); apply();
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
    cities = [(c, CITY_LABEL[c], sum(1 for j in jobs if j["city"] == c)) for c in CITY_ORDER]
    cities = sorted((c for c in cities if c[2]), key=lambda c: (c[0] in ("remote", "abroad", "other"), -c[2]))
    tracks = [(t, TRACK_LABEL[t], sum(1 for j in jobs if j["track"] == t)) for t in TRACK_LABEL]
    tracks = [t for t in tracks if t[2]]
    sources = sorted({j["source"] for j in jobs})
    sources = [(s, s, sum(1 for j in jobs if j["source"] == s)) for s in sources]
    fresh = sum(1 for j in jobs if j["new"])
    flags = [("remote", "Bisa remote", sum(1 for j in jobs if j["remote"])),
             ("pay", "Ada info gaji", sum(1 for j in jobs if j["salary"])),
             ("new", "Baru, 2 hari terakhir", fresh)]
    if jobs:
        tally = f"{len(jobs)} lowongan, urut dari yang terbaru"
        body = "".join(_entry(j, now) for j in jobs)
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
  <div class="searchbar"><div class="in-wrap">
    <form id="search" role="search">
      <label class="search" for="q"><span>Cari judul, perusahaan, atau kota</span>
        <span class="box">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
          <input id="q" type="search" autocomplete="off" placeholder="contoh: laravel" disabled>
        </span>
      </label>
    </form>
    <button type="button" class="toggle" id="toggle" aria-expanded="false" aria-controls="side" hidden>Filter</button>
  </div></div>
</header>
<div class="in-wrap shell">
  <aside id="aside" class="pinned" aria-label="Filter lowongan">
    <div id="side">
      <form id="filters" hidden>
        <h2 class="side-h">Filter</h2>
        <fieldset><legend>Kota</legend>{_options("city", cities)}</fieldset>
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
    <div class="list">
      <div class="empty" id="empty" hidden>
        <p>Tidak ada lowongan yang cocok. Coba kata kunci yang lebih pendek atau kurangi filter.</p>
        <button type="button" class="ghost" id="reset">Hapus semua filter</button>
      </div>
      {body}
    </div>
  </main>
  <section id="detail" class="pinned" aria-label="Detail lowongan" hidden></section>
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
