import html
import json
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel,Field,SecretStr
from . import db,connectors,analysis,research,assistant,jobs

app=FastAPI(title='Shipwreck Hunting Tool',version='0.1.0')
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','[::1]','testserver'])

@app.middleware('http')
async def local_only(request:Request,call_next):
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin:
        p=urlparse(origin)
        if p.hostname not in ('localhost','127.0.0.1','::1') or p.port not in (8787,5173):return JSONResponse({'detail':'Cross-origin mutation blocked'},403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    return response

@app.exception_handler(ValueError)
async def value_error(request,exc):return JSONResponse({'detail':str(exc)[:400]},400)

@app.exception_handler(RequestValidationError)
async def invalid_request(request,exc):
    # Default validation responses echo raw inputs, including credential fields.
    return JSONResponse({'detail':'Invalid request fields: '+', '.join('.'.join(map(str,e['loc'])) for e in exc.errors())},422)

@app.exception_handler(Exception)
async def unexpected(request,exc):return JSONResponse({'detail':'Operation failed: '+type(exc).__name__},500)

@app.get('/api/health')
def health():return {'application':'GHOSTFLEET','status':'ok','version':'0.1.0','counts':{k:len(db.all_records(k)) for k in ('wreck','survey','dataset','candidate','source')}}

@app.get('/api/workspace')
def workspace():
    sources=[{k:v for k,v in s.items() if k!='text'} for s in db.all_records('source')]
    return {'site':db.get('site','mystery-collier'),'claims':db.claims('mystery-collier'),'sources':sources,'vessels':research.rank(),'datasets':db.all_records('dataset'),'runs':db.all_records('run'),'candidates':db.all_records('candidate'),'coverage':db.get('coverage','wrecks'),'settings':assistant.settings(),'evaluations':db.all_records('evaluation')}

@app.get('/api/map')
def map_data():
    features=[]
    for w in db.all_records('wreck'):
        if w['lon'] is None or w['lat'] is None:continue
        features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[w['lon'],w['lat']]},'properties':{'id':w['id'],'name':w['name'],'quality':w['position_quality'],'kind':'wreck','status':w['status'],'year':w.get('year') or 0}})
    return {'wrecks':{'type':'FeatureCollection','features':features},'surveys':{'type':'FeatureCollection','features':[s['feature'] for s in db.all_records('survey') if s.get('feature')]}}

@app.get('/api/wrecks/{id}')
def wreck(id:str):
    r=db.get('wreck',id)
    if not r:raise HTTPException(404,'Record not found')
    return r

@app.get('/api/surveys/{id}/products')
def products(id:str):return connectors.products(id)

class Region(BaseModel):
    bbox:list[float]=Field(min_length=4,max_length=4)

@app.post('/api/surveys/discover')
def discover(r:Region):return connectors.discover_surveys(r.bbox)

@app.post('/api/wrecks/sync')
def sync(r:Region):return connectors.sync_wrecks(r.bbox)

@app.get('/api/sources/{id}')
def source(id:str):
    s=db.get('source',id)
    if not s:raise HTTPException(404,'Source not found')
    return s

@app.get('/api/sources/{id}/search')
def source_search(id:str,q:str):return connectors.search_source(id,q)

class SourceRequest(BaseModel):
    url:str=Field(max_length=2000)

@app.post('/api/sources')
def fetch_source(r:SourceRequest):return connectors.source(r.url)

@app.get('/api/search')
def search(q:str,archive:Literal['loc','internet_archive']='loc',from_year:int=1870,to_year:int=1925):return connectors.search_archive(q,archive,from_year,to_year)

@app.get('/api/archive-files/{identifier}')
def archive_files(identifier:str):return connectors.archive_files(identifier)

@app.get('/api/history')
def history():return {'searches':db.all_records('search'),'events':db.events()}

@app.get('/api/entities')
def entities(name:str):return research.entity_links(name)

