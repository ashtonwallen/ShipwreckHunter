from pathlib import Path
import urllib.request,concurrent.futures
from pypdf import PdfReader
urls={f'casualties-{y}':f'https://collections.lrfoundation.org.uk/asset/raw/casualty/{y}.pdf' for y in [1893,1898,1900]}
urls['H11277-report']='https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/DR/H11277.pdf'
def f(i):
 k,u=i
 try:
  p=Path('data/research/'+k+'.pdf');p.write_bytes(urllib.request.urlopen(u,timeout=45).read());reader=PdfReader(p);pages=[x.extract_text(extraction_mode='layout') or '' for x in reader.pages];Path('data/research/'+k+'-pages.json').write_text(__import__('json').dumps(pages),encoding='utf8');return k,len(pages),[(n+1,t[max(0,t.lower().find('boston')-200):t.lower().find('boston')+450]) for n,t in enumerate(pages) if 'boston' in t.lower()]
 except Exception as e:return k,str(e)
for r in concurrent.futures.ThreadPoolExecutor(4).map(f,urls.items()):print(r)
