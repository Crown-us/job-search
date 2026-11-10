"""Public static job board: index.html (fonts from Google Fonts) plus jobs.json.

Only public fields leave the database: title, company, location, salary,
remote flag, source, dates, track and the original URL. Personal CV fit,
gaps, letters, statuses and score reasons are never written.

Design notes ("Maniak Kerja", styled after laravel.com at the owner's request,
ENERGY 2 / RHYTHM 2 / MOTION 2):
- white page, near-black ink, hairline frame with red squares where lines cross: the
  repeated identity motif; Laravel's logo, name and illustrations are not used
- bright red #f53003 only for the decorative squares; buttons and red text use #d92a04
  so white-on-red and red-on-white pass WCAG AA
- Instrument Sans (light, tight headings) + IBM Plex Mono for small labels
- hero stats and the source strip show real counts; the strip replaces a client-logo
  bar, which this board does not have
- board = filters | dense list | pinned detail, separated by hairlines, no gaps; city is
  the first filter, track is a pill tab group above the list
- track keeps a small colour square so the categories stay scannable
- frosted header is the one blurred element: the list scrolls under it
- the list is server-rendered with titles linking to the original posting, so it
  works without JS; JavaScript adds filtering, the detail panel and the "/" shortcut
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


def candidates(min_score: int = 60, max_age_days: int = 30, now: datetime | None = None) -> list[tuple[dict, dict]]:
    """(db row, public entry) for fresh, named, track-matched postings not known to be closed."""
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=max_age_days)).timestamp()
    tracks = config.profile().get("tracks") or {}
    conn = db.connect()
    rows = [dict(r) for r in conn.execute(
        "SELECT id, source, company, title, url, location, remote, salary, department, description, "
        "posted_at, first_seen, checked_at FROM jobs WHERE COALESCE(closed_at, '') = ''"
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
        picked.append((row, {
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
        }))
    picked.sort(key=lambda pair: pair[1]["posted"], reverse=True)
    return picked


def select_jobs(min_score: int = 60, max_age_days: int = 30, now: datetime | None = None) -> list[dict]:
    """Public entries, newest first."""
    return [entry for _, entry in candidates(min_score, max_age_days, now)]


ARROW = ('<svg class="arrow" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" '
         'd="M5.22 14.78a.75.75 0 0 0 1.06 0l7.22-7.22v5.69a.75.75 0 0 0 1.5 0v-7.5a.75.75 0 0 0-.75-.75h-7.5a.75.75 '
         '0 0 0 0 1.5h5.69l-7.22 7.22a.75.75 0 0 0 0 1.06Z" clip-rule="evenodd"/></svg>')


def _entry(job: dict, now: datetime) -> str:
    e = html.escape
    track = TRACK_LABEL.get(job["track"], job["track"])
    posted_at = datetime.fromtimestamp(job["posted"], timezone.utc)
    ago = _ago(job["posted"], now)
    new = '<span class="new">Baru</span>' if job["new"] else ""
    pay = (f'<span class="pay">{e(job["salary"])}</span>' if job["salary"]
           else '<span class="pay none">Gaji tidak disebut</span>')
    trk = f'<span class="trk"><i aria-hidden="true"></i>{e(track)}</span>'
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
    excerpt = (f'<p class="label">Cuplikan iklan</p><p class="desc">{e(job["excerpt"])}</p>'
               if job["excerpt"] else "")
    haystack = e(f"{job['title']} {job['company']} {job['location']} {job['place']}".lower(), quote=True)
    jid = e(job["id"], quote=True)
    url = e(job["url"], quote=True)
    return f"""
    <article class="job t-{e(job['track'], quote=True)}" data-track="{e(job['track'], quote=True)}"
             data-city="{e(job['city'], quote=True)}" data-remote="{int(job['remote'])}"
             data-pay="{int(bool(job['salary']))}" data-new="{int(job['new'])}"
             data-src="{e(job['source'], quote=True)}" data-text="{haystack}">
      <div class="job-row">
        <h3 class="job-title"><a class="pick" href="{url}" target="_blank" rel="noopener nofollow">{e(job['title'])}</a></h3>
        <time class="ago" datetime="{posted_at.date().isoformat()}">{ago}</time>
        <p class="meta">{' · '.join(meta)}</p>
        <p class="tags">{pay}{trk}{new}</p>
      </div>
      <div class="more" id="more-{jid}">
        <div class="d-head">
          <p class="label">Detail lowongan</p>
          <p class="d-title">{e(job['title'])}</p>
          <p class="d-co">{e(job['company'])}</p>
          <p class="tags">{trk}{new}</p>
        </div>
        <dl class="facts">{dl}</dl>
        {excerpt}
        <a class="btn primary apply" href="{url}" target="_blank" rel="noopener nofollow">Lamar di {e(job['source'])}{ARROW}<span class="sr">(tab baru)</span></a>
        <p class="scam">Perusahaan yang sah tidak meminta biaya untuk melamar. Ada yang minta transfer? Jangan dibayar.</p>
      </div>
    </article>"""


FONTS = ("https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&"
         "family=IBM+Plex+Mono:wght@400;500&display=swap")

CSS = """
:root {
  --bg: #ffffff; --soft: #fafafa; --ink: #171717; --muted: #6b6b6b; --line: #e5e5e5;
  --red: #d92a04; --red-text: #d92a04; --mark: #f53003; --on-red: #ffffff;
  --sans: "Instrument Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0a0a0a; --soft: #141413; --ink: #ededec; --muted: #a1a09a; --line: #2a2a28; --red-text: #ff6a4d;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0a0a0a; --soft: #141413; --ink: #ededec; --muted: #a1a09a; --line: #2a2a28; --red-text: #ff6a4d;
  color-scheme: dark;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
html, body { overflow-x: clip; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 var(--sans); }
a, button, select, label:has(input[type=checkbox]), label:has(input[type=radio]),
input[type=checkbox], input[type=radio] { cursor: pointer; }
a { color: inherit; }
:focus-visible { outline: 2px solid var(--red-text); outline-offset: 2px; }
.label { font: 500 .72rem/1.4 var(--mono); text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin: 0; }

/* Frame: full-bleed hairlines, a framed column, red squares where lines cross (identity motif) */
.band { border-bottom: 1px solid var(--line); }
.frame { position: relative; max-width: 82rem; margin: 0 auto; border-left: 1px solid var(--line);
  border-right: 1px solid var(--line); }
.frame::before, .frame::after { content: ""; position: absolute; bottom: -4px; width: 7px; height: 7px;
  background: var(--mark); z-index: 2; }
.frame::before { left: -4px; } .frame::after { right: -4px; }

/* Header */
#top { position: sticky; top: 0; z-index: 6; background: color-mix(in srgb, var(--bg) 92%, transparent);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); }
#top .frame { border: 0; display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto;
  grid-template-areas: "brand search toggle theme"; align-items: center; gap: 10px 20px; padding: 10px 24px; }
