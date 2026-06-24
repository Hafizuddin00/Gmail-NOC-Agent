@echo off
:: ============================================================
:: status_agent.bat — Check if the Gmail NOC Agent is running
::                    and tail the latest log entries.
:: ============================================================

setlocal

set "ROOT=%~dp0..\.."
set "PID_FILE=%ROOT%\agent.pid"
set "LOG_FILE=%ROOT%\logs\agent.log"

echo ============================================================
echo  Gmail NOC Agent — Status
echo ============================================================

:: ── Check PID file ─────────────────────────────────────────────
if not exist "%PID_FILE%" (
    echo  Status : STOPPED ^(no PID file found^)
) else (
    set /p PID=<"%PID_FILE%"
    :: Check if the PID is actually alive
    tasklist /FI "PID eq %PID%" 2>nul | find "%PID%" >nul
    if %errorlevel% == 0 (
        echo  Status : RUNNING
        echo  PID    : %PID%
    ) else (
        echo  Status : STOPPED ^(stale PID file — process not found^)
        echo  Run stop_agent.bat to clean up.
    )
)

echo.
echo ── Last 30 log lines ────────────────────────────────────────

if not exist "%LOG_FILE%" (
    echo  ^(log file not found yet^)
) else (
    powershell -Command "Get-Content '%LOG_FILE%' -Tail 30"
)

echo.
echo ── Commands ─────────────────────────────────────────────────
echo   start_agent.bat        Start the agent in background
echo   stop_agent.bat         Stop the running agent
echo   status_agent.bat       Show this status screen
echo   tail_log.bat           Live-tail the log file
echo ============================================================

endlocal
