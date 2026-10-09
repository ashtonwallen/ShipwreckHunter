"""Validate saved provenance and artifacts without altering source data."""
import json
from backend import db,analysis

results=[]
for d in db.all_records('dataset'):
    p=db.DATA/d['path']
    assert analysis.sha256(p)==d['sha256'],p
    results.append({'name':d['name'],'sha256':d['sha256'],'bytes':p.stat().st_size})
for s in db.all_records('source'):
    if s.get('status')=='retrieved':
        assert analysis.sha256(db.DATA/'sources'/s['sha256'])==s['sha256']
        assert (db.DATA/'sources'/(s['sha256']+'.txt')).exists()
for r in db.all_records('run'):
    for field in ['original_url','processed_url']:
        assert (db.ROOT/r[field].lstrip('/')).exists(),r[field]
    for id in r['candidates']:assert db.get('candidate',id)
result={'status':'verified','created':db.now(),'datasets':results,'sources':len(db.all_records('source')),'runs':len(db.all_records('run'))}
(db.DATA/'exports/data-validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print('Verified source/raster hashes, extracted text and every saved run artifact.')
