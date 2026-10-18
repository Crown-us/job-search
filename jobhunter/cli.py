"""Command line entry point: python -m jobhunter <command>."""

from __future__ import annotations

import argparse
import json
import re
import sys

from rich.console import Console
from rich.table import Table

from . import config, db, pipeline
from . import analyze as analysis
from . import digest as daily_digest
from . import letter as cover_letter
from . import score as scoring
from .sources import ADAPTERS, BOARD_SOURCES

console = Console() if sys.stdout.isatty() else Console(width=110)

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
