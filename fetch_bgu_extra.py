"""
Local scraper for BGU extra job pages (WAF blocks GitHub Actions IPs).
Run locally, outputs bgu_extra_jobs_YYYY-MM-DD.csv
"""
import requests
from bs4 import BeautifulSoup
from datetime import date
import csv, re, sys

PAGES = {
    'pensioners': 'https://www.bgu.ac.il/recruitment/pensioners/',
    'admin':      'https://www.bgu.ac.il/recruitment/additional-jobs-administrative-and-technical-staff/',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36',
    'Accept-Language': 'he-IL,he;q=0.9',
    'Referer': 'https://www.bgu.ac.il/recruitment/',
}

today = date.today().isoformat()
outfile = f'bgu_extra_jobs_{today}.csv'
rows = []

for page_key, url in PAGES.items():
    print(f'Fetching {url}...')
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        print(f'  ERROR {r.status_code}', file=sys.stderr)
        continue
    soup = BeautifulSoup(r.text, 'html.parser')
    items = soup.select('div.simple-accordion')
    print(f'  Found {len(items)} jobs')
    for item in items:
        title_el = item.select_one('h3.simple-accordion__name')
        body_el  = item.select_one('div.simple-accordion__body')
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        body  = body_el.get_text(' ', strip=True) if body_el else ''
        # extract email from body
        email_match = re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', body)
        email = email_match.group(0) if email_match else ''
        rows.append({
            'title':    title,
            'company':  'אוניברסיטת בן-גוריון בנגב',
            'location': 'באר שבע',
            'url':      url,
            'date':     today,
            'deadline': '',
            'department': page_key,
            'email':    email,
        })

with open(outfile, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['title','company','location','url','date','deadline','department','email'])
    writer.writeheader()
    writer.writerows(rows)

print(f'Wrote {len(rows)} jobs to {outfile}')
