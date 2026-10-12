import html
import json
from contextlib import asynccontextmanager
from typing import Literal
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel,Field,SecretStr
from . import db,connectors,analysis,research,assistant,jobs,investigations
from .mcp_server import create_http_app

mcp_app=create_http_app()

@asynccontextmanager
async def lifespan(app):
    investigations.initialize_sample()
    async with mcp_app.router.lifespan_context(mcp_app):
        yield

app=FastAPI(title='Shipwreck Hunting Tool',version='0.1.0',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','[::1]','testserver'])

@app.middleware('http')
async def local_only(request:Request,call_next):
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin:
        p=urlparse(origin)
        try:
            same_origin=(p.scheme,p.hostname,p.port)==(request.url.scheme,request.url.hostname,request.url.port)
            dev_origin=p.scheme=='http' and p.hostname in ('localhost','127.0.0.1','::1') and p.port==5173
            allowed=(same_origin or dev_origin) and not p.username and not p.password
        except ValueError:allowed=False
        if not allowed:return JSONResponse({'detail':'Cross-origin mutation blocked'},403)
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
def workspace(site_id:str=investigations.DEFAULT):
    site=investigations.get(site_id)
    sources=[{k:v for k,v in s.items() if k!='text'} for s in investigations.sources(site_id)]
    return {'site':site,'investigations':db.all_records('site'),'notes':investigations.notes(site_id),'claims':db.claims(site_id),'sources':sources,'vessels':research.rank(site_id),'datasets':investigations.records(site_id,'dataset'),'runs':investigations.records(site_id,'run'),'candidates':investigations.records(site_id,'candidate'),'coverage':db.get('coverage','wrecks:'+site_id),'settings':assistant.settings(),'evaluations':investigations.records(site_id,'evaluation')}

class InvestigationRequest(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    region:str=Field(default='',max_length=300)
    objective:str=Field(default='',max_length=4000)

@app.get('/api/investigations')
def list_investigations():return db.all_records('site')

@app.post('/api/investigations')
def create_investigation(r:InvestigationRequest):return investigations.create(**r.model_dump())

@app.get('/api/map')
def map_data(site_id:str=investigations.DEFAULT):
    features=[]
    for w in investigations.records(site_id,'wreck'):
        if w['lon'] is None or w['lat'] is None:continue
        features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[w['lon'],w['lat']]},'properties':{'id':w['id'],'name':w['name'],'quality':w['position_quality'],'kind':'wreck','status':w['status'],'year':w.get('year') or 0}})
    return {'wrecks':{'type':'FeatureCollection','features':features},'surveys':{'type':'FeatureCollection','features':[s['feature'] for s in investigations.records(site_id,'survey') if s.get('feature')]}}

@app.get('/api/wrecks/{id}')
def wreck(id:str):
    r=db.get('wreck',id)
    if not r:raise HTTPException(404,'Record not found')
    return r

@app.get('/api/surveys/{id}/products')
def products(id:str):return connectors.products(id)

class SurveyRegistration(BaseModel):
    survey_id:str=Field(pattern=r'^[HW]\d{5}$')

@app.post('/api/surveys/register')
def register_survey(r:SurveyRegistration,site_id:str|None=None):
    if site_id:investigations.get(site_id)
    result=connectors.register_survey(r.survey_id)
    if site_id:
        investigations.link(site_id,'survey',result['id'])
        if result.get('metadata_source_id'):investigations.link(site_id,'source',result['metadata_source_id'])
    return result

@app.get('/api/surveys')
def saved_surveys(site_id:str|None=None):return investigations.records(site_id,'survey') if site_id else db.all_records('survey')

class ProductInspection(BaseModel):
    url:str=Field(max_length=2000)
    kind:Literal['bathymetry','sidescan']='bathymetry'
    max_bytes:int=Field(default=250_000_000,ge=1,le=1_000_000_000)

@app.post('/api/survey-products/inspect')
def inspect_product(r:ProductInspection):return connectors.inspect_product(**r.model_dump())

class Region(BaseModel):
    bbox:list[float]=Field(min_length=4,max_length=4)

@app.post('/api/investigations/{id}/region')
def investigation_region(id:str,r:Region):return investigations.set_bounds(id,r.bbox)

@app.post('/api/surveys/discover')
def discover(r:Region,site_id:str|None=None):
    if site_id:investigations.set_bounds(site_id,r.bbox)
    result=connectors.discover_surveys(r.bbox)
    if site_id:
        for f in result['features']:investigations.link(site_id,'survey',f['properties']['SURVEY_ID'])
    return result

@app.post('/api/wrecks/sync')
def sync(r:Region,site_id:str|None=None):
    if site_id:investigations.set_bounds(site_id,r.bbox)
    return connectors.sync_wrecks(r.bbox,site_id)

@app.get('/api/sources/{id}')
def source(id:str):
    s=db.get('source',id)
    if not s:raise HTTPException(404,'Source not found')
    return s

@app.get('/api/sources/{id}/search')
def source_search(id:str,q:str,offset:int=Query(default=0,ge=0),limit:int=Query(default=12,ge=1,le=30)):return connectors.search_source(id,q,offset,limit)

class SourceRequest(BaseModel):
    url:str=Field(max_length=2000)

