let investigationId=localStorage.getItem('shipwreck-investigation')||'mystery-collier';
export const currentInvestigation=()=>investigationId;
export function selectInvestigation(id:string){investigationId=id;localStorage.setItem('shipwreck-investigation',id)}
export async function api(path:string,body?:any):Promise<any>{
 const url=new URL('/api'+path,window.location.origin);
 if(!url.searchParams.has('site_id'))url.searchParams.set('site_id',investigationId);
 const r=await fetch(url,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!r.ok){let d;try{d=await r.json()}catch{d={detail:r.statusText}}throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));}return r.json();
}
export const fmt=(n:number,d=1)=>Number(n).toLocaleString(undefined,{maximumFractionDigits:d});
