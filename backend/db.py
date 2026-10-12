"""Small local research store. Source claims are append-only, never merged away."""
import json
import os
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('GHOSTFLEET_DATA', ROOT / 'data'))
DATA.mkdir(parents=True, exist_ok=True)
for directory in ('raw', 'derived', 'sources', 'media', 'exports'):
    (DATA / directory).mkdir(exist_ok=True)

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return uuid.uuid4().hex[:16]

def connect():
    c = sqlite3.connect(DATA / 'ghostfleet.sqlite', timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    return c

def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, subject TEXT NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, source_id TEXT NOT NULL, locator TEXT NOT NULL, stance TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, kind TEXT NOT NULL, data TEXT NOT NULL, created TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS claims_subject ON claims(subject);
        CREATE INDEX IF NOT EXISTS events_job ON events(job_id);
        ''')

def put(kind, data, id=None):
    id = id or data.get('id') or uid()
    data = {**data, 'id': id}
    with connect() as c:
        c.execute('INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data,updated=excluded.updated', (kind,id,json.dumps(data,allow_nan=False),now()))
    return data

def get(kind, id):
    with connect() as c:
        r = c.execute('SELECT data FROM records WHERE kind=? AND id=?',(kind,id)).fetchone()
    return json.loads(r[0]) if r else None

def all_records(kind):
    with connect() as c:
        rows=c.execute('SELECT data FROM records WHERE kind=? ORDER BY updated DESC',(kind,)).fetchall()
    return [json.loads(r[0]) for r in rows]


def put_many(records):
    """Publish a completed run and its candidates together, never a partial run."""
    with connect() as c:
        c.executemany('INSERT INTO records VALUES(?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data,updated=excluded.updated',
                      [(kind,item['id'],json.dumps(item,allow_nan=False),now()) for kind,item in records])


def list_detections(offset=0,limit=50,run_id=None,dataset_id=None,survey_id=None,status=None,include_coordinates=False,site_id=None):
    if not isinstance(offset,int) or offset<0 or not isinstance(limit,int) or not 1<=limit<=100:raise ValueError('Invalid pagination')
    if status is not None and status not in ('unreviewed','follow-up','rejected','known-feature'):raise ValueError('Invalid review status')
    clauses=["c.kind='candidate'", "EXISTS (SELECT 1 FROM records r WHERE r.kind='run' AND r.id=json_extract(c.data,'$.run_id'))"];values=[]
    for field,value in [('run_id',run_id),('dataset_id',dataset_id),('status',status)]:
        if value is not None:clauses.append(f"json_extract(c.data,'$.{field}')=?");values.append(value)
    if survey_id is not None:
        clauses.append("EXISTS (SELECT 1 FROM records d WHERE d.kind='dataset' AND d.id=json_extract(c.data,'$.dataset_id') AND json_extract(d.data,'$.survey_id')=?)");values.append(survey_id)
    scoped_datasets=None
    if site_id:
        from . import investigations
        investigations.get(site_id)
        scoped_datasets=investigations.linked_ids(site_id,'dataset')
        clauses.append("EXISTS (SELECT 1 FROM records l WHERE l.kind='investigation_link' AND json_extract(l.data,'$.site_id')=? AND json_extract(l.data,'$.kind')='dataset' AND json_extract(l.data,'$.entity_id')=json_extract(c.data,'$.dataset_id'))")
        values.append(site_id)
    where=' AND '.join(clauses)
    with connect() as c:
        total=c.execute('SELECT count(*) FROM records c WHERE '+where,values).fetchone()[0]
        rows=c.execute("SELECT c.data FROM records c WHERE "+where+" ORDER BY json_extract(c.data,'$.score') DESC,c.id LIMIT ? OFFSET ?",[*values,limit,offset]).fetchall()
    candidates=[json.loads(r[0]) for r in rows]
    if not include_coordinates:candidates=[{k:v for k,v in x.items() if k not in ('lon','lat')} for x in candidates]
    datasets={d['id']:d for d in all_records('dataset')}
    runs=[{k:v for k,v in r.items() if k!='candidates'} for r in all_records('run')
          if (scoped_datasets is None or r['dataset_id'] in scoped_datasets) and (not run_id or r['id']==run_id) and (not dataset_id or r['dataset_id']==dataset_id)
          and (not survey_id or datasets.get(r['dataset_id'],{}).get('survey_id')==survey_id)]
    return {'candidates':candidates,'total':total,'offset':offset,'limit':limit,'next_offset':offset+limit if offset+limit<total else None,
            'runs':runs,'legacy_truncated_run_ids':[r['id'] for r in runs if r.get('truncated')],
            'coordinate_policy':'internal coordinates included by request' if include_coordinates else 'omitted; request include_coordinates for local review',
            'limitation':'Window and repeated-run candidates are not spatially deduplicated. Inventory absence does not establish discovery.'}


def review_candidate(candidate_id,status,reason):
    if status not in ('unreviewed','follow-up','rejected','known-feature'):raise ValueError('Invalid review status')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValueError('Review requires a reason of 1 to 2000 characters')
    candidate=get('candidate',candidate_id)
    if not candidate:raise ValueError('Candidate not found')
    event(None,'review',{'candidate_id':candidate_id,'previous':candidate['status'],'status':status,'reason':reason})
    return put('candidate',{**candidate,'status':status,'reason':reason.strip(),'reviewed':now()})

def claim(subject, field, value, source_id, locator, stance='observation', id=None):
    if not get('source', source_id):
        raise ValueError('A saved source is required for every claim')
    with connect() as c:
        c.execute('INSERT OR IGNORE INTO claims VALUES(?,?,?,?,?,?,?,?)', (id or uid(),subject,field,json.dumps(value),source_id,locator,stance,now()))

def claims(subject):
    with connect() as c:
        rows=c.execute('SELECT * FROM claims WHERE subject=? ORDER BY created',(subject,)).fetchall()
    return [{**dict(r),'value':json.loads(r['value'])} for r in rows]

def event(job_id, kind, data):
    with connect() as c:
        c.execute('INSERT INTO events(job_id,kind,data,created) VALUES(?,?,?,?)',(job_id,kind,json.dumps(data,allow_nan=False),now()))

def events(job_id=None):
    with connect() as c:
        rows=c.execute('SELECT * FROM events '+('WHERE job_id=? ' if job_id else '')+'ORDER BY id DESC LIMIT 300', (job_id,) if job_id else ()).fetchall()
    return [{**dict(r),'data':json.loads(r['data'])} for r in rows]

init()
