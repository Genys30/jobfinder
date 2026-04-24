"""
fetch_taasuka.py  —  Nightly GitHub Action
Source: taasuka.gov.il (שירות התעסוקה — Israeli Employment Service)
Outputs: taasuka_jobs_{TODAY}.csv

Endpoint (no auth required):
  GET https://www.taasuka.gov.il/umbraco/surface/jobsearchsurface/searchjobs
  ?ProfessionCategoryCode=&FreeText=&IsEmployersJobSearch=false&page=N

Response: HTML fragment with div.jobItem elements + pagination.
"""

import requests, csv, re, time
from datetime import date
from bs4 import BeautifulSoup

TODAY   = date.today().isoformat()
BASE    = 'https://www.taasuka.gov.il/umbraco/surface/jobsearchsurface/searchjobs'
JOB_URL = 'https://www.taasuka.gov.il/he/Applicants/jobdetails?jobid={}'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; jobfinder-bot/1.0)',
    'Referer':    'https://www.taasuka.gov.il/he/Applicants/jobs',
    'Accept':     'text/html,application/xhtml+xml',
}
# Columns must match the rest of the project + new description field
FIELDNAMES = ['title', 'company', 'location', 'date', 'url',
              'department', 'workplace_type', 'description', 'source']


# ── helpers ──────────────────────────────────────────────────────────────────

def ddmmyyyy_to_iso(s):
    """'23.04.2026' → '2026-04-23'"""
    parts = s.split('.')
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return s


def fetch_page(page=1):
    params = {
        'ProfessionCategoryCode': '',
        'FreeText':               '',
        'IsEmployersJobSearch':   'false',
        'page':                   page,
    }
    try:
        r = requests.get(BASE, params=params, headers=HEADERS, timeout=30)
        if not r.ok:
            print(f"    HTTP {r.status_code} on page {page}")
            return None
        return r.text
    except Exception as e:
        print(f"    x page {page}: {e}")
        return None


def count_pages(soup):
    """Extract highest page number from pagination."""
    nums = []
    for a in soup.select('.pagination .page-item a'):
        try:
            nums.append(int(a.get_text(strip=True)))
        except ValueError:
            pass
    return max(nums) if nums else 1


def parse_jobs(html):
    soup  = BeautifulSoup(html, 'html.parser')
    jobs  = []

    for item in soup.select('div.jobItem'):
        job_id = item.get('jobid', '')
        title  = (item.get('jobtitle') or '').strip()
        if not title:
            a = item.select_one('.jobTitle a')
            title = a.get_text(strip=True) if a else ''

        # ── structured fields ─────────────────────────────────────────────
        location     = ''
        updated_date = ''
        for d in item.select('.jobDetails div'):
            strong = d.find('strong')
            span   = d.find('span')
            if not strong or not span:
                continue
            label = strong.get_text(strip=True)
            value = span.get_text(strip=True)
            if 'מקום' in label:       # מקום עבודה
                location = value
            elif 'תאריך' in label:    # תאריך עדכון
                updated_date = ddmmyyyy_to_iso(value)

        # ── description ───────────────────────────────────────────────────
        desc = ''
        text_div = item.select_one('.text')
        if text_div:
            desc = text_div.get_text(separator=' ', strip=True)
            desc = re.sub(r'\s+', ' ', desc)   # collapse whitespace

        jobs.append({
            'title':         title,
            'company':       '',           # taasuka hides employer names
            'location':      location,
            'date':          updated_date,
            'url':           JOB_URL.format(job_id) if job_id else '',
            'department':    '',
            'workplace_type': '',
            'description':   desc,
            'source':        'taasuka',
        })

    return soup, jobs


# ── main ─────────────────────────────────────────────────────────────────────

def write_csv(jobs, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)
    print(f"  Wrote {len(jobs)} rows → {filename}")


def run_taasuka():
    print("\n-- Taasuka (שירות התעסוקה) ------------------------------------------")
    all_jobs = []

    # Page 1 → also tells us total page count
    html = fetch_page(1)
    if not html:
        print("  x Could not fetch page 1")
        return []

    soup, jobs = parse_jobs(html)
    total_pages = count_pages(soup)
    all_jobs.extend(jobs)
    print(f"  Page 1/{total_pages}: {len(jobs)} jobs")

    for page in range(2, total_pages + 1):
        time.sleep(1)                      # be polite
        html = fetch_page(page)
        if not html:
            break
        _, jobs = parse_jobs(html)
        if not jobs:
            break
        all_jobs.extend(jobs)
        print(f"  Page {page}/{total_pages}: {len(jobs)} jobs")

    print(f"  Total: {len(all_jobs)} jobs")
    return all_jobs


if __name__ == '__main__':
    jobs = run_taasuka()
    if jobs:
        write_csv(jobs, f'taasuka_jobs_{TODAY}.csv')
    else:
        print("  No jobs fetched — no file written.")
