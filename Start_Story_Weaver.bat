@echo off
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
:: We use the absolute path to Node.js since it was missing from your system PATH
start "Gemini-Nokey Proxy" cmd /k "title Gemini-Nokey Proxy && cd /d C:\Users\suraj\Documents\gemini-nokey && C:\Users\suraj\Documents\node-v22.16.0-win-x64\node.exe node.mjs --host 0.0.0.0 --port 8080"
echo   - Proxy launched in a new window on port 8080.
echo.

echo [3/4] Starting Story Weaver Backend...
start "Story Weaver Server" cmd /k "title Story Weaver Backend && cd /d C:\Users\suraj\AppData\Local\Packages\1527c705-839a-4832-9118-54d4Bd6a0c89_cw5n1h2txyewy\LocalState\story-weaver && python main.py"
echo   - Backend launched in a new window on port 8000.
echo.

echo [4/4] Everything is ready!
echo You can now use the Story Weaver app. If you close the terminal windows that popped up, the servers will shut down.
echo.
pause
