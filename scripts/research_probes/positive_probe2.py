from pathlib import Path
import urllib.request,rasterio
from rasterio.warp import transform_bounds
for n in [7,8,13]:
 name=f'H11277_MB_50cm_MLLW_{n}of16.bag';p=Path('data/raw')/name
 if not p.exists():p.write_bytes(urllib.request.urlopen('https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/BAG/'+name,timeout=45).read())
 with rasterio.open(p) as ds:print(name,ds.shape,transform_bounds(ds.crs,'EPSG:4326',*ds.bounds))
