# Pipeline harian untuk Windows Task Scheduler: menjalankan scripts/daily.sh
# lewat Git Bash dengan venv Windows, supaya langkahnya sama persis dengan Linux
# (verify, site, publish gh-pages, Discord, sync).
# Output masuk ke data\logs\daily-YYYY-MM-DD.log.
# Dilewati kalau digest hari ini sudah ada (mis. timer Linux sudah jalan pagi ini);
# pakai -Force untuk tetap menjalankan.
param([switch]$Force)

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$today = Get-Date -Format 'yyyy-MM-dd'
$logDir = Join-Path $root 'data\logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir "daily-$today.log"

if (-not $Force -and (Test-Path (Join-Path $root "data\digest\digest-$today.html"))) {
    Add-Content -Encoding utf8 $log "==== $(Get-Date -Format s) dilewati: digest hari ini sudah ada ===="
    exit 0
}

$bash = 'C:\Program Files\Git\bin\bash.exe'
$py = Join-Path $env:USERPROFILE '.venvs\jobhunter\Scripts\python.exe'
foreach ($p in $bash, $py) {
    if (-not (Test-Path $p)) {
        Add-Content -Encoding utf8 $log "==== $(Get-Date -Format s) gagal: tidak ketemu $p ===="
        exit 1
    }
}

# Repo ini dimiliki user lain (partisi dipakai bareng Linux), jadi git butuh
# safe.directory; diset per-proses agar config global tidak disentuh.
$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'
$env:GIT_CONFIG_VALUE_0 = ($root -replace '\\', '/')
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PY = $py

Add-Content -Encoding utf8 $log "==== mulai $(Get-Date -Format s) ===="
& $bash -c 'scripts/daily.sh >> "$1" 2>&1' _ ($log -replace '\\', '/')
$code = $LASTEXITCODE
Add-Content -Encoding utf8 $log "==== selesai $(Get-Date -Format s) (exit $code) ===="
exit $code
