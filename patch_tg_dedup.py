html = open('index.html', encoding='utf-8').read()

# The issue: Promise.all loads files in parallel, so order is not guaranteed.
# Fix: sort allRows by date descending before dedup, so newest wins.
old = """  const seen = new Set();
  TG_JOBS = allRows.filter(r => {
    const k = (r.title || '').toLowerCase() + '|' + (r.company || '').toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });"""

new = """  // Sort newest first so dedup keeps the most recent version
  allRows.sort((a, b) => (b.updated || '').localeCompare(a.updated || ''));
  const seen = new Set();
  TG_JOBS = allRows.filter(r => {
    const k = (r.title || '').toLowerCase() + '|' + (r.company || '').toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });"""

if old in html:
    html = html.replace(old, new)
    open('index.html', 'w', encoding='utf-8').write(html)
    print('done')
else:
    print('NOT PATCHED - pattern not found')
