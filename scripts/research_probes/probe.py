import urllib.request,json,concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
urls={
'surveys':'https://gis.ngdc.noaa.gov/arcgis/rest/services/web_mercator/nos_hydro_dynamic/MapServer/0/query?f=geojson&where=1%3D1&geometry=-70.7,42.1,-70.0,42.7&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&outFields=*&resultRecordCount=100',
'awois':'https://services5.arcgis.com/HDRa0B57OVrv2E1q/arcgis/rest/services/Wrecks_and_Obstructions/FeatureServer/0/query?f=json&where=1%3D1&geometry=-71,41.8,-69.8,43&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&outFields=*&resultRecordCount=1000',
'bags':'https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11805/BAG/',
'collier':'https://stellwagen.noaa.gov/maritime/mystery-collier.html',
'usgs':'https://pubs.usgs.gov/sim/2005/2840/DATA/bathy/',
'nps':'https://www.nps.gov/articles/000/tracking-the-schooner-tay.htm'}
Path('data/research').mkdir(parents=True,exist_ok=True)
def f(item):
 k,u=item
 try:
  raw=urllib.request.urlopen(u,timeout=40).read();Path('data/research/'+k+'.txt').write_bytes(raw)
  if k in ['awois','surveys']:
   d=json.loads(raw);return k,str(d)[:5500]
  soup=BeautifulSoup(raw,'html.parser');return k,soup.get_text(' ',strip=True)[-13000:] if k=='nps' else str([(a.get_text(),a.get('href')) for a in soup.select('a[href]')])[:8000]
 except Exception as e:return k,str(e)
for r in concurrent.futures.ThreadPoolExecutor(6).map(f,urls.items()):print(r)
