html = open('index.html', encoding='utf-8').read()

if 'loadMod' in html:
    print('Already patched')
    exit()

errors = []

# 1. CSS variable
old_css = '--carmel:#1a7a5e;--carmel-pale:rgba(0,0,0,0.07);'
new_css = '--mod:#2c5f8a;--mod-pale:rgba(44,95,138,0.07);--carmel:#1a7a5e;--carmel-pale:rgba(0,0,0,0.07);'
if old_css in html:
    html = html.replace(old_css, new_css)
    print('✓ CSS variable added')
else:
    errors.append('CSS variable')

# 2. Badge style - after carmel-badge
old_badge = '  .carmel-badge{'
new_badge = '  .mod-badge{display:inline-block;margin-left:6px;font-family:\'JetBrains Mono\',monospace;font-size:8px;letter-spacing:.1em;text-transform:uppercase;color:#fff;padding:2px 5px;border-radius:2px;vertical-align:middle;transform:translateY(-1px);background:var(--mod);}\n  .mod-row:hover .title{color:var(--mod);}\n  .carmel-badge{'
if old_badge in html:
    html = html.replace(old_badge, new_badge)
    print('✓ Badge style added')
else:
    errors.append('Badge style')

# 3. Databar entry - after tgStatusText div
old_databar = '  <div class="datasrc"><span class="src-dot" style="background:var(--tg)"></span><span id="tgStatusText">Biltiformali: loading…</span></div>\n  </div>\n</div>'
new_databar = '  <div class="datasrc"><span class="src-dot" style="background:var(--tg)"></span><span id="tgStatusText">Biltiformali: loading…</span></div>\n  <span class="databar-sep">·</span>\n  <div class="datasrc"><span class="src-dot" style="background:var(--mod)"></span><span id="modStatusText">MOD: loading…</span></div>\n  </div>\n</div>'
if old_databar in html:
    html = html.replace(old_databar, new_databar)
    print('✓ Databar entry added')
else:
    errors.append('Databar entry')

# 4. Source dropdown option - after Biltiformali option
old_opt = '      <option value="Biltiformali-Telegram">Biltiformali 📱</option>\n  </select>'
new_opt = '      <option value="Biltiformali-Telegram">Biltiformali 📱</option>\n      <option value="mod">MOD 🛡️</option>\n  </select>'
if old_opt in html:
    html = html.replace(old_opt, new_opt)
    print('✓ Source dropdown option added')
else:
    errors.append('Source dropdown')

# 5. MOD_JOBS array declaration - after TG_JOBS
old_arr = 'let TG_JOBS = [];'
new_arr = 'let TG_JOBS = [];\nlet MOD_JOBS = [];  // Ministry of Defense'
if old_arr in html:
    html = html.replace(old_arr, new_arr)
    print('✓ MOD_JOBS array added')
else:
    errors.append('MOD_JOBS array')

# 6. activeSrc routing - after carmel
old_src = "  if(activeSrc==='carmel')    return CARMEL_JOBS;\n  const seen"
new_src = "  if(activeSrc==='carmel')    return CARMEL_JOBS;\n  if(activeSrc==='mod')        return MOD_JOBS;\n  const seen"
if old_src in html:
    html = html.replace(old_src, new_src)
    print('✓ activeSrc routing added')
else:
    errors.append('activeSrc routing')

# 7. Pool array - add MOD_JOBS
old_pool = '...OSEM_JOBS,...LI_JOBS,...TG_JOBS]'
new_pool = '...OSEM_JOBS,...LI_JOBS,...TG_JOBS,...MOD_JOBS]'
if old_pool in html:
    html = html.replace(old_pool, new_pool)
    print('✓ Pool array updated')
else:
    errors.append('Pool array')

# 8. SOURCE_EMPLOYER_TYPE
old_emp = "  'Biltiformali-Telegram':'nonprofit',"
new_emp = "  'Biltiformali-Telegram':'nonprofit',\n  'mod':'public',"
if old_emp in html:
    html = html.replace(old_emp, new_emp)
    print('✓ SOURCE_EMPLOYER_TYPE updated')
