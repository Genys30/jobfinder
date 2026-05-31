"""
fetch_jobs.py — Nightly GitHub Action
Sources: Comeet · Greenhouse · Lever · Ashby · Workable · Breezy
         + Mitam · Weizmann · BGU · HUJI · Technion
"""

import requests, csv, json, re, os, sys
from datetime import date

# ── Config ───────────────────────────────────────────────────────────────────

TECHMAP_FNS = [
    'admin','business','data-science','design','devops','finance','frontend',
    'hardware','hr','legal','marketing','procurement-operations','product',
    'project-management','qa','sales','security','software','support'
]
TECHMAP_BASE = 'https://raw.githubusercontent.com/mluggy/techmap/main/jobs/'
HEADERS      = {'User-Agent': 'Mozilla/5.0 (compatible; jobfinder-bot/1.0)'}
TODAY        = date.today().isoformat()
COMPANIES_FILE = 'companies.json'

ISRAEL_COUNTRIES = {'IL','ISR','ISRAEL'}
ISRAEL_CITIES = {
    'tel aviv','tel-aviv','herzliya','haifa','jerusalem','beer sheva',
    "be'er sheva",'petah tikva','raanana','netanya','rehovot',
    'rishon lezion','holon','bnei brak','kfar saba','modiin','ashkelon',
    'ashdod','bat yam','givatayim','rosh haayin','lod','ramla','nazareth',
    'hadera','caesarea','yokneam','matam','airport city','kiryat gat',
    'hod hasharon','ramat gan'
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_israel(text='', country='', remote=False):
    if remote: return True
    if country.upper() in ISRAEL_COUNTRIES: return True
    t = text.lower()
    if 'israel' in t: return True
    return any(c in t for c in ISRAEL_CITIES)

POSITION_TYPE_PATTERNS = {
    'maternity_cover': re.compile(
        r'חל"ד|חל״ד|ח\.ל\.ד|החלפה לחופשת לידה|החלפה לח"ל|מילוי מקום לחופשת לידה|'
        r'maternity.?cover|maternity.?leave.?cover|covering.?maternity',
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
    """Detect position_type from title and description text."""
    text = (title + ' ' + description).strip()
    for pt, rx in POSITION_TYPE_PATTERNS.items():
        if rx.search(text):
            return pt
    return ''

def dedup_jobs(jobs):
    seen = set()
    result = []
    for j in jobs:
        key = j.get('url') or (
            str(j.get('title','')).lower().strip() + '|' +
            str(j.get('company','')).lower().strip()
        )
        if key and key not in seen:
            seen.add(key)
            result.append(j)
    return result

def write_csv(rows, fields, fname):
    with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    print(f"   -> {len(rows)} jobs saved to {fname}")

def load_companies():
    """Загружает единый реестр компаний из companies.json"""
    try:
        with open(COMPANIES_FILE, encoding='utf-8') as f:
            companies = json.load(f)
        print(f"   Loaded {len(companies)} companies from {COMPANIES_FILE}")
        return companies
    except FileNotFoundError:
        print(f"   ERROR: {COMPANIES_FILE} not found!")
        sys.exit(1)

# ── Techmap scanner (только для обнаружения новых компаний) ──────────────────

def scan_techmap():
    """Сканирует techmap для поиска компаний, которых ещё нет в companies.json"""
    print("\n-- Techmap scan (new companies only) --------------------------------")
    companies = load_companies()

    # Собираем уже известные токены
    known_comeet   = {c['comeet'].split('/')[0].lower() for c in companies if c.get('comeet')}
    known_gh       = {c['greenhouse'].lower() for c in companies if c.get('greenhouse')}
    known_lever    = {c['lever'].lower() for c in companies if c.get('lever')}

    pat_comeet = re.compile(r'comeet\.co[m]?/jobs/([^/\s"\']+)/([0-9A-Fa-f]{2,}\.[0-9A-Fa-f]{3,})', re.I)
    pat_gh     = re.compile(r'boards(?:\.eu)?\.greenhouse\.io/([^/\s"\'?#]+)/jobs', re.I)
    pat_lever  = re.compile(r'jobs\.lever\.co/([^/\s"\'?#]+)/', re.I)

    new_comeet = {}
    new_gh     = {}
    new_lever  = {}

    for fn in TECHMAP_FNS:
        try:
            r = requests.get(TECHMAP_BASE + fn + '.csv', timeout=30, headers=HEADERS)
            if not r.ok: continue
            for row in csv.DictReader(r.text.splitlines()):
                url  = row.get('url','')
                comp = row.get('company','')

                m = pat_comeet.search(url)
                if m:
                    slug = m.group(1).lower()
                    uid  = m.group(2).upper()
                    if slug not in known_comeet and slug not in new_comeet:
                        new_comeet[slug] = {'slug': slug, 'uid': uid, 'name': comp or slug}

                m = pat_gh.search(url)
                if m:
                    t = m.group(1).lower()
                    if t not in known_gh and t not in new_gh:
                        new_gh[t] = {'token': t, 'name': comp or t}

                m = pat_lever.search(url)
                if m:
                    t = m.group(1).lower()
                    if t not in known_lever and t not in new_lever:
                        new_lever[t] = {'token': t, 'name': comp or t}

        except Exception as e:
            print(f"   warn: techmap/{fn} - {e}")

    print(f"   New companies found: comeet={len(new_comeet)} gh={len(new_gh)} lever={len(new_lever)}")
    return new_comeet, new_gh, new_lever

# ── COMEET ───────────────────────────────────────────────────────────────────

def comeet_token(slug, uid):
    try:
        r = requests.get(f'https://www.comeet.com/jobs/{slug}/{uid}', timeout=30, headers=HEADERS)
        if not r.ok: return None
        for p in [r'"token"\s*:\s*"([0-9A-F]{16,})"', r"'token'\s*:\s*'([0-9A-F]{16,})'",
                  r'[?&]token=([0-9A-F]{16,})', r'"companyToken"\s*:\s*"([0-9A-F]{16,})"']:
            m = re.search(p, r.text, re.I)
            if m: return m.group(1).upper()
    except: pass
    return None

def run_comeet(companies, tm_new):
    print("\n-- Comeet -----------------------------------------------------------")
    seen = set()
    all_c = []

    # Из companies.json
    for c in companies:
        if not c.get('active', True): continue
        if not c.get('comeet'): continue
        parts = c['comeet'].split('/')
        if len(parts) < 2: continue
        slug, uid = parts[0], parts[1]
        key = f"{slug.lower()}/{uid.upper()}"
        if key not in seen:
            seen.add(key)
            all_c.append({'slug': slug, 'uid': uid, 'name': c['name']})

    # Новые из techmap (не в companies.json ещё)
    for c in tm_new.values():
        key = f"{c['slug'].lower()}/{c['uid'].upper()}"
        if key not in seen:
            seen.add(key)
            all_c.append(c)

    print(f"   Companies: {len(all_c)}")
    jobs = []

    for i, c in enumerate(all_c, 1):
        slug, uid, name = c['slug'], c['uid'], c.get('name', c['slug'])
        print(f"   [{i}/{len(all_c)}] {name}")
        tok = comeet_token(slug, uid)
        if not tok:
            print("      x token not found")
            continue
        try:
            r = requests.get(
                f'https://www.comeet.co/careers-api/2.0/company/{uid}/positions'
                f'?token={tok}&details=false',
                timeout=60, headers=HEADERS
            )
            if not r.ok:
                print(f"      - {r.status_code}")
                continue
            pos = []
            for p in r.json():
                loc = p.get('location') or {}
                wt  = p.get('workplace_type', '')
                city = loc.get('city') or loc.get('name', '')
                if not is_israel(city + ' ' + loc.get('name',''), loc.get('country',''), 'remote' in wt.lower()):
                    continue
                title = p.get('name','')
                pos.append({
                    'title': title, 'company': p.get('company_name') or name,
                    'location': city, 'date': (p.get('time_updated') or '')[:10],
                    'url': p.get('url_active_page') or p.get('url_comeet_hosted_page',''),
                    'department': p.get('department',''), 'workplace_type': wt,
                    'position_type': detect_position_type(title)
                })
            print(f"      + {len(pos)}")
            jobs.extend(pos)
        except Exception as e:
            print(f"      x {e}")

    write_csv(dedup_jobs(jobs),
              ['title','company','location','date','url','department','workplace_type','position_type'],
              f'comeet_jobs_{TODAY}.csv')
    return len(dedup_jobs(jobs))

# ── GREENHOUSE ────────────────────────────────────────────────────────────────

def run_greenhouse(companies, tm_new):
    print("\n-- Greenhouse -------------------------------------------------------")
    seen = set()
    all_t = []

    for c in companies:
        if not c.get('active', True): continue
        if not c.get('greenhouse'): continue
        t = c['greenhouse'].lower()
        if t not in seen:
            seen.add(t)
            all_t.append({'token': t, 'name': c['name']})

    for c in tm_new.values():
        t = c['token'].lower()
        if t not in seen:
            seen.add(t)
            all_t.append(c)

    print(f"   Companies: {len(all_t)}")
    jobs = []

    for i, c in enumerate(all_t, 1):
        token, name = c['token'], c.get('name', c['token'])
        print(f"   [{i}/{len(all_t)}] {name}")
        try:
            r = requests.get(
                f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs',
                timeout=30, headers=HEADERS
            )
            if not r.ok:
                print(f"      - {r.status_code}")
                continue
            pos = []
            for job in r.json().get('jobs', []):
                loc_name = job.get('location', {}).get('name', '')
                offices  = job.get('offices', [])
                country  = next((o.get('country_code','') for o in offices if o.get('country_code')), '')
                office_names = ' '.join(o.get('name','') for o in offices)
                if not is_israel(loc_name + ' ' + office_names, country): continue
                wt   = 'Remote' if re.search(r'\bremote\b', loc_name, re.I) else \
                       ('Hybrid' if re.search(r'\bhybrid\b', loc_name, re.I) else '')
                dept = next((d.get('name','') for d in job.get('departments',[])), '')
                pos.append({
                    'title': job.get('title',''), 'company': name,
                    'location': loc_name.split(',')[0].strip(),
                    'date': (job.get('updated_at') or '')[:10],
                    'url': job.get('absolute_url',''), 'department': dept, 'workplace_type': wt,
                    'position_type': detect_position_type(job.get('title',''))
                })
            print(f"      + {len(pos)}")
            jobs.extend(pos)
        except Exception as e:
            print(f"      x {e}")

    write_csv(dedup_jobs(jobs),
              ['title','company','location','date','url','department','workplace_type','position_type'],
              f'greenhouse_jobs_{TODAY}.csv')
    return len(dedup_jobs(jobs))

# ── LEVER ─────────────────────────────────────────────────────────────────────

def run_lever(companies, tm_new):
    print("\n-- Lever ------------------------------------------------------------")
    seen = set()
    all_t = []

    for c in companies:
        if not c.get('active', True): continue
        if not c.get('lever'): continue
        t = c['lever'].lower()
        if t not in seen:
            seen.add(t)
            all_t.append({'token': t, 'name': c['name']})

    for c in tm_new.values():
        t = c['token'].lower()
        if t not in seen:
            seen.add(t)
            all_t.append(c)

    print(f"   Companies: {len(all_t)}")
    jobs = []

    for i, c in enumerate(all_t, 1):
        token, name = c['token'], c.get('name', c['token'])
        print(f"   [{i}/{len(all_t)}] {name}")
        try:
            r = requests.get(
                f'https://api.lever.co/v0/postings/{token}?mode=json',
                timeout=30, headers=HEADERS
            )
            if not r.ok:
                print(f"      - {r.status_code}")
                continue
            pos = []
            for job in r.json():
                cats  = job.get('categories', {})
                loc   = cats.get('location', '')
                wtype = job.get('workplaceType', '')
                if not is_israel(loc, remote=(wtype == 'remote')): continue
                ts = job.get('createdAt', 0)
                dt = date.fromtimestamp(ts/1000).isoformat() if ts else ''
                pos.append({
                    'title': job.get('text',''), 'company': name,
                    'location': loc, 'date': dt, 'url': job.get('hostedUrl',''),
                    'department': cats.get('team',''), 'workplace_type': wtype,
                    'position_type': detect_position_type(job.get('text',''))
                })
            print(f"      + {len(pos)}")
            jobs.extend(pos)
        except Exception as e:
            print(f"      x {e}")

    write_csv(dedup_jobs(jobs),
              ['title','company','location','date','url','department','workplace_type','position_type'],
              f'lever_jobs_{TODAY}.csv')
    return len(dedup_jobs(jobs))

# ── ASHBY ─────────────────────────────────────────────────────────────────────

def run_ashby(companies):
    print("\n-- Ashby -----------------------------------------------------------")
    seen = set()
    all_t = []

    for c in companies:
        if not c.get('active', True): continue
        if not c.get('ashby'): continue
        t = c['ashby'].lower()
        if t not in seen:
            seen.add(t)
            all_t.append({'token': t, 'name': c['name']})

    print(f"   Companies: {len(all_t)}")
    jobs = []

    for i, c in enumerate(all_t, 1):
        token, name = c['token'], c.get('name', c['token'])
        print(f"   [{i}/{len(all_t)}] {name}")
        try:
            r = requests.get(
                f'https://api.ashbyhq.com/posting-api/job-board/{token}',
                timeout=30, headers=HEADERS
            )
            if not r.ok:
                print(f"      - {r.status_code}")
                continue
            pos = []
            for job in r.json().get('jobPostings', []):
                if not job.get('isListed', True): continue
                loc    = job.get('locationName', '')
                remote = job.get('locationIsRemote', False)
                if not is_israel(loc, remote=remote): continue
                wt = 'Remote' if remote else ('Hybrid' if 'hybrid' in loc.lower() else '')
                pos.append({
                    'title': job.get('title',''), 'company': name,
                    'location': loc, 'date': (job.get('publishedDate') or '')[:10],
                    'url': job.get('externalLink') or job.get('jobUrl',''),
                    'department': job.get('departmentName',''), 'workplace_type': wt,
                    'position_type': detect_position_type(job.get('title',''))
                })
            print(f"      + {len(pos)}")
            jobs.extend(pos)
        except Exception as e:
            print(f"      x {e}")

    write_csv(dedup_jobs(jobs),
              ['title','company','location','date','url','department','workplace_type','position_type'],
              f'ashby_jobs_{TODAY}.csv')
    return len(dedup_jobs(jobs))

# ── WORKABLE ──────────────────────────────────────────────────────────────────

def run_workable(companies):
    print("\n-- Workable --------------------------------------------------------")
    seen = set()
    all_t = []

    for c in companies:
        if not c.get('active', True): continue
        if not c.get('workable'): continue
        t = c['workable'].lower()
        if t not in seen:
            seen.add(t)
            all_t.append({'token': t, 'name': c['name']})

    print(f"   Companies: {len(all_t)}")
    jobs = []

    for i, c in enumerate(all_t, 1):
        token, name = c['token'], c.get('name', c['token'])
        print(f"   [{i}/{len(all_t)}] {name}")
        try:
            r = requests.get(
                f'https://apply.workable.com/api/v1/widget/accounts/{token}',
                timeout=30, headers=HEADERS
            )
            if not r.ok:
                print(f"      - {r.status_code}")
                continue
            pos = []
            for job in r.json().get('jobs', []):
                loc     = job.get('location', {})
                city    = loc.get('city','')
                country = loc.get('country_code','')
                remote  = loc.get('telecommuting', False)
                loc_str = loc.get('location_str','') or f"{city}, {loc.get('country','')}"
                if not is_israel(loc_str + ' ' + city, country, remote): continue
                wt = 'Remote' if remote else ''
                pos.append({
                    'title': job.get('title',''), 'company': name,
                    'location': city or loc_str.split(',')[0].strip(),
                    'date': (job.get('created_at') or '')[:10],
                    'url': job.get('url',''), 'department': job.get('department',''),
                    'workplace_type': wt,
                    'position_type': detect_position_type(job.get('title',''))
                })
            print(f"      + {len(pos)}")
            jobs.extend(pos)
        except Exception as e:
            print(f"      x {e}")

    write_csv(dedup_jobs(jobs),
              ['title','company','location','date','url','department','workplace_type','position_type'],
              f'workable_jobs_{TODAY}.csv')
    return len(dedup_jobs(jobs))

# ── BREEZY ────────────────────────────────────────────────────────────────────

def run_breezy(companies):
    print("\n-- Breezy ----------------------------------------------------------")
    seen = set()
    all_t = []

    for c in companies:
        if not c.get('active', True): continue
        if not c.get('breezy'): continue
        t = c['breezy'].lower()
        if t not in seen:
            seen.add(t)
            all_t.append({'token': t, 'name': c['name']})

    print(f"   Companies: {len(all_t)}")
    jobs = []

    for i, c in enumerate(all_t, 1):
        token, name = c['token'], c.get('name', c['token'])
        print(f"   [{i}/{len(all_t)}] {name}")
        try:
            r = requests.get(
                f'https://api.breezy.hr/v3/company/{token}/positions?state=published',
                timeout=30, headers=HEADERS
            )
            if not r.ok:
                print(f"      - {r.status_code}")
                continue
            pos = []
            for job in r.json():
                loc    = job.get('location', {})
                city   = loc.get('city','')
                country= loc.get('country', {}).get('id','')
                remote = job.get('remote_location', False)
                if not is_israel(city, country, remote): continue
                wt = 'Remote' if remote else ''
                pos.append({
                    'title': job.get('name',''), 'company': name,
                    'location': city, 'date': (job.get('updated_date') or '')[:10],
                    'url': f"https://breezy.hr/p/{job.get('friendly_id','')}",
                    'department': job.get('department',''), 'workplace_type': wt,
                    'position_type': detect_position_type(job.get('name',''))
                })
            print(f"      + {len(pos)}")
            jobs.extend(pos)
        except Exception as e:
            print(f"      x {e}")

    write_csv(dedup_jobs(jobs),
              ['title','company','location','date','url','department','workplace_type','position_type'],
              f'breezy_jobs_{TODAY}.csv')
    return len(dedup_jobs(jobs))

# ── MITAM ─────────────────────────────────────────────────────────────────────

def run_mitam():
    print("\n-- Mitam (מגזר שלישי) -----------------------------------------------")
    SUPABASE_URL = "https://cbqnuxmnmimbdhmgfkwl.supabase.co/rest/v1/jobs"
    API_KEY = os.environ.get('MITAM_API_KEY', '')
    if not API_KEY:
        print("   x MITAM_API_KEY not set")
        return 0
    try:
        r = requests.get(SUPABASE_URL,
            params={
                "select": "id,title,location,job_type,field,created_at,slug,organizations(name)",
                "is_active": "eq.true",
                "order": "created_at.desc",
            },
            headers={
                "apikey": API_KEY,
                "Authorization": f"Bearer {API_KEY}",
                "Origin": "https://www.mitam-hr.org",
                "Referer": "https://www.mitam-hr.org/",
                "Accept": "application/json",
            },
            timeout=30)
        if not r.ok:
            print(f"   - {r.status_code} {r.text[:100]}")
            return 0
        jobs = []
        for j in r.json():
            if not j.get("title"): continue
            org  = j.get("organizations") or {}
            name = org.get("name", "") if isinstance(org, dict) else ""
            slug = j.get("slug") or str(j.get("id", ""))
            url  = f"https://www.mitam-hr.org/jobs/{slug}" if slug else "https://www.mitam-hr.org/Jobs"
            jobs.append({
                "title": (j.get("title") or "").strip(),
                "company": name or "עמותה",
                "location": (j.get("location") or "").strip(),
                "date": (j.get("created_at") or "")[:10] or TODAY,
                "url": url,
                "department": (j.get("field") or "").strip(),
                "workplace_type": (j.get("job_type") or "").strip(),
                "position_type": detect_position_type((j.get("title") or "")),
            })
        print(f"   + {len(jobs)}")
        write_csv(dedup_jobs(jobs),
                  ['title','company','location','date','url','department','workplace_type','position_type'],
                  f'mitam_jobs_{TODAY}.csv')
        return len(dedup_jobs(jobs))
    except Exception as e:
        print(f"   x {e}")
        return 0

# ── WEIZMANN ──────────────────────────────────────────────────────────────────

def run_weizmann():
    print("\n-- Weizmann Institute -----------------------------------------------")
    try:
        from bs4 import BeautifulSoup
        r = requests.get(
            "https://www.weizmann.ac.il/career/jobs",
            headers={**HEADERS, "Accept-Language": "he-IL,he;q=0.9,en;q=0.8"},
            timeout=30)
        if not r.ok:
            print(f"   - {r.status_code}")
            return 0
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        seen = set()
        for link in soup.select("a[href*='/career/jobs/']"):
            href = link.get("href", "")
            last = href.rstrip("/").split("?")[0].split("/")[-1]
            if not last or last == "jobs": continue
            url = "https://www.weizmann.ac.il" + href if href.startswith("/") else href
            if url in seen: continue
            seen.add(url)
            title_el = link.select_one("h2") or link.select_one("h3")
            title = (title_el.get_text(strip=True) if title_el else link.get_text(strip=True)).strip()
            if not title: continue
            department = ""
            workplace_type = ""
            for dt in link.select("dt"):
                dd = dt.find_next_sibling("dd")
                if not dd: continue
                label = dt.get_text(strip=True)
                value = dd.get_text(strip=True)
                if "קטגוריה" in label: department = value
                elif "היקף" in label: workplace_type = value
            jobs.append({
                "title": title, "company": "מכון ויצמן למדע",
                "location": "רחובות", "date": TODAY, "url": url,
                "department": department, "workplace_type": workplace_type,
                "position_type": detect_position_type(title),
            })
        print(f"   + {len(jobs)}")
        write_csv(jobs,
                  ["title","company","location","date","url","department","workplace_type","position_type"],
                  f"weizmann_jobs_{TODAY}.csv")
        return len(jobs)
    except Exception as e:
        print(f"   x {e}")
        return 0

# ── BGU ───────────────────────────────────────────────────────────────────────

def run_bgu():
    print("\n-- BGU --------------------------------------------------------------")
    try:
        from bs4 import BeautifulSoup
        URL = "https://bguhr.my.salesforce-sites.com/Gius?mode=external"
        def parse_date(s):
            m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', s)
            if not m: return TODAY
            d, mo, y = m.group(1), m.group(2), m.group(3)
            if len(y) == 2: y = "20" + y
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
        r = requests.get(URL, headers={**HEADERS,
            "Accept": "text/html,application/xhtml+xml",
            "Referer": "https://bguhr.my.salesforce-sites.com/"}, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        seen = set()
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 3: continue
            texts = [c.get_text(strip=True) for c in cells]
            if any(h in texts for h in ["שם המשרה","מס' משרה","Name"]): continue
            job_id    = texts[0].strip() if texts else ""
            title     = texts[1].strip() if len(texts) > 1 else ""
            date_str  = texts[3].strip() if len(texts) > 3 else (texts[2].strip() if len(texts) > 2 else "")
            if not title: continue
            if job_id in seen: continue
            seen.add(job_id or title)
            display_title = f"{title} (מס' {job_id})" if job_id else title
            jobs.append({
                "title": display_title, "company": "אוניברסיטת בן-גוריון בנגב",
                "location": "באר שבע", "date": TODAY,
                "deadline": parse_date(date_str) if date_str else "",
                "url": URL, "department": "", "workplace_type": "onsite",
                "position_type": detect_position_type(display_title),
            })
        print(f"   + {len(jobs)}")
        write_csv(jobs,
                  ["title","company","location","date","deadline","url","department","workplace_type","position_type"],
                  f"bgu_jobs_{TODAY}.csv")
        return len(jobs)
    except Exception as e:
        print(f"   x {e}")
        return 0

# ── HUJI ──────────────────────────────────────────────────────────────────────

def run_huji():
    print("\n-- HUJI Career ------------------------------------------------------")
    import time
    try:
        from bs4 import BeautifulSoup
        BASE_H   = "https://hujicareer.co.il"
        JOBS_URL = BASE_H + "/jobs/"
        REMOTE_KW = re.compile(r'מהבית|remote', re.I)
        HYBRID_KW = re.compile(r'היברידי|hybrid', re.I)
        LOC_KW = ["ירושלים","תל אביב","רמת גן","הרצליה","מהבית","חיפה",
                  "באר שבע","רחובות","פתח תקווה","ראשון לציון","נתניה"]

        def fetch(url):
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
                if r.status_code == 404: return None
                r.raise_for_status()
                return BeautifulSoup(r.text, "html.parser")
            except Exception as e:
                print(f"   [warn] {e}"); return None

        def parse(soup):
            jobs = []
            cards = soup.select("article") or soup.select(".jet-listing-grid__item")
            for card in cards:
                title_el = card.select_one("h4.jet-listing-dynamic-field__content") or \
                           card.select_one("h4") or card.select_one("h3")
                title = title_el.get_text(strip=True) if title_el else ""
                if not title: continue
                link_el = card.select_one("a.elementor-button") or card.select_one("a[href*='/jobs/']")
                url = ""
                if link_el:
                    href = link_el.get("href","")
                    if href and href.rstrip("/") != BASE_H + "/jobs":
                        url = href if href.startswith("http") else BASE_H + href
                if not url: continue
                text    = card.get_text(" ", strip=True)
                img     = card.select_one("img[alt]")
                company = img.get("alt","").strip() if img else ""
                if company and len(company) > 40: company = ""
                pub_date = ""
                m = re.search(r'(\d{2}/\d{2}/\d{4})', text)
                if m:
                    p = m.group(1).split("/")
                    pub_date = f"{p[2]}-{p[1]}-{p[0]}"
                location = next((kw for kw in LOC_KW if kw in text), "")
                wt = ("hybrid" if HYBRID_KW.search(title+" "+text[:100])
                      else "remote" if REMOTE_KW.search(title+" "+location)
                      else "onsite")
                jobs.append({
                    "title": title, "company": company or "HUJI Career",
                    "location": location, "date": pub_date or TODAY, "url": url,
                    "department": "", "workplace_type": wt,
                    "level": "junior", "source": "huji",
                    "position_type": detect_position_type(title),
                })
            return jobs

        all_jobs = []; seen = set()
        for page in range(1, 20):
            url  = JOBS_URL if page == 1 else BASE_H + f"/jobs/page/{page}/"
            soup = fetch(url)
            if not soup: break
            jobs = parse(soup)
            if not jobs: break
            new = 0
            for j in jobs:
                if j["url"] not in seen:
                    seen.add(j["url"]); all_jobs.append(j); new += 1
            print(f"   Page {page}: +{new} (total {len(all_jobs)})")
            if not soup.select_one("a.next.page-numbers, .nav-next a"): break
            time.sleep(0.5)

        print(f"   + {len(all_jobs)}")
        write_csv(all_jobs,
                  ["title","company","location","date","url","department","workplace_type","level","source","position_type"],
                  f"huji_jobs_{TODAY}.csv")
        return len(all_jobs)
    except Exception as e:
        print(f"   x {e}")
        return 0

# ── TECHNION ──────────────────────────────────────────────────────────────────

def run_technion():
    print("\n-- Technion HR ------------------------------------------------------")
    try:
        from bs4 import BeautifulSoup
        URL = "https://hr.technion.ac.il/positions/"
        r = requests.get(URL, headers={**HEADERS,
            "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
            "Referer": "https://hr.technion.ac.il/"}, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        seen = set()
        for card in soup.select("div.wrapper-job"):
            title_el = card.select_one("span.col-3")
            dept_el  = card.select_one("span.col-2")
            link_el  = card.select_one("a.wrap-btn") or card.select_one("div.wrap-btn a")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title: continue
            dept  = dept_el.get_text(strip=True) if dept_el else ""
            jobid = ""
            url   = URL
            if link_el:
                href = link_el.get("href","")
                if "jobid=" in href:
                    jobid = href.split("jobid=")[-1]
                    url   = f"https://hr.technion.ac.il/positions/?jobid={jobid}"
                elif href.startswith("http"):
                    url = href
            key = jobid or title
            if key in seen: continue
            seen.add(key)
            jobs.append({
                "title": title, "company": "הטכניון - מכון טכנולוגי לישראל",
                "location": "חיפה", "date": TODAY, "url": url,
                "department": dept, "workplace_type": "onsite",
                "position_type": detect_position_type(title),
            })
        print(f"   + {len(jobs)}")
        write_csv(jobs,
                  ["title","company","location","date","url","department","workplace_type","position_type"],
                  f"technion_jobs_{TODAY}.csv")
        return len(jobs)
    except Exception as e:
        print(f"   x {e}")
        return 0

# ── MACCABI ───────────────────────────────────────────────────────────────────

def run_maccabi():
    """Fetches Maccabi jobs via JSON API (POST).
    Endpoint: POST https://www.maccabi4u.co.il/Umbraco/api/SearchJobsApi/FilterJobs
    Payload fields: FreeText, ResultsPerPage, PageNumber, AdvertisingDestination
    """
    print("\n-- Maccabi Health Services (API) ------------------------------------")
    API_URL = "https://www.maccabi4u.co.il/Umbraco/api/SearchJobsApi/FilterJobs"
    HEADERS_MAC = {
        **HEADERS,
        "Content-Type":   "application/json",
        "Accept":         "application/json",
        "Origin":         "https://www.maccabi4u.co.il",
        "Referer":        "https://www.maccabi4u.co.il/careers/search-job-positions/",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    }
    RESULTS_PER_PAGE = 100
    jobs = []
    seen = set()
    page = 0

    try:
        # First call — discover total
        payload = {
            "FreeText":            "",
            "ResultsPerPage":      RESULTS_PER_PAGE,
            "PageNumber":          0,
            "AdvertisingDestination": 1,
        }
        r = requests.post(API_URL, json=payload, headers=HEADERS_MAC, timeout=30)
        if not r.ok:
            print(f"   - HTTP {r.status_code}")
            return 0
        data         = r.json()
        total        = data.get("TotalResults", 0)
        total_pages  = (total + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
        print(f"   Total jobs: {total}  pages: {total_pages}")

        def _parse_page(data):
            for item in data.get("Results", []):
                title = (item.get("Description") or "").strip()
                if not title:
                    continue
                url = (item.get("JobUrl") or "").strip()
                if not url:
                    job_id = item.get("JobId") or ""
                    if job_id:
                        url = f"https://www.maccabi4u.co.il/careers/all-positions/{job_id}/"
                if not url:
                    continue
                if url in seen:
                    continue
                seen.add(url)

                # Location: first area description
                areas = item.get("Areas") or []
                location = areas[0].get("Description", "ישראל") if areas else "ישראל"

                # Department
                dept = (item.get("Profession") or "").strip()

                # Description: strip HTML tags from Notes
                notes_raw = (item.get("Notes") or "").strip()
                import re as _re
                description = _re.sub(r'<[^>]+>', ' ', notes_raw)
                description = _re.sub(r'&nbsp;', ' ', description)
                description = _re.sub(r'\s{2,}', ' ', description).strip()

                jobs.append({
                    "title":          title,
                    "company":        "מכבי שירותי בריאות",
                    "location":       location,
                    "date":           TODAY,
                    "url":            url,
                    "department":     dept,
                    "workplace_type": "onsite",
                    "source":         "maccabi",
                    "description":    description,
                    "position_type":  detect_position_type(title, description),
                })

        _parse_page(data)
        print(f"   Page 0: {len(jobs)} jobs")

        for pg in range(1, total_pages):
            payload["PageNumber"] = pg
            try:
                r = requests.post(API_URL, json=payload, headers=HEADERS_MAC, timeout=30)
                if not r.ok:
                    print(f"   - page {pg}: HTTP {r.status_code}")
                    break
                _parse_page(r.json())
                print(f"   Page {pg}: total so far {len(jobs)}")
            except Exception as e:
                print(f"   x page {pg}: {e}")
                break

        print(f"   + {len(jobs)}")
        write_csv(jobs,
                  ["title","company","location","date","url","department","workplace_type","source","description","position_type"],
                  f"maccabi_jobs_{TODAY}.csv")
        return len(jobs)
    except Exception as e:
        print(f"   x {e}")
        return 0

# ── LEUMIT ────────────────────────────────────────────────────────────────────

def run_leumit():
    print("\n-- Leumit Health Services -------------------------------------------")
    try:
        from bs4 import BeautifulSoup
        BASE     = "https://www.leumit.co.il"
        LIST_URL = BASE + "/jobs/work-in-leumit/"
        HEADERS_LEU = {**HEADERS,
            "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
            "Referer": BASE + "/jobs/"}

        r = requests.get(LIST_URL, headers=HEADERS_LEU, timeout=30)
        if not r.ok:
            print(f"   - {r.status_code}")
            return 0

        soup = BeautifulSoup(r.text, "html.parser")

        # All job links: /jobs/work-in-leumit/{id-or-slug}/
        # They appear in swiper slides and in the main menu
        job_links = set()
        for a in soup.select("a[href*='/jobs/work-in-leumit/']"):
            href = a.get("href", "")
            # Exclude the base listing page itself
            slug = href.rstrip("/").split("/jobs/work-in-leumit/")[-1]
            if slug and slug not in ("", "work-in-leumit"):
                full = (BASE + href) if href.startswith("/") else href
                job_links.add(full)

        print(f"   Found {len(job_links)} job links")
        jobs = []
        seen = set()

        for url in sorted(job_links):
            if url in seen:
                continue
            seen.add(url)
            try:
                jr = requests.get(url, headers=HEADERS_LEU, timeout=20)
                if not jr.ok:
                    continue
                jsoup = BeautifulSoup(jr.text, "html.parser")

                title_el = jsoup.select_one("h1")
                title    = title_el.get_text(strip=True) if title_el else ""
                if not title:
                    continue

                # location is in div.sub-title > p (first p)
                loc_el   = jsoup.select_one("div.sub-title p")
                location = loc_el.get_text(strip=True) if loc_el else "ישראל"

                # description: main job body
                import re as _re
                desc_el = (
                    jsoup.select_one("div.job-description") or
                    jsoup.select_one("div.job-content") or
                    jsoup.select_one("div.content-area") or
                    jsoup.select_one("article") or
                    jsoup.select_one("main")
                )
                if desc_el:
                    for noise in desc_el.select("nav,header,footer,script,style"):
                        noise.decompose()
                    description = _re.sub(r"\s{2,}", " ", desc_el.get_text(separator=" ", strip=True)).strip()
                else:
                    description = ""

                jobs.append({
                    "title":          title,
                    "company":        "לאומית שירותי בריאות",
                    "location":       location,
                    "date":           TODAY,
                    "url":            url,
                    "department":     "",
                    "workplace_type": "onsite",
                    "source":         "leumit",
                    "description":    description,
                    "position_type":  detect_position_type(title, description),
                })
            except Exception as e:
                print(f"   warn {url}: {e}")
                continue

        print(f"   + {len(jobs)}")
        write_csv(jobs,
                  ["title","company","location","date","url","department","workplace_type","source","description","position_type"],
                  f"leumit_jobs_{TODAY}.csv")
        return len(jobs)
    except Exception as e:
        print(f"   x {e}")
        return 0

# ── MEUHEDET ──────────────────────────────────────────────────────────────────

def run_meuhedet():
    """Fetches Meuhedet jobs via Algolia API.
    App:   HCPGNF9T5W
    Key:   0cd884fd17bbf3fb3cf348fcd50dbe8b
    Index: prod_jobs
    Tag:   602_37
    """
    print("\n-- Meuhedet Health Services (Algolia) -------------------------------")
    ALGOLIA_URL = (
        "https://hcpgnf9t5w-dsn.algolia.net/1/indexes/*/queries"
        "?x-algolia-agent=Algolia%20for%20JavaScript%20(4.14.2)%3B%20Browser%20(lite)"
        "&x-algolia-api-key=0cd884fd17bbf3fb3cf348fcd50dbe8b"
        "&x-algolia-application-id=HCPGNF9T5W"
    )
    HITS_PER_PAGE = 1000
    jobs = []
    seen = set()

    import re as _re

    def _query_payload(page=0):
        params = (
            f"maxValuesPerFacet=1000"
            f"&page={page}"
            f"&tagFilters=%5B%5B%22602_37%22%5D%5D"
            f"&filters=ContentRating%3APublic"
            f"&hitsPerPage={HITS_PER_PAGE}"
            f"&facets=%5B%22GeoArea%22%2C%22Specialization%22%5D"
        )
        return {"requests": [{"indexName": "prod_jobs", "params": params}]}

    try:
        headers_alg = {
            **HEADERS,
            "Content-Type": "application/json",
            "Accept":       "application/json",
        }

        # First page — discover total
        r = requests.post(ALGOLIA_URL, json=_query_payload(0), headers=headers_alg, timeout=30)
        if not r.ok:
            print(f"   - HTTP {r.status_code}: {r.text[:200]}")
            return 0

        result     = r.json()["results"][0]
        nb_pages   = result.get("nbPages", 1)
        nb_hits    = result.get("nbHits", 0)
        print(f"   Total jobs: {nb_hits}  pages: {nb_pages}")

        def _parse_hits(hits):
            for h in hits:
                title = (h.get("JobDescription") or h.get("Description") or "").strip()
                if not title:
                    continue
                job_num = str(h.get("JobNumber") or h.get("Id") or "").strip()
                url = f"https://www.meuhedet.co.il/?id={job_num}&j=1" if job_num else ""
                if not url:
                    continue
                if url in seen:
                    continue
                seen.add(url)

                location = (h.get("City") or h.get("GeoArea") or "ישראל").strip()
                dept     = (h.get("Specialization") or "").strip()

                # Date from JobTimeSortAttr (Unix ms)
                ts = h.get("JobTimeSortAttr")
                if ts:
                    from datetime import datetime as _dt
                    try:
                        pub_date = _dt.utcfromtimestamp(ts / 1000).date().isoformat()
                    except Exception:
                        pub_date = TODAY
                else:
                    raw_date = (h.get("UpdateDate") or h.get("CreatedDate") or "")[:10]
                    pub_date = raw_date if raw_date else TODAY

                # Description: strip HTML from Notes
                notes_raw = (h.get("Notes") or "").strip()
                description = _re.sub(r'<[^>]+>', ' ', notes_raw)
                description = _re.sub(r'&nbsp;', ' ', description)
                description = _re.sub(r'\s{2,}', ' ', description).strip()

                jobs.append({
                    "title":          title,
                    "company":        "קופת חולים מאוחדת",
                    "location":       location,
                    "date":           pub_date,
                    "url":            url,
                    "department":     dept,
                    "workplace_type": "onsite",
                    "source":         "meuhedet",
                    "description":    description,
                    "position_type":  detect_position_type(title, description),
                })

        _parse_hits(result.get("hits", []))
        print(f"   Page 0: {len(jobs)} jobs")

        for pg in range(1, nb_pages):
            try:
                r = requests.post(ALGOLIA_URL, json=_query_payload(pg), headers=headers_alg, timeout=30)
                if not r.ok:
                    print(f"   - page {pg}: HTTP {r.status_code}")
                    break
                _parse_hits(r.json()["results"][0].get("hits", []))
                print(f"   Page {pg}: total so far {len(jobs)}")
            except Exception as e:
                print(f"   x page {pg}: {e}")
                break

        print(f"   + {len(jobs)}")
        write_csv(jobs,
                  ["title","company","location","date","url","department","workplace_type","source","description","position_type"],
                  f"meuhedet_jobs_{TODAY}.csv")
        return len(jobs)
    except Exception as e:
        print(f"   x {e}")
        return 0

# ── History snapshot ──────────────────────────────────────────────────────────

def update_history(results):
    import os, glob
    HIST   = 'history.csv'
    FIELDS = ['date','total','cyber','fintech','health','media','hardware',
              'defence','automotive','gaming','public','industrial','retail',
              'agritech','foodtech','rd','product','data','design','sales',
              'marketing','operations','support','management','intern',
              'remote','hybrid','onsite',
              'maternity_cover','part_time','freelance','internship',
              'linkedin','comeet','greenhouse','lever','ashby','workable','breezy']

    rows = []
    for src in ['comeet','greenhouse','lever','ashby','workable','breezy']:
        fname = f'{src}_jobs_{TODAY}.csv'
        if not os.path.exists(fname): continue
        with open(fname, encoding='utf-8-sig') as f:
            rows.extend(list(csv.DictReader(f)))

    li_files = sorted(glob.glob('linkedin_jobs_*.csv'))
    li_rows  = []
    if li_files:
        with open(li_files[-1], encoding='utf-8-sig') as f:
            li_rows = list(csv.DictReader(f))

    all_rows = rows + li_rows

    def g(row, *keys):
        for k in keys:
            v = (row.get(k) or row.get(k.title()) or '').strip()
            if v: return v
        return ''

    SECTOR_KW = {
        'cyber':      re.compile(r'cyber|security|firewall|malware|threat|siem|edr|xdr|zero.?trust|vulnerab|appsec', re.I),
        'fintech':    re.compile(r'fintech|payment|bank|financial|credit|insur|trading|crypto|blockchain|lending|payroll|neobank', re.I),
        'health':     re.compile(r'health|medical|medtech|biotech|pharma|genomic|clinical|patient|therap|diagnos|imaging|dental|cardio', re.I),
        'media':      re.compile(r'media|adtech|advertis|broadcast|streaming|entertainment|influencer|social media', re.I),
        'hardware':   re.compile(r'semiconductor|chip|silicon|processor|fpga|embedded|firmware|sensor|radar|lidar|photonic|robotic|circuit|wafer', re.I),
        'defence':    re.compile(r'defense|defence|military|weapon|missile|uav|unmanned|aerospace|tactical|drone', re.I),
        'automotive': re.compile(r'automotive|vehicle|fleet|electric vehicle|autonomous|adas|self.?driving|telematics|mobility|charging', re.I),
        'gaming':     re.compile(r'gaming|casino|esport|lottery|mobile game|game studio|slot|poker|bingo|fantasy sport', re.I),
        'public':     re.compile(r'government|municipal|govtech|ministry|smart city|public sector|civic tech|e.?gov|federal', re.I),
        'industrial': re.compile(r'industrial|manufacturing|factory|production|supply chain|logistics|warehouse|scada|automation|industry 4|iot', re.I),
        'retail':     re.compile(r'retail|e.?commerce|marketplace|fashion|apparel|consumer goods|grocery|dtc|point.?of.?sale', re.I),
        'agritech':   re.compile(r'agro|agriculture|agritech|farm|crop|irrigation|precision farm|soil|fertilizer|livestock|harvest', re.I),
        'foodtech':   re.compile(r'food|foodtech|nutrition|protein|plant.?based|cultivated meat|fermentation|beverage|culinary|alternative protein', re.I),
    }
    ROLE_KW = {
        'intern':     re.compile(r'intern|internship|student|trainee|apprentice|co.?op|graduate program', re.I),
        'management': re.compile(r'vp|vice president|cto|coo|cpo|ciso|cmo|cfo|ceo|head of|director|general manager|chief ', re.I),
        'rd':         re.compile(r'engineer|developer|devops|sre|architect|backend|frontend|full.?stack|mobile|firmware|embedded|platform|security research|qa|tester|sdet|software', re.I),
        'product':    re.compile(r'product manager|product owner|pm|product lead|program manager|project manager|scrum', re.I),
        'data':       re.compile(r'data scientist|data engineer|data analyst|analytics engineer|ml engineer|machine learning|deep learning|ai engineer|bi engineer|business intelligence|llm|computer vision', re.I),
        'design':     re.compile(r'designer|ux|ui|user experience|figma|product design|visual design|graphic', re.I),
        'sales':      re.compile(r'account executive|account manager|sales engineer|business development|bd|sdr|bdr|pre.?sales|revenue|partnership', re.I),
        'marketing':  re.compile(r'marketing|growth|content|seo|sem|brand|demand generation|campaign|copywriter|social media|pr|field marketing', re.I),
        'support':    re.compile(r'customer success|customer support|technical support|implementation|solutions engineer|integration engineer|onboarding|professional services', re.I),
        'operations': re.compile(r'hr|human resources|recruiter|talent acquisition|finance|accounting|legal|procurement|office manager|operations|ops|admin|it manager|supply chain', re.I),
    }

    def classify_sector(company):
        c = company.lower()
        for sec, rx in SECTOR_KW.items():
            if rx.search(c): return sec
        return ''

    def classify_role(title):
        for role, rx in ROLE_KW.items():
            if rx.search(title): return role
        return ''

    counts = {f: 0 for f in FIELDS}
    counts['date']       = TODAY
    counts['total']      = len(all_rows)
    counts['linkedin']   = len(li_rows)
    counts['comeet']     = results.get('comeet', 0)
    counts['greenhouse'] = results.get('greenhouse', 0)
    counts['lever']      = results.get('lever', 0)
    counts['ashby']      = results.get('ashby', 0)
    counts['workable']   = results.get('workable', 0)
    counts['breezy']     = results.get('breezy', 0)

    for row in all_rows:
        title   = g(row,'title','job_title','position')
        company = g(row,'company','company_name','employer')
        wt      = g(row,'workplace_type','work_type','location').lower()
        sec  = classify_sector(company)
        if sec: counts[sec] = counts.get(sec, 0) + 1
        role = classify_role(title)
        if role: counts[role] = counts.get(role, 0) + 1
        if 'remote' in wt:   counts['remote'] += 1
        elif 'hybrid' in wt: counts['hybrid'] += 1
        elif wt:             counts['onsite'] += 1

        pt = g(row, 'position_type').lower()
        if pt in ('maternity_cover', 'part_time', 'freelance', 'internship'):
            counts[pt] = counts.get(pt, 0) + 1

    existing = []
    if os.path.exists(HIST):
        with open(HIST, encoding='utf-8-sig') as f:
            existing = list(csv.DictReader(f))
    existing = [r for r in existing if r.get('date') != TODAY]
    existing.append(counts)

    with open(HIST, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(existing)
    print(f"   -> history.csv updated ({len(existing)} days)")

# ── Summary report ────────────────────────────────────────────────────────────

def print_summary(results):
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    total = 0
    for src, count in results.items():
        status = "✅" if isinstance(count, int) and count > 0 else ("⚠️ 0 jobs" if count == 0 else "❌")
        print(f"   {src:15}: {count if isinstance(count, int) else count} {status}")
        if isinstance(count, int): total += count
    print(f"   {'TOTAL':15}: {total}")
    print("="*60)

    if total == 0:
        print("\n❌ CRITICAL: All sources returned 0 jobs. Exiting with error.")
        sys.exit(1)

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"=== fetch_jobs.py {TODAY} ===\n")

    companies = load_companies()

    print("\nScanning techmap for new companies...")
    tm_comeet, tm_gh, tm_lever = scan_techmap()

    results = {}
    results['comeet']     = run_comeet(companies, tm_comeet)
    results['greenhouse'] = run_greenhouse(companies, tm_gh)
    results['lever']      = run_lever(companies, tm_lever)
    results['ashby']      = run_ashby(companies)
    results['workable']   = run_workable(companies)
    results['breezy']     = run_breezy(companies)
    results['maccabi']    = run_maccabi()
    results['leumit']     = run_leumit()
    results['meuhedet']   = run_meuhedet()
    results['mitam']      = run_mitam()
    results['weizmann']   = run_weizmann()
    results['bgu']        = run_bgu()
    results['huji']       = run_huji()
    results['technion']   = run_technion()

    print("\nUpdating history...")
    update_history(results)

    print_summary(results)
    print("\n=== All done ===")

if __name__ == '__main__':
    main()
