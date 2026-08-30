@echo off
setlocal
set "APP_DIR=%~dp0"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

echo ===================================================
echo     Story Weaver Startup Script
echo ===================================================
echo.

echo [1/3] Checking for existing servers to prevent conflicts...
echo   - Closing previous Story Weaver window, if it is already running...
taskkill /F /FI "WINDOWTITLE eq Story Weaver Backend" /T >nul 2>&1
echo   - Waiting 2 seconds for ports to fully release...
timeout /t 2 >nul
echo.

echo [2/3] Starting Story Weaver Backend...
if exist "%VENV_PY%" (
    echo   - Using virtual environment: %VENV_PY%
    start "Story Weaver Backend" cmd /k "title Story Weaver Backend && cd /d ""%APP_DIR%"" && ""%VENV_PY%"" main.py"
) else (
    echo   - Virtual environment not found - falling back to system Python.
    echo     Run: uv venv .venv ^&^& uv pip install -r requirements.txt
    start "Story Weaver Backend" cmd /k "title Story Weaver Backend && cd /d ""%APP_DIR%"" && python main.py"
)
echo   - Backend launched in a new window on port 8000.
echo.

echo [3/3] Everything is ready!
echo Open http://127.0.0.1:8000 in your browser and sign in with Google.
echo If you close the terminal window that popped up, the server will shut down.
echo.
pause