else:
    errors.append('SOURCE_EMPLOYER_TYPE')

# 9. DATABAR_SOURCES
old_db = "  { id:'tgStatusText', key:'telegram', label:'Biltiformali' },\n];"
new_db = "  { id:'tgStatusText', key:'telegram', label:'Biltiformali' },\n  { id:'modStatusText', key:'mod', label:'MOD' },\n];"
if old_db in html:
    html = html.replace(old_db, new_db)
    print('✓ DATABAR_SOURCES updated')
else:
    errors.append('DATABAR_SOURCES')

# 10. normMod + loadMod functions - before boot
NORM_AND_LOAD = '''
// ─── MOD NORMALIZER ──────────────────────────────────────────────────────────
function normMod(row) {
  const g = k => (row[k] == null ? '' : String(row[k]).trim());
  const title = g('title');
  if (!title) return null;
  return {
    source:      'mod',
    title:       title,
    company:     g('department') || 'משרד הביטחון',
    city:        g('city'),
    url:         g('url'),
    updated:     g('date'),
    description: g('description') || (g('education') ? 'דרישות השכלה: ' + g('education') : '') + (g('experience') ? ' ניסיון: ' + g('experience') : ''),
    level:       '',
    workType:    '',
    category:    '',
    size:        '',
    fnArea:      '',
  };
}

// ─── LOAD MOD ─────────────────────────────────────────────────────────────────
async function loadMod() {
  const filenames = [];
  for (let i = 0; i < 3; i++) {
    const d = new Date(); d.setDate(d.getDate() - i);
    const y = d.getFullYear(),
          m = String(d.getMonth() + 1).padStart(2, '0'),
          day = String(d.getDate()).padStart(2, '0');
    filenames.push('mod_jobs_' + y + '-' + m + '-' + day + '.csv');
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
      return parsed.data.map(row => normMod(row)).filter(Boolean);
    } catch (e) { return []; }
  }))).flat();

  const seen = new Set();
  MOD_JOBS = allRows.filter(r => {
    const k = r.url || (r.title + '|' + r.company);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });

  TOTALS['mod'] = MOD_JOBS.length;
  const $modStatus = document.getElementById('modStatusText');
  if ($modStatus) $modStatus.innerHTML = 'MOD: <strong>' + MOD_JOBS.length.toLocaleString() + ' jobs</strong>';
  applyFilters();
}

'''

old_boot = '// \u2500\u2500\u2500 BOOT'
if old_boot in html:
    html = html.replace(old_boot, NORM_AND_LOAD + old_boot)
    print('✓ normMod + loadMod added')
else:
    errors.append('normMod + loadMod')

# 11. Add loadMod() to boot Promise.all
old_boot_call = '    loadTelegram()\n  ]).catch'
new_boot_call = '    loadTelegram(),\n    loadMod()\n  ]).catch'
if old_boot_call in html:
    html = html.replace(old_boot_call, new_boot_call)
    print('✓ loadMod() added to boot')
else:
    errors.append('loadMod() in boot')

# 12. Row renderer - add mod-badge (find where carmel-badge is rendered)
old_render = "r.source==='carmel'?'<span class=\"carmel-badge\">CARMEL</span>'"
new_render = "r.source==='mod'?'<span class=\"mod-badge\">MOD</span>':r.source==='carmel'?'<span class=\"carmel-badge\">CARMEL</span>'"
if old_render in html:
    html = html.replace(old_render, new_render)
    print('✓ Row renderer badge added')
else:
    # Try alternate pattern
    errors.append('Row renderer badge (check manually)')

open('index.html', 'w', encoding='utf-8').write(html)

print('\n--- Summary ---')
if errors:
    print('NOT patched:')
    for e in errors: print(' -', e)
else:
    print('All patches applied successfully!')
