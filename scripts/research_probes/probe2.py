import json,urllib.request,concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
print('SURVEYS',[(x['properties']['SURVEY_ID'],x['properties']['SURVEY_YEAR'],x['properties']['SUBLOCALITY']) for x in json.loads(Path('data/research/surveys.txt').read_text())['features']])
urls={'w43':'https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/W00001-W02000/W00043/BAG/', 'collier':'https://stellwagen.noaa.gov/maritime/mystery-collier.html','mua':'https://mua.apps.uri.edu/in_the_field/noaa_coal.shtml','noaa11805':'https://www.ngdc.noaa.gov/nos/H10001-H12000/H11805.html'}
def f(item):
 k,u=item
 try:
  req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})
  raw=urllib.request.urlopen(req,timeout=30).read();Path('data/research/'+k+'.txt').write_bytes(raw)
  s=BeautifulSoup(raw,'html.parser');return k,s.get_text(' ',strip=True)[-13000:],[(a.get('src'),a.get('alt')) for a in s.select('img')]
 except Exception as e:return k,str(e)
for r in concurrent.futures.ThreadPoolExecutor().map(f,urls.items()):print(r)
s=BeautifulSoup(Path('data/research/nps.txt').read_bytes(),'html.parser');print('NPS',s.get_text(' ',strip=True)[1500:7000])