#top .frame::before, #top .frame::after { display: none; }
.brand { grid-area: brand; margin: 0; font-weight: 600; font-size: 1.3rem; letter-spacing: -0.03em; color: var(--red-text); }
#search { grid-area: search; justify-self: end; width: 100%; max-width: 26rem; }
.search { display: flex; align-items: center; gap: 8px; background: var(--soft); border: 1px solid var(--line);
  border-radius: 8px; min-height: 44px; padding: 0 10px 0 12px; cursor: text; }
.search:hover { border-color: color-mix(in srgb, var(--ink) 30%, var(--line)); }
.search:focus-within { border-color: var(--ink); }
.search svg { width: 16px; height: 16px; color: var(--muted); flex: none; }
.search-label { font-size: .9rem; font-weight: 500; }
.search input { flex: 1; min-width: 0; font: inherit; font-size: .92rem; color: var(--ink); background: transparent;
  border: 0; min-height: 42px; padding: 0; }
.search input:focus { outline: none; }
.search input::placeholder { color: var(--muted); }
kbd { font: 500 .72rem var(--mono); color: var(--muted); border: 1px solid var(--line); border-radius: 4px;
  padding: 1px 6px; background: var(--bg); }
.icon-btn { display: grid; place-items: center; width: 44px; height: 44px; padding: 0; color: var(--ink);
  background: var(--bg); border: 1px solid var(--line); border-radius: 8px; }
