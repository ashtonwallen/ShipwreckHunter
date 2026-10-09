export async function api(path:string,body?:any):Promise<any>{
 const r=await fetch('/api'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!r.ok){let d;try{d=await r.json()}catch{d={detail:r.statusText}}throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail));}return r.json();
}
export const fmt=(n:number,d=1)=>Number(n).toLocaleString(undefined,{maximumFractionDigits:d});
