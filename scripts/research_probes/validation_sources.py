import json
from pathlib import Path
p=json.loads(Path('data/research/H11277-report-pages.json').read_text())
for i in [19,20]:print('PDF PAGE',i+1,p[i])
from backend import connectors,db
s=connectors.source('https://stellwagen.noaa.gov/maritime/palmer-and-crary.html');print('PALMER',s['status'],s['id'],s['text'][:7000])
import urllib.request
for n in [3,5]:
 name=f'H11277_MB_50cm_MLLW_{n}of16.bag';p=Path('data/raw')/name
 p.write_bytes(urllib.request.urlopen('https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/BAG/'+name,timeout=45).read());print(name,p.stat().st_size)
