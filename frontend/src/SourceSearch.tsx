import {useState,useRef,useLayoutEffect} from 'react';
import {api} from './api';

export default function SourceSearch({source}:any){
 const [q,setQ]=useState(''),[searched,setSearched]=useState(''),[result,setResult]=useState<any>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const start=useRef<HTMLDivElement>(null);
 useLayoutEffect(()=>{if(result)start.current?.scrollIntoView({block:'start'})},[result]);
 async function search(query:string,offset=0){setError('');setBusy(true);try{setResult(await api('/sources/'+source.id+'/search?'+new URLSearchParams({q:query,offset:String(offset)})));setSearched(query)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 return <div className="source-search" ref={start}><form className="button-row" onSubmit={e=>{e.preventDefault();search(q)}}><input aria-label="Find within full source" placeholder="Search full saved text, including long registers" value={q} onChange={e=>setQ(e.target.value)} required/><button disabled={busy}>Find in source</button></form>
  {error&&<p role="alert">{error}</p>}
  {result&&<><p>{result.total_matches} matches across {result.text_length.toLocaleString()} characters, grouped into {result.total_excerpts} excerpts. {result.warning}</p>{result.matches.map((m:any)=><div key={m.character_offset}>{m.pdf_page&&<a href={source.url+'#page='+m.pdf_page} target="_blank" rel="noreferrer">PDF page {m.pdf_page}</a>}<pre>Character {m.character_offset}{'\n'}{m.excerpt}</pre></div>)}<div className="button-row"><button disabled={busy||result.offset===0} onClick={()=>search(searched,Math.max(0,result.offset-12))}>Previous excerpts</button><span>{result.total_excerpts?result.offset+1:0}–{result.offset+result.matches.length} of {result.total_excerpts}</span><button disabled={busy||result.next_offset==null} onClick={()=>search(searched,result.next_offset)}>Next excerpts</button></div></>}
  <small>The preview below is limited to 500,000 characters. Full saved text remains searchable.</small>
 </div>
}
