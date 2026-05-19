html = open('index.html', encoding='utf-8').read()

old = """function normMod(row) {
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
}"""

new = """function normMod(row) {
  const g = k => (row[k] == null ? '' : String(row[k]).trim());
  const title = g('title');
  if (!title) return null;
  const parts = [];
  if (g('summary'))    parts.push(g('summary'));
  if (g('education'))  parts.push('השכלה: ' + g('education'));
  if (g('experience')) parts.push('ניסיון: ' + g('experience'));
  return {
    source:      'mod',
    title:       title,
    company:     g('company') || 'משרד הביטחון',
    city:        g('location'),
    url:         g('url'),
    updated:     g('date_posted'),
    deadline:    g('deadline'),
    description: parts.join(' | '),
    level:       '',
    workType:    '',
    category:    '',
    size:        '',
    fnArea:      '',
  };
}"""

if old in html:
    html = html.replace(old, new)
    open('index.html', 'w', encoding='utf-8').write(html)
    print('✓ normMod fixed - location, date_posted, description all mapped correctly')
else:
    print('NOT PATCHED - pattern not found')
