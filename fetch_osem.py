"""
fetch_osem.py — Scraper for Osem-Nestlé careers page
Uses curl_cffi to bypass Akamai WAF via browser TLS impersonation.
Install: pip install curl_cffi beautifulsoup4

Two-phase:
  1. List pages (/career/open-positions?page=N) -> title, location, url
  2. Each job's detail page -> description (+ department, workplace_type if present)
"""
import csv
import re
import time
from datetime import date

BASE_URL  = 'https://www.osem-nestle.co.il'
JOBS_PATH = '/career/open-positions'
COMPANY   = 'Osem-Nestlé'
SOURCE    = 'osem'
TODAY     = date.today().isoformat()
FIELDS    = ['title', 'company', 'location', 'date', 'url',
             'department', 'workplace_type', 'description', 'source']

LOCATION_ALIASES = {
    'Beer Seva': 'Beer Sheva',
    'Qiryat Gat': 'Kiryat Gat',
    'Qiryat Malakhi': 'Kiryat Malachi',
    'RISHON LEZION': 'Rishon LeZion',
    'JERUSALEM': 'Jerusalem',
    'MAABAROT': 'Maabarot',
    'TEL AVIV': 'Tel Aviv',
    'Nazeret': 'Nazareth',
    'Ramat Hashofet': 'Ramat HaShofet',
    'Industrial Zone Hevel Modiin': 'Hevel Modiin',
    'Kibutz Biet Hashita': 'Kibbutz Beit HaShita',
}


def clean_location(raw: str) -> str:
    loc = re.sub(r',?\s*IL,?\s*\d*\s*$', '', raw).strip().rstrip(',').strip()
    # Strip the leading "location" word — site uses vowelized form מִקוּם as well as מיקום
    loc = re.sub(r'^(מִקוּם|מיקום|Location)\s*', '', loc).strip()
    loc = re.sub(r'^Industrial Zone\s+', '', loc)
    loc = LOCATION_ALIASES.get(loc, loc)
    return loc.strip()


def parse_page(html: str) -> list:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    for li in soup.select('li.column-job.views-row'):
        title_el = li.select_one('.views-field-field-job-offer-title a')
        loc_el   = li.select_one('.views-field-field-job-offer-location a')
        if not title_el:
            continue
        href = title_el['href']
        url  = BASE_URL + href if href.startswith('/') else href
        loc_raw = loc_el.get_text(strip=True) if loc_el else ''
        jobs.append({
            'title':          title_el.get_text(strip=True),
            'company':        COMPANY,
            'location':       clean_location(loc_raw),
            'date':           TODAY,
            'url':            url,
            'department':     '',
            'workplace_type': '',
            'description':    '',
            'source':         SOURCE,
        })
    return jobs


def parse_detail(html: str) -> dict:
    """Extract description (+ department/workplace_type) from an Osem job page.

    Description lives in <div class="description_single">. Structured data
    (department=industry, employmentType) is in the JSON-LD JobPosting block.
    """
    import json
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    out = {'description': '', 'department': '', 'workplace_type': 'onsite'}

    # Description — the visible job text
    desc_el = soup.select_one('.description_single')
    if desc_el:
        # Convert <p>/<br> to newlines, keep readable line breaks
        for br in desc_el.find_all('br'):
            br.replace_with('\n')
        parts = [p.get_text(' ', strip=True) for p in desc_el.find_all('p')]
        parts = [p for p in parts if p]
        text = '\n'.join(parts) if parts else desc_el.get_text('\n', strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        out['description'] = text.strip()[:4000]

    # JSON-LD JobPosting: department (industry) + employment type
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string or '')
        except Exception:
            continue
        graph = data.get('@graph', [data]) if isinstance(data, dict) else []
        for node in graph:
            if isinstance(node, dict) and node.get('@type') == 'JobPosting':
                if node.get('industry'):
                    out['department'] = str(node['industry']).strip()
                et = (node.get('employmentType') or '').upper()
                if 'PART' in et:
                    out['workplace_type'] = 'parttime'
                elif 'FULL' in et:
                    out['workplace_type'] = 'fulltime'
                # Fallback description from JSON-LD if the div was empty
                if not out['description'] and node.get('description'):
                    from html import unescape
                    raw = unescape(node['description'])
                    raw = re.sub(r'<[^>]+>', ' ', raw)
                    out['description'] = re.sub(r'\s+', ' ', raw).strip()[:4000]
                break
    return out


def run_osem():
    print("\n-- Osem-Nestlé -------------------------------------------------------")
    try:
        from curl_cffi import requests
    except ImportError:
        print("  curl_cffi not installed. Run: pip install curl_cffi")
        return []

    session = requests.Session(impersonate="chrome110")
    # Warm up
    try:
        session.get(f"{BASE_URL}/career", timeout=15)
        time.sleep(1)
    except Exception:
        pass

    all_jobs = []
    page = 0
    while True:
        url = f"{BASE_URL}{JOBS_PATH}?page={page}"
        print(f"  Fetching page {page}...")
        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print(f"  Page {page}: {e}")
            break
        jobs = parse_page(r.text)
        if not jobs:
            print(f"  No jobs on page {page} - stopping")
            break
        all_jobs.extend(jobs)
        print(f"    + {len(jobs)} jobs")
        if len(jobs) < 12:
            break
        page += 1
        time.sleep(1)

    # Dedupe by URL
    seen = set()
    deduped = [j for j in all_jobs if j['url'] not in seen and not seen.add(j['url'])]

    # Phase 2: fetch each job's detail page for a description
    print(f"  Fetching descriptions for {len(deduped)} jobs...")
    for i, job in enumerate(deduped, 1):
        try:
            r = session.get(job['url'], timeout=20)
            if r.ok:
                detail = parse_detail(r.text)
                job['description'] = detail['description']
                if detail['department']:
                    job['department'] = detail['department']
                if detail['workplace_type']:
                    job['workplace_type'] = detail['workplace_type']
        except Exception as e:
            print(f"    [{i}] detail failed: {e}")
        if i % 10 == 0:
            print(f"    ...{i}/{len(deduped)}")
        time.sleep(0.4)

    fname = f'osem_jobs_{TODAY}.csv'
    with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(deduped)
    with_desc = sum(1 for j in deduped if j['description'])
    print(f"  -> {len(deduped)} jobs saved to {fname} ({with_desc} with descriptions)")
    return deduped


if __name__ == '__main__':
    run_osem()
