"""Live public-source connectors, with immutable downloaded evidence and bounded IO."""
import hashlib
import io
import json
import re
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from . import db

SURVEYS='https://gis.ngdc.noaa.gov/arcgis/rest/services/web_mercator/nos_hydro_dynamic/MapServer/0'
WRECKS='https://services5.arcgis.com/HDRa0B57OVrv2E1q/arcgis/rest/services/Wrecks_and_Obstructions/FeatureServer/0'
ALLOWED=('noaa.gov','usgs.gov','loc.gov','archive.org','nps.gov','mass.gov','lrfoundation.org.uk','mua.apps.uri.edu','kirstinmeyer.blogspot.com','boem.gov','marinecadastre.gov','archives.gov','biodiversitylibrary.org','collections.mnhs.org','oregonnews.uoregon.edu','chroniclingamerica.loc.gov')
HEADERS={'User-Agent':'GHOSTFLEET/0.1 (local maritime research; public sources)'}

def validate_url(url):
    p=urlparse(url)
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not any(p.hostname==x or (p.hostname or '').endswith('.'+x) for x in ALLOWED):
        raise ValueError('Use an HTTPS URL from a supported public research archive')
    return url

def fetch(url, limit=25_000_000):
    with httpx.Client(timeout=40,headers=HEADERS,follow_redirects=False) as client:
        for _ in range(6):
            validate_url(url)
            with client.stream('GET',url) as r:
                if r.is_redirect:
                    url=urljoin(url,r.headers['location']);continue
                r.raise_for_status()
                chunks=[];size=0
                for chunk in r.iter_bytes():
                    size+=len(chunk)
                    if size>limit:raise ValueError('Source exceeds download limit')
                    chunks.append(chunk)
                return b''.join(chunks),r.headers.get('content-type',''),str(r.url)
    raise ValueError('Too many redirects')

def source(url, refresh=False):
    validate_url(url)
    id=hashlib.sha256(url.encode()).hexdigest()[:16]
    saved=db.get('source',id)
    if saved and not refresh:return saved
    try:
        raw,ctype,final=fetch(url)
        digest=hashlib.sha256(raw).hexdigest()
        (db.DATA/'sources'/digest).write_bytes(raw)
        links=[]
        if 'pdf' in ctype or raw.startswith(b'%PDF'):
            pages=PdfReader(io.BytesIO(raw)).pages
            text='\n'.join(f'\n[PDF page {i+1}]\n'+(p.extract_text() or '') for i,p in enumerate(pages[:300]))
            title=url.rsplit('/',1)[-1]
        elif 'text/plain' in ctype or urlparse(final).path.endswith('.txt'):
            title=url.rsplit('/',1)[-1]
            text=raw.decode('utf-8',errors='replace')
        else:
            soup=BeautifulSoup(raw,'html.parser')
            title=soup.title.get_text(' ',strip=True) if soup.title else url
            for a in soup.select('a[href]'):
                target=urljoin(final,a['href'])
                try:validate_url(target)
                except ValueError:continue
                links.append({'title':a.get_text(' ',strip=True)[:200],'url':target})
            for el in soup(['script','style','nav','header','footer']):el.decompose()
            text=soup.get_text(' ',strip=True)
        (db.DATA/'sources'/(digest+'.txt')).write_text(text,encoding='utf8')
        return db.put('source',{'url':url,'resolved_url':final,'title':title,'sha256':digest,'retrieved':db.now(),'status':'retrieved','text':text[:500_000],'text_length':len(text),'text_preview_truncated':len(text)>500_000,'links':links[:120],'content_type':ctype,'reliability':'archive document; evaluate original author and OCR','version_previous':saved.get('sha256') if saved else None},id)
    except Exception as e:
        code=e.response.status_code if isinstance(e,httpx.HTTPStatusError) else None
        return db.put('source',{'url':url,'title':url,'status':'unavailable','retrieved':db.now(),'error':f'HTTP {code}' if code else type(e).__name__,'text':''},id)

