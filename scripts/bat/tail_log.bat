@echo off
:: ============================================================
:: tail_log.bat — Live-tail logs/agent.log (Ctrl+C to stop)
:: ============================================================

setlocal

set "ROOT=%~dp0..\.."
set "LOG_FILE=%ROOT%\logs\agent.log"

if not exist "%LOG_FILE%" (
    echo [!] Log file not found: %LOG_FILE%
    echo     Start the agent first with start_agent.bat
    pause
    exit /b 1
)

echo [*] Tailing log file ^(Ctrl+C to stop^):
echo     %LOG_FILE%
echo.

powershell -Command "Get-Content '%LOG_FILE%' -Wait -Tail 50"

endlocal
