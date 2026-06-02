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
echo [1/8] Pulling latest from GitHub...

:: Back up LinkedIn CSVs before clean (git clean deletes untracked files)
if not exist "%TEMP%\li_backup" mkdir "%TEMP%\li_backup"
for %%f in (linkedin_jobs_*.csv) do (
    echo   Backing up %%f...
    copy /Y "%%f" "%TEMP%\li_backup\%%f" >nul
)

git reset --hard HEAD >nul 2>&1
git pull
if errorlevel 1 (
    echo ERROR: git pull failed. Check your internet connection or GitHub credentials.
    pause
    exit /b 1
)

:: Restore LinkedIn CSVs after clean
for %%f in ("%TEMP%\li_backup\linkedin_jobs_*.csv") do (
    echo   Restoring %%~nxf...
    copy /Y "%%f" "%PROJECT_DIR%\%%~nxf" >nul
)
rd /s /q "%TEMP%\li_backup" >nul 2>&1
echo.



:: ── Step 2: Fetch Telegram ────────────────────────────────────────────────
:: NOTE: fetch_jobs.py and fetch_gotfriends.py now run automatically in
:: GitHub Actions every night. This .bat only handles LinkedIn (collected
:: manually with the Chrome extension) and the local-only sources below.

echo [2/8] Fetching Telegram @biltiformali...
%PYTHON_CMD% fetch_telegram_biltiformali.py --days 1
if errorlevel 1 (
    echo WARNING: Telegram fetch failed - continuing anyway.
)
%PYTHON_CMD% -c "import os,glob; from datetime import date,timedelta; cutoff=str(date.today()-timedelta(days=30)); [os.remove(f) for f in glob.glob('jobs_telegram_biltiformali_*.csv') if f[-14:-4] < cutoff]"
echo.
echo [3/8] Fetching Rambam jobs (local only)...
%PYTHON_CMD% fetch_rambam.py
if errorlevel 1 (
    echo WARNING: Rambam fetch failed - continuing anyway.
)
echo.
echo [4/8] Fetching BGU jobs (local only)...
%PYTHON_CMD% fetch_bgu.py
if errorlevel 1 (
    echo WARNING: BGU fetch failed - continuing anyway.
)
echo.
echo [5/8] Fetching Maccabi jobs (local only)...
%PYTHON_CMD% fetch_maccabi.py
if errorlevel 1 (
    echo WARNING: Maccabi fetch failed - continuing anyway.
)
echo.
echo [6/8] Fetching MOD jobs (local only)...
%PYTHON_CMD% fetch_mod_jobs.py
if errorlevel 1 (
    echo WARNING: MOD fetch failed - continuing anyway.
)
echo.

:: ── Step 7: Upload all CSVs to Google Drive (history archive) ─────────────
:: rclone only transfers new/changed files, so this is cheap to run daily.
:: Using "*.csv" so every naming pattern is covered (source_jobs_*, jobs_telegram_*, etc).
echo [7/8] Uploading CSVs to Google Drive...
where rclone >nul 2>&1
if errorlevel 1 (
    if exist "%PROJECT_DIR%\rclone.exe" (
        set "RCLONE_CMD=%PROJECT_DIR%\rclone.exe"
    ) else (
        echo WARNING: rclone not found - skipping Drive upload.
        echo   Install rclone or place rclone.exe in the project folder.
        goto :after_drive
    )
) else (
    set "RCLONE_CMD=rclone"
)
"%RCLONE_CMD%" copy . gdrive:jobfinder-data --include "*.csv"
if errorlevel 1 (
    echo WARNING: Drive upload failed - continuing anyway.
) else (
    echo   Drive archive up to date.
)
:after_drive
echo.

:: ── Step 8: Commit and push ───────────────────────────────────────────────
echo [8/8] Committing and pushing CSVs...
git add -- *.csv
git diff --staged --quiet && (
    echo No new data to commit.
) || (
    git commit -m "chore: jobs update %date:~6,4%-%date:~3,2%-%date:~0,2%"
)
echo.

:: ── Pull then Push ────────────────────────────────────────────────────────
echo Syncing with GitHub before push...
git pull --rebase origin main
if errorlevel 1 (
    echo ERROR: git pull --rebase failed. Resolve conflicts and run again.
    pause
    exit /b 1
)
git push
echo.

echo ===================================
echo  Done! Check jobfinder site.
echo ===================================
echo.
pause
