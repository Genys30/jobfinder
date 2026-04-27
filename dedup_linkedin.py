"""
dedup_linkedin.py - deduplicates linkedin_jobs_*.csv files
Deduplicates by title+company (catches reposted jobs with different URLs).
Run from the jobfinder folder: py dedup_linkedin.py
"""
import csv, glob, sys, os

EXPECTED_HEADERS = {'title', 'company', 'location', 'url', 'date'}

def has_header(first_row):
    values = [v.strip().lower() for v in first_row]
    return any(v in EXPECTED_HEADERS for v in values)

def dedup_file(fpath):
    with open(fpath, newline='', encoding='utf-8-sig') as f:
        raw = list(csv.reader(f))

    if not raw:
        print(f'  {fpath}: empty, skipping')
        return

    if has_header(raw[0]):
        headers = [h.strip().lower() for h in raw[0]]
        data = raw[1:]
        has_hdr = True
    else:
        headers = ['title', 'company', 'location', 'url', 'date']
        data = raw
        has_hdr = False

    try:
        title_idx   = headers.index('title')
        company_idx = headers.index('company')
        url_idx     = headers.index('url')
    except ValueError:
        print(f'  {fpath}: unexpected columns {headers}, skipping')
        return

    seen = set()
    unique = []
    dupes = 0

    for row in data:
        if len(row) <= max(title_idx, company_idx, url_idx):
            continue
        title   = row[title_idx].strip().lower()
        company = row[company_idx].strip().lower()
        # Deduplicate by title+company — catches same job reposted with different URL
        key = f'{title}|{company}'
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        unique.append(row)

    with open(fpath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if has_hdr:
            writer.writerow(raw[0])
        else:
            writer.writerow(['title', 'company', 'location', 'url', 'date'])
        writer.writerows(unique)

    print(f'  {os.path.basename(fpath)}: {len(unique)} unique jobs ({dupes} dupes removed)')

files = glob.glob('linkedin_jobs_*.csv')
if not files:
    print('No LinkedIn files found.')
    sys.exit(0)

for f in sorted(files):
    dedup_file(f)
