"""Command line entry point: python -m jobhunter <command>."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime

from rich.console import Console
from rich.table import Table

from . import config, db, pipeline
from . import analyze as analysis
from . import digest as daily_digest
from . import discord_notify as discord
from . import discord_sync
from . import letter as cover_letter
from . import score as scoring
from . import toast as windows_toast
from .sources import ADAPTERS, BOARD_SOURCES

console = Console() if sys.stdout.isatty() else Console(width=110)

try:  # legacy Windows consoles default to cp1252 and crash on "≥" or "·"
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SRC_SHORT = {
    "greenhouse": "gh",
    "ashby": "ash",
    "lever": "lv",
    "workable": "wk",
    "remoteok": "rok",
    "hackernews": "hn",
}


def _short(text: str, width: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: max(1, width - 3)] + "..."


def _title_width(reserved: int) -> int:
    return max(28, console.width - reserved)


def _job_table(rows: list[dict], show_reason: bool = False) -> None:
    col = {"scr": 5, "company": 18, "location": 18, "src": 6, "status": 8}
    title_w = _title_width(sum(col.values()) + 10)
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Scr", justify="right", width=col["scr"], no_wrap=True)
    table.add_column("Company", width=col["company"], no_wrap=True)
    table.add_column("Title", width=title_w, no_wrap=True)
    table.add_column("Location", width=col["location"], no_wrap=True)
    table.add_column("Src", width=col["src"], no_wrap=True)
    table.add_column("Status", width=col["status"], no_wrap=True)
    for r in rows:
        table.add_row(
            "-" if r.get("score") is None else str(r["score"]),
            _short(r.get("company"), col["company"] - 1),
            _short(r.get("title"), title_w - 1),
            _short(r.get("location") or ("Remote" if r.get("remote") else "-"), col["location"] - 1),
            SRC_SHORT.get(r.get("source", ""), (r.get("source") or "")[:5]),
            r.get("status") or "",
        )
    console.print(table)
    if show_reason:
        for r in rows[:5]:
            if r.get("score_reason"):
                console.print(f"  [dim]{r['score']} {_short(r.get('title'), 38)} -> {r['score_reason']}[/]")


def _top_rows(limit: int, status: str = "") -> list[dict]:
    conn = db.connect()
    sql = "SELECT * FROM jobs"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY COALESCE(score, -1) DESC, first_seen DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows


def cmd_discover(args) -> int:
    result = pipeline.run_discover(
        sources=args.source,
        full=args.full,
        per_board_limit=args.per_board,
        total_limit=args.limit,
        apply_filters=not args.no_filter,
        dry_run=args.dry_run,
    )

    console.print(
        f"[bold]fetched[/] {result['fetched']}  "
        f"[bold]match filter[/] {result['matched']}  "
        f"[bold]unique[/] {result['unique']}  "
        f"[bold]new[/] {result['inserted']}  "
        f"[bold]seen[/] {result['known']}"
    )
    if result["by_source"]:
        console.print("  per source: " + ", ".join(f"{k}={v}" for k, v in result["by_source"].items()))
    for err in result["errors"][:10]:
        console.print(f"  [yellow]! {err}[/]")

    if args.dry_run:
        profile = config.profile()
        preview = []
        for job in result["jobs"]:
            row = job.as_row()
            row["score"], row["score_reason"] = scoring.score_one(row, profile)
            row["status"] = "new"
            preview.append(row)
        preview.sort(key=lambda r: r["score"], reverse=True)
        _job_table(preview[: args.show], show_reason=True)
        console.print("[dim]dry run: nothing written[/]")
        return 0

    scored = scoring.score_jobs()
    console.print(f"[dim]scored {scored} new posting(s)[/]")
    _job_table(_top_rows(args.show), show_reason=True)
    return 0


def cmd_list(args) -> int:
    conn = db.connect()
    where, params = [], []
    if args.status:
        where.append("status = ?")
        params.append(args.status)
    if args.search:
        where.append("(title LIKE ? OR company LIKE ? OR department LIKE ?)")
        params.extend([f"%{args.search}%"] * 3)
    if args.min_score:
        where.append("COALESCE(score, -1) >= ?")
        params.append(args.min_score)
    sql = "SELECT * FROM jobs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(score, -1) DESC, first_seen DESC LIMIT ?"
    params.append(args.limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()

    if args.json:
        console.print_json(json.dumps(rows, indent=2))
        return 0

    _job_table(rows)
    console.print(f"[dim]{len(rows)} row(s)[/]")
    return 0


def cmd_score(args) -> int:
    count = scoring.score_jobs(rescore=args.rescore, limit=args.limit)
    console.print(f"scored {count} posting(s)")
    if count:
        _job_table(_top_rows(args.show), show_reason=True)
    return 0


def cmd_enrich(args) -> int:
    result = pipeline.enrich_jobs(
        min_chars=args.min_chars, limit=args.limit, min_score=args.min_score
    )
    console.print(
        f"candidates {result['candidates']}  [bold]updated {result['updated']}[/]  "
        f"skipped {result['skipped']}"
    )
    for err in result["errors"][:8]:
        console.print(f"  [yellow]! {err}[/]")
    return 0


def cmd_analyze(args) -> int:
    profile = config.profile()
    conn = db.connect()
    sql = "SELECT * FROM jobs WHERE length(description) > 300"
    params: list = []
    if args.min_score:
        sql += " AND COALESCE(score, -1) >= ?"
        params.append(args.min_score)
    if args.search:
        sql += " AND (title LIKE ? OR company LIKE ?)"
        params.extend([f"%{args.search}%"] * 2)
    sql += " ORDER BY COALESCE(score, -1) DESC LIMIT ?"
    params.append(args.limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    if not rows:
        console.print("[yellow]belum ada JD lengkap — jalankan `python -m jobhunter enrich` dulu[/]")
        conn.close()
        return 0

    console.print(f"[dim]engine: {'llm' if analysis.has_llm() else 'heuristic'} | {len(rows)} lowongan[/]")
    for row in rows:
        result = analysis.analyze(row, profile)
        db.save_analysis(conn, row["id"], result)
        colour = "green" if result["fit"] >= 75 else "yellow" if result["fit"] >= 55 else "red"
        console.print(
            f"[{colour}]{result['fit']:>3}[/] {_short(row['title'], 54)} "
            f"[dim]@ {_short(row['company'], 20)} | skor {row['score']}[/]"
        )
        console.print(f"     {result['verdict']}")
        for gap in result["gaps"][:3]:
            console.print(f"     [red]- {gap}[/]")
        for strength in result["strengths"][:2]:
            console.print(f"     [green]+ {strength}[/]")
        console.print(f"     [dim]id: {row['id']}[/]")
    conn.close()
    return 0


def cmd_letter(args) -> int:
    conn = db.connect()
    row = conn.execute("SELECT * FROM jobs WHERE id LIKE ?", (f"{args.job_id}%",)).fetchone()
    conn.close()
    if row is None:
        console.print("[red]tidak ada lowongan dengan id itu[/]")
        return 1

    job = dict(row)
    if len(job.get("description") or "") < 300:
        console.print("[yellow]JD masih pendek — jalankan `python -m jobhunter enrich` dulu[/]")

    profile = config.profile()
    result = analysis.analyze(job, profile)
    text, engine = cover_letter.build(job, profile, result)

    console.print(
        f"[bold]{job['title']}[/] @ {job['company']}  "
        f"[dim]fit={result['fit']} engine={engine}[/]"
    )
    console.print("")
    console.print(text)

    if not args.no_save:
        out_dir = config.DATA_DIR / "letters"
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", (job["company"] + "-" + job["title"]).lower()).strip("-")[:60]
        path = out_dir / f"{job['id'][:8]}-{slug}.md"
        path.write_text(
            f"# {job['title']} — {job['company']}\n\n{job['url']}\n\n{text}\n",
            encoding="utf-8",
        )
        console.print("")
        console.print(f"[dim]disimpan: {path}[/]")
    return 0


def cmd_digest(args) -> int:
    path = daily_digest.write(limit=args.limit, min_fit=args.min_fit, open_after=args.open)
    console.print(f"[bold]digest[/] {path}")
    if not args.open:
        console.print(f"[dim]buka di browser: {path.as_uri()}[/]")
    if args.email:
        status = daily_digest.email_html(
            path.read_text(encoding="utf-8"),
            f"Lowongan buat Kevin - {path.stem.replace('digest-', '')}",
        )
        console.print(f"[bold]email[/] {status}")
    return 0


def cmd_toast(args) -> int:
    conn = db.connect()
    rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT j.id, j.title, j.company, j.score, a.fit
            FROM jobs j LEFT JOIN analyses a ON a.job_id = j.id
            WHERE j.status = 'new' AND COALESCE(a.fit, j.score, 0) >= ?
            ORDER BY COALESCE(a.fit, j.score, 0) DESC
            LIMIT ?
            """,
            (args.min_fit, args.limit),
        )
    ]
    conn.close()

    ok, message, engine = windows_toast.show(
        "Job Hunter", windows_toast.shortlist_lines(rows), mode=args.mode
    )
    console.print(("[green]ok[/] " if ok else "[red]gagal[/] ") + f"[{engine}] {message}")
    return 0 if ok else 1


