import json
import pytest
from fastapi.testclient import TestClient
from backend import db,research,connectors,assistant,jobs
from backend.main import app

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path)
    for name in ['raw','derived','sources','media','exports']:(tmp_path/name).mkdir()
    db.init()
    monkeypatch.setattr(assistant.keyring,'get_password',lambda *a:None)

def seed():
    db.put('source',{'title':'Primary record','url':'https://www.nps.gov/test','status':'retrieved','text':'Source'},'s')
    db.put('site',{'name':'Test site','length_m':32.9,'beam_m':7,'conclusion':'Unidentified','next_steps':['Read original register']},'mystery-collier')

def test_conflicting_claims_preserved_and_unlinked_sources_rejected():
    seed();db.claim('mystery-collier','masts','two','s','profile');db.claim('mystery-collier','masts','two or three','s','caption','contradicts')
    assert len(db.claims('mystery-collier'))==2
    with pytest.raises(ValueError):db.claim('x','f','v','missing','page 1')

def test_missing_data_does_not_gain_match_points_and_exclusion_overrides_score():
    seed();db.put('vessel',{'name':'Unknown specs'},'a')
    db.put('vessel',{'name':'Perfect size but wrong wreck','length_m':32.9,'beam_m':7,'construction':'wood','rig':'schooner','cargo':'coal','excluded':True,'contradictions':['Documented wreck elsewhere']},'b')
    ranked=research.rank();assert ranked[0]['score']==0
    assert ranked[1]['score']==100 and ranked[1]['excluded']

def test_entity_resolution_explains_links_without_merging():
    db.put('vessel',{'name':'Mary A. White','aliases':['MARY A WHITE']},'a')
    link=research.entity_links('Mary A White')[0]
    assert link['similarity']==1 and link['auto_merged'] is False
    assert len(db.all_records('vessel'))==1

def test_report_withholds_internal_coordinates():
    seed();s=db.get('site','mystery-collier');db.put('site',{**s,'lon':-70.123456789,'lat':42.123456789})
    text=research.report();assert '-70.123456789' not in text
    assert 'No definitive identification' in text

@pytest.mark.parametrize('url',['http://127.0.0.1/secret','https://noaa.gov.evil.example/','https://user:pass@noaa.gov/','file:///etc/passwd','https://www.noaa.gov:444/'])
def test_source_fetch_cannot_access_arbitrary_hosts(url):
    with pytest.raises(ValueError):connectors.validate_url(url)

def test_api_validation_never_echoes_key_and_blocks_cross_origin():
    client=TestClient(app)
    response=client.post('/api/settings',json={'provider':'bad','model':'x','key':'DO-NOT-LEAK'})
    assert response.status_code==422 and 'DO-NOT-LEAK' not in response.text
    response=client.post('/api/settings',headers={'origin':'https://evil.example'},json={'provider':'openai','model':'x','key':'DO-NOT-LEAK'})
    assert response.status_code==403 and 'DO-NOT-LEAK' not in response.text
    assert 'key' not in client.get('/api/settings').json()

def test_arbitrary_provider_endpoint_rejected():
    with pytest.raises(ValueError):assistant.configure('local','x',endpoint='http://10.0.0.1/v1')

def test_api_source_required_for_vessel():
    client=TestClient(app)
    response=client.post('/api/vessels',json={'name':'No evidence','source_id':'x','locator':'p1'})
    assert response.status_code==400

@pytest.mark.parametrize('provider',['openai','anthropic','gemini','openrouter','local'])
def test_provider_adapters_send_real_tool_schemas(monkeypatch,provider):
    sent=[]
    class Response:
        status_code=200
        def json(self):
            if provider=='anthropic':return {'content':[{'type':'tool_use','id':'t1','name':'get_investigation','input':{}}],'usage':{'input_tokens':4,'output_tokens':2}}
            return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'t1','type':'function','function':{'name':'get_investigation','arguments':'{}'}}]}}],'usage':{'total_tokens':6}}
    class Client:
        def __init__(self,*a,**k):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def post(self,url,**kwargs):sent.append((url,kwargs));return Response()
    monkeypatch.setattr(assistant.httpx,'Client',Client)
    conf={'provider':provider,'model':'test-model','endpoint':assistant.PROVIDERS[provider]}
    m,t=assistant.complete([{'role':'system','content':assistant.SYSTEM},{'role':'user','content':'Investigate'}],conf,'SECRET')
    assert m['tool_calls'][0]['function']['name']=='get_investigation' and t==6
    assert sent[0][1]['json']['tools']
    if provider=='anthropic':assert 'input_schema' in sent[0][1]['json']['tools'][0]
    else:assert sent[0][1]['json']['tools'][0]['function']['parameters']['additionalProperties'] is False

