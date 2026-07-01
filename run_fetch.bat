@echo off
title JobFinder â€” Fetch Jobs
echo.
echo ===================================
echo  JobFinder â€” Fetching jobs...
echo ===================================
echo.

:: â”€â”€ Auto-detect project path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

:: â”€â”€ Check Git â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
where git >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git is not installed or not in PATH.
    echo.
    echo Download and install Git from: https://git-scm.com/download/win
    echo After installing, close and re-open this window.
    pause
    exit /b 1
)

:: â”€â”€ Check if this is a git repo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

:: â”€â”€ Check Python â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

:: â”€â”€ Install missing Python packages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

:: â”€â”€ Step 1: Pull â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [1/40] Pulling latest from GitHub...

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

:: â”€â”€ Clean LinkedIn tracking URLs (runs only if linkedin_jobs_*.csv exists) â”€
if exist "%PROJECT_DIR%\linkedin_jobs_*.csv" (
    echo Cleaning LinkedIn CSV tracking URLs...
    %PYTHON_CMD% clean_linkedin_csv.py
    if errorlevel 1 (
        echo WARNING: LinkedIn URL cleaning failed - continuing anyway.
    )
    echo.
)

:: â”€â”€ Step 2: Fetch Telegram â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:: NOTE: fetch_jobs.py and fetch_gotfriends.py now run automatically in
:: GitHub Actions every night. This .bat only handles LinkedIn (collected
:: manually with the Chrome extension) and the local-only sources below.

