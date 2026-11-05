@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  start "" http://localhost:8000
  py -3 server.py
) else (
  where python >nul 2>nul
  if %errorlevel% neq 0 (
    echo Python 3 bulunamadi. Python 3.10 veya daha yeni bir surum kurup tekrar dene.
    pause
    exit /b 1
  )
  start "" http://localhost:8000
  python server.py
)
pause
