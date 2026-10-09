import urllib.request,concurrent.futures
from bs4 import BeautifulSoup
from pathlib import Path
urls={k:f'https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/{k}/BAG/' for k in ['H11421','H11277']}
def f(item):
 k,u=item
 try:
  raw=urllib.request.urlopen(u,timeout=30).read();Path('data/research/'+k+'.txt').write_bytes(raw);return k,BeautifulSoup(raw,'html.parser').get_text(' ',strip=True)
 except Exception as e:return k,str(e)
for r in concurrent.futures.ThreadPoolExecutor().map(f,urls.items()):print(r)
