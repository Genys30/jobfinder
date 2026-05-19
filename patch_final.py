html = open('index.html', encoding='utf-8').read()

errors = []

# 1. Add option to Source dropdown
OLD_OPT = "      <option value=\"carmel\">Carmel \U0001f3e5</option>\n  </select>"
NEW_OPT = "      <option value=\"carmel\">Carmel \U0001f3e5</option>\n      <option value=\"Biltiformali-Telegram\">Biltiformali \U0001f4f1</option>\n  </select>"
if OLD_OPT in html:
    html = html.replace(OLD_OPT, NEW_OPT)
    print('✓ Source dropdown option added')
else:
    errors.append('Source dropdown - pattern not found')

# 2. Add to SOURCE_EMPLOYER_TYPE
OLD_SRC = "  'joint':'nonprofit',\n  'bar':'academic'"
NEW_SRC = "  'joint':'nonprofit',\n  'Biltiformali-Telegram':'nonprofit',\n  'bar':'academic'"
if OLD_SRC in html:
    html = html.replace(OLD_SRC, NEW_SRC)
    print('✓ SOURCE_EMPLOYER_TYPE updated')
else:
    errors.append('SOURCE_EMPLOYER_TYPE - pattern not found')

# 3. Add to DATABAR_SOURCES
OLD_DB = "  { id:'carmelStatusText', key:'carmel', label:'Carmel' },\n];"
NEW_DB = "  { id:'carmelStatusText', key:'carmel', label:'Carmel' },\n  { id:'tgStatusText', key:'telegram', label:'Biltiformali' },\n];"
if OLD_DB in html:
    html = html.replace(OLD_DB, NEW_DB)
    print('✓ DATABAR_SOURCES updated')
else:
    errors.append('DATABAR_SOURCES - pattern not found')

open('index.html', 'w', encoding='utf-8').write(html)

if errors:
    print('\nNOT PATCHED:')
    for e in errors:
        print(' -', e)
else:
    print('\nAll patches applied successfully.')
