@echo off
:: ============================================================
:: start_agent.bat — Launch Gmail NOC Agent in the background
:: The process survives terminal/window closure.
:: ============================================================

setlocal

:: ── Resolve project root (same folder as this script) ─────────
set "ROOT=%~dp0..\.."
set "VENV_PYTHON=%ROOT%\venv\Scripts\pythonw.exe"
set "MAIN=%ROOT%\main.py"
set "PID_FILE=%ROOT%\agent.pid"
set "LOG_FILE=%ROOT%\logs\agent.log"

:: ── Guard: already running? ────────────────────────────────────
if exist "%PID_FILE%" (
    set /p EXISTING_PID=<"%PID_FILE%"
    echo [!] Agent may already be running with PID %EXISTING_PID%.
    echo     Check logs\agent.log or run stop_agent.bat first.
    pause
    exit /b 1
)

:: ── Create logs directory if missing ──────────────────────────
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"

:: ── Check pythonw exists ───────────────────────────────────────
if not exist "%VENV_PYTHON%" (
    echo [ERROR] pythonw.exe not found at:
    echo         %VENV_PYTHON%
    echo         Make sure the virtual environment is set up.
    pause
    exit /b 1
)

:: ── Launch detached (START /B with pythonw hides the window) ──
echo [*] Starting Gmail NOC Agent in background...
echo     Python : %VENV_PYTHON%
echo     Script : %MAIN%
echo     Log    : %LOG_FILE%
echo.

:: pythonw.exe has no console window; stdout/stderr still go to
:: the log file via Python's logging module.
start "" /B "%VENV_PYTHON%" "%MAIN%"

:: Give the process a moment to write its PID file
timeout /t 3 /nobreak >nul

if exist "%PID_FILE%" (
    set /p NEW_PID=<"%PID_FILE%"
    echo [OK] Agent started successfully ^(PID: %NEW_PID%^)
    echo      Tail logs with:  powershell Get-Content logs\agent.log -Wait
) else (
    echo [WARN] PID file not found yet — agent may still be initialising.
    echo        Check logs\agent.log for startup errors.
)

endlocal
