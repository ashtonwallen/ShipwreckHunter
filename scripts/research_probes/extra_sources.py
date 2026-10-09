import urllib.request,json
from pathlib import Path
from bs4 import BeautifulSoup
u='https://stellwagen.noaa.gov/maritime/shipwrecks.html'
s=BeautifulSoup(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'})).read(),'html.parser');print([(a.text,a.get('href')) for a in s.select('a[href]') if any(v in a.text for v in ['Palmer','Crary','Lamartine'])])
from backend import db
print([(w['id'],w['name'],w['lon'],w['lat']) for w in db.all_records('wreck') if w['name'] in ['ACTOR','ACTIVE']])
