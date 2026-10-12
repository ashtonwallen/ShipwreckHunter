import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds
from fastapi.testclient import TestClient
from mcp import Client

from backend import analysis,connectors,db,jobs
from backend.main import app
from backend.mcp_server import create_server


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path)
    for name in ['raw','derived','sources','media','exports']:(tmp_path/name).mkdir()
    db.init()


@pytest.fixture
def anyio_backend():return 'asyncio'


def write_raster(data,name='survey.tif',dtype='float32',nodata=-9999):
    if data.ndim==2:data=data[None,:,:]
    path=db.DATA/'raw'/name
    with rasterio.open(path,'w',driver='GTiff',width=data.shape[2],height=data.shape[1],count=data.shape[0],dtype=dtype,
                       crs='EPSG:26919',transform=from_origin(365000,4720000,.5,.5),nodata=nodata) as ds:
        ds.write(data.astype(dtype))
    return path


def test_large_original_windows_preserve_cells_uncertainty_and_resume(monkeypatch):
    monkeypatch.setattr(analysis,'MAX_CELLS',4096)
    z=np.arange(120*150,dtype='float32').reshape(120,150)*.001-30
    uncertainty=np.full_like(z,.35)
    path=write_raster(np.stack([z,uncertainty]));digest=analysis.sha256(path)
    result=analysis.ingest_product(path,'H10000','https://data.ngdc.noaa.gov/test.tif',tile_size=64,overlap=8)
    assert result['header']['requires_windows'] and len(result['datasets'])>1
    covered=np.zeros_like(z,dtype=bool)
    for d in result['datasets']:
        c,r,w,h=d['source_window'];filled,valid,transform,_,u=analysis.load(d)
        np.testing.assert_array_equal(filled,z[r:r+h,c:c+w])
        np.testing.assert_array_equal(u,uncertainty[r:r+h,c:c+w])
        assert transform.c==365000+c*.5 and transform.f==4720000-r*.5
        covered[r:r+h,c:c+w]|=valid
        assert d['parent_sha256']==digest and d['width']*d['height']<=4096
    assert covered.all() and analysis.sha256(path)==digest
    again=analysis.ingest_product(path,'H10000','https://data.ngdc.noaa.gov/test.tif',tile_size=64,overlap=8)
    assert result['dataset_ids']==again['dataset_ids']
    assert len(db.all_records('dataset'))==len(result['datasets'])
    assert not list((db.DATA/'derived').rglob('*.tif'))



def test_requested_bbox_limits_processing_and_empty_windows_skipped(monkeypatch):
    path=write_raster(np.full((100,100),-20.))
    with rasterio.open(path) as ds:
        bbox=transform_bounds(ds.crs,'EPSG:4326',365010,4719970,365025,4719990)
    result=analysis.ingest_product(path,'H10000','https://data.ngdc.noaa.gov/test.tif',bbox=bbox)
    assert len(result['datasets'])==1
    d=result['datasets'][0]
    assert d['width']<=32 and d['height']<=42 and d['valid_cells']<10000
    with pytest.raises(ValueError,match='do not overlap'):
        analysis.ingest_product(path,'H10000','https://data.ngdc.noaa.gov/test.tif',bbox=[0,0,1,1])
    monkeypatch.setattr(analysis,'MAX_CELLS',4096)
    z=np.full((128,128),-9999.);z[5:20,5:20]=-20
    sparse=analysis.ingest_product(write_raster(z,'sparse.tif'),'H10000','https://data.ngdc.noaa.gov/sparse.tif',tile_size=64,overlap=0)
    assert sparse['skipped_empty_windows']==3 and len(sparse['datasets'])==1


def test_legacy_materialized_subset_provenance_is_not_applied_twice():
    d=analysis.ingest(write_raster(np.full((80,100),-20.)),'test','https://data.ngdc.noaa.gov/test.tif')
    d.update(source_window=[2400,4800,100,80],parent_sha256='original parent hash')
    z,valid,transform,_,_=analysis.load(d)
    assert z.shape==(80,100) and valid.all() and transform.c==365000


def test_rgb_sonar_white_is_uncovered_and_green_is_not_uncertainty():
    rgb=np.full((3,80,80),255,dtype='uint8');rgb[:,20:60,20:60]=75
    d=analysis.ingest(write_raster(rgb,dtype='uint8',nodata=None),'test','https://data.ngdc.noaa.gov/test.tif',kind='sidescan')
    z,valid,_,_,uncertainty=analysis.load(d)
    assert valid.sum()==1600 and uncertainty is None and not d['has_uncertainty_band']
    assert set(z[valid])=={75}
    assert not analysis.detect(d['id'])['candidates']
    blank=write_raster(np.full((3,40,40),255,dtype='uint8'),'blank.tif','uint8',None)
    with pytest.raises(ValueError,match='No usable'):
        analysis.ingest_product(blank,'test','https://data.ngdc.noaa.gov/blank.tif',kind='sidescan')


def test_all_eligible_detections_survive_beyond_old_cap():
    z=np.full((560,560),-20.)
    yy,xx=np.mgrid[:560,:560]
    for row in range(30,551,40):
        for col in range(30,551,40):
            z[((xx-col)/12)**2+((yy-row)/4)**2<1]+=3
    d=analysis.ingest(write_raster(z),'test','https://data.ngdc.noaa.gov/test.tif')
    run=analysis.detect(d['id'])
    assert len(run['candidates'])>150
    assert len(run['candidates'])==run['eligible_count'] and not run['truncated']
    assert all(db.get('candidate',id) for id in run['candidates'])