def arcgis(base, bbox, geojson=True):
    if len(bbox)!=4 or not(-180<=bbox[0]<bbox[2]<=180 and -90<=bbox[1]<bbox[3]<=90):raise ValueError('Invalid west,south,east,north bounds')
    features=[];offset=0
    with httpx.Client(timeout=45,headers=HEADERS) as client:
        while offset<10000:
            params={'f':'geojson' if geojson else 'json','where':'1=1','geometry':','.join(map(str,bbox)),'geometryType':'esriGeometryEnvelope','inSR':4326,'outSR':4326,'outFields':'*','resultRecordCount':1000,'resultOffset':offset,'orderByFields':'OBJECTID' if geojson else 'OBJECTID_1'}
            r=client.get(base+'/query',params=params);r.raise_for_status();d=r.json()
            if 'error' in d:raise ValueError('Archive query failed: '+str(d['error'].get('message')))
            batch=d.get('features',[]);features+=batch
            if not d.get('exceededTransferLimit') and len(batch)<1000:break
            if not batch:break
            offset+=len(batch)
    return features,offset>=10000

def discover_surveys(bbox):
    features,truncated=arcgis(SURVEYS,bbox)
    for f in features:
        p=f['properties'];db.put('survey',{'feature':f,'name':p['SURVEY_ID'],'year':p.get('SURVEY_YEAR'),'locality':p.get('SUBLOCALITY'),'url':p.get('DOWNLOAD_URL'),'catalog_source':SURVEYS,'retrieved':db.now()},p['SURVEY_ID'])
    return {'features':features,'count':len(features),'truncated':truncated,'source':SURVEYS,'bbox':bbox}

def sync_wrecks(bbox):
    features,truncated=arcgis(WRECKS,bbox,False)
    for f in features:store_wreck(f)
    snapshot=db.put('coverage',{'bbox':bbox,'count':len(features),'truncated':truncated,'source':WRECKS,'retrieved':db.now(),'limitation':'Third-party ArcGIS copy of NOAA AWOIS. Histories may be truncated; incomplete inventory, not a verified wreck census.'},'wrecks')
    return snapshot

def store_wreck(f):
    p=f['attributes'];g=f.get('geometry',{})
    return db.put('wreck',{'name':p.get('vesselTerm') or 'Unnamed record','lon':g.get('x',p.get('longitudeD')),'lat':g.get('y',p.get('latitudeDD')),'position_quality':p.get('positionQu','Unknown'),'position_source':p.get('positionSo'),'history':p.get('history'),'year':p.get('yearSunk') or None,'raw':p,'source_url':WRECKS,'status':'catalogued; verification not inferred','retrieved':db.now()},str(p.get('record',p['OBJECTID_1'])))

def products(survey_id):
    survey=db.get('survey',survey_id)
    if not survey:raise ValueError('Discover this survey first')
    raw,_,_=fetch(survey['url'])
    soup=BeautifulSoup(raw,'html.parser');out=[]
    for a in soup.select('a[href]'):
        url=urljoin(survey['url'],a['href'])
        if re.search(r'\.(bag|tif|tiff|xml|pdf|jpg|tfw|jpw)(\?|$)',url,re.I):
            out.append({'name':a.get_text(' ',strip=True),'url':url,'ingestible':bool(re.search(r'\.(bag|tif|tiff)$',url,re.I))})
    return out

def download(url,max_bytes=250_000_000,cancel=lambda:False):
    validate_url(url)
    name=urlparse(url).path.rsplit('/',1)[-1]
    if not re.fullmatch(r'[\w.-]+\.(bag|tif|tiff)',name,re.I):raise ValueError('Only BAG and GeoTIFF survey products are supported')
    destination=db.DATA/'raw'/(hashlib.sha256(url.encode()).hexdigest()[:10]+'-'+name)
    if destination.exists():return destination
    part=destination.with_suffix(destination.suffix+'.part')
    meta=part.with_suffix(part.suffix+'.json')
    start=part.stat().st_size if part.exists() else 0
    validator=json.loads(meta.read_text()).get('validator') if meta.exists() else None
    # Never concatenate ranges from potentially different source revisions.
    if not validator:start=0
    headers={'Range':f'bytes={start}-','If-Range':validator} if start else {}
    with httpx.Client(timeout=60,headers=HEADERS) as client:
        with client.stream('GET',url,headers=headers) as r:
            r.raise_for_status()
            if r.status_code not in (200,206):raise ValueError('Unexpected download response')
            if r.status_code==206 and not r.headers.get('content-range','').startswith(f'bytes {start}-'):raise ValueError('Invalid resume response')
            if r.status_code==200:start=0
            meta.write_text(json.dumps({'url':url,'validator':r.headers.get('etag') or r.headers.get('last-modified')}))
            if start+int(r.headers.get('content-length',0))>max_bytes:raise ValueError('Product exceeds download budget')
            with part.open('ab' if start else 'wb') as stream:
                size=start
                for chunk in r.iter_bytes(1024*1024):
                    if cancel():raise InterruptedError('Cancelled; partial download retained')
                    size+=len(chunk)
                    if size>max_bytes:raise ValueError('Product exceeds download budget')
                    stream.write(chunk)
    part.replace(destination)
    return destination

