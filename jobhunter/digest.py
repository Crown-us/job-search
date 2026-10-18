"""Daily digest as a self-contained HTML file, with optional email delivery.

No accounts, no phone, no server: the file opens in any browser and works
offline. Email delivery is opt-in through SMTP_* in .env.
"""

from __future__ import annotations

import html
import smtplib
import sqlite3
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from . import config

COLOURS = {"good": "#2f9e5f", "mid": "#c8922a", "low": "#b44d4d"}


def _tone(fit: int | None) -> str:
    if fit is None:
        return "low"
    if fit >= 75:
        return "good"
    if fit >= 55:
        return "mid"
    return "low"


def _load(limit: int, min_fit: int) -> list[sqlite3.Row]:
    conn = sqlite3.connect(config.db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT j.*, a.fit, a.verdict, a.gaps, a.strengths
        FROM jobs j
        LEFT JOIN analyses a ON a.job_id = j.id
        WHERE j.status IN ('new', 'shortlist')
          AND COALESCE(a.fit, j.score, 0) >= ?
        ORDER BY COALESCE(a.fit, j.score, 0) DESC, j.score DESC
        LIMIT ?
        """,
        (min_fit, limit),
    ).fetchall()
    conn.close()
    return list(rows)


def _letter_path(job_id: str) -> Path | None:
    folder = config.DATA_DIR / "letters"
    if not folder.exists():
        return None
    matches = sorted(folder.glob(f"{job_id[:8]}-*.md"))
    return matches[0] if matches else None


def _card(row: sqlite3.Row, index: int) -> str:
    fit = row["fit"]
    tone = _tone(fit)
    gaps = [g for g in (row["gaps"] or "").split("\n") if g.strip()]
    strengths = [s for s in (row["strengths"] or "").split("\n") if s.strip()]
    letter = _letter_path(row["id"])

    gap_html = "".join(f"<li class='gap'>{html.escape(g)}</li>" for g in gaps[:4])
    strength_html = "".join(f"<li class='plus'>{html.escape(s)}</li>" for s in strengths[:3])
    letter_link = (
        f"<a class='btn ghost' href='{letter.as_uri()}'>Surat siap</a>" if letter else ""
    )
    remote = " · remote" if row["remote"] else ""

    return f"""
    <article class="card {tone}">
      <div class="rank">{index:02d}</div>
      <div class="body">
        <div class="head">
          <h2><a href="{html.escape(row['url'])}" target="_blank">{html.escape(row['title'])}</a></h2>
          <span class="fit" title="fit">{'–' if fit is None else fit}</span>
        </div>
        <p class="meta">{html.escape(row['company'])} · {html.escape(row['location'] or 'lokasi tidak disebut')}{remote}
           · skor {row['score']} · {html.escape(row['source'])}</p>
        <p class="verdict">{html.escape(row['verdict'] or '')}</p>
        <ul class="facts">{strength_html}{gap_html}</ul>
        <div class="actions">
          <a class="btn" href="{html.escape(row['url'])}" target="_blank">Buka lowongan</a>
          {letter_link}
          <code>python -m jobhunter status {row['id'][:8]} applied</code>
        </div>
      </div>
    </article>"""


def render(rows: list[sqlite3.Row]) -> str:
    today = datetime.now().strftime("%A, %d %B %Y")
    cards = "".join(_card(row, i) for i, row in enumerate(rows, 1))
    good = sum(1 for r in rows if (r["fit"] or 0) >= 75)
    empty = "<p class='empty'>Belum ada lowongan di atas ambang. Jalankan <code>discover</code> lalu <code>analyze</code>.</p>"

    return f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Hunter — {today}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:32px 20px 64px; font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
         background:#f6f6f4; color:#1d1d1b; }}
  @media (prefers-color-scheme: dark) {{ body {{ background:#161615; color:#eceae4; }} }}
  .wrap {{ max-width:920px; margin:0 auto; }}
  header h1 {{ margin:0 0 4px; font-size:26px; letter-spacing:-0.4px; }}
  header p {{ margin:0; opacity:.62; font-size:13px; }}
  .stats {{ display:flex; gap:24px; margin:22px 0 28px; padding:14px 18px;
            border:1px solid rgba(128,128,128,.25); border-radius:12px; }}
  .stats div {{ font-size:12px; opacity:.7; }}
  .stats b {{ display:block; font-size:20px; opacity:1; margin-top:2px; }}
  .card {{ display:flex; gap:14px; padding:18px; margin-bottom:14px; border-radius:12px;
           border:1px solid rgba(128,128,128,.22); border-left:4px solid var(--tone);
           background:rgba(255,255,255,.6); }}
  @media (prefers-color-scheme: dark) {{ .card {{ background:rgba(255,255,255,.04); }} }}
  .card.good {{ --tone:{COLOURS['good']}; }} .card.mid {{ --tone:{COLOURS['mid']}; }} .card.low {{ --tone:{COLOURS['low']}; }}
  .rank {{ font:600 12px/1 ui-monospace,monospace; opacity:.35; padding-top:4px; }}
  .body {{ flex:1; min-width:0; }}
  .head {{ display:flex; gap:12px; align-items:baseline; justify-content:space-between; }}
  h2 {{ margin:0; font-size:16px; line-height:1.35; }}
  h2 a {{ color:inherit; text-decoration:none; border-bottom:1px solid rgba(128,128,128,.35); }}
  h2 a:hover {{ border-color:currentColor; }}
  .fit {{ font:600 13px/1 ui-monospace,monospace; color:var(--tone); white-space:nowrap; }}
  .meta {{ margin:6px 0 0; font-size:12.5px; opacity:.62; }}
  .verdict {{ margin:10px 0 8px; font-size:13.5px; }}
  ul.facts {{ margin:0; padding:0; list-style:none; display:flex; flex-wrap:wrap; gap:6px 14px; font-size:12.5px; }}
  ul.facts li::before {{ content:"+ "; color:{COLOURS['good']}; }}
  ul.facts li.gap::before {{ content:"– "; color:{COLOURS['low']}; }}
  ul.facts li.gap {{ opacity:.8; }}
  .actions {{ display:flex; align-items:center; gap:10px; margin-top:12px; flex-wrap:wrap; }}
  .btn {{ font-size:12.5px; text-decoration:none; padding:6px 12px; border-radius:7px;
          background:var(--tone); color:#fff; }}
  .btn.ghost {{ background:transparent; color:inherit; border:1px solid rgba(128,128,128,.4); }}
  code {{ font:11.5px/1.4 ui-monospace,monospace; opacity:.5; }}
  .empty {{ opacity:.6; }}
  footer {{ margin-top:28px; font-size:12px; opacity:.5; }}
</style></head>
<body><div class="wrap">
  <header>
    <h1>Lowongan buat Kevin</h1>
    <p>{today} · digest otomatis</p>
  </header>
  <div class="stats">
    <div>Ditampilkan<b>{len(rows)}</b></div>
    <div>Fit ≥ 75<b>{good}</b></div>
    <div>Ambang fit<b>≥ 55</b></div>
  </div>
  {cards or empty}
  <footer>Dibuat oleh jobhunter · <code>python -m jobhunter digest</code> ·
  data dari JobStreet, Greenhouse, Ashby, Kalibrr</footer>
</div></body></html>"""


def write(limit: int = 12, min_fit: int = 55, open_after: bool = False) -> Path:
    rows = _load(limit, min_fit)
    out_dir = config.DATA_DIR / "digest"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"digest-{datetime.now():%Y-%m-%d}.html"
    path.write_text(render(rows), encoding="utf-8")
    if open_after:
        import webbrowser

        webbrowser.open(path.as_uri())
    return path


def email_html(html_text: str, subject: str) -> str:
    """Send the digest through SMTP. Returns a status string."""
    env = config.env()
    host = (env.get("SMTP_HOST") or "").strip()
    user = (env.get("SMTP_USER") or "").strip()
    password = (env.get("SMTP_PASS") or "").strip()
    to_addr = (env.get("DIGEST_TO") or user).strip()
    if not (host and user and password and to_addr):
        return "smtp belum dikonfigurasi (SMTP_HOST, SMTP_USER, SMTP_PASS, DIGEST_TO)"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = user
    message["To"] = to_addr
    message.set_content("Buka versi HTML untuk tampilan lengkap.")
    message.add_alternative(html_text, subtype="html")

    port = int(env.get("SMTP_PORT") or 587)
    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(message)
        return f"terkirim ke {to_addr}"
    except Exception as exc:
        return f"gagal kirim: {type(exc).__name__}: {exc}"
