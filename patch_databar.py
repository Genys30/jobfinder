html = open('index.html', encoding='utf-8').read()

if 'tgStatusText' in html:
    print('Already patched')
    exit()

# 1. Add CSS variable for Telegram color (after --carmel or similar)
html = html.replace(
    '--carmel)',
    '--carmel);--tg:#0088cc'
)

# 2. Add databar entry after Carmel
html = html.replace(
    '  </div>\n</div>\n\n<!-- Filters -->',
    '  <span class="databar-sep">·</span>\n  <div class="datasrc"><span class="src-dot" style="background:var(--tg)"></span><span id="tgStatusText">Biltiformali: loading…</span></div>\n  </div>\n</div>\n\n<!-- Filters -->'
)

# 3. Update loadTelegram to set status text and TOTALS
html = html.replace(
    '  TOTALS[\'telegram\'] = TG_JOBS.length;\n  populateDropdowns();\n  applyFilters();\n}',
    '  TOTALS[\'telegram\'] = TG_JOBS.length;\n  const $tgStatus = document.getElementById(\'tgStatusText\');\n  if($tgStatus) $tgStatus.innerHTML=\'Biltiformali: <strong>\'+TG_JOBS.length.toLocaleString()+\' jobs</strong>\';\n  populateDropdowns();\n  applyFilters();\n}'
)

# If TOTALS line not there yet, add it
if "TOTALS['telegram']" not in html:
    html = html.replace(
        '  applyFilters();\n}\n\n// \u2500\u2500\u2500 BOOT',
        '  TOTALS[\'telegram\'] = TG_JOBS.length;\n  const $tgStatus = document.getElementById(\'tgStatusText\');\n  if($tgStatus) $tgStatus.innerHTML=\'Biltiformali: <strong>\'+TG_JOBS.length.toLocaleString()+\' jobs</strong>\';\n  populateDropdowns();\n  applyFilters();\n}\n\n// \u2500\u2500\u2500 BOOT'
    )

open('index.html', 'w', encoding='utf-8').write(html)

html2 = open('index.html', encoding='utf-8').read()
print('tgStatusText:', 'tgStatusText' in html2)
print('TOTALS telegram:', "TOTALS['telegram']" in html2)
print('databar entry:', 'Biltiformali: loading' in html2)
