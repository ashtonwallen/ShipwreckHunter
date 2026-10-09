from backend import connectors,db
for identifier in ['merchantvessels00guargoog','annuallistmerch00navigoog']:
 fs=connectors.archive_files(identifier);print(identifier,fs)
 text=next((x for x in fs if x['name'].endswith('_djvu.txt')),None)
 if text:
  s=connectors.source(text['url']);print('SOURCE',s['id'],s['status'],len(s.get('text','')))
  for term in ['Actor','ACTOR','Active','ACTIVE','Tay']:
   at=s.get('text','').find(term)
   if at>=0:print(term,s['text'][max(0,at-150):at+1200])
