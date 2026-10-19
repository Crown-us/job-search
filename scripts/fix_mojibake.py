"""Repair UTF-8 text mangled by PowerShell's default encoding.

Reading a UTF-8 file and writing it back with `Set-Content -Encoding utf8`
double-encodes non-ASCII characters. Keys are escape sequences, so this file
never matches itself when it processes its own source.

Run: python scripts/fix_mojibake.py
"""

from __future__ import annotations

import pathlib

REPLACEMENTS = {
    "\u00e2\u2030\u00a5": "\u2265",
    "\u00e2\u20ac\u201d": "\u2014",
    "\u00e2\u20ac\u201c": "\u2013",
    "\u00c2\u00b7": "\u00b7",
    "\u00e2\u0153\u2026": "\u2705",
    "\u00f0\u0178\u201d\u2013": "\U0001f516",
    "\u00e2\u0152": "\u274c",
    "\u00f0\u0178\u201c\u2026": "\U0001f4c5",
    "\u00f0\u0178\u2020": "\U0001f3c6",
    "\u00e2\u2020\u2019": "\u2192",
    "\u00e2\u20ac\u2122": "\u2019",
}

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGETS = (
    list(ROOT.glob("jobhunter/**/*.py"))
    + list(ROOT.glob("scripts/*.py"))
    + [ROOT / "README.md", ROOT / "daily.cmd"]
)


def main() -> int:
    changed = 0
    for path in TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        for bad, good in REPLACEMENTS.items():
            text = text.replace(bad, good)
        if text != original:
            path.write_text(text, encoding="utf-8")
            changed += 1
            print(f"fixed {path.relative_to(ROOT)}")
    print(f"{changed} file diperbaiki")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
