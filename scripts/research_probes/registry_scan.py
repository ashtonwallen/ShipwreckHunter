import urllib.request
from pathlib import Path
p=Path('data/research/merchant-register-1903.pdf')
if not p.exists():p.write_bytes(urllib.request.urlopen('https://archive.org/download/annuallistmerch00navigoog/annuallistmerch00navigoog.pdf',timeout=60).read())
import pymupdf
pdf=pymupdf.open(p)
for i in range(min(120,len(pdf))):
 t=pdf[i].get_text()
 if 'Actor' in t:
  print('PDF PAGE',i+1,t[:900]);pdf[i].get_pixmap(matrix=pymupdf.Matrix(1.8,1.8)).save(f'data/exports/registry-actor-{i+1}.png')
