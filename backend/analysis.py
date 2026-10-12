"""Reproducible screening, not a trained shipwreck classifier.

Two independent terrain operators: local Gaussian residual and morphological
white top-hat. Side-scan supports local contrast segmentation, without inventing
depth from acoustic intensity. All spatial calculations use the source CRS.
"""
import hashlib
import json
import math
import platform
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.transform import xy
from rasterio.windows import Window, from_bounds
from scipy import ndimage as ndi
from pyproj import CRS, Transformer, Geod
from PIL import Image
from . import db

VERSION='terrain-screen-0.3'
MAX_CELLS=12_000_000
GEOD=Geod(ellps='WGS84')

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def validate_raster(ds, kind):
    if kind not in ('bathymetry','sidescan'):raise ValueError('Unknown raster kind')
    if not ds.crs:raise ValueError('Missing CRS: assign documented source CRS before ingestion')
    crs=CRS(ds.crs)
    if not crs.is_projected or crs.axis_info[0].unit_name.lower() not in ('metre','meter'):raise ValueError('Screening requires a projected CRS in metres. Reproject with GDAL first; do not assign an invented CRS.')
    if ds.transform.b or ds.transform.d or ds.transform.a<=0 or ds.transform.e>=0:raise ValueError('Rotate/reproject raster to north-up before screening')
    if ds.count>2 and kind=='bathymetry':raise ValueError('RGB image is not a measured elevation raster')
    return crs


def inspect_raster(path,kind='bathymetry'):
    """Read the local raster header without loading its full cell array."""
    with rasterio.open(path) as ds:
        crs=validate_raster(ds,kind)
        return {'width':ds.width,'height':ds.height,'cells':ds.width*ds.height,
                'bands':ds.count,'resolution_m':list(ds.res),'crs_name':crs.name,
                'bounds':list(transform_bounds(ds.crs,'EPSG:4326',*ds.bounds,densify_pts=21)),
                'requires_windows':ds.width*ds.height>MAX_CELLS,
                'nodata':float(ds.nodata) if ds.nodata is not None and np.isfinite(ds.nodata) else None,
                'coverage_note':'Header bounds do not establish valid-data coverage',
                'crs_warning':None if crs.to_authority() else 'CRS has no authority identifier; verify source datum before comparing surveys'}


def raster_cells(ds,kind,window=None):
    a=ds.read(1,window=window,masked=True)
    valid=~np.ma.getmaskarray(a)&np.isfinite(a.data)&(np.abs(a.data)<1e6)
    z=a.data.astype('float32')
    if kind=='sidescan' and ds.count>=3:
        rgb=ds.read([1,2,3],window=window,masked=True)
        valid &= ~np.ma.getmaskarray(rgb).any(axis=0)&np.isfinite(rgb.data).all(axis=0)
        # NOAA display mosaics often use opaque white outside sonar coverage.
        # Explicit heuristic, not an absence observation or calibrated backscatter.
        if all(ds.dtypes[i]=='uint8' for i in range(3)):
            valid &= ~np.all(rgb.data==255,axis=0)
        if ds.count==4:valid &= ds.read(4,window=window)>0
        z=rgb.data.astype('float32').mean(axis=0)
    return z,valid