echo [2/40] Fetching Telegram @biltiformali...
%PYTHON_CMD% fetch_telegram_biltiformali.py --days 1
if errorlevel 1 (
    echo WARNING: Telegram fetch failed - continuing anyway.
)
%PYTHON_CMD% -c "import os,glob; from datetime import date,timedelta; cutoff=str(date.today()-timedelta(days=30)); [os.remove(f) for f in glob.glob('jobs_telegram_biltiformali_*.csv') if f[-14:-4] < cutoff]"
echo.
echo [3/40] Fetching Rambam jobs (local only)...
%PYTHON_CMD% fetch_rambam.py
if errorlevel 1 (
    echo WARNING: Rambam fetch failed - continuing anyway.
)
echo.
echo [4/40] Fetching BGU jobs (local only)...
%PYTHON_CMD% fetch_bgu.py
if errorlevel 1 (
    echo WARNING: BGU fetch failed - continuing anyway.
)
echo.
echo [5/40] Fetching Maccabi jobs (local only)...
%PYTHON_CMD% fetch_maccabi.py
if errorlevel 1 (
    echo WARNING: Maccabi fetch failed - continuing anyway.
)
echo.
echo [6/40] Fetching MOD jobs (local only)...
%PYTHON_CMD% fetch_mod_jobs.py
if errorlevel 1 (
    echo WARNING: MOD fetch failed - continuing anyway.
)
echo.
echo [7/40] Fetching Clalit jobs (local only)...
%PYTHON_CMD% fetch_clalit.py
if errorlevel 1 (
    echo WARNING: Clalit fetch failed - continuing anyway.
)
echo.
echo [8/40] Fetching TAU jobs (local only)...
%PYTHON_CMD% fetch_tau.py
if errorlevel 1 (
    echo WARNING: TAU fetch failed - continuing anyway.
)
echo.
echo [9/40] Fetching Haifa jobs (local only)...
%PYTHON_CMD% fetch_haifa.py
if errorlevel 1 (
    echo WARNING: Haifa fetch failed - continuing anyway.
)
echo.
echo [10/40] Fetching Bar-Ilan jobs (local only)...
%PYTHON_CMD% fetch_bar.py
if errorlevel 1 (
    echo WARNING: Bar-Ilan fetch failed - continuing anyway.
)
echo.
echo [11/40] Fetching Afeka jobs (local only)...
%PYTHON_CMD% fetch_afeka.py
if errorlevel 1 (
    echo WARNING: Afeka fetch failed - continuing anyway.
)
echo.
echo [12/40] Fetching SCE jobs (local only, Playwright)...
%PYTHON_CMD% fetch_sce.py
if errorlevel 1 (
    echo WARNING: SCE fetch failed - continuing anyway.
)
echo.
echo [13/40] Fetching Braude jobs (local only)...
%PYTHON_CMD% fetch_braude.py
if errorlevel 1 (
    echo WARNING: Braude fetch failed - continuing anyway.
)
echo.
echo [14/40] Fetching HIT jobs (local only, curl_cffi)...
%PYTHON_CMD% fetch_hit.py
if errorlevel 1 (
    echo WARNING: HIT fetch failed - continuing anyway.
)
echo.
echo [15/40] Fetching Azrieli jobs (local only, curl_cffi)...
%PYTHON_CMD% fetch_azrieli.py
if errorlevel 1 (
    echo WARNING: Azrieli fetch failed - continuing anyway.
)
echo.
echo [16/40] Fetching Shenkar jobs (local only)...
%PYTHON_CMD% fetch_shenkar.py
if errorlevel 1 (
    echo WARNING: Shenkar fetch failed - continuing anyway.
)
echo.
echo [17/40] Fetching Sapir jobs (local only, CIVI feed)...
%PYTHON_CMD% fetch_sapir.py
if errorlevel 1 (
    echo WARNING: Sapir fetch failed - continuing anyway.
)
echo.
echo [18/40] Fetching Emek Yezreel (YVC) jobs (local only)...
%PYTHON_CMD% fetch_yvc.py
if errorlevel 1 (
    echo WARNING: YVC fetch failed - continuing anyway.
)
echo.
echo [19/40] Fetching Tel-Hai jobs (local only)...
%PYTHON_CMD% fetch_telhai.py
if errorlevel 1 (
    echo WARNING: Tel-Hai fetch failed - continuing anyway.
)
echo.
echo [20/40] Fetching Ruppin jobs (local only, Playwright non-headless)...
%PYTHON_CMD% fetch_ruppin.py
if errorlevel 1 (
    echo WARNING: Ruppin fetch failed - continuing anyway.
)
echo.
echo [21/40] Fetching Ichilov jobs (local only)...
%PYTHON_CMD% fetch_ichilov.py
if errorlevel 1 (
    echo WARNING: Ichilov fetch failed - continuing anyway.
)
echo.
echo [22/40] Fetching GotFriends jobs (local only)...
%PYTHON_CMD% fetch_gotfriends.py
if errorlevel 1 (
    echo WARNING: GotFriends fetch failed - continuing anyway.
)
echo.
echo [23/40] Fetching HUJI positions (local only)...
%PYTHON_CMD% fetch_huji_positions.py
if errorlevel 1 (
    echo WARNING: HUJI positions fetch failed - continuing anyway.
)
echo.
echo [24/40] Fetching Shaare Zedek jobs (local only, Playwright)...
%PYTHON_CMD% fetch_szmc.py
if errorlevel 1 (
    echo WARNING: Shaare Zedek fetch failed - continuing anyway.
)
echo.
echo [25/40] Fetching Hadassah jobs (local only, Playwright)...
%PYTHON_CMD% fetch_hadassah.py
if errorlevel 1 (
    echo WARNING: Hadassah fetch failed - continuing anyway.
)
echo.
echo [26/40] Fetching Deloitte jobs (local only, Playwright)...
%PYTHON_CMD% fetch_deloitte.py
if errorlevel 1 (
    echo WARNING: Deloitte fetch failed - continuing anyway.
)
echo.
echo [27/40] Fetching EY jobs (local only, Playwright)...
%PYTHON_CMD% fetch_ey.py
if errorlevel 1 (
    echo WARNING: EY fetch failed - continuing anyway.
)
echo.
echo [28/40] Fetching BIS jobs (local only, Playwright)...
%PYTHON_CMD% fetch_bis.py
if errorlevel 1 (
    echo WARNING: BIS fetch failed - continuing anyway.
)
echo.
echo [29/40] Fetching Joint jobs (local only, Playwright)...
%PYTHON_CMD% fetch_joint.py
if errorlevel 1 (
    echo WARNING: Joint fetch failed - continuing anyway.
)
echo.
echo [30/40] Fetching Osem-Nestle jobs (local only, curl_cffi)...
%PYTHON_CMD% fetch_osem.py
if errorlevel 1 (
    echo WARNING: Osem fetch failed - continuing anyway.
)
echo.

