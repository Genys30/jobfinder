f = open('jobs_telegram_biltiformali_2026-05-20.csv', encoding='utf-8-sig').read()
print('Size:', len(f), 'chars')
print('Lines:', f.count('\n'))
print('First 300:', repr(f[:300]))
