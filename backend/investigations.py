"""Investigation identity and evidence scope; surveys/sources remain reusable libraries."""
import hashlib
from . import db

DEFAULT = 'mystery-collier'


def get(site_id=DEFAULT):
    site = db.get('site', site_id)
    if not site:
        raise ValueError('Unknown investigation')
    return site


def create(name, region='', objective=''):
    name, region, objective = name.strip(), region.strip(), objective.strip()
    if not name or len(name) > 200 or len(region) > 300 or len(objective) > 4000:
        raise ValueError('Enter an investigation name (up to 200 characters)')
    return db.put('site', {
        'name': name, 'region': region, 'objective': objective,
        'status': 'Not assessed', 'conclusion': 'No assessment recorded yet.',
        'next_steps': [], 'created': db.now(),
    })


def belongs(record, site_id):
    # Old vessel records belong only to the original investigation.
    return record.get('site_id', DEFAULT) == site_id


def notes(site_id):
    get(site_id)
    return [n for n in db.all_records('research_note') if belongs(n, site_id)]


def sources(site_id):
    ids = linked_ids(site_id, 'source') | {c['source_id'] for c in db.claims(site_id)}
    for n in notes(site_id):
        ids.update(n.get('source_ids', []))
    for v in db.all_records('vessel'):
        if belongs(v, site_id):
            ids.update(v.get('source_ids', []))
            ids.update(c['source_id'] for c in db.claims(v['id']))
    return [s for s in db.all_records('source') if s['id'] in ids]


def link(site_id, kind, entity_id):
    get(site_id)
    if not db.get(kind, entity_id):
        raise ValueError('Unknown record to attach')
    id = hashlib.sha256(f'{site_id}:{kind}:{entity_id}'.encode()).hexdigest()[:24]
    return db.put('investigation_link', dict(site_id=site_id, kind=kind, entity_id=entity_id), id)


def linked_ids(site_id, kind):
    return {r['entity_id'] for r in db.all_records('investigation_link')
            if r['site_id'] == site_id and r['kind'] == kind}


def records(site_id, kind):
    get(site_id)
    if kind == 'source':
        return sources(site_id)
    if kind in ('run', 'candidate'):
        ids = linked_ids(site_id, 'dataset')
        return [r for r in db.all_records(kind) if r.get('dataset_id') in ids]
    if kind == 'evaluation':
        runs = {r['id'] for r in records(site_id, 'run')}
        return [r for r in db.all_records(kind) if any(t.get('run_id') in runs for t in r.get('results', []))]
    ids = linked_ids(site_id, kind)
    return [r for r in db.all_records(kind) if r['id'] in ids]


def job_site(job):
    args = job.get('args', {})
    return args.get('site_id') or args.get('arguments', {}).get('site_id')


def require_link(site_id, kind, id):
    if id not in {r['id'] for r in records(site_id, kind)}:
        raise ValueError('Record does not belong to this investigation')


def set_bounds(site_id, bbox):
    if len(bbox) != 4 or not (-180 <= bbox[0] < bbox[2] <= 180 and -90 <= bbox[1] < bbox[3] <= 90):
        raise ValueError('Invalid research bounds')
    return db.put('site', {**get(site_id), 'bbox': bbox})


def initialize_sample():
    """Label the default example without creating or modifying user investigations."""
    if db.get('site', DEFAULT):
        db.put('site', {**get(DEFAULT), 'sample': True})


def report(site_id):
    site = get(site_id)
    lines = [f'# {site["name"]}', '', site.get('region', ''), '',
             '## Research objective', '', site.get('objective') or 'No objective recorded.', '',
             '## Current assessment', '', site.get('conclusion') or 'Not assessed.', '',
             'A research lead is not a detected wreck or an established identification.', '', '## Evidence', '']
    claims = db.claims(site_id)
    for c in claims:
        lines.append(f'- **{c["field"]}** ({c["stance"]}): {c["value"]} — {c["locator"]}. Source: {c["source_id"]}.')
    if not claims:
        lines.append('No evidence claims saved yet.')
    for note in notes(site_id):
        lines += ['', f'## {note["subject"]}', '', note['text'], '',
                  'Contradictions: ' + ('; '.join(note.get('contradictions', [])) or 'None recorded.'),
                  'Source records: ' + ', '.join(note.get('source_ids', []))]
    vessels = [v for v in db.all_records('vessel') if belongs(v, site_id)]
    if vessels:
        lines += ['', '## Historical vessel records', '']
        for v in vessels:
            lines += [f'- {v["name"]}: {v.get("notes", "Unreviewed historical record")}.']
    datasets={d['id']:d for d in records(site_id,'dataset')}
    if datasets:
        lines += ['', '## Survey screening', '']
        for run in records(site_id,'run'):
            dataset=datasets[run['dataset_id']]
            lines.append(f'- {dataset.get("name",dataset["id"])}: {len(run.get("candidates",[]))} screening candidates, not validated wrecks. [Original data]({dataset.get("url", "")}).')
    lines += ['', '## Sources', '']
    for s in sources(site_id):
        lines.append(f'- {s["id"]}: [{s.get("title", s["id"])}]({s.get("url", "")}); status {s.get("status", "unknown")}; retrieved {s.get("retrieved", "unknown")}.')
    return '\n'.join(lines)