def test_tool_loop_executes_and_persists_real_results(monkeypatch):
    seed();monkeypatch.setattr(assistant,'settings',lambda:{'configured':True,'provider':'openai','model':'test','endpoint':'https://api.openai.com/v1'})
    monkeypatch.setattr(assistant.keyring,'get_password',lambda *a:'SECRET')
    responses=iter([({'role':'assistant','content':None,'tool_calls':[{'id':'t1','type':'function','function':{'name':'get_investigation','arguments':'{}'}}]},6),({'role':'assistant','content':'Unidentified. SECRET'},3)])
    monkeypatch.setattr(assistant,'complete',lambda *a:next(responses))
    result=assistant.investigate('Research','testjob')
    assert 'SECRET' not in json.dumps(result)
    assert result['tokens']==9
    assert db.events('testjob')[1]['data']['result']['site']['name']=='Test site'
    assert 'SECRET' not in json.dumps(db.get('conversation','testjob'))

def test_research_job_resumes_at_checkpoint(monkeypatch):
    seed();calls=[]
    monkeypatch.setattr(connectors,'search_archive',lambda *args:calls.append(args) or {'results':[]})
    j=db.put('job',{'kind':'research','args':{},'status':'interrupted','checkpoint':3,'progress':50,'cancel_requested':False,'limits':{'wall_seconds':600,'max_steps':8,'max_tokens':30000}},'checkpoint')
    jobs.run(j['id']);assert db.get('job',j['id'])['status']=='complete'
    assert calls==[]

def test_full_source_search_reads_beyond_preview():
    seed();text='x'*510000+'\nACTOR evidence at end'
    (db.DATA/'sources/full.txt').write_text(text,encoding='utf8')
    db.put('source',{'title':'Register','status':'retrieved','sha256':'full','url':'https://archive.org/test','text':text[:500000]},'full')
    result=connectors.search_source('full','ACTOR')
    assert result['total_matches']==1 and result['matches'][0]['character_offset']==510001

def test_plain_ocr_preserves_columns_and_line_breaks(monkeypatch):
    text='ACTOR       108\nACTIVE       92\n<unreadable>\n'
    monkeypatch.setattr(connectors,'fetch',lambda url:(text.encode(),'text/plain',url))
    result=connectors.source('https://archive.org/download/test/test_djvu.txt')
    assert result['text']==text
    assert (db.DATA/'sources'/(result['sha256']+'.txt')).read_text()==text

def test_assistant_cooperative_cancel_resumes_pending_calls_once(monkeypatch):
    seed();monkeypatch.setattr(assistant,'settings',lambda:{'configured':True,'provider':'local'})
    calls=[{'id':f't{i}','type':'function','function':{'name':'get_investigation','arguments':'{}'}} for i in range(2)]
    responses=iter([({'role':'assistant','content':None,'tool_calls':calls},8),({'role':'assistant','content':'Review completed'},3)])
    monkeypatch.setattr(assistant,'complete',lambda *a:next(responses))
    performed=[]
    monkeypatch.setattr(assistant,'execute',lambda name,args:performed.append(name) or {'actual_result':'saved'})
    with pytest.raises(InterruptedError):assistant.investigate('Research','resume-tools',cancel=lambda:len(performed)==1)
    saved=db.get('conversation','resume-tools')
    assert len(performed)==1 and len(saved['pending_calls'])==1
    result=assistant.investigate('Research','resume-tools')
    assert len(performed)==2 and result['status']=='complete'
    assert len([e for e in db.events('resume-tools') if e['kind']=='tool'])==2

def test_followup_reuses_prior_conversation(monkeypatch):
    monkeypatch.setattr(assistant,'settings',lambda:{'configured':True,'provider':'local'})
    db.put('conversation',{'messages':[{'role':'system','content':assistant.SYSTEM},{'role':'user','content':'First request'},{'role':'assistant','content':'Earlier evidence'}],'steps':1,'tokens':5},'prior')
    seen=[]
    monkeypatch.setattr(assistant,'complete',lambda messages,*args:seen.extend(messages) or ({'role':'assistant','content':'Followup answer'},2))
    assistant.investigate('Compare that evidence','next',previous_job_id='prior')
    assert any(m.get('content')=='Earlier evidence' for m in seen)
    assert seen[-1]['content']=='Compare that evidence'
