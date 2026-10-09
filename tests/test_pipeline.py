import json
import shutil
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from backend import db,analysis

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path)
    for name in ['raw','derived','sources','media','exports']:(tmp_path/name).mkdir()
    db.init()

def raster(z,name='survey.tif'):
    path=db.DATA/'raw'/name
    with rasterio.open(path,'w',driver='GTiff',width=z.shape[1],height=z.shape[0],count=1,dtype='float32',crs='EPSG:26919',transform=from_origin(365000,4720000,.5,.5),nodata=-9999) as ds:ds.write(z.astype('float32'),1)
    return path

def test_real_bag_preserves_original_and_crs():
    original=db.ROOT/'data/raw/H11277_MB_50cm_MLLW_1of16.bag'
    path=db.DATA/'raw'/original.name;shutil.copyfile(original,path)
    d=analysis.ingest(path,'H11277','https://data.ngdc.noaa.gov/'+path.name,acquisition=['2003-09-08','2003-09-17'])
    assert d['resolution_m']==[.5,.5]
    assert d['sha256']==analysis.sha256(original)
    assert d['vertical_datum']=='MLLW'
    assert -71<d['bounds'][0]<-70 and 42<d['bounds'][1]<43
    r=analysis.detect(d['id'])
    assert r['valid_cells']==297175
    assert len(r['candidates'])>0
    c=db.get('candidate',r['candidates'][0])
    assert 'not evidence of discovery' in c['catalog_assessment']
    assert 'not probability' in c['score_type']
    assert analysis.sha256(path)==d['sha256']

def test_flat_terrain_and_nodata_edges_are_not_wrecks():
    z=np.full((200,200),-20,dtype=float);z[:15,:]=-9999
    d=analysis.ingest(raster(z),'test','https://example.invalid')
    for method in ['residual','tophat']:
        r=analysis.detect(d['id'],method)
        assert r['candidates']==[]

@pytest.mark.parametrize('method',['residual','tophat'])
def test_known_synthetic_geometry_units_and_reproducibility(method):
    yy,xx=np.mgrid[:200,:200];z=np.full((200,200),-20.)
    z[((xx-100)/30)**2+((yy-100)/8)**2<1]+=3
    d=analysis.ingest(raster(z),'synthetic unit test','https://example.invalid')
    r=analysis.detect(d['id'],method);cs=[db.get('candidate',id) for id in r['candidates']]
    assert len(cs)==1
    assert 25<cs[0]['length_m']<32
    assert 5<cs[0]['width_m']<10
    assert abs(cs[0]['bearing_degrees']-90)<5
    again=analysis.detect(d['id'],method)
    assert db.get('candidate',again['candidates'][0])['score']==cs[0]['score']

def test_3d_keeps_missing_cells_open():
    z=np.full((40,40),-15.);z[:10,:]=-9999
    d=analysis.ingest(raster(z),'test','https://example.invalid');surface=analysis.surface(d['id'])
    assert surface['elevations'].count(None)==400
    assert set(v for v in surface['elevations'] if v is not None)=={-15.}

def test_cancel_does_not_return_a_completed_run():
    d=analysis.ingest(raster(np.ones((100,100))*-20),'test','https://example.invalid')
    with pytest.raises(InterruptedError):analysis.detect(d['id'],cancel=lambda:True)
    assert not db.all_records('run')

def test_geographic_raster_rejected_without_inventing_metre_units():
    path=db.DATA/'raw'/'geographic.tif'
    with rasterio.open(path,'w',driver='GTiff',width=10,height=10,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(-70,42,.01,.01)) as ds:ds.write(np.ones((10,10),dtype='float32'),1)
    with pytest.raises(ValueError,match='projected CRS'):analysis.ingest(path,'test','https://example.invalid')

def test_uncertain_catalogue_position_blocks_absence_inference():
    db.put('wreck',{'lon':-70,'lat':42,'name':'Reported loss','position_quality':'Poor'},'w')
    m=analysis.cross_reference(-70.04,42)
    assert len(m)==1 and m[0]['screening_buffer_m']==5556
