"""Two local workers; durable steps and explicit resumption, no external queue."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from . import db, connectors, analysis, research

POOL=ThreadPoolExecutor(max_workers=2,thread_name_prefix='ghostfleet')
LOCK=threading.RLock()
ACTIVE=set()

def recover():
    for job in db.all_records('job'):
        if job['status'] in ('running','queued'):
            db.put('job',{**job,'status':'interrupted','message':'Process stopped. Resume from saved checkpoint.'})

def update(id,**changes):
    with LOCK:
        j=db.get('job',id);j.update(changes);j['updated']=db.now();db.put('job',j)
        return j

def submit(kind,args):
    if kind not in ('analysis','ingest','research','assistant'):raise ValueError('Unsupported job')
    if len([j for j in db.all_records('job') if j['status'] in ('queued','running')])>=12:raise ValueError('Queue full')
    job=db.put('job',{'kind':kind,'args':args,'status':'queued','progress':0,'checkpoint':0,'created':db.now(),'cancel_requested':False,'message':'Queued','limits':{'wall_seconds':min(14400,max(30,args.get('wall_seconds',600))),'max_steps':min(100,max(1,args.get('max_steps',8))),'max_tokens':min(500000,max(1000,args.get('max_tokens',30000)))}})
    POOL.submit(run,job['id']);return job

def cancel(id):
    return update(id,cancel_requested=True,message='Cancellation requested; stops at next IO/processing checkpoint')

def resume(id,extra_steps=8):
    with LOCK:
        j=db.get('job',id)
        if not j:raise ValueError('Unknown job')
        if id in ACTIVE or j['status'] in ('queued','running'):raise ValueError('Job is already active')
        j['limits']['max_steps']=min(100,j['limits']['max_steps']+extra_steps)
        j['limits']['max_tokens']=min(500000,j['limits']['max_tokens']+30000)
        db.put('job',j);j=update(id,status='queued',cancel_requested=False)
        POOL.submit(run,id);return j

def run(id):
    with LOCK:
        if id in ACTIVE:return
        ACTIVE.add(id)
    job=update(id,status='running',message='Starting');start=time.monotonic()
    def stopped():return db.get('job',id)['cancel_requested'] or time.monotonic()-start>job['limits']['wall_seconds']
    def checkpoint(n,total):update(id,checkpoint=n,progress=round(100*n/total),message=f'Completed step {n} of {total}')
    try:
        args=job['args'];kind=job['kind']
        if stopped():raise InterruptedError()
        if kind=='analysis':
            update(id,message='Reading measured raster and screening anomalies',progress=15)
            result=analysis.detect(args['dataset_id'],args.get('method','residual'),args.get('threshold',3),args.get('scale_m',12),stopped)
        elif kind=='ingest':
            update(id,message='Downloading original product; partial transfers are retained',progress=10)
            path=connectors.download(args['url'],cancel=stopped)
            if stopped():raise InterruptedError()
            update(id,message='Validating CRS, units and grid',progress=75)
            survey=db.get('survey',args['survey_id']);p=survey.get('feature',{}).get('properties',{}) if survey else {}
            result=analysis.ingest(path,args['survey_id'],args['url'],args.get('kind','bathymetry'),[p.get('DATE_SURVEY_BEGIN'),p.get('DATE_SURVEY_END')],args.get('elevation_positive_up',True))
        elif kind=='assistant':
            from .assistant import investigate
            result=investigate(args['prompt'],id,job['limits']['max_steps'],job['limits']['max_tokens'],stopped,checkpoint,args.get('previous_job_id'))
        else:
            steps=[('Read archaeological profile',lambda:db.claims('mystery-collier')),('Search digitized newspapers',lambda:connectors.search_archive(args.get('query','coal schooner Boston lost'),'loc')),('Search vessel registry catalogues',lambda:connectors.search_archive('title:(merchant vessels United States) AND mediatype:texts','internet_archive')),('Test vessel hypotheses',research.rank),('Review contradictions',lambda:[{'name':v['name'],'contradictions':v['contradictions'],'missing':v['missing']} for v in research.rank()]),('Save source-backed report',lambda:{'report':research.report()})]
            for i,(name,fn) in enumerate(steps):
                if i<job['checkpoint']:continue
                if stopped():raise InterruptedError()
                update(id,message=name);r=fn();db.event(id,'research',{'step':name,'result':r});checkpoint(i+1,len(steps))
            result={'report_url':'/api/report?format=markdown','summary':'Evidence audit complete. No identification established. Review archived results and contradictions.'}
        db.event(id,'result',result)
        update(id,status='limited' if result.get('status')=='limited' else 'complete',progress=100,result=result,message='Saved results' if result.get('status')!='limited' else 'Resource limit reached')
    except InterruptedError:
        update(id,status='cancelled' if db.get('job',id)['cancel_requested'] else 'limited',message='Checkpoint saved; job can be resumed')
    except Exception as e:
        # Never serialize request headers, provider responses, or credentials.
        message=str(e)[:400] if isinstance(e,ValueError) else type(e).__name__
        db.event(id,'error',{'error':message});update(id,status='failed',message=message)
    finally:
        with LOCK:ACTIVE.discard(id)

recover()
