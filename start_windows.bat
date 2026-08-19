@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/4] Checking Python...
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 is not installed. Install it from https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  set "PYTHON=python"
) else (
  set "PYTHON=py -3"
)

if not exist ".venv\Scripts\python.exe" (
  echo [2/4] Creating virtual environment...
  %PYTHON% -m venv .venv
  if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
echo [3/4] Installing/updating dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo .env was created from .env.example.
  echo Open .env and fill BOT_TOKEN and OWNER_ID, then run this file again.
  notepad .env
  pause
  exit /b 0
)

echo [4/4] Starting Shihab bot...
:restart
python bot.py
set "STATUS=%ERRORLEVEL%"
if "%STATUS%"=="0" exit /b 0
echo The bot stopped with code %STATUS%. Retrying in 5 seconds...
timeout /t 5 /nobreak >nul
goto restart

:error
echo Installation failed. Check the message above.
pause
exit /b 1
