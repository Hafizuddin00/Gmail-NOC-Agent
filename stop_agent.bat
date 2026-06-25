@echo off
:: ============================================================
:: stop_agent.bat — Stop the background Gmail NOC Agent
:: ============================================================

setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PID_FILE=%ROOT%\agent.pid"

if not exist "%PID_FILE%" (
    echo [!] No PID file found — agent is probably not running.
    exit /b 0
)

set /p PID=<"%PID_FILE%"
echo [*] Stopping agent (PID: %PID%)...

:: Terminate the process
taskkill /PID %PID% /F >nul 2>&1

if %errorlevel% == 0 (
    echo [OK] Agent stopped.
) else (
    echo [WARN] Could not kill PID %PID% — it may have already stopped.
)

:: Remove the PID file
del "%PID_FILE%" >nul 2>&1
echo [*] PID file removed.

endlocal
