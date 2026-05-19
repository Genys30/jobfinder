html = open('index.html', encoding='utf-8').read()

if 'modBadge' in html:
    print('Already patched')
    exit()

# 1. Add modBadge definition after carmelBadge
old = "const carmelBadge = r.source==='carmel'?'<span class=\"carmel-badge\">Carmel</span>':'';"
new = "const carmelBadge = r.source==='carmel'?'<span class=\"carmel-badge\">Carmel</span>':'';\n    const modBadge = r.source==='mod'?'<span class=\"mod-badge\">MOD</span>':'';"
if old in html:
    html = html.replace(old, new)
    print('✓ modBadge definition added')
else:
    print('NOT PATCHED - carmelBadge definition not found')
    exit()

# 2. Add modBadge to title render
old_title = '+carmelBadge+hujiBadge+'
new_title = '+carmelBadge+modBadge+hujiBadge+'
if old_title in html:
    html = html.replace(old_title, new_title)
    print('✓ modBadge added to title render')
else:
    print('NOT PATCHED - title render pattern not found')
    exit()

# 3. Add mod to rowCls map
old_cls = "carmel:' carmel-row'}"
new_cls = "carmel:' carmel-row',mod:' mod-row'}"
if old_cls in html:
    html = html.replace(old_cls, new_cls)
    print('✓ mod-row class added')
else:
    print('WARNING - rowCls pattern not found, skipping')

open('index.html', 'w', encoding='utf-8').write(html)
print('\nDone!')
