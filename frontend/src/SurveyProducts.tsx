import {useEffect,useState} from 'react';
import {api,fmt} from './api';

export default function SurveyProducts({surveyId,onSurvey,start,onError}:any){
 const [surveys,setSurveys]=useState<any[]>([]),[products,setProducts]=useState<any[]>([]),[registration,setRegistration]=useState(''),[busy,setBusy]=useState(false),[checks,setChecks]=useState<any>({}),[budget,setBudget]=useState(250);
 const refresh=()=>api('/surveys').then(setSurveys);
 useEffect(()=>{refresh().catch((e:any)=>onError(e.message))},[]);
 useEffect(()=>{setProducts([]);setChecks({})},[surveyId]);
 async function perform(fn:()=>Promise<any>){setBusy(true);try{await fn()}catch(e:any){onError(e.message)}finally{setBusy(false)}}
 const kind=(p:any)=>/SSS|sidescan|side.scan/i.test(p.name+' '+p.url)?'sidescan':'bathymetry';
 return <section className="survey-products"><h3>NOAA products</h3>
  <form className="button-row" onSubmit={e=>{e.preventDefault();perform(async()=>{const s=await api('/surveys/register',{survey_id:registration.trim().toUpperCase()});await refresh();onSurvey(s.id);setProducts(await api('/surveys/'+s.id+'/products'))})}}>
   <input aria-label="Register NOAA survey ID" placeholder="H11277" value={registration} pattern="[HhWw][0-9]{5}" required onChange={e=>setRegistration(e.target.value)}/><button disabled={busy}>Register</button>
  </form>
  <select aria-label="NOAA survey" value={surveyId} onChange={e=>onSurvey(e.target.value)}>
   {!surveys.some(s=>s.id===surveyId)&&<option value={surveyId}>{surveyId||'Select or register a survey'}</option>}
   {surveys.map(s=><option key={s.id} value={s.id}>{s.name||s.id}</option>)}
  </select>
  <button className="full" disabled={busy||!surveyId} onClick={()=>perform(async()=>setProducts(await api('/surveys/'+surveyId+'/products')))}>List NOAA products</button>
  <label>Download limit per product (MB)<input aria-label="Product download limit MB" type="number" min="1" max="1000" value={budget} onChange={e=>{setBudget(+e.target.value);setChecks({})}}/></label>
  <div className="product-list">{products.map(p=><article key={p.url}>
   <a href={p.url} target="_blank" rel="noreferrer">{p.name||p.url.split('/').pop()}</a>
   {p.ingestible&&<><div className="button-row"><button disabled={busy||budget<1||budget>1000} onClick={()=>perform(async()=>{const check=await api('/survey-products/inspect',{url:p.url,kind:kind(p),max_bytes:Math.floor(budget*1e6)});setChecks((old:any)=>({...old,[p.url]:check}))})}>Inspect</button>
    <button disabled={busy||budget<1||budget>1000||checks[p.url]?.within_download_limit===false} onClick={()=>perform(()=>start('ingest',{url:p.url,survey_id:surveyId,kind:kind(p),max_bytes:Math.floor(budget*1e6)}))}>Ingest</button></div>
    {checks[p.url]&&<small>{checks[p.url].cached?'Cached original · ':''}{checks[p.url].bytes==null?'Size unavailable':fmt(checks[p.url].bytes/1e6)+' MB'}{checks[p.url].within_download_limit===false?' · exceeds limit':''}
     {checks[p.url].raster?<><br/>{checks[p.url].raster.width} × {checks[p.url].raster.height} cells · {checks[p.url].raster.resolution_m.join(' × ')} m{checks[p.url].raster.requires_windows?' · automatic windows':''}</>:<><br/>Grid dimensions checked after download.</>}
     {checks[p.url].warning&&<><br/>{checks[p.url].warning}</>}
    </small>}
   </>}
  </article>)}</div>
  <small>Originals are cached. Large grids use overlapping source windows without resampling. Empty windows are skipped. Limits apply per product, not per campaign.</small>
 </section>
}
