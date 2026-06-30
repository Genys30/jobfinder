#!/usr/bin/env python3
"""
fetch_discount.py — Scrapes open positions at Bank Discount (בנק דיסקונט).

  ATS:  Oracle Recruiting Cloud (ORC) / Career Site Builder (CSB)
  Site: CX_3001 on ehsb.fa.em2.oraclecloud.com (hosted at discountbank.co.il/DB/jobs/)
  API:  GET /hcmRestApi/resources/latest/recruitingCEJobRequisitions
        with expand=all returns requisitionList inline.
  Limit: Oracle public API hard-caps the requisitionList at 25 records
         (TotalJobsCount reflects the real total, e.g. 68). No public
         pagination endpoint is available — this is an Oracle platform
         constraint. The 25 most-recent jobs are captured.
  LOCAL-ONLY: not required (Oracle CDN accessible globally), but run
              locally to avoid CI IP blocks on the Discount website.

  Fields per job: Id, Title, PostedDate, ShortDescriptionStr,
                  PrimaryLocation (city, region, country), Department.
  URL: https://www.discountbank.co.il/DB/jobs/#he/sites/CX_3001/requisitions/{Id}/details
  Dedup: by URL (unique per job via Id).

Output: discount_jobs_YYYY-MM-DD.csv
Usage:  py fetch_discount.py
"""

import csv, re, sys, glob
from datetime import date, timedelta

import requests

TODAY       = date.today().isoformat()
OUTPUT_FILE = f"discount_jobs_{TODAY}.csv"
SOURCE      = "discount"
COMPANY     = "בנק דיסקונט"
ORACLE_HOST = "https://ehsb.fa.em2.oraclecloud.com"
SITE        = "CX_3001"
API_URL     = (f"{ORACLE_HOST}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
               f"?onlyData=true&limit=25&expand=all&finder=findReqs;siteNumber={SITE}")
JOB_BASE_URL = f"https://www.discountbank.co.il/DB/jobs/#he/sites/{SITE}/requisitions"

FIELDNAMES = [
    "title", "company", "location", "date", "url",
    "department", "workplace_type", "source", "description", "position_type"
]

HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Referer": "https://www.discountbank.co.il/DB/jobs/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
}


def clean(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def title_to_position_type(title):
    t = title or ""
    if re.search(r'חל"ד|חל״ד|חופשת לידה|מילוי מקום|החלפה', t):
        return "maternity_cover"
    if re.search(r"מתמחה|התמחות", t) or re.search(r"\bintern\b", t, re.I):
        return "internship"
    if re.search(r"סטודנט", t):
        return "part_time"
    if re.search(r"חצי משרה|משרה חלקית|חלקית", t):
        return "part_time"
    return ""


def parse_location(primary_location):
    """'ראשון לציון, מרכז, ישראל' -> 'ראשון לציון'"""
    if not primary_location:
        return "ישראל"
    parts = [p.strip() for p in primary_location.split(",")]
    return parts[0] if parts else "ישראל"


def load_first_seen():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob("discount_jobs_*.csv"))
    prev_file = None
    for f in reversed(candidates):
        if yesterday in f:
            prev_file = f
            break
    if prev_file is None and candidates:
        prev_file = candidates[-1]
    if prev_file is None:
        return {}
    result = {}
    try:
        with open(prev_file, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                u = row.get("url", "").strip()
                d = row.get("date", "").strip()
                if u and d:
                    result[u] = d
    except Exception:
        pass
    return result


def scrape():
    first_seen = load_first_seen()
    session = requests.Session()

    print(f"\n[Bank Discount] fetching Oracle ORC API ...")
    try:
        r = session.get(API_URL, timeout=30, headers=HEADERS)
    except Exception as e:
        print(f"  ERROR: {e}")
        return []

    if r.status_code != 200:
        print(f"  HTTP {r.status_code}: {r.text[:200]}")
        return []

    try:
        data = r.json()
    except Exception as e:
        print(f"  JSON parse error: {e}")
        return []

    search = data.get("items", [{}])[0]
    raw_jobs = search.get("requisitionList", [])
    total = search.get("TotalJobsCount", len(raw_jobs))
    print(f"  TotalJobsCount={total}, returning {len(raw_jobs)} (Oracle API limit=25)")

    jobs = []
    seen_urls = set()
    for j in raw_jobs:
        job_id = j.get("Id", "")
        if not job_id:
            continue
        url = f"{JOB_BASE_URL}/{job_id}/details"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = clean(j.get("Title", ""))
        if not title:
            continue

        location = parse_location(j.get("PrimaryLocation") or "")
        posted   = j.get("PostedDate") or TODAY
        dept     = clean(j.get("Department") or j.get("Organization") or "")
        desc     = clean(j.get("ShortDescriptionStr") or "")
        if j.get("ExternalQualificationsStr"):
            desc += " | " + clean(j["ExternalQualificationsStr"])
        desc = desc[:1500]
        pt = title_to_position_type(title)

        jobs.append({
            "title":          title,
            "company":        COMPANY,
            "location":       location,
            "date":           first_seen.get(url, posted),
            "url":            url,
            "department":     dept,
            "workplace_type": "onsite",
            "source":         SOURCE,
            "description":    desc,
            "position_type":  pt,
        })
        tag = f" [{pt}]" if pt else ""
        print(f"  {job_id}: {title[:50]}{tag}  | {location}"
              + (f"  | {dept[:25]}" if dept else ""))

    return jobs


def main():
    jobs = scrape()

    if not jobs:
        print("\nNo jobs found — no file written.")
        sys.exit(0)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(jobs)

    print(f"\nWrote {len(jobs)} jobs -> {OUTPUT_FILE}")
    print("Next steps:")
    print("  git add -f discount_jobs_*.csv fetch_discount.py")
    print("  git commit -m 'feat: add Bank Discount careers scraper (Oracle ORC)'")
    print("  git pull --rebase origin main && git push")


if __name__ == "__main__":
    main()
