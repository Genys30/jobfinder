html = open('index.html', encoding='utf-8').read()

old = "    fnArea:   '',\n  };\n}\n"
new = "    fnArea:   '',\n    description: g('description') || g('raw_text') || '',\n  };\n}\n"

if old in html:
    html = html.replace(old, new, 1)  # only first occurrence = normTelegram
    open('index.html', 'w', encoding='utf-8').write(html)
    print('done')
else:
    print('NOT PATCHED')