def ingest(path, survey_id, url, kind='bathymetry', acquisition=None, elevation_positive_up=True,window=None,parent_sha256=None):
    path=Path(path).resolve()
    if db.DATA.resolve() not in path.parents:raise ValueError('Raster must be in local data directory')
    with rasterio.open(path) as ds:
        crs=validate_raster(ds,kind)
        win=Window(*window) if window else Window(0,0,ds.width,ds.height)
        if any(v!=int(v) for v in [win.col_off,win.row_off,win.width,win.height]) or win.width<1 or win.height<1 or win.col_off<0 or win.row_off<0 or win.col_off+win.width>ds.width or win.row_off+win.height>ds.height:raise ValueError('Invalid source pixel window')
        if win.width*win.height>MAX_CELLS:raise ValueError('Product exceeds 12 million cell limit; use automatic product ingestion')
        bounds=list(transform_bounds(ds.crs,'EPSG:4326',*ds.window_bounds(win),densify_pts=21))
        wkt=ds.crs.to_wkt()
        record={'survey_id':survey_id,'name':path.name,'url':url,'path':str(path.relative_to(db.DATA.resolve())),'sha256':parent_sha256 or sha256(path),'kind':kind,'width':ds.width,'height':ds.height,'resolution_m':list(ds.res),'crs_wkt':wkt,'crs_name':crs.name,'bounds':bounds,'transform':list(ds.transform),'acquisition':acquisition,'tags':ds.tags(),'ingested':db.now(),'elevation_positive_up':elevation_positive_up,'vertical_datum':'MLLW' if 'Lower Low Water' in wkt or 'MLLW' in path.name else 'Not established','has_uncertainty_band':ds.count>1,'resolution_warning':'Too coarse for small-vessel morphology' if max(ds.res)>3 else None}
        record['has_uncertainty_band']=kind=='bathymetry' and ds.count>1
        record['coverage_mask']='source nodata and finite cells; uint8 RGB sidescan additionally excludes all-white pixels and zero alpha'
        if window:
            parent=parent_sha256 or record['sha256']
            identity=json.dumps([parent,window,kind,elevation_positive_up],separators=(',',':'))
            record.update(sha256=hashlib.sha256(identity.encode()).hexdigest(),parent_sha256=parent,source_window=window,raster_storage='source-window',
                          width=int(win.width),height=int(win.height),transform=list(ds.window_transform(win)),
                          name=f'{path.name} [r{int(win.row_off)} c{int(win.col_off)}]',
                          processing='Lossless source pixel window; no resampling; original file retained')
    return db.put('dataset',record,record['sha256'][:16])


