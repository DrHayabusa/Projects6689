@echo off
REM ASSISTRAN - one-command run for Windows (cmd.exe or double-click).
REM Installs deps, builds frontend + backend, then starts a single server
REM that serves BOTH the UI and the API on one port.
REM
REM Override defaults before running, e.g.:
REM   set PORT=3000
REM   set OLLAMA_URL=http://192.168.1.50:11434
REM   run.cmd
setlocal

if not defined OLLAMA_URL set "OLLAMA_URL=http://127.0.0.1:11434"
if not defined MODEL_NAME set "MODEL_NAME=qwen2.5-coder:32b"
if not defined PORT set "PORT=8080"

cd /d "%~dp0"

echo Installing dependencies...
call npm install || goto :err

echo Building frontend + backend...
call npm run build || goto :err

echo.
echo ============================================================
echo   ASSISTRAN is starting on a single port.
echo   OLLAMA_URL = %OLLAMA_URL%
echo   MODEL_NAME = %MODEL_NAME%
echo.
echo   Open this link in Chrome or Edge:
echo       http://localhost:%PORT%
echo ============================================================
echo.

call npm run start
goto :eof

:err
echo.
echo Build failed - see the output above.
exit /b 1
