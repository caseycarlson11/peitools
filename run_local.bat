@echo off
echo ============================================
echo  PEI Tools - Local Dev Server
echo  Open http://localhost:5000 in your browser
echo  Press Ctrl+C to stop
echo ============================================
echo.

cd /d "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com"

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python from https://python.org
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Checking dependencies...
pip install flask pymupdf pytesseract pillow werkzeug --quiet

echo.
echo Starting Flask dev server...
echo.

:: Run Flask in debug mode with auto-reload
set FLASK_ENV=development
set FLASK_DEBUG=1
python app.py
pause