def cmd_discord(args) -> int:
    conn = db.connect()
    sql = """
        SELECT j.*, a.fit, a.verdict, a.gaps, a.strengths
        FROM jobs j LEFT JOIN analyses a ON a.job_id = j.id
        WHERE j.status IN ('new', 'shortlist') AND COALESCE(a.fit, j.score, 0) >= ?
    """
    params: list = [args.min_fit]
    if args.only_new:
        sql += " AND j.id NOT IN (SELECT job_id FROM deliveries WHERE channel = 'discord')"
    sql += " ORDER BY COALESCE(a.fit, j.score, 0) DESC, j.score DESC LIMIT ?"
    params.append(args.limit)
    rows = [dict(r) for r in conn.execute(sql, params)]

    payload = discord.build_payload(rows, args.min_fit)
    thread_name = f"Lowongan {datetime.now():%d %b}" if args.thread else None
    attachments = discord.letter_files(rows, limit=5) if args.attach_letters else []

    if args.dry_run:
        if args.per_job:
            for row in rows[: args.limit]:
                console.print(discord.preview(discord.build_single(row)))
                console.print("")
        else:
            console.print(discord.preview(discord.build_payload(rows, args.min_fit)))
        if thread_name:
            console.print(f"[dim]thread: {thread_name}[/]")
        for name, data in attachments:
            console.print(f"[dim]lampiran: {name} ({len(data)} bytes)[/]")
        console.print("[dim]dry run: tidak dikirim[/]")
        conn.close()
        return 0

    if not rows:
        console.print("[dim]tidak ada lowongan baru untuk dikirim[/]")
        conn.close()
        return 0

    if args.per_job:
        # One message per job: a reaction then maps to exactly one posting.
        sent = 0
        for row in rows:
            payload = discord.build_single(row)
            files = discord.letter_files([row], limit=1) if args.attach_letters else []
            ok, message, message_id = discord.send(payload, attachments=files)
            if ok:
                db.record_deliveries(conn, [row["id"]], "discord", message_id)
                sent += 1
                console.print(f"  [green]ok[/] {_short(row['title'], 44)} [dim]{message}[/]")
            else:
                console.print(f"  [red]x[/] {_short(row['title'], 44)} {message}")
            time.sleep(1.2)  # stay well under the 30/min webhook limit
        console.print(f"terkirim {sent}/{len(rows)} pesan")
        conn.close()
        return 0 if sent else 1

    payload = discord.build_payload(rows, args.min_fit)
    ok, message, _message_id = discord.send(payload, thread_name=thread_name, attachments=attachments)
    console.print(("[green]ok[/] " if ok else "[red]gagal[/] ") + message)
    if ok:
        db.record_deliveries(conn, [row["id"] for row in rows], "discord")
    conn.close()
    return 0 if ok else 1