def ingest_product(path,survey_id,url,kind='bathymetry',acquisition=None,elevation_positive_up=True,bbox=None,cancel=lambda:False,progress=lambda n,total:None,tile_size=2000,overlap=100):
    """Register bounded views of a cached original, including restart-safe provenance."""
    path=Path(path).resolve()
    if db.DATA.resolve() not in path.parents:raise ValueError('Raster must be in local data directory')
    if not 32<=tile_size<=3000 or not 0<=overlap<tile_size:raise ValueError('Invalid window size or overlap')
    header=inspect_raster(path,kind);parent=sha256(path)
    with rasterio.open(path) as ds:
        c0=r0=0;c1=ds.width;r1=ds.height
        if bbox is not None:
            if len(bbox)!=4 or not (-180<=bbox[0]<bbox[2]<=180 and -90<=bbox[1]<bbox[3]<=90):raise ValueError('Invalid west,south,east,north bounds')
            projected=transform_bounds('EPSG:4326',ds.crs,*bbox,densify_pts=21)
            win=from_bounds(*projected,ds.transform)
            c0=max(0,math.floor(win.col_off));r0=max(0,math.floor(win.row_off))
            c1=min(ds.width,math.ceil(win.col_off+win.width));r1=min(ds.height,math.ceil(win.row_off+win.height))
            if c0>=c1 or r0>=r1:raise ValueError('Requested bounds do not overlap this product')
        tiled=(c1-c0)*(r1-r0)>MAX_CELLS
        step=tile_size-overlap
        windows=([Window(c,r,min(tile_size,c1-c),min(tile_size,r1-r)) for r in range(r0,r1,step) for c in range(c0,c1,step)] if tiled else [Window(c0,r0,c1-c0,r1-r0)])
        if len(windows)>512:raise ValueError('Product requires more than 512 windows; choose a smaller bounding box')
        records=[];skipped=0
        for i,win in enumerate(windows):
            if cancel():raise InterruptedError()
            _,valid=raster_cells(ds,kind,win)
            if not valid.any():skipped+=1;progress(i+1,len(windows));continue
            pixels=[int(win.col_off),int(win.row_off),int(win.width),int(win.height)]
            # A window ID includes the parent hash and interpretation, so resume
            # reuses the same record without changing candidate references.
            d=ingest(path,survey_id,url,kind,acquisition,elevation_positive_up,window=pixels,parent_sha256=parent)
            d.update(valid_cells=int(valid.sum()),valid_fraction=float(valid.mean()),window_overlap_pixels=overlap if tiled else 0)
            db.put('dataset',d);records.append(d);progress(i+1,len(windows))
        if not records:raise ValueError('No usable raster cells in requested coverage')
    result={'parent_sha256':parent,'original_url':url,'original_bytes':path.stat().st_size,'header':header,
            'dataset_ids':[d['id'] for d in records],'datasets':records,'skipped_empty_windows':skipped,
            'window_count':len(windows),'overlap_pixels':overlap if tiled else 0,
            'coverage_note':'Window areas overlap; do not sum as unique coverage. Overlapping detections are not deduplicated.'}
    manifest_id=hashlib.sha256(json.dumps([parent,bbox,tile_size,overlap,kind,elevation_positive_up]).encode()).hexdigest()[:16]
    folder=db.DATA/'derived'/'ingestion';folder.mkdir(exist_ok=True)
    (folder/(manifest_id+'.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
    return result

def load(dataset):
    with rasterio.open(db.DATA/dataset['path']) as ds:
        # Older GDAL subset records also store parent source_window provenance,
        # but their path already points to a materialized crop.
        window=Window(*dataset['source_window']) if dataset.get('raster_storage')=='source-window' else None
        z,valid=raster_cells(ds,dataset['kind'],window)
        if dataset['kind']=='bathymetry' and not dataset['elevation_positive_up']:z=-z
        if not valid.any():raise ValueError('No usable raster cells')
        indexes=ndi.distance_transform_edt(~valid,return_distances=False,return_indices=True)
        filled=z[tuple(indexes)]
        uncertainty=ds.read(2,window=window,masked=True).astype('float32').filled(np.nan) if dataset['kind']=='bathymetry' and ds.count>1 else None
        return filled,valid,ds.window_transform(window) if window else ds.transform,ds.crs,uncertainty

def operators(z,valid,resolution,scale_m=12,method='residual',threshold=3):
    sigma=max(1,scale_m/resolution)
    if method=='tophat':
        size=min(81,max(3,int(sigma)*2+1))
        background=ndi.grey_opening(z,size=(size,size))
    else:background=ndi.gaussian_filter(z,sigma=sigma)
    residual=z-background
    # Nodata margins cannot become object edges. Physical buffer is recorded.
    interior=valid&(ndi.distance_transform_edt(valid)>max(3,3/resolution))
    samples=residual[interior]
    if not len(samples):raise ValueError('Too few valid interior cells')
    median=float(np.median(samples));noise=max(float(np.median(np.abs(samples-median))*1.4826),0.04)
    cutoff=median+threshold*noise
    mask=interior&(residual>cutoff)
    mask=ndi.binary_opening(mask,iterations=1)
    mask=ndi.binary_closing(mask,iterations=1)&interior
    labels,count=ndi.label(mask)
    return residual,labels,{'cutoff':cutoff,'robust_noise':noise,'median':median,'components':int(count),'nodata_buffer_m':max(3*resolution,3)}

def image(z,valid,path,residual=False):
    values=z[valid]
    if residual:
        limit=max(float(np.percentile(np.abs(values),98)),.01);t=np.clip(z/limit,-1,1)
        rgb=np.stack([25+np.maximum(t,0)*220,65+np.abs(t)*120,95+np.maximum(-t,0)*145],axis=-1)
    else:
        lo,hi=np.percentile(values,[2,98]);t=np.clip((z-lo)/max(hi-lo,.001),0,1)
        rgb=np.stack([15+t*95,38+t*160,54+t*170],axis=-1)
    rgba=np.dstack([np.clip(rgb,0,255).astype('uint8'),valid.astype('uint8')*255])
    im=Image.fromarray(rgba);im.thumbnail((2048,2048));im.save(path)

def cross_reference(lon,lat,radius_m=150,records=None):
    matches=[]
    for w in db.all_records('wreck') if records is None else records:
        if w.get('lon') is None or w.get('lat') is None:continue
        _,_,distance=GEOD.inv(lon,lat,w['lon'],w['lat'])
        # Conservative screening buffers, NOT measured source accuracy.
        buffer={'High':100,'Med':500,'Low':5556,'Poor':5556}.get(w.get('position_quality'),5556)
        if distance<=radius_m+buffer:
            association='close catalogue position' if w.get('position_quality')=='High' and distance<=radius_m else 'uncertain positional association'
            matches.append({'id':w['id'],'name':w['name'],'distance_m':round(distance,1),'position_quality':w.get('position_quality'),'screening_buffer_m':buffer,'association':association,'buffer_basis':'quality-class screening heuristic, not measured source accuracy','source_url':w.get('source_url')})
    return sorted(matches,key=lambda x:x['distance_m'])[:10]


def catalogue_assessment(matches):
    if any(m.get('association')=='close catalogue position' for m in matches):return 'close to a high-quality catalogue position; compare shape and source history before identifying'
    if matches:return 'within an uncertain catalogue screening buffer; same-object association unresolved'
    return 'no nearby record in loaded inventory; not evidence of discovery'

def detect(dataset_id,method='residual',threshold=3,scale_m=12,cancel=lambda:False):
    dataset=db.get('dataset',dataset_id)
    if not dataset:raise ValueError('Unknown dataset')
    if method not in ('residual','tophat'):raise ValueError('Unknown detection method')
    if not 1<=threshold<=10 or not 2<=scale_m<=50:raise ValueError('Invalid processing parameters')
    z,valid,affine,crs,uncertainty=load(dataset)
    rx,ry=dataset['resolution_m'];resolution=max(rx,ry)
    if resolution>5:raise ValueError('Resolution exceeds 5 m. Individual wreck screening disabled.')
    if cancel():raise InterruptedError()
    residual,labels,stats=operators(z,valid,resolution,scale_m,method,threshold)
    params={'method':method,'threshold_sigma':threshold,'scale_m':scale_m,'min_length_m':5,'max_length_m':180,'max_candidates':None,'version':VERSION}
    run_id=db.uid();folder=db.DATA/'derived'/run_id;folder.mkdir()
    image(z,valid,folder/'original.png');image(residual,valid,folder/'residual.png',True)
    transformer=Transformer.from_crs(crs,'EPSG:4326',always_xy=True)
    candidates=[];catalogue=db.all_records('wreck')
    for number,sl in enumerate(ndi.find_objects(labels),1):
        if cancel():raise InterruptedError()
        if sl is None:continue
        yy,xx=np.where(labels[sl]==number);yy=yy+sl[0].start;xx=xx+sl[1].start
        if len(xx)<12:continue
        points=np.column_stack([xx*rx,-yy*ry]);center=points.mean(axis=0)
        vals,vecs=np.linalg.eigh(np.cov((points-center).T));major=vecs[:,-1];minor=vecs[:,0]
        major_extent=float(np.ptp(points@major)+resolution);minor_extent=float(np.ptp(points@minor)+resolution)
        if not 5<=major_extent<=180 or minor_extent<1.5 or minor_extent>70:continue
        elongation=major_extent/minor_extent
        if elongation>15:continue
        cx,cy=xy(affine,float(yy.mean()),float(xx.mean()));lon,lat=transformer.transform(cx,cy)
        peak=float(np.max(residual[yy,xx]));compact=min(1,len(xx)*rx*ry/(major_extent*minor_extent))
        # Review priority is explicitly heuristic and uncalibrated.
        shape_score=math.exp(-((elongation-3)/2.5)**2)
        score=min(99,round(100*(.4*shape_score+.3*compact+.3*min(peak/(stats['cutoff']*3+1e-6),1))))
        nearby=cross_reference(lon,lat,records=catalogue)
        r0=max(0,sl[0].start-20);r1=min(z.shape[0],sl[0].stop+20);c0=max(0,sl[1].start-20);c1=min(z.shape[1],sl[1].stop+20)
        id=f'{run_id}-{number}'
        candidates.append({'id':id,'run_id':run_id,'dataset_id':dataset_id,'lon':float(lon),'lat':float(lat),'length_m':round(major_extent,1),'width_m':round(minor_extent,1),'measurement_floor_m':resolution*2,'bearing_degrees':round(math.degrees(math.atan2(major[0],major[1]))%180,1),'bearing_reference':'source grid north, axis ambiguous by 180 degrees','relief_m':round(peak,2) if dataset['kind']=='bathymetry' else None,'local_intensity_contrast':round(peak,2) if dataset['kind']=='sidescan' else None,'score':score,'score_type':'uncalibrated review-priority heuristic; not probability','elongation':round(elongation,2),'pixels':len(xx),'status':'unreviewed','alternatives':['rock or bedrock ridge','dredging or harbor structure','fishing gear or debris','survey seam or interpolation artifact'],'nearby_records':nearby,'catalog_assessment':'near an uncertain catalogue record' if nearby else 'no nearby record in loaded inventory; not evidence of discovery','bbox_pixels':[sl[1].start,sl[0].start,sl[1].stop,sl[0].stop],'crop_pixels':[c0,r0,c1,r1],'uncertainty_m':float(np.nanmedian(uncertainty[yy,xx])) if uncertainty is not None and np.isfinite(uncertainty[yy,xx]).any() else None})
    candidates.sort(key=lambda x:x['score'],reverse=True)
    total=len(candidates)
    for candidate in candidates:
        if cancel():raise InterruptedError()
        candidate['catalog_assessment']=catalogue_assessment(candidate['nearby_records'])
        c0,r0,c1,r1=candidate['crop_pixels'];name=candidate['id']+'.png'
        image(z[r0:r1,c0:c1],valid[r0:r1,c0:c1],folder/name)
        candidate['image_url']=f'/data/derived/{run_id}/{name}'
    result={'id':run_id,'dataset_id':dataset_id,'dataset_sha256':dataset['sha256'],'parameters':params,'statistics':stats,'created':db.now(),'candidates':[c['id'] for c in candidates],'eligible_count':total,'truncated':False,'valid_cells':int(valid.sum()),'area_m2':int(valid.sum()*rx*ry),'original_url':f'/data/derived/{run_id}/original.png','processed_url':f'/data/derived/{run_id}/residual.png','software':{'python':platform.python_version(),'rasterio':rasterio.__version__,'numpy':np.__version__},'evaluation':'No exhaustive labelled ground truth. Precision, recall and discovery status are unknown.','catalog_coverage':db.get('coverage','wrecks')}
    (folder/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    if cancel():raise InterruptedError()
    db.put_many([('candidate',c) for c in candidates]+[('run',result)])
    return result

def surface(dataset_id,candidate_id=None):
    dataset=db.get('dataset',dataset_id)
    if not dataset or dataset['kind']!='bathymetry':raise ValueError('3D requires measured bathymetry')
    z,valid,affine,crs,_=load(dataset)
    if candidate_id:
        c=db.get('candidate',candidate_id)
        if not c or c['dataset_id']!=dataset_id:raise ValueError('Candidate not in dataset')
        c0,r0,c1,r1=c['crop_pixels'];z=z[r0:r1,c0:c1];valid=valid[r0:r1,c0:c1]
    step=max(1,int(math.ceil(max(z.shape)/128)))
    zz=z[::step,::step];vv=valid[::step,::step]
    return {'width':zz.shape[1],'height':zz.shape[0],'dx':dataset['resolution_m'][0]*step,'dy':dataset['resolution_m'][1]*step,'elevations':[float(v) if m else None for v,m in zip(zz.flat,vv.flat)],'datum':dataset['vertical_datum'],'sampling':'nearest source cells; gaps left open','source_resolution_m':dataset['resolution_m'],'display_stride':step}
