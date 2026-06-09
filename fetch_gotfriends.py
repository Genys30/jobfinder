#!/usr/bin/env python3
"""
fetch_gotfriends.py — GotFriends (גוטפרנדס) tech recruitment listings scraper.

Israel's largest tech-only recruitment platform. Jobs are exclusive — most won't
appear on Greenhouse/Lever/etc. No API: plain HTML, server-rendered.
URL pattern: /jobslobby/{category}/?page=N&total=TOTALPAGES

Output: gotfriends_jobs_{TODAY}.csv (columns: title, company, location, date, url,
department, workplace_type).

Pure requests. Prints per-category diagnostics so we can see if parsing works.
403 may occur from datacenter IPs — runs locally.
"""

import csv
import re
import sys
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

TODAY = date.today().isoformat()


def load_first_seen(pattern, key_field="url"):
    import glob
    from datetime import timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    candidates = sorted(glob.glob(pattern))
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
        with open(prev_file, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = row.get(key_field, "").strip()
                d = row.get("date", "").strip()
                if k and d:
                    result[k] = d
    except Exception:
        pass
    return result

BASE = "https://www.gotfriends.co.il"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Referer": BASE + "/",
}

# Top-level categories only — subcategory pages duplicate the same jobs
CATEGORIES = [
    ("software", "Software Development"),
    ("ai", "AI & ML"),
    ("datasecurity", "Cyber & Security"),
    ("algorithm", "Algorithms & Data Science"),
    ("qa", "QA & Automation"),
    ("executive-position", "Executive"),
    ("graduates", "Graduates (8200/Mamram)"),
    ("projects", "Product Management"),
    ("system", "DevOps & System"),
    ("bibig_data", "BI & Big Data"),
]

LOC_MAP = {
    'ת"א והמרכז': "Tel Aviv", "תל אביב": "Tel Aviv", "השרון": "Sharon",
    "חיפה והצפון": "Haifa", "חיפה": "Haifa", "ירושלים": "Jerusalem",
    "באר שבע והדרום": "Beer Sheva", "באר שבע": "Beer Sheva",
    "שפלה": "Shfela", "אילת": "Eilat",
}
REMOTE_KW = re.compile(r"ריילוקיישן|relocation|remote|מהבית|מרחוק", re.I)
HYBRID_KW = re.compile(r"היברידי|hybrid", re.I)
COLUMNS = ["title", "company", "location", "date", "url", "department", "workplace_type"]


def map_loc(raw):
    raw = raw.strip()
    for heb, eng in LOC_MAP.items():
        if heb in raw:
            return eng
    return "Israel"


def parse_page(html, cat_en, first_seen):
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for h2 in soup.find_all("h2"):
        a = h2.find("a", href=re.compile(r"/jobslobby/"))
        if not a:
            a = h2.find_parent("a", href=re.compile(r"/jobslobby/"))
        if not a:
            continue
        href = a.get("href", "")
        # job pages are deeper than category pages (≥4 path segments)
        if len([p for p in href.split("/") if p]) < 4:
            continue
        url = href if href.startswith("http") else BASE + href
        title = h2.get_text(strip=True)
        if not title:
            continue
        node = h2 if not h2.find_parent("a") else h2.find_parent("a")
        context_parts = []
        sib = node.next_sibling
        steps = 0
        while sib and steps < 8:
            if hasattr(sib, "name"):
                if sib.name == "h2":
                    break
                context_parts.append(sib.get_text(" ", strip=True))
            elif isinstance(sib, str):
                context_parts.append(sib.strip())
            sib = sib.next_sibling
            steps += 1
        context = " ".join(context_parts)

        location = "Israel"
        parent = node.parent if node else None
        if parent:
            for dt in parent.find_all("dt"):
                if "מיקום" in dt.get_text():
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        location = map_loc(dd.get_text(strip=True))
                    break
        if location == "Israel":
            m = re.search(r"מיקום[:\s]+([^\n\|]{2,30})", context)
            if m:
                location = map_loc(m.group(1))

        combined = title + " " + context
        wt = ("Remote" if REMOTE_KW.search(combined)
              else "Hybrid" if HYBRID_KW.search(combined) else "onsite")
        jobs.append({
            "title": title, "company": "GotFriends", "location": location,
            "date": first_seen.get(url, TODAY), "url": url, "department": cat_en, "workplace_type": wt,
        })
    return jobs


def write_csv(rows, fname):
    with open(fname, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")


def run_gotfriends():
    print("\n-- GotFriends (גוטפרנדס) -------------------------------------------")
    first_seen = load_first_seen("gotfriends_jobs_*.csv", key_field="url")
    all_jobs = []
    seen_urls = set()

    for cat_slug, cat_en in CATEGORIES:
        cat_url = f"{BASE}/jobslobby/{cat_slug}/"
        print(f"  [{cat_slug}]", end="", flush=True)
        total_pages = 1
        page = 1
        while page <= total_pages and page <= 40:
            url = cat_url if page == 1 else f"{cat_url}?page={page}&total={total_pages}"
            try:
                r = requests.get(url, timeout=30, headers=HEADERS)
                if not r.ok:
                    print(f" x{r.status_code}", end="")
                    break
                if page == 1:
                    for m in re.finditer(r"[?&]total=(\d+)", r.text):
                        detected = int(m.group(1))
                        if detected > total_pages:
                            total_pages = detected
                        break
                new_jobs = parse_page(r.text, cat_en, first_seen)
                added = 0
                for j in new_jobs:
                    if j["url"] not in seen_urls:
                        seen_urls.add(j["url"])
                        all_jobs.append(j)
                        added += 1
                print(f" p{page}+{added}", end="", flush=True)
                page += 1
                time.sleep(0.35)
            except Exception as e:
                print(f" x{e}", end="")
                break
        print()

    write_csv(all_jobs, f"gotfriends_jobs_{TODAY}.csv")
    return len(all_jobs)


if __name__ == "__main__":
    count = run_gotfriends()
    print(f"\nDone. {count} GotFriends jobs.")
    sys.exit(0)
