"""Load real demonstration evidence and run reproducible screening.
Run from repository root: python -m scripts.seed
"""
import hashlib
import json
from pathlib import Path
from bs4 import BeautifulSoup
from backend import db,connectors,analysis,research

def archived(id,title,url,path,reliability):
    p=db.DATA/path
    if not p.exists():return connectors.source(url)
    raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if p.suffix=='.json':text=raw.decode('utf8')
    else:text=BeautifulSoup(raw,'html.parser').get_text(' ',strip=True)
    (db.DATA/'sources'/digest).write_bytes(raw)
    (db.DATA/'sources'/(digest+'.txt')).write_text(text,encoding='utf8')
    return db.put('source',{'title':title,'url':url,'retrieved':db.now(),'sha256':digest,'text':text,'status':'retrieved','reliability':reliability},id)

def seed():
    archived('noaa-collier','NOAA — Mystery Collier','https://stellwagen.noaa.gov/maritime/mystery-collier.html','research/collier.txt','Primary archaeological agency; public summary')
    archived('researcher-2020','Kirstin Meyer-Kaiser — The Mystery Collier, 28 July 2020','https://kirstinmeyer.blogspot.com/2020/07/the-mystery-collier.html','research/researcher.html','First-person expedition account; copper interpretation provisional')
    archived('mua-2011','Deborah Marx, NOAA — Fueling the Northeast','https://mua.apps.uri.edu/in_the_field/noaa_coal.shtml','research/mua.txt','NOAA archaeologist writing for Museum of Underwater Archaeology')
    archived('nps-tay','National Park Service — Tracking the Schooner Tay','https://www.nps.gov/articles/000/tracking-the-schooner-tay.htm','research/nps.txt','Government heritage synthesis citing registry and contemporary newspapers')
    archived('noaa-h11277','NOAA NCEI — H11277 survey metadata','https://www.ngdc.noaa.gov/nos/H10001-H12000/H11277.html','research/H11277.html','Primary survey archive')
    archived('awois-snapshot','AWOIS records — regional ArcGIS copy',connectors.WRECKS,'research/awois.txt','Derived copy of NOAA inventory; some text fields truncate source history')
    report=connectors.source('https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/DR/H11277.pdf')
    db.put('site',{'name':'Mystery Collier','status':'Unidentified','region':'Eastern Stellwagen Bank National Marine Sanctuary','location_note':'Precise site position is not published in the source profile. No inferred point is displayed.','depth_text':'> 400 ft / > 121.9 m','length_m':32.9184,'beam_m':7.0104,'period':'Possibly late 19th or early 20th century','construction':'Wood','rig':'Schooner; mast count uncertain','cargo':'Coal','conclusion':'The archaeological evidence supports a small wooden coal-carrying schooner. The available sources do not establish a named identity. The saved list separates sparse regional loss leads from vessels excluded by their documented wreck locations. No named candidate presently has enough independent support to be a leading identification.','next_steps':['Obtain NOAA’s measured site plan, original sonar metadata and diagnostic ROV frames; resolve the two-versus-three-mast ambiguity.','Check 90–125 ft wooden schooners in annual merchant registers, retaining registry identifiers and aliases. Broaden bounds if surviving hull length differs from registered length.','Trace each shortlisted vessel through later registers: apparent storm losses can have been repaired, as Tay illustrates.','Inspect loss reports and original newspaper scans for last cargo, voyage, disappearance and rescue locations. Test alternatives to an 1898 loss.','Compare copper sheathing, fasteners, stern form and artifact maker marks; request archaeological interpretation rather than dating from appearance alone.']},'mystery-collier')
    evidence=[('Surviving dimensions','Approximately 108 × 23 ft (32.9 × 7.0 m), estimated from side-scan sonar','Ship Stats','measurement estimate'),('Depth','More than 400 ft (121.9 m)','Ship Stats','source observation'),('Construction','Wooden schooner; builder and build year unknown','Ship Stats','source observation'),('Masts','Profile lists two; sonar caption permits two or three','Ship Stats and lead image caption','conflicting source claims'),('Cargo','Coal occurs on and around the wreck','Coal photograph caption','source observation'),('Loss period','Possibly late nineteenth or early twentieth century; not a dated loss','Ship Stats','hypothesis'),('Investigation','Located in 2003; examined with side-scan sonar and ROV imagery','Present Day','source observation'),('Artifacts','Bell, tableware, bottles, toilet and shoe photographed; no identifying inscription reported','Image captions','source observation'),('Identity','Name, registry, owner and fate of crew unknown; no named candidate in this profile','Ship Stats','missing evidence')]
    for i,(field,value,locator,stance) in enumerate(evidence):db.claim('mystery-collier',field,value,'noaa-collier',locator,stance,'collier-'+str(i))
    db.claim('mystery-collier','Hull surface','Expedition observer interpreted green hull material as likely copper sheathing; requires confirmation','researcher-2020','2020-07-28, paragraph discussing Calvin’s ROV observations','interpretation','copper')
    db.claim('mystery-collier','Orientation','Expedition account describes north–south alignment in northeastern sanctuary','researcher-2020','2020-07-28, opening paragraph','source observation','orientation')
    db.claim('mystery-collier','Coal distribution','Archaeologist describes coal reaching the main deck beams','mua-2011','Mystery Collier image caption','source observation','coal-hold')
    surveys=json.loads((db.DATA/'research/surveys.txt').read_text())
    for f in surveys['features']:
        p=f['properties'];db.put('survey',{'feature':f,'name':p['SURVEY_ID'],'year':p['SURVEY_YEAR'],'locality':p['SUBLOCALITY'],'url':p['DOWNLOAD_URL'],'catalog_source':connectors.SURVEYS,'retrieved':db.now()},p['SURVEY_ID'])
    wrecks=json.loads((db.DATA/'research/awois.txt').read_text())
    for f in wrecks['features']:connectors.store_wreck(f)
    db.put('coverage',{'bbox':[-71,41.8,-69.8,43],'count':len(wrecks['features']),'truncated':False,'source':connectors.WRECKS,'retrieved':db.now(),'limitation':'Regional ArcGIS AWOIS copy; incomplete inventory with truncated histories. No absence or identification inference.'},'wrecks')
    for name in ['ACTOR','ACTIVE']:
        w=next(x for x in db.all_records('wreck') if x['name']==name)
        id=name.lower();date='1924' if name=='ACTOR' else '1921'
        db.put('vessel',{'name':name.title(),'aliases':[],'rig':'schooner','loss_date':date,'loss_location':'Massachusetts regional AWOIS position; not independently verified','source_ids':['awois-snapshot'],'excluded':False,'contradictions':['No dimensions, cargo or independent link to the Mystery Collier have been established.','Catalogue positions near Boston Harbor conflict with the northeastern Stellwagen account; original loss notices and position quality require checking.'],'notes':'Low-information regional loss lead with a spatial mismatch, not a proposed identification. Historical name has not been resolved to a unique registry entry.','catalog_record_id':w['id']},id)
        db.claim(id,'Reported loss',f'{name.title()}, schooner, reported sunk {date}','awois-snapshot',f'AWOIS record {w["id"]}; description field (truncated)','unverified historical report',id+'-loss')
    db.put('vessel',{'name':'Tay','aliases':[],'length_m':93.7*.3048,'beam_m':27.7*.3048,'construction':'wood','rig':'two-masted schooner','cargo':'coal on documented earlier voyages; lumber on final voyage','loss_date':'1911-07-29','loss_location':'Sand Beach / Grand Head, Acadia, Maine','excluded':True,'contradictions':['Documented shore wreck in Maine in 1911, not deep water at Stellwagen.','Later voyages disprove treating the 1898 storm damage as a final loss.','Final cargo was lumber.'],'notes':'Useful exclusion and measurement caution: NPS labels 27.7 ft width and 12.1 ft beam. This source terminology is inconsistent; inspect the original register before using either as an exact beam.','source_ids':['nps-tay']},'tay')
    db.claim('tay','Registry account','NPS summarizes an 1887 wooden two-masted schooner, 93.7 ft long and 27.7 ft wide, from Lloyd’s 1890 register','nps-tay','The Schooner Tay (1887–1911)','secondary transcription','tay-registry')
    db.claim('tay','Loss and survival','Damaged in 1898 but subsequently returned to trade; final loss at Sand Beach in July 1911','nps-tay','Chronological account and wreck photographs','documented contradiction','tay-loss')
    for id,name,length,masts in [('frank-palmer','Frank A. Palmer',274.5,4),('louise-crary','Louise B. Crary',267.1,5)]:
        s=connectors.source('https://stellwagen.noaa.gov/maritime/palmer-and-crary.html')
        db.put('vessel',{'name':name,'aliases':[],'length_m':length*.3048,'beam_m':44.2*.3048,'construction':'wood','rig':f'{masts}-masted schooner','cargo':'coal','loss_date':'1902-12-17','loss_location':'Known paired wreck site, Stellwagen region','excluded':True,'contradictions':['Much longer than the 108 ft sonar estimate.','Independently documented paired wreck site; not the isolated Mystery Collier.'],'notes':'Regional coal-trade comparator, excluded from identification. Current NOAA profile supplies dimensions; earlier web-indexed expedition account used rounded lengths.','source_ids':[s['id']]},id)
        db.claim(id,'Dimensions and fate',f'{length} ft long, 44.2 ft broad, {masts} masts; collision loss on 17 December 1902',s['id'],'Ship Stats and Historical Background','source observation',id+'-current-facts')
    for tile in (1,2,3,5,7):
        p=db.DATA/'raw'/f'H11277_MB_50cm_MLLW_{tile}of16.bag'
        d=analysis.ingest(p,'H11277','https://data.ngdc.noaa.gov/platforms/ocean/nos/coast/H10001-H12000/H11277/BAG/'+p.name,acquisition=['2003-09-08','2003-09-17'])
        if not any(r['dataset_id']==d['id'] and r['catalog_coverage'] for r in db.all_records('run')):
            r=analysis.detect(d['id']);print(p.name,len(r['candidates']),'candidates')
    (db.DATA/'exports/mystery-collier.md').write_text(research.report(),encoding='utf8')
    print('Saved',len(db.all_records('wreck')),'wreck records,',len(db.all_records('survey')),'surveys and sourced investigation')

if __name__=='__main__':seed()
