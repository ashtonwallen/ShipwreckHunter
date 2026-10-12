import {BookOpen,Map,MessageSquare,Plus} from 'lucide-react';

export default function InvestigationOverview({workspace,openSource,onArchives,onMap,onEvidence,onAssistant}:any){
 const {site,notes,claims,datasets}=workspace;
 return <div className="investigation-overview">
  <section className="panel"><h3>Research objective</h3><p>{site.objective||'No objective recorded.'}</p>
   <div className="button-row"><button onClick={onMap}><Map size={15}/>Choose research area</button><button onClick={onArchives}><BookOpen size={15}/>Add sources</button><button disabled={!workspace.sources.length} onClick={onEvidence}><Plus size={15}/>Add evidence</button><button onClick={onAssistant}><MessageSquare size={15}/>Research with assistant</button></div>
  </section>
  <section className="panel"><h3>Current assessment</h3><p>{site.conclusion}</p><small>{claims.length} evidence claims · {workspace.sources.length} sources · {datasets.length} survey grids</small></section>
  <section><h3>Research notes <span className="muted">({notes.length})</span></h3>
   {!notes.length&&<p className="muted">No notes yet. Start with a source or ask the assistant to investigate your objective. Notes and evidence will stay with this investigation.</p>}
   {notes.map((n:any)=><details className="panel research-note" key={n.id}><summary>{n.subject.split(':').pop().replaceAll('-',' ')}<small>{new Date(n.created).toLocaleDateString()}</small></summary><p>{n.text}</p>{n.contradictions?.length>0&&<><h4>Contradictions and limits</h4><ul>{n.contradictions.map((c:string,i:number)=><li key={i}>{c}</li>)}</ul></>}<div className="button-row">{n.source_ids?.map((id:string)=><button key={id} onClick={()=>openSource(id)}>{workspace.sources.find((s:any)=>s.id===id)?.title||id}</button>)}</div></details>)}
  </section>
 </div>
}