.icon-btn svg { width: 18px; height: 18px; }
.icon-btn:hover, .btn.ghost:hover { background: var(--soft); }
.icon-btn:active, .btn:active { transform: translateY(1px); }
.theme { grid-area: theme; }
.theme[data-mode="dark"] .moon, .theme:not([data-mode="dark"]) .sun { display: none; }
.btn.toggle { grid-area: toggle; display: none; }

/* Buttons */
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; padding: 0 18px;
  border-radius: 8px; font: 500 .95rem var(--sans); text-decoration: none; border: 1px solid transparent; }
.btn.primary { background: var(--red); color: var(--on-red); }
.btn.primary:hover { background: color-mix(in srgb, var(--red) 88%, #000); }
.btn.ghost { background: var(--bg); color: var(--ink); border-color: var(--line); }
.arrow { width: 16px; height: 16px; flex: none; transition: transform .1s ease-out; }
.btn.ghost .arrow { color: var(--red-text); }
.btn:hover .arrow { transform: translate(1px, -1px); }

/* Hero */
.hero { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); }
.hero-copy { padding: 72px 48px 64px; }
h1 { font-weight: 400; font-size: clamp(2.4rem, 5.2vw, 4.2rem); line-height: 1.02; letter-spacing: -0.045em; margin: 0; max-width: 14ch; }
.lede { color: var(--muted); font-size: 1.15rem; line-height: 1.5; max-width: 32rem; margin: 20px 0 32px; }
.cta { display: flex; flex-wrap: wrap; gap: 12px; }
.stats { border-left: 1px solid var(--line); display: grid; align-content: stretch; margin: 0; }
.stats div { display: flex; flex-direction: column; justify-content: center; gap: 6px; padding: 22px 32px; }
.stats div + div { border-top: 1px solid var(--line); }
.stats dd { margin: 0; font-size: 2rem; letter-spacing: -0.03em; line-height: 1.1; }
.stats dd small { font-size: .95rem; color: var(--muted); letter-spacing: 0; }

/* Source strip: real sources with counts, standing in for a client logo bar */
.strip { display: grid; grid-template-columns: 15rem repeat(auto-fit, minmax(9rem, 1fr)); }
.strip > * { padding: 22px 24px; display: flex; flex-direction: column; justify-content: center; gap: 4px; }
.strip > * + * { border-left: 1px solid var(--line); }
.strip strong { font-weight: 500; font-size: 1.05rem; letter-spacing: -0.01em; }
.strip span { color: var(--muted); font-size: .85rem; }

/* Board: filters | list | detail, separated by hairlines, no gaps */
.board { display: grid; grid-template-columns: 15rem minmax(0, 1fr); }
.js .board { grid-template-columns: 15rem minmax(0, 1fr) 27rem; }
.pinned { position: sticky; top: calc(var(--hdr, 64px) + 1px); align-self: start;
  max-height: calc(100vh - var(--hdr, 64px) - 1px); overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; }
#aside { border-right: 1px solid var(--line); padding: 28px 22px; }
#side h2 { font-size: 1.05rem; font-weight: 500; letter-spacing: -0.01em; margin: 0 0 16px; }
fieldset { border: 0; padding: 0; margin: 0 0 20px; min-width: 0; }
legend { padding: 0; margin-bottom: 6px; }
.opt { display: flex; align-items: center; gap: 10px; min-height: 34px; font-size: .92rem; }
.opt input { width: 16px; height: 16px; margin: 0; accent-color: var(--red); flex: none; }
.opt small { margin-left: auto; font: 400 .75rem var(--mono); color: var(--muted); }
.side-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.btn.done { display: none; }

.list-col { min-width: 0; }
.list-head { padding: 28px 28px 18px; border-bottom: 1px solid var(--line); }
.list-head h2 { display: flex; align-items: center; gap: 10px; font-weight: 400; font-size: 1.9rem;
  letter-spacing: -0.035em; line-height: 1.1; margin: 0 0 6px; }
.total { font: 500 .8rem var(--mono); border: 1px solid var(--line); border-radius: 999px; padding: 2px 10px;
  letter-spacing: 0; }
.sub { margin: 0 0 16px; color: var(--muted); font-size: .9rem; }
.tabs { display: flex; gap: 2px; padding: 4px; border: 1px solid var(--line); border-radius: 999px; width: max-content;
  max-width: 100%; overflow-x: auto; scrollbar-width: none; background: var(--soft); }
.tabs label { position: relative; flex: none; display: inline-flex; align-items: center; min-height: 36px; padding: 0 14px;
  border-radius: 999px; font-size: .88rem; color: var(--muted); border: 1px solid transparent; }
.tabs input { position: absolute; opacity: 0; inset: 0; margin: 0; }
.tabs label:hover { color: var(--ink); }
.tabs label:has(input:checked) { background: var(--bg); color: var(--ink); font-weight: 500; border-color: var(--line);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .06); }
.tabs label:has(input:focus-visible) { outline: 2px solid var(--red-text); outline-offset: 1px; }

