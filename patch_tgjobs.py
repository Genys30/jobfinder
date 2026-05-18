html = open('index.html', encoding='utf-8').read()

if html.count('TG_JOBS') > 2 and '...TG_JOBS' in html:
    print('Already patched')
    exit()

# Pool 1 - line ~2055 - ends with ...OSEM_JOBS,...LI_JOBS
html = html.replace(
    '...OSEM_JOBS,...LI_JOBS]',
    '...OSEM_JOBS,...LI_JOBS,...TG_JOBS]'
)

# Pool 2 - line ~3749 - ends with ...RB_JOBS,...BL_JOBS,...SK_JOBS]
html = html.replace(
    '...RB_JOBS,...BL_JOBS,...SK_JOBS];',
    '...RB_JOBS,...BL_JOBS,...SK_JOBS,...TG_JOBS];'
)

# Pool 3 - line ~3887 - ends with RB_JOBS,BL_JOBS,SK_JOBS)
html = html.replace(
    'RB_JOBS,BL_JOBS,SK_JOBS)',
    'RB_JOBS,BL_JOBS,SK_JOBS,TG_JOBS)'
)

open('index.html', 'w', encoding='utf-8').write(html)

html2 = open('index.html', encoding='utf-8').read()
count = html2.count('TG_JOBS')
print(f'TG_JOBS appears {count} times -', 'OK' if count >= 5 else 'CHECK MANUALLY')
