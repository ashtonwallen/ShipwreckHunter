import urllib.request,concurrent.futures
from pathlib import Path
Path('data/raw').mkdir(exist_ok=True);Path('data/media').mkdir(exist_ok=True)
urls={
'data/raw/H11277_MB_50cm_MLLW_1of16.bag':'https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/BAG/H11277_MB_50cm_MLLW_1of16.bag',
'data/raw/H11277_MB_50cm_MLLW_2of16.bag':'https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/BAG/H11277_MB_50cm_MLLW_2of16.bag',
'data/research/1898-casualty-returns.pdf':'https://lloyds-production.s3.amazonaws.com/_file/general/1898-casualty-returns.pdf',
'data/research/H11277.html':'https://www.ngdc.noaa.gov/nos/H10001-H12000/H11277.html',
'data/research/H11277.xml':'https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/ISO/H11277.xml'}
for name in ['6-1000','1-400','3-1000','4-1000','2-600','10-1000']:
 urls['data/media/collier-'+name+'.jpg']='https://stellwagen.noaa.gov/media/img/20200810-mystery-collier-'+name+'.jpg'
def f(item):
 p,u=item
 try:
  r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read();Path(p).write_bytes(r);return p,len(r)
 except Exception as e:return p,str(e)
for r in concurrent.futures.ThreadPoolExecutor(6).map(f,urls.items()):print(r)
