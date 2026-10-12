import json
import pytest
from fastapi.testclient import TestClient
from backend import db, investigations, assistant, jobs, connectors
from backend.main import app
from backend.mcp_server import execute as mcp_execute


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path)
    for name in ('raw','derived','sources','media','exports'):(tmp_path/name).mkdir()
    db.init()
    monkeypatch.setattr(assistant.keyring,'get_password',lambda *a:None)
    db.put('site',dict(name='Mystery Collier',conclusion='Original assessment',next_steps=[]),'mystery-collier')


def test_new_workspace_is_empty_and_every_collection_is_scoped():
    c=TestClient(app)
    a=c.post('/api/investigations',json={'name':' Lake A ','objective':'Find anomalies'}).json()
    b=c.post('/api/investigations',json={'name':'Lake B'}).json()
    assert a['name']=='Lake A' and a['id']!=b['id']
    db.put('source',dict(title='Lake A document',url='https://www.maine.gov/a',text='Evidence A'),'s')
    investigations.link(a['id'],'source','s')
    db.claim(a['id'],'hull','Observed A','s','page 1')
    db.put('vessel',dict(name='Vessel A',site_id=a['id']),'v')
    db.put('survey',dict(name='HA',feature={'type':'Feature','properties':{'SURVEY_ID':'HA'},'geometry':None}),'HA')
    investigations.link(a['id'],'survey','HA')
    db.put('dataset',dict(survey_id='HA',name='Grid A'),'d')
    investigations.link(a['id'],'dataset','d')
    db.put('run',dict(dataset_id='d',candidates=['contact']),'r')
    db.put('candidate',dict(dataset_id='d',run_id='r',score=1,status='unreviewed'),'contact')
    db.put('wreck',dict(lon=-70,lat=44,name='Known A',position_quality='High',status='known'),'wreck')
    investigations.link(a['id'],'wreck','wreck')
    db.put('job',dict(kind='research',args={'site_id':a['id']},status='complete'),'j')
    db.event('j','research',{'summary':'Only A'})
    assistant.execute('save_research_note',dict(site_id=a['id'],subject='A note',text='Only A',source_ids=['s'],contradictions=[]))
    wa=c.get('/api/workspace',params={'site_id':a['id']}).json()
    wb=c.get('/api/workspace',params={'site_id':b['id']}).json()
    for key in ('sources','claims','notes','vessels','datasets','runs','candidates'):
        assert wa[key] and wb[key]==[],key
    for site,count in [(a,1),(b,0)]:
        params={'site_id':site['id']}
        assert len(c.get('/api/map',params=params).json()['wrecks']['features'])==count
        assert len(c.get('/api/map',params=params).json()['surveys']['features'])==count
        assert c.get('/api/candidates',params=params).json()['total']==count
        assert len(c.get('/api/surveys',params=params).json())==count
        assert len(c.get('/api/jobs',params=params).json())==count
        assert len(c.get('/api/history',params=params).json()['events'])==count
    report=c.get('/api/report',params={'site_id':b['id']}).text
    assert 'Lake B' in report and 'Only A' not in report and 'Mystery Collier' not in report
    assert c.get('/api/report',params={'site_id':a['id']}).headers['content-disposition'].endswith(a['id']+'-report.md"')


def test_imports_attach_only_to_requesting_investigation(monkeypatch):
    a=investigations.create('A');b=investigations.create('B');c=TestClient(app)
    source=db.put('source',dict(title='Document',text='Saved',url='https://www.maine.gov/a'),'s')
    monkeypatch.setattr(connectors,'source',lambda url:source)
    assert c.post('/api/sources',params={'site_id':a['id']},json={'url':source['url']}).status_code==200
    assert investigations.sources(a['id']) and not investigations.sources(b['id'])
    search=db.put('search',dict(query='ship',results=[]),'q')
    monkeypatch.setattr(connectors,'search_archive',lambda *a,**kw:search)
    c.get('/api/search',params={'q':'ship','site_id':a['id']})
    assert investigations.records(a['id'],'search') and not investigations.records(b['id'],'search')
    assert c.post('/api/claims',params={'site_id':b['id']},json=dict(subject=a['id'],field='x',value='y',source_id='s',locator='page')).status_code==400


def test_analysis_cannot_use_another_investigations_grid(monkeypatch):
    a=investigations.create('A');b=investigations.create('B')
    db.put('dataset',{'name':'A grid'},'d');investigations.link(a['id'],'dataset','d')
    with pytest.raises(ValueError,match='does not belong'):
        jobs.submit('analysis',{'site_id':b['id'],'dataset_id':'d'})
    assert not db.all_records('job')


def test_assistant_context_and_notes_cannot_drift_between_sites(monkeypatch):
    a=investigations.create('Lake A');b=investigations.create('Lake B')
    db.put('source',{'title':'A source','text':'evidence'},'s')
    db.put('job',{'args':{'site_id':a['id']}},'j')
    monkeypatch.setattr(assistant,'settings',lambda:{'configured':True,'provider':'local'})
    replies=iter([
        ({'role':'assistant','content':'','tool_calls':[{'id':'t','type':'function','function':{'name':'save_research_note','arguments':json.dumps(dict(site_id=b['id'],subject='Note',text='A evidence',source_ids=['s'],contradictions=[]))}}]},1),
        ({'role':'assistant','content':'Saved'},1),
    ])
    seen=[]
    def complete(messages,*args):seen.append(json.dumps(messages));return next(replies)
    monkeypatch.setattr(assistant,'complete',complete)
    assistant.investigate('Investigate this lake','j')
    assert 'Lake A' in seen[0] and 'Mystery Collier' not in seen[0]
    assert len(investigations.notes(a['id']))==1 and not investigations.notes(b['id'])
    db.put('job',{'args':{'site_id':b['id']}},'other')
    with pytest.raises(ValueError,match='another investigation'):
        assistant.investigate('continue','other',previous_job_id='j')


def test_sample_initialization_preserves_user_investigations_and_unassigned_records():
    site=investigations.create('Example lake')
    db.put('source',{'title':'Lake document'},'s')
    investigations.link(site['id'],'source','s')
    db.put('research_note',dict(site_id=site['id'],subject='Coverage',text='Original text',source_ids=['s']),'n')
    db.put('dataset',{'survey_id':'TEST'},'unassigned-grid')
    investigations.initialize_sample();investigations.initialize_sample()
    assert db.get('site','mystery-collier')['sample'] is True
    assert db.get('site',site['id'])==site
    assert len(db.all_records('site'))==2
    assert db.get('research_note','n')['text']=='Original text'
    assert not investigations.notes('mystery-collier')
    assert not investigations.records('mystery-collier','dataset')
    assert db.get('dataset','unassigned-grid')
    assert len(investigations.notes(site['id']))==1
    assert mcp_execute('get_report',{'site_id':site['id']})['text'].startswith('# Example lake')


def test_empty_name_and_unknown_context_rejected():
    c=TestClient(app)
    assert c.post('/api/investigations',json={'name':'   '}).status_code==400
    assert c.get('/api/workspace?site_id=missing').status_code==400
    assert not db.get('site','missing')