def search_archive(query, archive='loc',from_year=1870,to_year=1925):
    query=query.strip()[:300]
    if not query:raise ValueError('Enter search terms')
    if not 1600<=from_year<=to_year<=2100:raise ValueError('Invalid archive date range')
    key=hashlib.sha256((archive+query.lower()+str(from_year)+str(to_year)).encode()).hexdigest()[:16]
    cached=db.get('search',key)
    if cached and cached.get('status')=='complete':return {**cached,'cached':True}
    results=[]
    try:
        with httpx.Client(timeout=40,headers=HEADERS,follow_redirects=True) as c:
            if archive=='loc':
                r=c.get('https://www.loc.gov/search/',params={'fo':'json','q':query,'c':20,'dates':f'{from_year}/{to_year}'});r.raise_for_status()
                for x in r.json().get('results',[]):results.append({'title':x.get('title'),'url':(x.get('id') or x.get('url','')).replace('http://www.loc.gov/','https://www.loc.gov/'),'date':x.get('date'),'description':x.get('description',[]),'source':'Library of Congress catalogue; discovery record, not corroboration'})
            elif archive=='internet_archive':
                r=c.get('https://archive.org/advancedsearch.php',params={'q':f'({query}) AND year:[{from_year} TO {to_year}]','output':'json','rows':20,'fl[]':['identifier','title','year']});r.raise_for_status()
                for x in r.json().get('response',{}).get('docs',[]):results.append({'title':x.get('title'),'url':'https://archive.org/details/'+x['identifier'],'date':x.get('year'),'description':[],'source':'Internet Archive catalogue; inspect scan before making a claim'})
            else:raise ValueError('Unknown archive')
        result={'query':query,'archive':archive,'from_year':from_year,'to_year':to_year,'results':results,'retrieved':db.now(),'status':'complete'}
    except Exception as e:
        result={'query':query,'archive':archive,'results':[],'retrieved':db.now(),'status':'unavailable','error':type(e).__name__}
    return db.put('search',result,key)

def archive_files(identifier):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}',identifier):raise ValueError('Invalid Internet Archive identifier')
    raw,_,_=fetch('https://archive.org/metadata/'+identifier)
    data=json.loads(raw)
    return [{'name':f['name'],'url':f'https://archive.org/download/{identifier}/'+f['name'],'format':f.get('format'),'size':f.get('size'),'note':'OCR is unverified; check scan before asserting a registry entry'} for f in data.get('files',[]) if f['name'].endswith(('_djvu.txt','.pdf','_text.pdf'))][:40]

def search_source(source_id,query):
    saved=db.get('source',source_id)
    if not saved or saved['status']!='retrieved':raise ValueError('Retrieve source first')
    path=db.DATA/'sources'/(saved['sha256']+'.txt')
    text=path.read_text(encoding='utf8') if path.exists() else saved.get('text','')
    if not query.strip():raise ValueError('Enter a search term')
    matches=list(re.finditer(re.escape(query),text,re.I))
    return {'source_id':source_id,'url':saved['url'],'total_matches':len(matches),'text_length':len(text),'matches':[{'character_offset':m.start(),'excerpt':text[max(0,m.start()-400):m.end()+1600]} for m in matches[:12]],'warning':'OCR and column order may be wrong; inspect the original page before transcribing vessel specifications.'}
