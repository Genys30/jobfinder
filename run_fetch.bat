@echo off
title JobFinder — Fetch Jobs
echo.
echo ===================================
echo  JobFinder — Fetching jobs...
echo ===================================
echo.

:: ── Auto-detect project path ──────────────────────────────────────────────
set "PROJECT_DIR=%USERPROFILE%\Desktop\Projects\jobfinder"

if not exist "%PROJECT_DIR%" (
    echo ERROR: Project folder not found at:
    echo   %PROJECT_DIR%
    echo.
    echo Please edit this .bat file and set PROJECT_DIR to your actual folder path.
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"
echo Project folder: %PROJECT_DIR%
echo.

:: ── Check Git ──────────────────────────────────────────────────────────────
where git >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed or not in PATH.
    echo.
    echo Download and install Git from: https://git-scm.com/download/win
    echo After installing, close and re-open this window.
    pause
    exit /b 1
)

:: ── Check if this is a git repo ───────────────────────────────────────────
if not exist "%PROJECT_DIR%\.git" (
    echo ERROR: The project folder is not a Git repository.
    echo.
    echo Your files were probably copied manually instead of cloned.
    echo To fix this, open Command Prompt and run:
    echo.
    echo   cd /d "%USERPROFILE%\Desktop\Projects"
    echo   git clone https://github.com/Genys30/jobfinder
    echo.
    echo Then move any extra files ^(like LinkedIn CSVs^) into the cloned folder
    echo and run this script again.
    pause
    exit /b 1
)

:: ── Check Python ──────────────────────────────────────────────────────────
where py >nul 2>&1
if errorlevel 1 (
    where python >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python is not installed or not in PATH.
        echo.
        echo Download and install Python from: https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during install.
        pause
        exit /b 1
    )
    set PYTHON_CMD=python
) else (
    set PYTHON_CMD=py
)

:: ── Install missing Python packages ───────────────────────────────────────
echo Checking Python dependencies...
%PYTHON_CMD% -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo   Installing requests...
    %PYTHON_CMD% -m pip install requests --quiet --no-warn-script-location
)
%PYTHON_CMD% -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install 'requests'. Try running as Administrator.
    pause
    exit /b 1
)
%PYTHON_CMD% -c "import bs4" >nul 2>&1
if errorlevel 1 (
    echo   Installing beautifulsoup4...
    %PYTHON_CMD% -m pip install beautifulsoup4 --quiet --no-warn-script-location
)
%PYTHON_CMD% -c "import bs4" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install 'beautifulsoup4'. Try running as Administrator.
    pause
    exit /b 1
)
echo   All dependencies OK.
echo.

:: ── Step 1: Pull ──────────────────────────────────────────────────────────
echo [1/4] Pulling latest from GitHub...
git reset --hard HEAD >nul 2>&1
git clean -fd --exclude=linkedin_jobs_*.csv --exclude=output.txt --exclude=run_fetch.bat >nul 2>&1
git pull
if errorlevel 1 (
    echo ERROR: git pull failed. Check your internet connection or GitHub credentials.
    pause
    exit /b 1
)
echo.

:: ── Step 1.5: Dedup LinkedIn CSVs ─────────────────────────────────────────
echo Deduplicating LinkedIn CSVs...
%PYTHON_CMD% dedup_linkedin.py
echo.

:: ── Step 2: Fetch jobs ────────────────────────────────────────────────────
echo [2/4] Fetching jobs from Comeet, Greenhouse, Lever, Taasuka...
%PYTHON_CMD% fetch_jobs.py
if errorlevel 1 (
    echo ERROR: fetch_jobs.py failed. See error above.
    pause
    exit /b 1
)
%PYTHON_CMD% fetch_taasuka.py
if errorlevel 1 (
    echo ERROR: fetch_taasuka.py failed. See error above.
    pause
    exit /b 1
)
echo.

:: ── Step 3: Commit CSVs ───────────────────────────────────────────────────
echo [3/4] Committing CSVs...
git add -- *.csv
git diff --staged --quiet && (
    echo No new data to commit.
) || (
    git commit -m "chore: jobs update %date:~6,4%-%date:~3,2%-%date:~0,2%"
)
echo.

:: ── Step 4: Push ──────────────────────────────────────────────────────────
echo [4/4] Pushing to GitHub...
git push
echo.

echo ===================================
echo  Done! Check jobfinder site.
echo ===================================
echo.
pause
