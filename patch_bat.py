bat = open('run_fetch.bat', encoding='utf-8').read()

telegram_block = (
    '\necho [2b/4] Fetching Telegram @biltiformali...\n'
    '%PYTHON_CMD% fetch_telegram_biltiformali.py --days 1\n'
    'if errorlevel 1 (\n'
    '    echo WARNING: Telegram fetch failed - continuing anyway.\n'
    ')\n'
    '%PYTHON_CMD% -c "import os,glob; from datetime import date,timedelta; cutoff=str(date.today()-timedelta(days=30)); [os.remove(f) for f in glob.glob(\'jobs_telegram_biltiformali_*.csv\') if f[-14:-4] < cutoff]"\n'
    'echo.\n'
)

marker = 'echo [3/4] Committing CSVs'
if marker not in bat:
    print('NOT PATCHED - marker not found')
elif 'fetch_telegram' in bat:
    print('Already patched')
else:
    bat2 = bat.replace(marker, telegram_block + marker)
    open('run_fetch.bat', 'w', encoding='utf-8').write(bat2)
    print('done')
