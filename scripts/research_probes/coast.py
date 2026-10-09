import urllib.request,json
from pathlib import Path
from shapely.geometry import shape,mapping,box
url='https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson'
raw=urllib.request.urlopen(url,timeout=60).read();d=json.loads(raw)
features=[]
for f in d['features']:
 g=shape(f['geometry']);g=g.intersection(box(-85,20,-45,60))
 if not g.is_empty:features.append({'type':'Feature','properties':{},'geometry':mapping(g)})
Path('data/media/land.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features}),encoding='utf8')
Path('data/media/land-provenance.json').write_text(json.dumps({'source':url,'sha256':__import__('hashlib').sha256(raw).hexdigest(),'clip':[-85,20,-45,60],'scale':'1:10 million','license':'public domain','purpose':'Context only; not for navigation or measurement'}))
print('Land context saved')
