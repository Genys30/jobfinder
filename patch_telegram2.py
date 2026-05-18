html = open('index.html', encoding='utf-8').read()

if 'loadTelegram' in html:
    print('Already patched')
    exit()

NORM = """
// ─── TELEGRAM NORMALIZER ─────────────────────────────────────────────────────
function normTelegram(row) {
  const g = k => (row[k] == null ? '' : String(row[k]).trim());
  const title = g('title');
  if (!title) return null;
  return {
    source:   'Biltiformali-Telegram',
    title:    title,
    company:  g('company'),
    city:     g('city'),
    url:      g('url'),
    updated:  g('date_posted'),
    level:    g('level'),
    workType: g('work_type'),
    sector:   g('sector'),
    category: '',
    size:     '',
    fnArea:   '',
  };
}

"""

LOADER = """
// ─── LOAD TELEGRAM ───────────────────────────────────────────────────────────
let TG_JOBS = [];
async function loadTelegram() {
  const filenames = [];
  for (let i = 0; i < 3; i++) {
    const d = new Date(); d.setDate(d.getDate() - i);
    const y = d.getFullYear(),
          m = String(d.getMonth() + 1).padStart(2, '0'),
          day = String(d.getDate()).padStart(2, '0');
    filenames.push('jobs_telegram_biltiformali_' + y + '-' + m + '-' + day + '.csv');
  }
  const allRows = (await Promise.all(filenames.map(async fname => {
    try {
      const r = await fetch(LI_RAW + fname);
      if (!r.ok) return [];
      const text = await r.text();
      const parsed = Papa.parse(text, {
        header: true, skipEmptyLines: true,
        transformHeader: h => h.replace(/^\\uFEFF/, '').trim().toLowerCase()
      });
      return parsed.data.map(row => normTelegram(row)).filter(Boolean);
    } catch (e) { return []; }
  }))).flat();

  const seen = new Set();
  TG_JOBS = allRows.filter(r => {
    const k = (r.title || '').toLowerCase() + '|' + (r.company || '').toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  applyFilters();
}

"""

# Insert normTelegram before LOAD LINKEDIN
marker1 = '// \u2500\u2500\u2500 LOAD LINKEDIN'
html = html.replace(marker1, NORM + marker1)

# Insert loadTelegram before BOOT
marker2 = '// \u2500\u2500\u2500 BOOT'
html = html.replace(marker2, LOADER + marker2)

# Add loadTelegram() to boot Promise.all
html = html.replace('loadOsem()\n  ]).', 'loadOsem(),\n    loadTelegram()\n  ]).')

open('index.html', 'w', encoding='utf-8').write(html)

# Verify
html2 = open('index.html', encoding='utf-8').read()
print('normTelegram:', 'normTelegram' in html2)
print('loadTelegram:', 'loadTelegram' in html2)
print('TG_JOBS:', 'TG_JOBS' in html2)