@app.post('/api/sources')
def fetch_source(r:SourceRequest,site_id:str|None=None):
    if site_id:investigations.get(site_id)
    result=connectors.source(r.url)
    if site_id:investigations.link(site_id,'source',result['id'])
    return result

@app.get('/api/search')
def search(q:str,archive:Literal['loc','internet_archive']='loc',from_year:int=1870,to_year:int=1925,site_id:str|None=None):
    if site_id:investigations.get(site_id)
    result=connectors.search_archive(q,archive,from_year,to_year)
    if site_id:investigations.link(site_id,'search',result['id'])
    return result

@app.get('/api/archive-files/{identifier}')
def archive_files(identifier:str):return connectors.archive_files(identifier)

@app.get('/api/history')
def history(site_id:str|None=None):
    if site_id is None:return {'searches':db.all_records('search'),'events':db.events()}
    investigations.get(site_id)
    ids={j['id'] for j in db.all_records('job') if investigations.job_site(j)==site_id}
    return {'searches':investigations.records(site_id,'search'), 'events':[e for e in db.events() if e.get('job_id') in ids]}


@app.get('/api/entities')
def entities(name:str,site_id:str|None=None):return research.entity_links(name,site_id)

class VesselRequest(BaseModel):
    site_id:str=investigations.DEFAULT
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
def vessel(r:VesselRequest,site_id:str|None=None):
    if site_id:r.site_id=site_id
    investigations.get(r.site_id)
    if not db.get('source',r.source_id):raise ValueError('Save a source first')
    d=r.model_dump();d['source_ids']=[d.pop('source_id')];locator=d.pop('locator');v=db.put('vessel',d)
    for field,value in d.items():
        if value and field not in ('source_ids','aliases','site_id'):db.claim(v['id'],field,value,r.source_id,locator,'researcher transcription')
    return v

class ClaimRequest(BaseModel):
    subject:str
    field:str=Field(min_length=1,max_length=200)
    value:str=Field(min_length=1,max_length=4000)
    source_id:str
    locator:str=Field(min_length=1,max_length=500)
    stance:Literal['observation','supports','contradicts','hypothesis','missing']='observation'

@app.post('/api/claims')
def claim(r:ClaimRequest,site_id:str|None=None):
    if site_id:
        investigations.get(site_id)
        if r.subject!=site_id:raise ValueError('Evidence must belong to the selected investigation')
    db.claim(**r.model_dump())
    return {'saved':True}

class JobRequest(BaseModel):
    kind:Literal['analysis','ingest','research','assistant']
    args:dict=Field(default_factory=dict)

@app.post('/api/jobs')
def submit(r:JobRequest,site_id:str|None=None):return jobs.submit(r.kind,{**r.args,**({'site_id':site_id} if site_id else {})})

@app.get('/api/jobs')
def list_jobs(site_id:str|None=None):return [j for j in db.all_records('job') if site_id is None or investigations.job_site(j)==site_id]

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
    reason:str=Field(min_length=1,max_length=2000)

@app.get('/api/candidates')
def candidates(offset:int=Query(default=0,ge=0),limit:int=Query(default=50,ge=1,le=100),run_id:str|None=None,dataset_id:str|None=None,survey_id:str|None=None,status:Literal['unreviewed','follow-up','rejected','known-feature']|None=None,include_coordinates:bool=False,site_id:str|None=None):
    return db.list_detections(offset,limit,run_id,dataset_id,survey_id,status,include_coordinates,site_id)

@app.post('/api/candidates/{id}/review')
def review(id:str,r:Review):
    c=db.get('candidate',id)
    if not c:raise HTTPException(404,'Candidate not found')
    return db.review_candidate(id,r.status,r.reason)

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
def report(format:Literal['markdown','html','json']='markdown',site_id:str=investigations.DEFAULT):
    text=research.report(site_id)
    if format=='json':
        return {'site':investigations.get(site_id),'claims':db.claims(site_id),'notes':investigations.notes(site_id),'vessels':research.rank(site_id),'sources':[{k:v for k,v in x.items() if k!='text'} for x in investigations.sources(site_id)],'coordinate_policy':'withheld; no sensitive site coordinates in this report'}
    if format=='html':
        import markdown
        body=markdown.markdown(html.escape(text),extensions=['tables'])
        return Response('<!doctype html><meta charset="utf-8"><title>Shipwreck investigation report</title><style>body{font:16px/1.65 system-ui;max-width:900px;margin:50px auto;padding:0 28px;color:#172631}a{color:#126c86}h1,h2,h3{line-height:1.25}code{overflow-wrap:anywhere}@media print{body{margin:0}a{color:inherit}}</style>'+body,media_type='text/html')
    return Response(text,media_type='text/markdown',headers={'Content-Disposition':f'attachment; filename="{investigations.get(site_id)["id"]}-report.md"'})

# Only images/derived artifacts are served; raw source snapshots, DB and secrets
# cannot be fetched by guessing a static file path.
# Register the exact /mcp route before the catch-all frontend, without redirects.
app.router.routes.extend(mcp_app.routes)
app.mount('/data/media',StaticFiles(directory=db.DATA/'media'),name='media')
app.mount('/data/derived',StaticFiles(directory=db.DATA/'derived'),name='derived')
DIST=db.ROOT/'frontend/dist'
if DIST.exists():app.mount('/',StaticFiles(directory=DIST,html=True),name='frontend')
