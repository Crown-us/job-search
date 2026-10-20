"""Kill every running jobhunter bot process (Windows), as a cleanup."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    killed = 0
    try:
        out = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout
    except Exception as exc:
        print("wmic gagal:", exc)
        out = ""

    for line in out.splitlines():
        if "jobhunter bot" not in line:
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        pid = parts[-1] if parts else ""
        if not pid.isdigit():
            continue
        try:
            os.kill(int(pid), 9)
            killed += 1
            print("killed", pid)
        except OSError as exc:
            print("gagal kill", pid, exc)

    print(f"{killed} proses dihentikan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
