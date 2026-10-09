import json,urllib.request,concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
for f in json.loads(Path('data/research/awois.txt').read_text())['features']:
 a=f['attributes'];n=a['vesselTerm'];h=a['history'] or ''
 if 'COAL' in h.upper() or 'SCHOONER' in h.upper():print(n,h)
urls={'lloyds':'https://heritage.lrfoundation.org.uk/archive-library/casualty-returns','researcher':'https://kirstinmeyer.blogspot.com/2020/07/the-mystery-collier.html'}
def f(i):
 k,u=i
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read();Path('data/research/'+k+'.html').write_bytes(r);s=BeautifulSoup(r,'html.parser');return k,[(a.text,a.get('href')) for a in s.select('a[href]') if '189' in a.text] if k=='lloyds' else s.get_text(' ',strip=True)[-13000:]
 except Exception as e:return k,str(e)
for r in concurrent.futures.ThreadPoolExecutor().map(f,urls.items()):print(r)
