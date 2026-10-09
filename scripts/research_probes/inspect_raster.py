from pathlib import Path
import rasterio,numpy as np
from bs4 import BeautifulSoup
for p in Path('data/raw').glob('*.bag'):
 with rasterio.open(p) as ds:
  a=ds.read(1,masked=True);print(p.name,ds.shape,ds.crs,ds.res,ds.bounds,ds.tags(),float(a.min()),float(a.max()),a.count())
s=BeautifulSoup(Path('data/research/H11277.html').read_bytes(),'html.parser');print(s.get_text(' ',strip=True)[-8000:]);print([(a.get_text(),a.get('href')) for a in s.select('a[href]') if '.xml' in a['href'] or 'DR/' in a['href']])
