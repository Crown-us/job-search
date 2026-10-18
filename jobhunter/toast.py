"""Windows desktop notifications, two engines.

toast   — Windows.UI.Notifications, the real Windows 10/11 toast. Needs an
          AppUserModelID that Windows recognises. Unpackaged processes get
          "no package identity (0x80073D54)" unless the ID is registered in
          HKCU\\SOFTWARE\\Classes\\AppUserModelId.
balloon — System.Windows.Forms.NotifyIcon balloon. Older look, but works from
          any process with no registration at all.

`show()` tries toast first and falls back to balloon, so the command works
whether or not the AppID has been registered.

WinRT projections live in Windows PowerShell 5.1, not PowerShell 7, so both
engines run in a child `powershell.exe`. Results go to files: piped grandchild
stdio is not allowed in this sandbox.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from xml.sax.saxutils import escape

from . import config

APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"


def _app_id() -> str:
    """Allow a registered custom AppID: set TOAST_APP_ID in .env."""
    return (config.env().get("TOAST_APP_ID") or "").strip() or APP_ID

TOAST_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null

    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml((Get-Content -Raw -LiteralPath '__XML_PATH__'))

    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('__APP_ID__')
    $notifier.Show($toast)
    Write-Output 'SHOWN'
}
catch {
    Write-Output ('FAILED ' + $_.Exception.GetType().FullName + ': ' + $_.Exception.Message)
    if ($_.Exception.InnerException) { Write-Output ('INNER ' + $_.Exception.InnerException.Message) }
}
"""

BALLOON_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing

    $payload = Get-Content -Raw -LiteralPath '__PAYLOAD__' | ConvertFrom-Json
    $icon = New-Object System.Windows.Forms.NotifyIcon
    $icon.Icon = [System.Drawing.SystemIcons]::Information
    $icon.Visible = $true
    $icon.ShowBalloonTip(10000, [string]$payload.title, [string]$payload.body,
                         [System.Windows.Forms.ToolTipIcon]::Info)
    Start-Sleep -Seconds 4
    $icon.Dispose()
    Write-Output 'SHOWN'
}
catch {
    Write-Output ('FAILED ' + $_.Exception.GetType().FullName + ': ' + $_.Exception.Message)
}
"""


def build_xml(title: str, lines: list[str]) -> str:
    body = "".join(f"<text>{escape(line)}</text>" for line in lines[:3])
    return (
        '<toast scenario="reminder">'
        '<visual><binding template="ToastGeneric">'
        f"<text>{escape(title)}</text>{body}"
        "</binding></visual>"
        '<audio src="ms-winsoundevent:Notification.Default"/>'
        "</toast>"
    )


def _run(script: str, workdir, timeout: int) -> tuple[bool, str]:
    """Run a PowerShell 5.1 script body and read SHOWN / FAILED from stdout."""
    out_path = workdir / "out.txt"
    err_path = workdir / "err.txt"
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        with open(out_path, "w", encoding="utf-8") as out, open(err_path, "w", encoding="utf-8") as err:
            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-OutputFormat", "Text",
                    "-ExecutionPolicy", "Bypass",
                    "-EncodedCommand", encoded,
                ],
                stdout=out,
                stderr=err,
                timeout=timeout,
            )
    except FileNotFoundError:
        return False, "powershell.exe tidak ditemukan"
    except subprocess.TimeoutExpired:
        return False, "powershell.exe timeout"

    stdout = out_path.read_text(encoding="utf-8", errors="replace")
    if "SHOWN" in stdout:
        return True, ""
    for line in stdout.splitlines():
        if line.startswith(("FAILED", "INNER")):
            return False, line[:220]
    stderr = err_path.read_text(encoding="utf-8", errors="replace").strip()
    return False, (stderr.splitlines()[-1][:200] if stderr else f"exit {proc.returncode}")


def _workdir() -> "object":
    # The system temp folder is partly read-only inside the sandbox; the workspace is not.
    path = config.DATA_DIR / "tmp" / f"notify-{int(time.time() * 1000)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def show(title: str, lines: list[str], mode: str = "auto", timeout: int = 30) -> tuple[bool, str, str]:
    """Fire a notification. Returns (ok, detail, engine_used)."""
    if os.name != "nt":
        return False, "notifikasi hanya tersedia di Windows", "none"

    workdir = _workdir()
    xml_path = workdir / "toast.xml"
    payload_path = workdir / "payload.json"
    xml_path.write_text(build_xml(title, lines), encoding="utf-8")
    payload_path.write_text(
        json.dumps({"title": title, "body": " | ".join(lines[:2])}), encoding="utf-8"
    )

    toast_error = ""
    if mode in ("auto", "toast"):
        ok, detail = _run(
            TOAST_SCRIPT.replace("__XML_PATH__", str(xml_path)).replace("__APP_ID__", _app_id()),
            workdir,
            timeout,
        )
        if ok:
            return True, "toast native tampil", "toast"
        toast_error = detail
        if mode == "toast":
            return False, detail, "toast"

    ok, detail = _run(
        BALLOON_SCRIPT.replace("__PAYLOAD__", str(payload_path)), workdir, timeout
    )
    if ok:
        note = "balloon tampil"
        if toast_error:
            note += f" (toast ditolak: {toast_error[:90]})"
        return True, note, "balloon"
    return False, f"toast: {toast_error or 'skip'} | balloon: {detail}", "none"


def shortlist_lines(rows: list[dict]) -> list[str]:
    if not rows:
        return ["Belum ada lowongan baru di atas ambang."]
    lines = [f"{len(rows)} lowongan layak dilihat"]
    for row in rows[:2]:
        fit = row.get("fit")
        fit_text = f"fit {fit}" if fit is not None else f"skor {row.get('score')}"
        lines.append(f"{row['title'][:44]} - {row['company'][:22]} ({fit_text})")
    return lines
