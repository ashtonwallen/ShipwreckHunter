import {useEffect,useState} from 'react';
import {api} from './api';

export default function DetectionList({run,selected,onSelect,refresh}:any){
 const [offset,setOffset]=useState(0),[status,setStatus]=useState(''),[result,setResult]=useState<any>(null),[error,setError]=useState('');
 useEffect(()=>{setOffset(0);setStatus('')},[run.id]);
 useEffect(()=>{let active=true;setResult(null);setError('');const query=new URLSearchParams({run_id:run.id,offset:String(offset),limit:'50',include_coordinates:'true'});if(status)query.set('status',status);
  api('/candidates?'+query).then(r=>{if(active)setResult(r)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false};
 },[run.id,offset,status,refresh]);
 return <section><div className="table-toolbar"><h3>{result?.total??'…'} terrain candidates</h3><label>Review status <select aria-label="Filter candidate status" value={status} onChange={e=>{setOffset(0);setStatus(e.target.value)}}><option value="">All</option>{['unreviewed','follow-up','rejected','known-feature'].map(s=><option key={s}>{s}</option>)}</select></label></div>
  {run.truncated&&<p className="notice-inline">Older run retained {run.candidates.length} of {run.eligible_count} eligible detections. Analyze again to retain every eligible detection; prior reviews remain attached to the older run.</p>}
  <small>Scores are uncalibrated review priority. Overlapping windows and repeated runs can contain the same object.</small>
  {error&&<p role="alert">{error}</p>}
  <div className="detections" key={run.id+':'+offset+':'+status}>{result?.candidates.map((c:any)=><button className={'detection-row '+(selected?.id===c.id?'selected':'')} key={c.id} onClick={()=>onSelect(c)}><img alt="Candidate raster crop" loading="lazy" src={c.image_url}/><span><strong>{c.length_m} × {c.width_m} m</strong><small>{c.relief_m!=null?c.relief_m+' m residual relief':'Intensity feature'} · {c.bearing_degrees}° grid axis</small></span><span className="match-label">{c.nearby_records.some((m:any)=>m.association==='close catalogue position')?'Close catalogue position':c.nearby_records.length?'Uncertain association':'No loaded match'}</span><span className="tag">{c.status}</span><strong className="score">{c.score}</strong></button>)}</div>
  {result&&<div className="button-row"><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous candidates</button><span>{result.total?offset+1:0}–{Math.min(offset+50,result.total)} of {result.total}</span><button disabled={result.next_offset==null} onClick={()=>setOffset(result.next_offset)}>Next candidates</button></div>}
 </section>
}
