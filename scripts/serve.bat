@echo off
setlocal
cd /d %~dp0\..

where python >nul 2>nul
if errorlevel 1 (
  echo Python is required. Install from https://www.python.org/downloads/
  exit /b 1
)

set PORT=8080
echo Starting local server at http://localhost:%PORT%
start "" http://localhost:%PORT%/index.html
python -m http.server %PORT%