def cmd_sync(args) -> int:
    result = discord_sync.sync(limit=args.limit, dry_run=args.dry_run)
    if not result["ok"]:
        console.print(f"[red]gagal[/] {result['error']}")
        return 1
    if not result["changed"]:
        console.print("[dim]tidak ada reaksi yang mengubah status[/]")
    for job_id, title, status in result["changed"]:
        console.print(f"  [green]{status:<10}[/] {_short(title, 48)} [dim]({job_id[:8]})[/]")
    console.print(f"[dim]memindai {result['scanned']} pesan | {discord_sync.legend()}[/]")
    return 0


def cmd_clean(args) -> int:
    """Delete stored postings that no longer pass filters.yaml."""
    from .model import Job

    flt = config.filters()
    conn = db.connect()
    # Never delete something the user already acted on: applied/interview rows
    # are history, not candidates.
    rows = [
        dict(r)
        for r in conn.execute("SELECT * FROM jobs WHERE status IN ('new', 'shortlist')")
    ]

    victims = []
    for row in rows:
        job = Job(
            source=row["source"],
            company=row["company"],
            title=row["title"],
            url=row["url"],
            location=row["location"] or "",
            remote=bool(row["remote"]),
            salary=row["salary"] or "",
            department=row["department"] or "",
            description=row["description"] or "",
            posted_at=row["posted_at"] or "",
        )
        if not pipeline.passes_filters(job, flt):
            victims.append(row)

    if not victims:
        console.print("database sudah bersih, tidak ada yang melanggar filter")
        conn.close()
        return 0

    for row in victims[:15]:
        console.print(f"  [red]x[/] {(row['company'] or '-')[:28]:<30} {_short(row['title'], 46)}")
    if len(victims) > 15:
        console.print(f"  [dim]... dan {len(victims) - 15} lainnya[/]")
    console.print(f"[bold]{len(victims)}[/] lowongan tidak lolos filter")

    if args.dry_run:
        console.print("[dim]dry run: tidak ada yang dihapus[/]")
        conn.close()
        return 0

    ids = [(row["id"],) for row in victims]
    conn.executemany("DELETE FROM jobs WHERE id = ?", ids)
    conn.executemany("DELETE FROM analyses WHERE job_id = ?", ids)
    conn.executemany("DELETE FROM deliveries WHERE job_id = ?", ids)
    conn.commit()
    left = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    console.print(f"dihapus. sisa [bold]{left}[/] lowongan")
    return 0


