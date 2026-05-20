html = open('index.html', encoding='utf-8').read()

# Fix URL in normTelegram - normalize any broken https://tps:// or ttps:// patterns
old = "    url:      g('url'),"
new = """    url:      (function(u){
      u = (u||'').trim();
      // Fix broken URLs: https://tps://, ttps://, tps://, ://
      u = u.replace(/^(https?:\\/\\/)+/, 'https://');  // remove duplicate https://
      u = u.replace(/^ttps:\\/\\//, 'https://');
      u = u.replace(/^tps:\\/\\//, 'https://');
      u = u.replace(/^:\\/\\//, 'https://');
      if (!u.startsWith('http') && u.includes('://')) {
        u = 'https://' + u.split('://').slice(1).join('://');
      }
      return u;
    })(g('url')),"""

if old in html:
    html = html.replace(old, new, 1)  # only first occurrence = normTelegram
    open('index.html', 'w', encoding='utf-8').write(html)
    print('done')
else:
    print('NOT PATCHED - pattern not found')
