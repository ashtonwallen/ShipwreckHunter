"""Explicit live smoke run against the local server and public archives."""
import json,time
import httpx
from backend import db

def main():
    results={}
    with httpx.Client(base_url='http://127.0.0.1:8787',timeout=90) as c:
        def get(url):
            r=c.get(url);r.raise_for_status();return r.json()
        workspace=get('/api/workspace');results['health']=get('/api/health')
        products=get('/api/surveys/H11277/products');assert any(p['ingestible'] for p in products);results['noaa_products']=len(products)
        results['archive_searches']={}
        for archive,q in [('loc','schooner coal'),('internet_archive','title:(merchant vessels)')]:
            data=get(f'/api/search?archive={archive}&q={q}&from_year=1885&to_year=1905')
            results['archive_searches'][archive]={'status':data['status'],'count':len(data['results']),'date_bounds':[1885,1905],'error':data.get('error')}
            assert data['status'] in ('complete','unavailable')
            if data['status']=='unavailable':assert not data['results']
        files=get('/api/archive-files/merchantvessels00guargoog');assert any(f['name'].endswith('_djvu.txt') for f in files)
        results['registry_files']=len(files)
        matches=get('/api/sources/a9a7644d7d297bcc/search?q=ACTOR');assert matches['total_matches']>0
        results['full_registry_characters_searched']=matches['text_length']
        surface=get('/api/datasets/'+workspace['datasets'][0]['id']+'/surface');assert any(x is None for x in surface['elevations'])
        results['surface']={'width':surface['width'],'height':surface['height'],'gaps_preserved':True}
        r=c.get('/api/report?format=html');r.raise_for_status();assert 'Mystery Collier' in r.text and '<h1>' in r.text
        (db.DATA/'exports/mystery-collier.html').write_text(r.text,encoding='utf8')
        dataset=next(d for d in workspace['datasets'] if d['name'].endswith('_1of16.bag'))
        r=c.post('/api/jobs',json={'kind':'analysis','args':{'dataset_id':dataset['id'],'method':'residual','threshold':3,'scale_m':12}});r.raise_for_status();job=r.json()
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            done=get('/api/jobs/'+job['id'])
            if done['status'] not in ('queued','running'):break
            time.sleep(.3)
        assert done['status']=='complete',done
        results['actual_analysis_job']={'id':job['id'],'status':done['status'],'candidate_count':len(done['result']['candidates'])}
        results['settings_do_not_return_credentials']='key' not in get('/api/settings')
    (db.DATA/'exports/live-validation.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