.job { position: relative; border-bottom: 1px solid var(--line); }
.job-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 16px; padding: 18px 28px; }
.job:hover .job-row { background: var(--soft); }
.job.sel .job-row, .job.open .job-row { background: var(--soft); }
.job.sel .job-title, .job.open .job-title { color: var(--red-text); }
.job.sel .job-row { box-shadow: inset 0 0 0 1px var(--line); }
.job-title { font-size: 1.05rem; line-height: 1.3; font-weight: 500; letter-spacing: -0.01em; margin: 0; overflow-wrap: anywhere; }
.pick { font: inherit; color: inherit; background: none; border: 0; padding: 0; text-align: left; text-decoration: none; letter-spacing: inherit; }
.pick::after { content: ""; position: absolute; inset: 0; }
.pick:focus-visible { outline: none; }
.job:has(.pick:focus-visible) { outline: 2px solid var(--red-text); outline-offset: -2px; }
.ago { font: 400 .75rem var(--mono); color: var(--muted); white-space: nowrap; padding-top: 3px; }
.meta { grid-column: 1 / -1; margin: 0; font-size: .9rem; color: var(--muted); overflow-wrap: anywhere; }
.meta .co { color: var(--ink); }
.tags { grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; margin: 8px 0 0; }
.pay { font-weight: 500; font-size: .9rem; margin-right: 4px; }
.pay.none { font-weight: 400; color: var(--muted); }
.trk { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--line); border-radius: 6px;
  padding: 1px 8px; font-size: .78rem; color: var(--ink); background: var(--bg); }
.trk i { width: 7px; height: 7px; background: var(--tint); }
.new { font: 500 .7rem var(--mono); text-transform: uppercase; letter-spacing: .04em; color: var(--red-text);
  border: 1px solid color-mix(in srgb, var(--red-text) 40%, transparent); border-radius: 6px; padding: 2px 7px; }
