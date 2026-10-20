"""Exercise the slash-command handler without Discord."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunter import bot


def main() -> int:
    for keyword, extra in [("laravel", {}), ("desain", {}), ("python", {"remote": True}), ("zzzz", {})]:
        data = {
            "name": "cari",
            "options": [{"name": "kata", "value": keyword}, *[
                {"name": k, "value": v} for k, v in extra.items()
            ]],
        }
        payload = bot.handle_command(data)
        content = payload.get("content", "").encode("ascii", "replace").decode("ascii")
        embeds = payload.get("embeds") or []
        print(f"/cari {keyword} {extra} -> {content!r} | {len(embeds)} embed")
        for embed in embeds[:2]:
            title = (embed.get("title") or "").encode("ascii", "replace").decode("ascii")
            desc = (embed.get("description") or "").replace("\n", " | ")
            desc = desc.encode("ascii", "replace").decode("ascii")
            print(f"    {title} :: {desc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
