"""
clean_linkedin_csv.py
Strip LinkedIn tracking parameters from the URL column of the most recent
linkedin_jobs_*.csv file in the current directory.

Usage (run once after Chrome-extension export, before git commit):
    python clean_linkedin_csv.py

Before: https://www.linkedin.com/jobs/view/4423633279/?eBP=Cw...&refId=...&trk=...  (519 chars)
After:  https://www.linkedin.com/jobs/view/4423633279/                               (46 chars)
Result: file shrinks from ~500 KB → ~120 KB (4x smaller, loads 4x faster in browser)
"""

import csv
import glob
import os
import re
import sys


def clean_url(url: str) -> str:
    """Keep only the canonical job URL — strip all tracking query params."""
    # Preferred: extract job view URL (covers 99% of LinkedIn job links)
    m = re.match(r'(https://www\.linkedin\.com/jobs/view/\d+/?)', url)
    if m:
        base = m.group(1)
        return base if base.endswith('/') else base + '/'
    # Fallback: strip everything from '?' onward
    return re.sub(r'\?.*$', '', url)


def main():
    # Find the most recent linkedin_jobs_*.csv in the current directory
    pattern = 'linkedin_jobs_*.csv'
    files = sorted(glob.glob(pattern))
    if not files:
        print(f'[clean_linkedin] ERROR: no files matching {pattern!r} found in {os.getcwd()}')
        sys.exit(1)

    path = files[-1]
    print(f'[clean_linkedin] processing: {path}')

    original_size = os.path.getsize(path)

    with open(path, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames or 'url' not in fieldnames:
        print('[clean_linkedin] ERROR: no "url" column found — check CSV header')
        sys.exit(1)

    cleaned = 0
    for row in rows:
        original = row.get('url', '')
        clean = clean_url(original)
        if clean != original:
            row['url'] = clean
            cleaned += 1

    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    new_size = os.path.getsize(path)
    saved_kb = (original_size - new_size) / 1024
    print(f'[clean_linkedin] {len(rows)} rows processed, {cleaned} URLs cleaned')
    print(f'[clean_linkedin] size: {original_size/1024:.0f} KB → {new_size/1024:.0f} KB  (saved {saved_kb:.0f} KB)')
    print(f'[clean_linkedin] done → {path}')


if __name__ == '__main__':
    main()
