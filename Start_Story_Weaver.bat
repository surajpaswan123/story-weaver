@echo off
setlocal
set "APP_DIR=%~dp0"
set "PROXY_DIR=%USERPROFILE%\Documents\gemini-nokey"
set "NODE_EXE=%USERPROFILE%\Documents\node-v22.16.0-win-x64\node.exe"
if not exist "%NODE_EXE%" set "NODE_EXE=node"

echo ===================================================
echo     Story Weaver & AI Proxy Startup Script
echo ===================================================
echo.

echo [1/4] Checking for existing servers to prevent conflicts...
echo   - Closing previous Story Weaver window, if it is already running...
taskkill /F /FI "WINDOWTITLE eq Story Weaver Backend" /T >nul 2>&1
echo   - Closing previous Gemini-Nokey window, if it is already running...
taskkill /F /FI "WINDOWTITLE eq Gemini-Nokey Proxy" /T >nul 2>&1
echo   - Waiting 2 seconds for ports to fully release...
timeout /t 2 >nul
echo.

echo [2/4] Starting Gemini-Nokey Local AI Proxy...
if exist "%PROXY_DIR%\node.mjs" (
    start "Gemini-Nokey Proxy" cmd /k "title Gemini-Nokey Proxy && cd /d ""%PROXY_DIR%"" && ""%NODE_EXE%"" node.mjs --host 127.0.0.1 --port 8080"
    echo   - Proxy launched locally on 127.0.0.1:8080.
) else (
    echo   - Proxy not found at "%PROXY_DIR%"; continuing without it.
)
echo.

echo [3/4] Starting Story Weaver Backend...
start "Story Weaver Server" cmd /k "title Story Weaver Backend && cd /d ""%APP_DIR%"" && python main.py"
echo   - Backend launched in a new window on port 8000.
echo.

echo [4/4] Everything is ready!
echo You can now use the Story Weaver app. If you close the terminal windows that popped up, the servers will shut down.
echo.
pause