class VesselRequest(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    aliases:list[str]=[]
    length_m:float|None=Field(default=None,gt=0,lt=500)
    beam_m:float|None=Field(default=None,gt=0,lt=100)
    construction:str|None=None
    rig:str|None=None
    cargo:str|None=None
    loss_date:str|None=None
    loss_location:str|None=None
    notes:str=''
    source_id:str
    locator:str=Field(min_length=1,max_length=500)

@app.post('/api/vessels')
def vessel(r:VesselRequest):
    if not db.get('source',r.source_id):raise ValueError('Save a source first')
    d=r.model_dump();d['source_ids']=[d.pop('source_id')];locator=d.pop('locator');v=db.put('vessel',d)
    for field,value in d.items():
        if value and field not in ('source_ids','aliases'):db.claim(v['id'],field,value,r.source_id,locator,'researcher transcription')
    return v

class ClaimRequest(BaseModel):
    subject:str
    field:str=Field(min_length=1,max_length=200)
    value:str=Field(min_length=1,max_length=4000)
    source_id:str
    locator:str=Field(min_length=1,max_length=500)
    stance:Literal['observation','supports','contradicts','hypothesis','missing']='observation'

@app.post('/api/claims')
def claim(r:ClaimRequest):db.claim(**r.model_dump());return {'saved':True}

class JobRequest(BaseModel):
    kind:Literal['analysis','ingest','research','assistant']
    args:dict=Field(default_factory=dict)

@app.post('/api/jobs')
def submit(r:JobRequest):return jobs.submit(r.kind,r.args)

@app.get('/api/jobs')
def list_jobs():return db.all_records('job')

@app.get('/api/jobs/{id}')
def job(id:str):
    j=db.get('job',id)
    if not j:raise HTTPException(404,'Job not found')
    return {**j,'events':db.events(id)}

@app.post('/api/jobs/{id}/cancel')
def cancel(id:str):
    if not db.get('job',id):raise HTTPException(404,'Job not found')
    return jobs.cancel(id)

@app.post('/api/jobs/{id}/resume')
def resume(id:str):return jobs.resume(id)

@app.get('/api/datasets/{id}/surface')
def surface(id:str,candidate_id:str|None=None):return analysis.surface(id,candidate_id)

class Review(BaseModel):
    status:Literal['unreviewed','follow-up','rejected','known-feature']
    reason:str=Field(max_length=2000)

@app.post('/api/candidates/{id}/review')
def review(id:str,r:Review):
    c=db.get('candidate',id)
    if not c:raise HTTPException(404,'Candidate not found')
    db.event(None,'review',{'candidate_id':id,'previous':c['status'],**r.model_dump()})
    return db.put('candidate',{**c,**r.model_dump(),'reviewed':db.now()})

class Configuration(BaseModel):
    provider:Literal['openai','anthropic','gemini','openrouter','local']
    model:str=Field(max_length=120)
    key:SecretStr=SecretStr('')
    endpoint:str|None=None

@app.get('/api/settings')
def settings():return assistant.settings()

@app.post('/api/settings')
def configure(r:Configuration):return assistant.configure(r.provider,r.model,r.key.get_secret_value(),r.endpoint)

@app.get('/api/report')
def report(format:Literal['markdown','html','json']='markdown'):
    text=research.report()
    if format=='json':
        return {'site':db.get('site','mystery-collier'),'claims':db.claims('mystery-collier'),'vessels':research.rank(),'sources':[{k:v for k,v in x.items() if k!='text'} for x in db.all_records('source')],'coordinate_policy':'withheld; no sensitive site coordinates in this report'}
    if format=='html':
        import markdown
        body=markdown.markdown(html.escape(text),extensions=['tables'])
        return Response('<!doctype html><meta charset="utf-8"><title>Shipwreck investigation report</title><style>body{font:16px/1.65 system-ui;max-width:900px;margin:50px auto;padding:0 28px;color:#172631}a{color:#126c86}h1,h2,h3{line-height:1.25}code{overflow-wrap:anywhere}@media print{body{margin:0}a{color:inherit}}</style>'+body,media_type='text/html')
    return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="Mystery-Collier-report.md"'})

# Only images/derived artifacts are served; raw source snapshots, DB and secrets
# cannot be fetched by guessing a static file path.
app.mount('/data/media',StaticFiles(directory=db.DATA/'media'),name='media')
app.mount('/data/derived',StaticFiles(directory=db.DATA/'derived'),name='derived')
DIST=db.ROOT/'frontend/dist'
if DIST.exists():app.mount('/',StaticFiles(directory=DIST,html=True),name='frontend')
