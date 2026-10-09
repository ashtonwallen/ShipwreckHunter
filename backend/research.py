"""Auditable vessel comparison and source-backed reports."""
import difflib
import math
import re
from . import db

def normalize(name):
    return re.sub(r'[^a-z0-9]','',name.lower())

def entity_links(name):
    result=[]
    for v in db.all_records('vessel'):
        names=[v['name']]+v.get('aliases',[])
        scores=[(difflib.SequenceMatcher(None,normalize(name),normalize(n)).ratio(),n) for n in names]
        score,match=max(scores)
        if score>.55:result.append({'vessel_id':v['id'],'name':v['name'],'matched_name':match,'similarity':round(score,3),'reason':'Normalized punctuation/case and character sequence similarity. Name alone never establishes identity.','auto_merged':False})
    return sorted(result,key=lambda x:x['similarity'],reverse=True)

def rank(site_id='mystery-collier'):
    site=db.get('site',site_id)
    if not site:raise ValueError('Unknown investigation')
    results=[]
    # Transparent compatibility, not Bayesian posterior. Missing dimensions
    # contribute zero, so absent measurements cannot increase the score.
    for vessel in db.all_records('vessel'):
        rows=[];support=[];contradictions=[];missing=[];score=0
        for field,weight,tolerance in [('length_m',35,.2),('beam_m',25,.25)]:
            a=site.get(field);b=vessel.get(field)
            if a and b:
                relative=abs(a-b)/a;value=math.exp(-.5*(relative/tolerance)**2);score+=weight*value
                rows.append({'field':field,'wreck':a,'vessel':b,'weight':weight,'contribution':round(weight*value,1),'relative_difference':round(relative,3),'caution':'Sonar surviving extent and registry dimensions may use different conventions'})
                (support if relative<=tolerance else contradictions).append(f'{field}: {b:.1f} m versus wreck estimate {a:.1f} m')
            else:missing.append(field)
        for field,target,weight in [('construction','wood',10),('rig','schooner',10),('cargo','coal',20)]:
            val=vessel.get(field)
            if val:
                match=target in val.lower();score+=weight if match else 0
                (support if match else contradictions).append(f'{field}: {val}')
                rows.append({'field':field,'wreck':target,'vessel':val,'weight':weight,'contribution':weight if match else 0})
            else:missing.append(field)
        contradictions+=vessel.get('contradictions',[])
        excluded=vessel.get('excluded',False)
        status='excluded by documented loss/site evidence' if excluded else 'unverified research lead'
        if not vessel.get('loss_date'):missing.append('loss date')
        if not vessel.get('loss_location'):missing.append('loss location')
        results.append({**vessel,'score':round(score,1),'score_type':'feature compatibility / 100; not identification probability','status':status,'support':support,'contradictions':contradictions,'missing':missing,'breakdown':rows})
    return sorted(results,key=lambda v:(v.get('excluded',False),-v['score']))

def report(site_id='mystery-collier'):
    site=db.get('site',site_id)
    if not site:raise ValueError('Unknown investigation')
    claims=db.claims(site_id);sources={s['id']:s for s in db.all_records('source')}
    lines=[f'# Shipwreck investigation — {site["name"]}',f'Generated {db.now()}','', '## Finding','',site['conclusion'],'','No definitive identification has been established. This report withholds site coordinates.','', '## Archaeological evidence','']
    used=set()
    for c in claims:
        source=sources.get(c['source_id'],{});used.add(c['source_id'])
        lines.append(f'- **{c["field"]}** ({c["stance"]}): {c["value"]}. [{source.get("title","Source")}]({source.get("url","")}) — {c["locator"]}.')
    lines+=['','## Historical leads and exclusions','','Compatibility scores are transparent heuristics, not posterior probabilities. Missing measurements, incomplete casualty inventories and differences between surviving wreck extent and registered dimensions prevent a confident ranking.']
    for v in rank(site_id):
        lines+=['',f'### {v["name"]} — {v["status"]}',f'Feature compatibility: {v["score"]}/100. {v.get("notes","")}', '', 'Supporting similarities: '+('; '.join(v['support']) or 'None established')+'.','Contradictions: '+('; '.join(v['contradictions']) or 'None recorded; absence of contradiction is not support')+'.','Missing: '+(', '.join(v['missing']) or 'No fields missing in this limited comparison')+'.']
        for c in db.claims(v['id']):
            source=sources.get(c['source_id'],{});used.add(c['source_id']);lines.append(f'- {c["field"]}: {c["value"]} [{source.get("title","Source")}]({source.get("url","")}), {c["locator"]}.')
    lines+=['','## Tests that could discriminate between identities','']+[f'{i+1}. {s}' for i,s in enumerate(site['next_steps'])]
    lines+=['','## Research coverage and limitations','', 'The initial investigation searched NOAA archaeological accounts, a first-person expedition account, public heritage profiles, web-indexed contemporary newspaper reports and archive catalogues. It does not constitute a complete census of New England losses. Catalogue search hits are leads, not verified vessel records. OCR must be checked against scans. Broad date compatibility cannot tie a vessel to a particular storm.','', 'Digitized U.S. merchant-vessel register OCR was retrieved from Internet Archive. Names recur and OCR column order is corrupted. No dimensions were transferred from an adjacent OCR column into a candidate record without a page-level check.','', 'Lloyd’s Register casualty PDFs and the tested Library of Congress newspaper PDF returned HTTP 403. No unavailable page contents were inferred. AWOIS records come from an ArcGIS copy and some histories are truncated; this cannot establish the absence of a wreck.','', '## Survey screening demonstration','']
    for run in db.all_records('run'):
        ds=db.get('dataset',run['dataset_id'])
        lines +=[f'- {ds["name"]}: {len(run["candidates"])} unreviewed terrain candidates; {ds["resolution_m"]} m cells; parameters {run["parameters"]}; source SHA-256 `{ds["sha256"]}`. [Survey product]({ds["url"]}). {run["evaluation"]}']
    lines +=['','The Gloucester Harbor demonstration is a different site from the Mystery Collier. No detection has been validated as a new wreck. A missing catalogue match is not a discovery.']
    for evaluation in db.all_records('evaluation'):
        lines+=['','### Spatial holdout screening audit',evaluation['protocol'],evaluation['limitation']]
        for test in evaluation['results']:
            lines.append(f'- {test["method"]}: {test["known_wreck_points_near_detections"]}/{test["known_wreck_points_on_grid"]} selected documented wreck points and {test["known_rock_points_near_detections"]}/{test["known_rock_points_on_grid"]} selected documented rock points within 10 m of a candidate segment. These are proximity checks, not confirmed detections or a complete precision/recall estimate.')
    notes=db.all_records('research_note')
    if notes:
        lines+=['','## Saved AI research notes — unreviewed','']
        for note in notes:
            lines +=[f'### {note["subject"]}',note['text'],'Contradictions: '+'; '.join(note.get('contradictions',[]))]
            used.update(note.get('source_ids',[]))
    lines+=['','## Provenance','']
    for s in sources.values():
        if 'archive.org/download/' in s.get('url',''):used.add(s['id'])
    for id in sorted(used):
        s=sources.get(id,{})
        lines.append(f'- [{s.get("title",id)}]({s.get("url","")}); retrieved {s.get("retrieved","unknown")}; status {s.get("status")}; SHA-256 `{s.get("sha256","not retrieved")}`.')
    return '\n'.join(lines)
