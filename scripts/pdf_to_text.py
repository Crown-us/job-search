"""Dump text from PDFs to data/cv_text/*.txt and report how much came out."""

from __future__ import annotations

import pathlib
import re
import sys

from pypdf import PdfReader

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "cv_text"


def clean(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main(paths: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for raw in paths:
        src = pathlib.Path(raw)
        try:
            reader = PdfReader(str(src))
            pages = [(page.extract_text() or "") for page in reader.pages]
        except Exception as exc:
            print(f"FAIL {src.name}: {type(exc).__name__}: {exc}")
            continue
        text = clean("\n\n".join(pages))
        out = OUT / (src.stem + ".txt")
        out.write_text(text, encoding="utf-8")
        density = len(text) / max(1, len(reader.pages))
        flag = "TEXT" if density > 200 else "IMAGE?"
        print(f"{flag:6} {src.name[:52]:<52} pages={len(reader.pages)} chars={len(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
