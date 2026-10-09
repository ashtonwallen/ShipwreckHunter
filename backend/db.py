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
