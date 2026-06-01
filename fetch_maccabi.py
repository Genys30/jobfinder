"""
fetch_maccabi.py — Fetches Maccabi Health Services jobs via JSON API.
Endpoint: POST https://www.maccabi4u.co.il/Umbraco/api/SearchJobsApi/FilterJobs

NOTE: maccabi4u.co.il blocks requests from cloud/CI IPs (GitHub Actions).
      Run this script LOCALLY and commit the CSV manually.

Output: maccabi_jobs_YYYY-MM-DD.csv
Usage:  py fetch_maccabi.py
"""

import csv, re, sys
from datetime import date

import requests

TODAY      = date.today().isoformat()
OUTFILE    = f"maccabi_jobs_{TODAY}.csv"
FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

API_URL = "https://www.maccabi4u.co.il/Umbraco/api/SearchJobsApi/FilterJobs"
HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type":    "application/json",
    "Accept":          "application/json",
    "Origin":          "https://www.maccabi4u.co.il",
    "Referer":         "https://www.maccabi4u.co.il/careers/search-job-positions/",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
}
RESULTS_PER_PAGE = 100

POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפה לח"ל|מילוי מקום לחופשת לידה|'
        r'maternity.?cover|maternity.?leave.?cover|covering.?maternity|'
        r'maternity.?leave.?replace|maternity.?replace|replace\w*.?maternity',
        re.I | re.UNICODE
    ),
    'part_time': re.compile(
        r'משרה חלקית|עבודה חלקית|היקף חלקי|חלקי\b|part.?time|part time',
        re.I | re.UNICODE
    ),
    'freelance': re.compile(
        r'פרילנס|פרי-לנס|freelance|free.?lance',
        re.I | re.UNICODE
    ),
    'internship': re.compile(
        r"סטאז'|סטאז|התמחות|מתמחה|intern(ship)?|co.?op\b|trainee",
        re.I | re.UNICODE
    ),
}

def detect_position_type(title='', description=''):
    text = (title + ' ' + description).strip()
    for pt, rx in POSITION_TYPE_PATTERNS.items():
        if rx.search(text):
            return pt
    return ''

def strip_html(raw):
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = re.sub(r'&nbsp;', ' ', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def fetch_all_jobs() -> list[dict]:
    jobs = []
    seen = set()

    payload = {
        "FreeText":               "",
        "ResultsPerPage":         RESULTS_PER_PAGE,
        "PageNumber":             0,
        "AdvertisingDestination": 1,
    }

    print(f"Fetching page 0 …")
    try:
        r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
    except Exception as e:
        print(f"  ✗ Connection error: {e}")
        return []

    if r.status_code == 403:
        print(f"  ✗ 403 Forbidden — maccabi4u.co.il blocks server/CI requests.")
        print(f"    Run this script locally on your machine.")
        return []
    if not r.ok:
        print(f"  ✗ HTTP {r.status_code}: {r.text[:200]}")
        return []

    data        = r.json()
    total       = data.get("TotalResults", 0)
    total_pages = (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
    print(f"  Total jobs: {total}  pages: {total_pages}")

    def _parse(data):
        for item in data.get("Results", []):
            title = (item.get("Description") or "").strip()
            if not title:
                continue
            url = (item.get("JobUrl") or "").strip()
            if not url:
                job_id = item.get("JobId") or ""
                if job_id:
                    url = f"https://www.maccabi4u.co.il/careers/all-positions/{job_id}/"
            if not url or url in seen:
                continue
            seen.add(url)

            areas    = item.get("Areas") or []
            location = areas[0].get("Description", "ישראל") if areas else "ישראל"
            dept     = (item.get("Profession") or "").strip()
            desc     = strip_html(item.get("Notes") or "")

            jobs.append({
                "title":          title,
                "company":        "מכבי שירותי בריאות",
                "location":       location,
                "date":           TODAY,
                "url":            url,
                "department":     dept,
                "workplace_type": "onsite",
                "source":         "maccabi",
                "description":    desc,
                "position_type":  detect_position_type(title, desc),
            })

    _parse(data)
    print(f"  Page 0: {len(jobs)} jobs")

    for pg in range(1, total_pages):
        payload["PageNumber"] = pg
        try:
            r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=30)
            if not r.ok:
                print(f"  ✗ page {pg}: HTTP {r.status_code}")
                break
            _parse(r.json())
            print(f"  Page {pg}: total so far {len(jobs)}")
        except Exception as e:
            print(f"  ✗ page {pg}: {e}")
            break

    return jobs


def main():
    jobs = fetch_all_jobs()

    if not jobs:
        print("\n⚠️  No jobs found — no file written.")
        sys.exit(0)

    with open(OUTFILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\n✅ Wrote {len(jobs)} jobs → {OUTFILE}")
    print("\nSample:")
    for j in jobs[:5]:
        print(f"  • [{j['department'] or 'general'}] {j['title'][:60]}")

    print("\nNext steps:")
    print("  git add maccabi_jobs_*.csv fetch_maccabi.py")
    print("  git commit -m 'chore: add maccabi jobs'")
    print("  git pull --rebase && git push")


if __name__ == "__main__":
    main()
