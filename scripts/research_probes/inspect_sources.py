import json
from bs4 import BeautifulSoup
from pathlib import Path
for k in ['surveys','awois']:
 d=json.loads(Path('data/research/'+k+'.txt').read_text());print(k,'count',len(d.get('features',[])),d.keys());print([x.get('properties',x.get('attributes')) for x in d.get('features',[])][:12])
for k in ['bags','usgs']:
 p=Path('data/research/'+k+'.txt')
 if p.exists():print(k,BeautifulSoup(p.read_bytes(),'html.parser').get_text(' ',strip=True))
soup=BeautifulSoup(Path('data/research/collier.txt').read_bytes(),'html.parser');print('IMAGES',[(a.get('src'),a.get('alt')) for a in soup.select('img')])
soup=BeautifulSoup(Path('data/research/nps.txt').read_bytes(),'html.parser');print('NPS',soup.get_text(' ',strip=True)[1000:11000])