:: â”€â”€ Step 30: Teva Pharmaceuticals â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [31/40] Fetching Teva jobs (local only)...
%PYTHON_CMD% fetch_teva.py
if errorlevel 1 (
    echo WARNING: Teva fetch failed - continuing anyway.
)
echo.

:: â”€â”€ Step 32: NAMER (national local-authority tenders, Azure APIM) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [32/40] Fetching NAMER jobs (local only, requests/APIM)...
%PYTHON_CMD% fetch_namer.py
if errorlevel 1 (
    echo WARNING: NAMER fetch failed - continuing anyway.
)
echo.

:: â”€â”€ Step 33: Bank Hapoalim â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [33/40] Fetching Bank Hapoalim jobs (local only, curl_cffi)...
%PYTHON_CMD% fetch_hapoalim.py
if errorlevel 1 (
    echo WARNING: Hapoalim fetch failed - continuing anyway.
)
echo.

:: â”€â”€ Step 34: Bank Leumi â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [34/40] Fetching Bank Leumi jobs (local only, requests/BS4)...
%PYTHON_CMD% fetch_leumi.py
if errorlevel 1 (
    echo WARNING: Leumi fetch failed - continuing anyway.
)
echo.

:: â”€â”€ Step 35: Mizrahi-Tefahot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [35/40] Fetching Mizrahi-Tefahot jobs (local only, requests/BS4)...
%PYTHON_CMD% fetch_mizrahi.py
if errorlevel 1 (
    echo WARNING: Mizrahi fetch failed - continuing anyway.
)
echo.

:: â”€â”€ Step 36: Bank Discount â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [36/41] Fetching Bank Discount jobs (Oracle ORC API, plain requests)...
%PYTHON_CMD% fetch_discount.py
if errorlevel 1 (
    echo WARNING: Discount fetch failed - continuing anyway.
)
echo.

:: â”€â”€ Step 37: FIBI (×”×‘× ×§ ×”×‘×™× ×œ××•×ž×™ ×”×¨××©×•×Ÿ + ×ž×ª"×£) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [37/41] Fetching FIBI jobs (local only, requests/BS4)...
%PYTHON_CMD% fetch_fibi.py
if errorlevel 1 (
    echo WARNING: FIBI fetch failed - continuing anyway.
)
echo.

:: ── Step 38: Phoenix Insurance (הפניקס) ────────────────────────────────────
echo [38/41] Fetching Phoenix Insurance jobs (local only, Playwright)...
%PYTHON_CMD% fetch_phoenix.py
if errorlevel 1 (
    echo WARNING: Phoenix fetch failed - continuing anyway.
)
echo.

:: ── Step 39: Source health check â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:: Verifies every source produced a fresh, non-empty CSV with the right
:: columns. Writes health_report.json (committed below). Never aborts the bat.
echo [39/41] Running source health check...
%PYTHON_CMD% check_health.py
echo.

:: â”€â”€ Step 32: Upload all CSVs to Google Drive (history archive) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
:: rclone only transfers new/changed files, so this is cheap to run daily.
:: Using "*.csv" so every naming pattern is covered (source_jobs_*, jobs_telegram_*, etc).
echo [40/41] Uploading CSVs to Google Drive...
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

:: â”€â”€ Step 8: Commit and push â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
echo [41/41] Committing and pushing CSVs...
git add -- *.csv health_report.json
git diff --staged --quiet && (
    echo No new data to commit.
) || (
    git commit -m "chore: jobs update %date:~6,4%-%date:~3,2%-%date:~0,2%"
)
echo.

:: â”€â”€ Pull then Push â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
