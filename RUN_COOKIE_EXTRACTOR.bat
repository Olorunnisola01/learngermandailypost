@echo off
echo === German Quiz Cookie Extractor ===
echo.

echo [1] Killing any open Chrome windows...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 3 /nobreak >nul

echo [2] Removing stale lock files...
del /F /Q "%LOCALAPPDATA%\Google\Chrome\User Data\SingletonLock" 2>nul
del /F /Q "%LOCALAPPDATA%\Google\Chrome\User Data\SingletonSocket" 2>nul
del /F /Q "%LOCALAPPDATA%\Google\Chrome\User Data\SingletonCookie" 2>nul
del /F /Q "%LOCALAPPDATA%\Google\Chrome\User Data\Profile 12\LOCK" 2>nul

echo [3] Starting Chrome with remote debugging on port 9222...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --remote-allow-origins=* ^
  --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" ^
  --profile-directory="Profile 12" ^
  --no-first-run ^
  --no-default-browser-check ^
  https://www.youtube.com

echo [4] Waiting 12 seconds for Chrome to fully load...
timeout /t 12 /nobreak

echo [5] Running cookie extraction and pushing to GitHub...
cd /d "%~dp0"
python extract_cookies_simple.py

echo.
echo === Done! You can close this window and re-open Chrome normally ===
pause