def test_cancel_during_thumbnail_creation_does_not_publish_partial_candidates(monkeypatch):
    z=np.full((200,200),-20.);z[40:50,40:80]+=3;z[120:130,120:160]+=3
    d=analysis.ingest(write_raster(z),'test','https://data.ngdc.noaa.gov/test.tif')
    written=[];original=analysis.image
    def image(*args,**kwargs):
        original(*args,**kwargs);written.append(args[2])
    monkeypatch.setattr(analysis,'image',image)
    with pytest.raises(InterruptedError):analysis.detect(d['id'],cancel=lambda:len(written)>=3)
    assert not db.all_records('candidate') and not db.all_records('run')


def test_close_catalogue_position_is_distinct_from_uncertainty_buffer():
    db.put('wreck',{'lon':-70,'lat':42,'name':'Known position','position_quality':'High'},'close')
    db.put('wreck',{'lon':-70.04,'lat':42,'name':'Imprecise obstruction','position_quality':'Low'},'uncertain')
    matches=analysis.cross_reference(-70,42)
    assert matches[0]['association']=='close catalogue position'
    assert matches[1]['association']=='uncertain positional association'
    assert 'compare shape' in analysis.catalogue_assessment(matches)
    assert 'unresolved' in analysis.catalogue_assessment(matches[1:])


def seed_candidates():
    db.put('dataset',{'survey_id':'H10000'},'d')
    db.put('run',{'dataset_id':'d','truncated':True},'r')
    db.put_many([('candidate',{'id':f'c{i:03d}','run_id':'r','dataset_id':'d','score':i%3,'status':'unreviewed','lon':-70.,'lat':43.}) for i in range(121)])


@pytest.mark.anyio
async def test_mcp_paging_reviews_catalogue_sync_and_survey_registration(monkeypatch):
    seed_candidates()
    monkeypatch.setattr(connectors,'sync_wrecks',lambda bbox:{'bbox':bbox,'count':3})
    monkeypatch.setattr(connectors,'source',lambda url:{'status':'retrieved','text':'NOAA H10000','id':'metadata'})
    async with Client(create_server()) as client:
        page=(await client.call_tool('list_detections',{'survey_id':'H10000','limit':100})).structured_content
        assert page['total']==121 and page['next_offset']==100 and 'lon' not in page['candidates'][0]
        tail=(await client.call_tool('list_detections',{'run_id':'r','offset':100,'limit':100,'include_coordinates':True})).structured_content
        assert len(tail['candidates'])==21 and tail['next_offset'] is None
        assert len({c['id'] for c in page['candidates']+tail['candidates']})==121
        assert tail['candidates'][0]['lon']==-70 and page['legacy_truncated_run_ids']==['r']
        review=await client.call_tool('review_candidate',{'candidate_id':'c000','status':'known-feature','reason':'NOAA report page 31 coordinate and shape match'})
        assert not review.is_error
        filtered=(await client.call_tool('list_detections',{'status':'known-feature'})).structured_content
        assert filtered['total']==1 and filtered['candidates'][0]['id']=='c000'
        assert not (await client.call_tool('sync_wreck_catalogue',{'bbox':[-71,42,-70,43]})).is_error
        registered=(await client.call_tool('register_survey',{'survey_id':'H10000'})).structured_content
        assert registered['url'].endswith('/H08001-H10000/H10000.html') and 'feature' not in registered
        assert (await client.call_tool('review_candidate',{'candidate_id':'c000','status':'known-feature','reason':'   '})).is_error
    assert any(e['kind']=='review' for e in db.events())


def test_cached_preflight_and_ingest_job_never_redownload(monkeypatch):
    url='https://data.ngdc.noaa.gov/test.tif'
    cached=connectors.product_path(url)
    write_raster(np.full((100,100),-20.)).replace(cached)
    monkeypatch.setattr(connectors.httpx,'Client',lambda *a,**kw:pytest.fail('Cached ingestion must not use network'))
    assert connectors.inspect_product(url)['download_required_bytes']==0
    db.put('survey',{'name':'Test'},'test')
    monkeypatch.setattr(jobs.POOL,'submit',lambda *a:None)
    job=jobs.submit('ingest',{'url':url,'survey_id':'test','kind':'bathymetry'})
    jobs.run(job['id']);saved=db.get('job',job['id'])
    assert saved['status']=='complete' and len(saved['result']['dataset_ids'])==1
    assert any(e['kind']=='download' for e in db.events(job['id']))


def test_source_search_pages_do_not_hide_later_features():
    text=''.join(f'[PDF page {n}]\nwreck wreck wreck\n'+('x'*2100)+'\n' for n in range(1,16))
    db.put('source',{'status':'retrieved','sha256':'unused','text':text,'url':'https://archive.org/test.pdf'},'s')
    first=connectors.search_source('s','wreck');last=connectors.search_source('s','wreck',offset=first['next_offset'])
    assert first['total_matches']==45 and first['total_excerpts']==15
    assert [m['pdf_page'] for m in last['matches']]==[13,14,15]
    assert last['next_offset'] is None
    assert all(a['excerpt_end']<=b['excerpt_start'] for a,b in zip(first['matches'],first['matches'][1:]))


def test_alternate_loopback_port_accepts_same_origin_and_rejects_other_sites():
    client=TestClient(app,base_url='http://127.0.0.1:8799')
    body={'candidate_id':'missing'}
    response=client.post('/api/candidates/missing/review',headers={'Origin':'http://127.0.0.1:8799'},json={'status':'rejected','reason':'test'})
    assert response.status_code==404
    for origin in ['https://evil.example','http://127.0.0.1:8888','http://localhost:bad']:
        assert client.post('/api/candidates/missing/review',headers={'Origin':origin},json=body).status_code==403