.t-fullstack { --tint: #2563eb; } .t-it_support { --tint: #0d9488; } .t-ai_junior { --tint: #7c3aed; }
.t-admin_data { --tint: #737373; } .t-marketing { --tint: #ea580c; } .t-video_editor { --tint: #db2777; }
.t-graphic_design { --tint: #ca8a04; } .t-social_media { --tint: #16a34a; }

/* Detail: hidden in the row; shown inline (narrow) or copied into the pinned panel (wide) */
.more { display: none; position: relative; z-index: 1; padding: 0 28px 24px; background: var(--soft); }
.job.open .more { display: block; }
.job.open .more .d-head { display: none; }
#detail { border-left: 1px solid var(--line); padding: 28px; }
.d-title { font-size: 1.6rem; line-height: 1.15; letter-spacing: -0.035em; margin: 10px 0 6px; overflow-wrap: anywhere; }
.d-co { margin: 0; color: var(--muted); }
#detail .tags { margin: 14px 0 22px; }
.facts { margin: 0 0 22px; border-top: 1px solid var(--line); }
.facts div { display: grid; grid-template-columns: 6.5rem minmax(0, 1fr); gap: 12px; padding: 9px 0;
  border-bottom: 1px solid var(--line); }
.facts dt { font: 400 .75rem/1.9 var(--mono); text-transform: uppercase; letter-spacing: .03em; color: var(--muted); }
.facts dd { margin: 0; font-size: .92rem; overflow-wrap: anywhere; }
.desc { font-size: .92rem; color: var(--ink); margin: 6px 0 22px; }
.apply { width: 100%; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
.scam { font-size: .82rem; color: var(--muted); margin: 14px 0 0; }
.d-empty { color: var(--muted); margin: 0; }
@keyframes rise { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
.job.in { animation: rise .3s ease-out both; }
#detail.fade > * { animation: rise .22s ease-out both; }

.empty { padding: 32px 28px; border-bottom: 1px solid var(--line); }
.empty p { margin: 0 0 14px; font-size: 1.05rem; max-width: 36rem; }

.foot { display: grid; grid-template-columns: 1fr 1fr; }
.foot section { padding: 40px 48px 48px; }
.foot section + section { border-left: 1px solid var(--line); }
.foot h2 { font-weight: 400; font-size: 1.5rem; letter-spacing: -0.03em; margin: 0 0 12px; }
.foot p { margin: 0 0 10px; color: var(--muted); max-width: 36rem; }
.checks { list-style: none; padding: 0; margin: 0 0 14px; }
.checks li { display: flex; gap: 10px; margin-bottom: 6px; color: var(--ink); }
.checks svg { width: 16px; height: 16px; color: var(--red-text); flex: none; margin-top: 4px; }

@media (max-width: 1179px) {
  .js .board, .board { grid-template-columns: 15rem minmax(0, 1fr); }
  #detail { display: none; }
}
@media (max-width: 900px) {
  .hero { grid-template-columns: minmax(0, 1fr); }
  .stats { border-left: 0; border-top: 1px solid var(--line); grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .stats div + div { border-top: 0; border-left: 1px solid var(--line); }
  .stats div { padding: 18px 20px; }
  .stats dd { font-size: 1.5rem; }
  .strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .strip > * { border-top: 1px solid var(--line); }
  .strip > :first-child { grid-column: 1 / -1; border-top: 0; }
  .strip > * + * { border-left: 0; }
  .strip > :nth-child(odd):not(:first-child) { border-left: 1px solid var(--line); }
  .foot { grid-template-columns: minmax(0, 1fr); }
  .foot section + section { border-left: 0; border-top: 1px solid var(--line); }
}
@media (max-width: 860px) {
  .js .board, .board { grid-template-columns: minmax(0, 1fr); }
  #aside { position: static; max-height: none; overflow: visible; padding: 0; border: 0; }
  /* Filter opens as a sheet under the pinned header; elevated because it covers the list */
  #side { display: none; position: fixed; z-index: 7; top: calc(var(--hdr, 120px) + 8px); left: 16px; right: 16px;
    max-height: calc(100vh - var(--hdr, 120px) - 24px); overflow-y: auto; overscroll-behavior: contain;
    border: 1px solid var(--line); border-radius: 12px; padding: 18px; background: var(--bg);
    box-shadow: 0 18px 40px rgba(0, 0, 0, .22); }
  #side.open { display: block; }
  .opt { min-height: 44px; }
  .btn.toggle, .btn.done { display: inline-flex; }
  #top .frame { grid-template-columns: minmax(0, 1fr) auto auto; grid-template-areas: "brand toggle theme" "search search search";
    padding: 10px 16px; }
  #search { max-width: none; justify-self: stretch; }
  kbd { display: none; }
}
@media (max-width: 560px) {
  .hero-copy { padding: 40px 20px 36px; }
  .stats dd { font-size: 1.25rem; }
  .stats div { padding: 14px 14px; }
  .list-head { padding: 22px 16px 14px; }
  .job-row { padding: 14px 16px; }
  .more { padding: 0 16px 20px; }
  .facts div { grid-template-columns: 5.5rem minmax(0, 1fr); }
  .foot section { padding: 32px 20px 36px; }
  .strip > * { padding: 16px; }
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
    btn.dataset.mode = dark ? 'dark' : 'light';
    btn.setAttribute('aria-label', dark ? 'Ganti ke mode terang' : 'Ganti ke mode gelap');
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
      tabs = document.getElementById('tabs'), total = document.getElementById('total'),
      count = document.getElementById('count'), empty = document.getElementById('empty'),
      bar = document.getElementById('top'), detail = document.getElementById('detail'),
      wide = matchMedia('(min-width: 1180px)'),
      jobs = Array.prototype.slice.call(document.querySelectorAll('.job')), all = jobs.length, chosen = null;
  if (!all) return;
  root.classList.add('js');
  form.hidden = false; tabs.hidden = false; q.disabled = false; toggle.hidden = false; detail.hidden = false;
  function pad() {
    var pinned = getComputedStyle(bar).position === 'sticky';
    root.style.setProperty('--hdr', (pinned ? bar.offsetHeight : 0) + 'px');
    root.style.scrollPaddingTop = (pinned ? bar.offsetHeight + 8 : 0) + 'px';
  }
  pad(); addEventListener('resize', pad);

  // Titles link to the original posting; with JS they become buttons that open the detail.
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
    return Array.prototype.slice.call(document.querySelectorAll('input[name="' + name + '"]:checked'))
      .map(function (i) { return i.value; }).filter(Boolean);
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
        if (shown < 14) { void job.offsetWidth; job.style.animationDelay = (shown * 25) + 'ms'; job.classList.add('in'); }
        shown++;
      }
    });
    total.textContent = shown;
    count.textContent = shown === all ? all + ' lowongan, urut dari yang terbaru'
      : 'Menampilkan ' + shown + ' dari ' + all + ' lowongan';
    empty.hidden = shown !== 0;
    var active = cities.length + srcs.length + flags.length;
    toggle.textContent = active ? 'Filter (' + active + ')' : 'Filter';
    sync();
  }
  function reset() { form.reset(); tabs.reset(); q.value = ''; apply(); q.focus(); }
  form.addEventListener('change', apply);
  tabs.addEventListener('change', apply);
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
    if (e.key === 'Escape' && side.classList.contains('open')) { setOpen(false, true); return; }
    var t = e.target, typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
    if (e.key === '/' && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); q.focus(); }
  });
  controls(); apply();
})();
"""


def _options(name: str, items: list[tuple[str, str, int]]) -> str:
    e = html.escape
    return "".join(
        f'<label class="opt"><input type="checkbox" name="{name}" value="{e(v, quote=True)}"> {e(text)}'
        f'<small>{n}</small></label>' for v, text, n in items)


CHECK = ('<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 '
         '1.4l-8 8a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.4L8 12.58l7.3-7.3a1 1 0 0 1 1.4 0Z" clip-rule="evenodd"/></svg>')


def render(jobs: list[dict], name: str, now: datetime | None = None) -> str:
    now = (now or datetime.now(timezone.utc)).astimezone(WIB)
    e = html.escape
    cities = [(c, CITY_LABEL[c], sum(1 for j in jobs if j["city"] == c)) for c in CITY_ORDER]
    cities = sorted((c for c in cities if c[2]), key=lambda c: (c[0] in ("remote", "abroad", "other"), -c[2]))
    tracks = [(t, TRACK_LABEL[t], sum(1 for j in jobs if j["track"] == t)) for t in TRACK_LABEL]
    tracks = [t for t in tracks if t[2]]
    sources = sorted({j["source"] for j in jobs}, key=lambda s: -sum(1 for j in jobs if j["source"] == s))
    sources = [(s, s, sum(1 for j in jobs if j["source"] == s)) for s in sources]
    fresh = sum(1 for j in jobs if j["new"])
    paid = sum(1 for j in jobs if j["salary"])
    flags = [("remote", "Bisa remote", sum(1 for j in jobs if j["remote"])),
             ("pay", "Ada info gaji", paid),
             ("new", "Baru, 2 hari terakhir", fresh)]
    stamp = f"{now.day} {MONTHS[now.month - 1][:3]}, {now:%H.%M} WIB"
    tabs = '<label><input type="radio" name="track" value="" checked> Semua</label>' + "".join(
        f'<label><input type="radio" name="track" value="{t}"> {e(label)}</label>' for t, label, _ in tracks)
    strip = "".join(f'<div><strong>{e(s)}</strong><span>{n} lowongan</span></div>' for s, _, n in sources[:5])
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
<header id="top" class="band"><div class="frame">
  <p class="brand">{e(name)}</p>
  <form id="search" role="search">
    <label class="search" for="q">
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="9" cy="9" r="6"/><path d="m17 17-3.5-3.5"/></svg>
      <span class="search-label">Cari</span>
      <input id="q" type="search" autocomplete="off" placeholder="posisi, PT, kota" disabled>
      <kbd aria-hidden="true">/</kbd>
    </label>
  </form>
  <button type="button" class="btn ghost toggle" id="toggle" aria-expanded="false" aria-controls="side" hidden>Filter</button>
  <button type="button" class="icon-btn theme" id="theme" aria-pressed="false" aria-label="Ganti ke mode gelap" hidden>
    <svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>
    <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
  </button>
</div></header>

<section class="band"><div class="frame hero">
  <div class="hero-copy">
    <h1>Lowongan kerja yang jelas siapa yang buka.</h1>
    <p class="lede">Dikumpulkan tiap pagi dari JobStreet, Kalibrr, dan halaman karier perusahaan.
    Iklan tanpa nama perusahaan dibuang sebelum sampai ke sini.</p>
    <div class="cta">
      <a class="btn primary" href="#papan">Lihat {len(jobs)} lowongan</a>
      <a class="btn ghost" href="#cara-kerja">Cara kerja papan ini</a>
    </div>
  </div>
  <dl class="stats">
    <div><dt class="label">Baru, 2 hari terakhir</dt><dd>{fresh} <small>lowongan</small></dd></div>
    <div><dt class="label">Mencantumkan gaji</dt><dd>{paid} <small>dari {len(jobs)}</small></dd></div>
    <div><dt class="label">Diperbarui</dt><dd>{now:%H.%M} <small>WIB, {now.day} {MONTHS[now.month - 1][:3]}</small></dd></div>
  </dl>
</div></section>

<section class="band" aria-label="Sumber data"><div class="frame strip">
  <p class="label">Sumber data<br>edisi hari ini</p>
  {strip}
</div></section>

<div class="band" id="papan"><div class="frame board">
  <aside id="aside" class="pinned" aria-label="Filter lowongan">
    <div id="side">
      <form id="filters" hidden>
        <h2>Filter</h2>
        <fieldset><legend class="label">Kota</legend>{_options("city", cities)}</fieldset>
        <fieldset><legend class="label">Lowongan</legend>{_options("flag", flags)}</fieldset>
        <fieldset><legend class="label">Sumber</legend>{_options("src", sources)}</fieldset>
        <div class="side-actions">
          <button type="button" class="btn ghost" id="reset-side">Hapus filter</button>
          <button type="button" class="btn primary done" id="done">Selesai</button>
        </div>
      </form>
    </div>
  </aside>
  <main class="list-col">
    <div class="list-head">
      <h2>Lowongan terbaru <span class="total" id="total">{len(jobs)}</span></h2>
      <p class="sub"><span id="count" aria-live="polite">{tally}</span> · Diperbarui {stamp}</p>
      <form id="tabs" class="tabs" aria-label="Bidang" hidden>{tabs}</form>
    </div>
    <div class="empty" id="empty" hidden>
      <p>Tidak ada lowongan yang cocok. Coba kata kunci yang lebih pendek atau kurangi filter.</p>
      <button type="button" class="btn ghost" id="reset">Hapus semua filter</button>
    </div>
    {body}
  </main>
  <section id="detail" class="pinned" aria-label="Detail lowongan" hidden></section>
</div></div>

<footer class="band" id="cara-kerja"><div class="frame foot">
  <section>
    <h2>Cara kerja papan ini</h2>
    <ul class="checks">
      <li>{CHECK}Ditarik tiap pagi dari JobStreet, Kalibrr, dan halaman karier perusahaan</li>
      <li>{CHECK}Duplikat dan posting lebih dari 30 hari dibuang</li>
      <li>{CHECK}Iklan tanpa nama perusahaan (misalnya "Private Advertiser") tidak dimuat</li>
    </ul>
    <p>Tombol Lamar membuka halaman aslinya di tab baru; lamar di sana. Terakhir diperbarui {now:%d-%m-%Y %H:%M} WIB.</p>
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
