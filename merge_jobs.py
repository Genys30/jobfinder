"""
merge_jobs.py  —  run after fetch_jobs.py
Merges all dated CSV files into a single jobs.json for the frontend.
"""
import csv, json, glob, os
from collections import Counter
os.chdir(os.path.dirname(os.path.abspath(__file__)))

COMPANY_ALIASES = {
    'solaredge technologies': 'SolarEdge',
    'nvidia ai':              'NVIDIA',
    'nvidia':                 'NVIDIA',
}

def normalize_company(name):
    if not name: return name
    return COMPANY_ALIASES.get(name.lower().strip(), name)

# (src_key, src_label, optional_glob_pattern)
SOURCES = [
    ('comeet',                       'comeet'),
    ('greenhouse',                   'greenhouse'),
    ('lever',                        'lv'),
    ('ashby',                        'ab'),
    ('workable',                     'wk'),
    ('gotfriends',                   'gf'),
    ('topmatch',                     'ichilov'),
    ('mitam',                        'mt'),
    ('weizmann',                     'weizmann'),
    ('bgu',                          'bgu'),
    ('huji_alumni',                  'huji-alumni'),
    ('huji_positions',               'huji'),
    ('technion',                     'technion'),
    ('tau',                          'tau'),
    ('haifa',                        'haifa'),
    ('bar',                          'bar'),
    ('bar_alumni',                   'bar-alumni'),
    ('bis',                          'bis'),
    ('kpmg',                         'kpmg'),
    ('deloitte',                     'deloitte'),
    ('ey',                           'ey'),
    ('joint',                        'joint'),
    ('clalit',                       'clalit'),
    ('szmc',                         'szmc'),
    ('hadassah',                     'hadassah'),
    ('mod',                          'mod'),
    ('osem',                         'osem'),
    ('jobs_telegram_biltiformali',   'telegram',  'jobs_telegram_biltiformali_*.csv'),
]

all_jobs = []
seen_urls = set()

for entry in SOURCES:
    src_key, src_label = entry[0], entry[1]
    pattern = entry[2] if len(entry) > 2 else f'{src_key}_jobs_*.csv'
    files = sorted(glob.glob(pattern))
    if not files:
        continue
    latest = files[-1]
    try:
        with open(latest, encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                url = (row.get('url') or '').strip()
                title = (row.get('title') or '').strip()
                location = (row.get('location') or row.get('city') or '').strip()
                company = normalize_company((row.get('company') or '').strip())
                date = (row.get('date') or row.get('date_posted') or '').strip()
                department = (row.get('department') or '').strip()
                workplace_type = (row.get('workplace_type') or '').strip()
                description = (row.get('description') or row.get('summary') or '').strip()

                if not title:
                    continue

                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)

                all_jobs.append({
                    'title':          title,
                    'company':        company,
                    'location':       location,
                    'date':           date,
                    'url':            url,
                    'department':     department,
                    'workplace_type': workplace_type,
                    'description':    description[:1500] if description else '',
                    'source':         src_label,
                })
    except Exception as e:
        print(f'  warn: {src_key} — {e}')

with open('jobs.json', 'w', encoding='utf-8') as f:
    json.dump(all_jobs, f, ensure_ascii=False, separators=(',', ':'))

size_kb = os.path.getsize('jobs.json') // 1024
src_counts = Counter(j['source'] for j in all_jobs)
print(f'Merged {len(all_jobs)} jobs → jobs.json ({size_kb} KB)')
for entry in SOURCES:
    src_key, src_label = entry[0], entry[1]
    pattern = entry[2] if len(entry) > 2 else f'{src_key}_jobs_*.csv'
    files = sorted(glob.glob(pattern))
    fname = files[-1] if files else 'NOT FOUND'
    cnt = src_counts.get(src_label, 0)
    print(f'  {src_key} ({src_label}): {fname} → {cnt} jobs')
