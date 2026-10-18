"""Fetch a pure-python wheel from PyPI and unpack it, bypassing pip.

pip cannot write its own temp metadata inside this sandbox, so we download the
wheel with urllib (which works) and treat it as the plain zip it is.
"""

from __future__ import annotations

import io
import json
import pathlib
import sys
import urllib.request
import zipfile

DEST = pathlib.Path(__file__).resolve().parent.parent / ".pylibs"


def fetch_wheel(package: str) -> str:
    meta = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{package}/json", timeout=30))
    wheels = [u for u in meta["urls"] if u["filename"].endswith("-py3-none-any.whl")]
    if not wheels:
        wheels = [u for u in meta["urls"] if u["filename"].endswith(".whl")]
    wheel = max(wheels, key=lambda u: u["upload_time"])
    data = urllib.request.urlopen(wheel["url"], timeout=90).read()
    zipfile.ZipFile(io.BytesIO(data)).extractall(DEST)
    return wheel["filename"]


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    for package in sys.argv[1:] or ["pypdf"]:
        print("unpacked", fetch_wheel(package), "->", DEST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
