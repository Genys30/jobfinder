"""
merge_jobs.py  —  run after fetch_jobs.py
Merges all dated CSV files into a single jobs.json for the frontend.
"""
import csv, json, glob, os, re

FIELDS = ['title', 'company', 'location', 'date', 'url', 'department', 'workplace_type', 'description', 'source']

COMPANY_ALIASES = {
    'solaredge technologies': 'SolarEdge',
    'nvidia ai':              'NVIDIA',
    'nvidia':                 'NVIDIA',
}

def normalize_company(name):
    if not name: return name
    return COMPANY_ALIASES.get(name.lower().strip(), name)

# source_key → source label used in frontend
SOURCES = [
    ('comeet',          'comeet'),
    ('greenhouse',      'greenhouse'),
    ('lever',           'lever'),
    ('ashby',           'ashby'),
    ('workable',        'workable'),
    ('gotfriends',      'gotfriends'),
    ('topmatch',        'topmatch'),
    ('mitam',           'mitam'),
    ('weizmann',        'academic'),
    ('bgu',             'academic'),
    ('huji_alumni',     'huji'),
    ('huji_positions',  'huji'),
    ('technion',        'academic'),
    ('tau',             'academic'),
    ('haifa',           'academic'),
    ('bar',             'bar'),
    ('bar_alumni',      'bar'),
    ('bis',             'bis'),
    ('kpmg',            'kpmg'),
    ('deloitte',        'deloitte'),
    ('ey',              'ey'),
    ('joint',           'joint'),
    ('ichilov',         'ichilov'),
    ('clalit',          'clalit'),
    ('szmc',            'szmc'),
    ('hadassah',        'hadassah'),
    ('mod',             'mod'),
    ('osem',            'osem'),
    ('telegram',        'telegram'),
]

all_jobs = []
seen_urls = set()
seen_title_co = set()

for src_key, src_label in SOURCES:
    files = sorted(glob.glob(f'{src_key}_jobs_*.csv'))
    if not files:
        continue
    latest = files[-1]
    try:
        with open(latest, encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                url = (row.get('url') or '').strip()
                title = (row.get('title') or '').strip()
                # use city field as fallback for location
                location = (row.get('location') or row.get('city') or '').strip()
                company = normalize_company((row.get('company') or '').strip())
                date = (row.get('date') or row.get('date_posted') or '').strip()
                department = (row.get('department') or '').strip()
                workplace_type = (row.get('workplace_type') or '').strip()
                description = (row.get('description') or row.get('summary') or '').strip()

                if not title:
                    continue

                # dedup by url, then by title+company
                dedup_key = url if url else None
                title_co_key = title.lower() + '|' + company.lower()

                if dedup_key and dedup_key in seen_urls:
                    continue
                if title_co_key in seen_title_co:
                    continue

                if dedup_key:
                    seen_urls.add(dedup_key)
                seen_title_co.add(title_co_key)

                all_jobs.append({
                    'title':         title,
                    'company':       company,
                    'location':      location,
                    'date':          date,
                    'url':           url,
                    'department':    department,
                    'workplace_type': workplace_type,
                    'description':   description[:1500] if description else '',
                    'source':        src_label,
                })
    except Exception as e:
        print(f'  warn: {src_key} — {e}')

with open('jobs.json', 'w', encoding='utf-8') as f:
    json.dump(all_jobs, f, ensure_ascii=False, separators=(',', ':'))

size_kb = os.path.getsize('jobs.json') // 1024
print(f'Merged {len(all_jobs)} jobs → jobs.json ({size_kb} KB)')
for src_key, _ in SOURCES:
    files = sorted(glob.glob(f'{src_key}_jobs_*.csv'))
    print(f'  {src_key}: {files[-1] if files else "NOT FOUND"}')
