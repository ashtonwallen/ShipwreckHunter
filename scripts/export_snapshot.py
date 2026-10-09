"""Portable local evidence snapshot; contains coordinates, never credentials."""
import json
from backend import db,research

def export():
    with db.connect() as connection:
        records=[dict(r) for r in connection.execute("SELECT kind,id,data,updated FROM records WHERE kind NOT IN ('settings','conversation')")]
        claims=[dict(r) for r in connection.execute('SELECT * FROM claims')]
    for r in records:r['data']=json.loads(r['data'])
    snapshot={'created':db.now(),'sharing':'LOCAL RESEARCH: coordinates included; review before sharing','records':records,'claims':claims}
    (db.DATA/'exports/research-snapshot.json').write_text(json.dumps(snapshot,indent=2),encoding='utf8')
    (db.DATA/'exports/mystery-collier.md').write_text(research.report(),encoding='utf8')
    print(f'Exported {len(records)} records and {len(claims)} source claims; no credential settings included.')

if __name__=='__main__':export()
