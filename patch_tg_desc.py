html = open('index.html', encoding='utf-8').read()

old = """    fnArea:      '',
  };
}

// ─── LOAD TELEGRAM"""

new = """    fnArea:      '',
    description: g('description') || g('raw_text') || '',
  };
}

// ─── LOAD TELEGRAM"""

if old in html:
    html = html.replace(old, new)
    open('index.html', 'w', encoding='utf-8').write(html)
    print('✓ normTelegram updated with description')
else:
    print('NOT PATCHED - pattern not found')
