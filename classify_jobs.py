"""
classify_jobs.py — LLM batch classifier for jobfinder data
Reads GotFriends + Comeet CSVs, classifies each job, writes classified_jobs.csv

Usage: python classify_jobs.py
Cost estimate: ~4600 jobs x ~300 tokens = ~1.4M tokens = ~$4 at Sonnet pricing
"""

import csv, json, re, os, time
from datetime import date
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
TODAY = date.today().isoformat()
SOURCES = ['gotfriends', 'comeet', 'greenhouse']
OUTPUT_FILE = f'classified_jobs_{TODAY}.csv'
CHECKPOINT_FILE = 'classify_checkpoint.json'
BATCH_SIZE = 10   # jobs per API call (cheaper than 1 by 1)
SLEEP_BETWEEN = 0.5  # seconds between batches

OUTPUT_FIELDS = [
    'title', 'company', 'source', 'department', 'date', 'url',
    'core_or_support', 'seniority', 'barrier_score', 'flexibility_score',
    'tech_stack_recency', 'requires_military_unit',
    'years_experience_required', 'degree_required',
    'description_snippet'
]

SYSTEM_PROMPT = """You are an expert analyst of the Israeli high-tech job market.
You will receive a list of job postings (in Hebrew or English) and must classify each one.
Return ONLY a JSON array with one object per job, in the same order.
No preamble, no markdown, no explanation — pure JSON array only.

For each job return:
{
  "core_or_support": "core" or "support",
  "seniority": "junior" | "mid" | "senior" | "lead" | "executive",
  "barrier_score": 1-5,
  "flexibility_score": 1-5,
  "tech_stack_recency": "cutting_edge" | "standard" | "legacy",
  "requires_military_unit": true or false,
  "years_experience_required": integer (0 if not specified),
  "degree_required": true or false
}

Definitions:
- core: hands-on R&D, Engineering, DevOps, Architecture, QA, Data Science, AI/ML, Security Research, hands-on coding/implementation roles
- support: Product Management, Project Management, Marketing, Sales, HR, Finance, Operations, CS/CX, Legal, Admin, Social work, Business Development, Partnerships, Recruitment/Talent, IT Management, Cyber Management (CISO, Security Manager, Incident Response Manager, SOC Manager)
- CRITICAL RULE: Manager/Director titles = support UNLESS role explicitly involves hands-on coding or research. "Security Engineer" = core. "Security Manager" = support. "Data Scientist" = core. "Data Team Lead" who manages without coding = support.
- Hebrew core signals: מפתח/ת, מהנדס/ת, חוקר/ת, ארכיטקט, אלגוריתם, DevOps, QA, תשתיות, פיתוח
- Hebrew support signals: מנהל/ת (manager), רכז/ת (coordinator), יועץ/ת (consultant), עסקי, שיווק, מכירות, גיוס, משאבי אנוש, פרויקט, לקוחות, תמיכה
- barrier_score: 1=very open (any background welcome), 3=standard tech reqs, 5=very specific rare stack/unit required
- flexibility_score: 1=strict office 9-6 only, 3=hybrid standard, 5=full remote flexible hours
- requires_military_unit: true ONLY if explicitly mentions יחידה 8200/ממר"ם/מת"ם/81/הייטק צבאי or named elite unit
- years_experience_required: minimum years explicitly stated (0 if not mentioned)
- degree_required: true ONLY if תואר ראשון/אקדמאי explicitly required (not just "advantage")"""


def load_jobs():
    """Load jobs from today's and yesterday's CSVs."""
    from datetime import timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    
    jobs = []
    seen_urls = set()
    
    for src in SOURCES:
        for day in [TODAY, yesterday]:
            fname = f'{src}_jobs_{day}.csv'
            if not Path(fname).exists():
                continue
            with open(fname, encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    url = row.get('url', '').strip()
                    desc = row.get('description', '').strip()
                    if not url or url in seen_urls:
                        continue
                    if not desc:
                        continue  # skip jobs without description
                    seen_urls.add(url)
                    jobs.append({
                        'title':       row.get('title', ''),
                        'company':     row.get('company', ''),
                        'source':      src,
                        'department':  row.get('department', ''),
                        'date':        row.get('date', day),
                        'url':         url,
                        'description': desc[:800],  # truncate for token efficiency
                    })
    
    print(f"Loaded {len(jobs)} jobs with descriptions")
    return jobs


def load_checkpoint():
    if Path(CHECKPOINT_FILE).exists():
        return json.load(open(CHECKPOINT_FILE, encoding='utf-8'))
    return {}


def save_checkpoint(results):
    json.dump(results, open(CHECKPOINT_FILE, 'w'), ensure_ascii=False, indent=2)


def classify_batch(batch, api_key):
    """Send a batch of jobs to Claude API for classification."""
    import urllib.request
    
    user_content = json.dumps([
        {'index': i, 'title': j['title'], 'company': j['company'],
         'description': j['description']}
        for i, j in enumerate(batch)
    ], ensure_ascii=False)
    
    payload = json.dumps({
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 1000,
        'system': SYSTEM_PROMPT,
        'messages': [{'role': 'user', 'content': user_content}]
    }, ensure_ascii=False).encode('utf-8')
    
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=payload,
        headers={
            'Content-Type': 'application/json; charset=utf-8',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01'
        }
    )
    
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    
    text = data['content'][0]['text'].strip()
    # Strip markdown if present
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return json.loads(text)


def main():
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        print("  Windows: set ANTHROPIC_API_KEY=sk-ant-...")
        return
    
    jobs = load_jobs()
    if not jobs:
        print("No jobs found with descriptions. Run bat file first.")
        return
    
    # Load checkpoint (resume if interrupted)
    results = load_checkpoint()
    print(f"Checkpoint: {len(results)} already classified")
    
    # Filter out already classified
    todo = [j for j in jobs if j['url'] not in results]
    print(f"To classify: {len(todo)} jobs")
    
    total_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch_num, i in enumerate(range(0, len(todo), BATCH_SIZE), 1):
        batch = todo[i:i+BATCH_SIZE]
        print(f"Batch {batch_num}/{total_batches} ({len(batch)} jobs)...", end=' ', flush=True)
        
        try:
            classifications = classify_batch(batch, ANTHROPIC_API_KEY)
            for j, c in zip(batch, classifications):
                results[j['url']] = {**j, **c}
            save_checkpoint(results)
            print(f"✓")
        except Exception as e:
            print(f"✗ {e}")
        
        time.sleep(SLEEP_BETWEEN)
    
    # Write output CSV
    rows = list(results.values())
    for r in rows:
        r['description_snippet'] = r.get('description', '')[:100]
    
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    
    print(f"\n✅ Done! {len(rows)} jobs classified → {OUTPUT_FILE}")
    
    # Summary stats
    from collections import Counter
    core_pct = sum(1 for r in rows if r.get('core_or_support') == 'core') / len(rows) * 100
    barrier_avg = sum(int(r.get('barrier_score', 3)) for r in rows) / len(rows)
    mil_pct = sum(1 for r in rows if r.get('requires_military_unit')) / len(rows) * 100
    print(f"\nSummary:")
    print(f"  Core roles: {core_pct:.1f}%")
    print(f"  Avg barrier score: {barrier_avg:.2f}/5")
    print(f"  Requires military unit: {mil_pct:.1f}%")
    print(f"\nSeniority breakdown:")
    sen = Counter(r.get('seniority','?') for r in rows)
    for k, v in sen.most_common():
        print(f"  {k}: {v} ({100*v/len(rows):.1f}%)")


if __name__ == '__main__':
    main()
