$ErrorActionPreference = "Stop"

$port = 8080
$root = Split-Path -Parent $PSScriptRoot

Set-Location $root

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python is required. Install from https://www.python.org/downloads/" -ForegroundColor Yellow
  exit 1
}

Write-Host "Starting local server at http://localhost:$port" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray

Start-Process "http://localhost:$port/index.html"
python -m http.server $port