def cmd_stats(_args) -> int:
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    console.print(f"[bold]total postings:[/] {total}")
    for label, sql in (
        ("by source", "SELECT source, COUNT(*) c FROM jobs GROUP BY source ORDER BY c DESC"),
        ("by status", "SELECT status, COUNT(*) c FROM jobs GROUP BY status ORDER BY c DESC"),
        ("top companies", "SELECT company, COUNT(*) c FROM jobs GROUP BY company ORDER BY c DESC LIMIT 8"),
    ):
        console.print(f"[bold]{label}[/]")
        for r in conn.execute(sql).fetchall():
            console.print(f"  {(r[0] or '-'):<24} {r[1]}")
    last = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    if last:
        console.print(
            f"[dim]last run {last['started_at']} fetched={last['fetched']} "
            f"inserted={last['inserted']} kept={last['kept']}[/]"
        )
    conn.close()
    return 0


def cmd_status(args) -> int:
    conn = db.connect()
    cur = conn.execute("UPDATE jobs SET status=? WHERE id LIKE ?", (args.value, f"{args.job_id}%"))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        console.print("[red]no job matched that id[/]")
        return 1
    console.print(f"updated {cur.rowcount} row(s) -> {args.value}")
    return 0


def cmd_probe(args) -> int:
    cfg = config.companies()
    sources = args.source or [s for s in BOARD_SOURCES if cfg.get(s)]
    for name in sources:
        tokens = cfg.get(name) or []
        console.print(f"[bold]{name}[/] ({len(tokens)} candidate board(s))")
        for token in tokens:
            try:
                jobs = ADAPTERS[name](token)
                if jobs:
                    console.print(f"  [green]OK[/]    {token:<22} {len(jobs)} job(s)")
                else:
                    console.print(f"  [yellow]EMPTY[/] {token}")
            except Exception as exc:
                console.print(f"  [red]DEAD[/]  {token:<22} {type(exc).__name__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobhunter", description="Aggregate and shortlist job postings.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("discover", help="pull boards, filter, dedupe, score, store")
    p.add_argument("--source", action="append", choices=sorted(ADAPTERS), help="limit to one source (repeatable)")
    p.add_argument("--full", action="store_true", help="also download job descriptions")
    p.add_argument("--no-filter", action="store_true", help="store everything, skip filters.yaml")
    p.add_argument("--dry-run", action="store_true", help="show ranked results without writing")
    p.add_argument("--per-board", type=int, default=40, help="cap jobs taken per board")
    p.add_argument("--limit", type=int, default=0, help="cap total stored per run")
    p.add_argument("--show", type=int, default=12, help="rows to print")
    p.set_defaults(func=cmd_discover)

    p = sub.add_parser("list", help="show stored postings, best first")
    p.add_argument("--status", default="")
    p.add_argument("--search", default="")
    p.add_argument("--min-score", type=int, default=0)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("score", help="(re)score stored postings")
    p.add_argument("--rescore", action="store_true", help="recompute even when a score exists")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--show", type=int, default=12)
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("enrich", help="download full job descriptions for shortlisted postings")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--min-score", type=int, default=0)
    p.add_argument("--min-chars", type=int, default=300)
    p.set_defaults(func=cmd_enrich)

    p = sub.add_parser("analyze", help="compare each JD against your profile (gap analysis)")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--min-score", type=int, default=0)
    p.add_argument("--search", default="")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("letter", help="draft a tailored cover letter for one posting")
    p.add_argument("job_id")
    p.add_argument("--no-save", action="store_true")
    p.set_defaults(func=cmd_letter)

    p = sub.add_parser("digest", help="build today's shortlist as a local HTML page")
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--min-fit", type=int, default=55)
    p.add_argument("--open", action="store_true", help="open it in the default browser")
    p.add_argument("--email", action="store_true", help="also send it through SMTP")
    p.set_defaults(func=cmd_digest)

    p = sub.add_parser("toast", help="pop a Windows notification with today's top picks")
    p.add_argument("--min-fit", type=int, default=75)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--mode", choices=["auto", "toast", "balloon"], default="auto")
    p.set_defaults(func=cmd_toast)

    p = sub.add_parser("discord", help="post today's shortlist to a Discord webhook")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--min-fit", type=int, default=55)
    p.add_argument("--only-new", action="store_true", help="skip jobs already posted to Discord")
    p.add_argument("--per-job", action="store_true", help="one message per job, so reactions map 1:1")
    p.add_argument("--thread", action="store_true", help="post inside a new thread named for today")
    p.add_argument("--attach-letters", action="store_true", help="attach generated cover letters")
    p.add_argument("--dry-run", action="store_true", help="print the payload instead of sending")
    p.set_defaults(func=cmd_discord)

    p = sub.add_parser("sync", help="apply Discord reactions to job statuses")
    p.add_argument("--limit", type=int, default=50, help="how many recent messages to scan")
    p.add_argument("--dry-run", action="store_true", help="show changes without writing")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("clean", help="delete stored postings that violate current filters")
    p.add_argument("--dry-run", action="store_true", help="list them without deleting")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("stats", help="database summary")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("status", help="move a posting through the pipeline")
    p.add_argument("job_id")
    p.add_argument("value", choices=["new", "shortlist", "applied", "interview", "offer", "rejected", "skipped"])
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("probe", help="find out which candidate boards actually exist")
    p.add_argument("--source", action="append", choices=sorted(BOARD_SOURCES))
    p.set_defaults(func=cmd_probe)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
