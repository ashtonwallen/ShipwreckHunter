"""Fixed-parameter, spatial holdout audit against NOAA descriptive-report features.

This is point proximity screening, not a segmentation benchmark or calibrated
classifier evaluation. The selected report features are not exhaustive labels.
"""
import json
from pyproj import Transformer
from backend import db,analysis

def dms(deg,minute,second):return deg+minute/60+second/3600

# Visually checked against H11277 report PDF page 20 (printed page 2)
# and pages 158–159 (printed pages 140–141), plus page 21 (printed page 3).
LABELS=[
 ('1.9','wreck',dms(42,36,52.528),-dms(70,39,15.723),'PDF p20'),
 ('1.12','wreck',dms(42,36,49.937),-dms(70,39,19.879),'PDF p20'),
 ('3.17','wreck',dms(42,36,36.702),-dms(70,39,30.173),'PDF pp158–159'),
 ('1.10','rock',dms(42,36,41.957),-dms(70,39,23.816),'PDF p20'),
 ('2.35','rock',dms(42,36,55.699),-dms(70,39,6.479),'PDF p21'),
 ('2.36','rock',dms(42,36,25.540),-dms(70,39,34.199),'PDF p21'),
 ('2.38','rock',dms(42,36,56.574),-dms(70,39,8.786),'PDF p21'),
 ('2.39','rock',dms(42,36,57.626),-dms(70,39,5.431),'PDF p21'),
 ('2.40','rock',dms(42,36,57.021),-dms(70,39,6.490),'PDF p21')
]

def evaluate():
    p=db.DATA/'raw/H11277_MB_50cm_MLLW_7of16.bag'
    dataset=analysis.ingest(p,'H11277','https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/BAG/'+p.name,acquisition=['2003-09-08','2003-09-17'])
    z,valid,affine,crs,_=analysis.load(dataset);transformer=Transformer.from_crs('EPSG:4326',crs,always_xy=True)
    tests=[]
    for method in ['residual','tophat']:
        existing=next((r for r in db.all_records('run') if r['dataset_id']==dataset['id'] and r['parameters']['method']==method and r['parameters']['threshold_sigma']==3 and r['parameters']['scale_m']==12),None)
        run=existing or analysis.detect(dataset['id'],method=method,threshold=3,scale_m=12)
        candidates=[db.get('candidate',id) for id in run['candidates']]
        rows=[]
        for id,kind,lat,lon,locator in LABELS:
            x,y=transformer.transform(lon,lat);col,row=~affine*(x,y)
            inside=0<=row<valid.shape[0] and 0<=col<valid.shape[1] and bool(valid[int(row),int(col)])
            matches=[]
            if inside:
                for c in candidates:
                    b=c['bbox_pixels'];dx=max(b[0]-col,0,col-b[2])*.5;dy=max(b[1]-row,0,row-b[3])*.5
                    if (dx*dx+dy*dy)**.5<=10:matches.append(c['id'])
            rows.append({'report_feature':id,'label':kind,'locator':locator,'on_valid_grid':inside,'detected_within_10m_of_segment':bool(matches),'candidate_ids':matches})
        n_positive=sum(r['label']=='wreck' and r['on_valid_grid'] for r in rows)
        hits=sum(r['label']=='wreck' and r['on_valid_grid'] and r['detected_within_10m_of_segment'] for r in rows)
        n_negative=sum(r['label']=='rock' and r['on_valid_grid'] for r in rows)
        false_alarms=sum(r['label']=='rock' and r['on_valid_grid'] and r['detected_within_10m_of_segment'] for r in rows)
        tests.append({'method':method,'run_id':run['id'],'known_wreck_points_on_grid':n_positive,'known_wreck_points_near_detections':hits,'known_rock_points_on_grid':n_negative,'known_rock_points_near_detections':false_alarms,'rows':rows,'candidate_count':len(candidates),'candidate_cap_applied':run['truncated']})
    result={'protocol':'Fixed threshold 3 sigma / context 12 m, frozen on BAG tile 1 before inspecting labels. BAG tile 7 is a spatial holdout from the same 2003 survey; not independent-survey generalization.','source':'https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/DR/H11277.pdf','dataset_sha256':dataset['sha256'],'created':db.now(),'limitation':'Nine selected point labels only, not an exhaustive or independent ground-truth segmentation. 10 m proximity does not establish object equivalence. No precision/recall for all candidates or calibrated probabilities are claimed.','results':tests}
    db.put('evaluation',result,'H11277-holdout')
    (db.DATA/'exports/detection-evaluation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    for test in tests:print({k:v for k,v in test.items() if k!='rows'})
    return result

if __name__=='__main__':evaluate()
