import {useState,useRef,useEffect} from 'react';
import {ZoomIn,ZoomOut,RotateCcw,Ruler,Box,Layers2} from 'lucide-react';
import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';
import {api,fmt} from './api';

function Terrain({dataset,candidate}:{dataset:any,candidate:any}){
 const host=useRef<HTMLDivElement>(null);const [error,setError]=useState(''),[datum,setDatum]=useState(''),[metrics,setMetrics]=useState('');
 useEffect(()=>{
  let disposed=false;let cleanup=()=>{};
  api(`/datasets/${dataset.id}/surface${candidate?'?candidate_id='+candidate.id:''}`).then(d=>{
   if(disposed||!host.current)return;setDatum(d.datum);
   const el=host.current,w=el.clientWidth,h=el.clientHeight;
   const scene=new THREE.Scene();scene.background=new THREE.Color('#080f17');
   const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setSize(w,h);renderer.setPixelRatio(Math.min(devicePixelRatio,2));el.appendChild(renderer.domElement);
   const width=(d.width-1)*d.dx,height=(d.height-1)*d.dy,span=Math.max(width,height),values=d.elevations.filter((v:any)=>v!==null),low=Math.min(...values),high=Math.max(...values),center=(high+low)/2;
   setMetrics(`Elevation ${low.toFixed(1)} to ${high.toFixed(1)} m; mesh ${width.toFixed(0)} × ${height.toFixed(0)} m; grid interval ${(span/10).toFixed(1)} m`);
   const camera=new THREE.PerspectiveCamera(45,w/h,.01,span*20);camera.position.set(span*.4,span*.65,span*.9);
   const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;
   const positions:number[]=[],colors:number[]=[],indices:number[]=[];
   for(let y=0;y<d.height;y++)for(let x=0;x<d.width;x++){let z=d.elevations[y*d.width+x];positions.push(x*d.dx-width/2,(z??center)-center,y*d.dy-height/2);const t=(z-low)/Math.max(.01,high-low);const c=new THREE.Color().setHSL(.55-t*.09,.35,.18+t*.4);colors.push(c.r,c.g,c.b)}
   for(let y=0;y<d.height-1;y++)for(let x=0;x<d.width-1;x++){const a=y*d.width+x,b=a+1,c=a+d.width,e=c+1;if([a,b,c,e].every(i=>d.elevations[i]!==null))indices.push(a,c,b,b,c,e)}
   const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));geometry.setIndex(indices);geometry.computeVertexNormals();
   const material=new THREE.MeshStandardMaterial({vertexColors:true,side:THREE.DoubleSide,roughness:1});const mesh=new THREE.Mesh(geometry,material);scene.add(mesh);
   scene.add(new THREE.HemisphereLight(0xbce6ff,0x19323c,2));const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(span,span,span/2);scene.add(light);
   const grid=new THREE.GridHelper(span,10,0x31515e,0x1c323e);grid.position.y=low-center-.5;scene.add(grid);
   const axes=new THREE.AxesHelper(span*.15);axes.position.set(-width/2,low-center,-height/2);scene.add(axes);
   let frame=0;const draw=()=>{controls.update();renderer.render(scene,camera);frame=requestAnimationFrame(draw)};draw();
   const observer=new ResizeObserver(()=>{const w=el.clientWidth,h=el.clientHeight;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h)});observer.observe(el);
   cleanup=()=>{cancelAnimationFrame(frame);observer.disconnect();controls.dispose();geometry.dispose();material.dispose();renderer.dispose();el.replaceChildren()};
  }).catch(e=>setError(e.message));return()=>{disposed=true;cleanup()};
 },[dataset.id,candidate?.id]);
 return <div className="terrain"><div ref={host} className="terrain-canvas"/>{error&&<p className="error">{error}</p>}<div className="terrain-note">{metrics}<br/>Measured elevation · {datum} · vertical scale 1:1 · drag to orbit · gaps remain open</div></div>
}

export default function RasterView({dataset,run,candidate}:{dataset:any,run:any,candidate?:any}){
 const [zoom,setZoom]=useState(1),[contrast,setContrast]=useState(1.2),[mode,setMode]=useState('compare'),[measure,setMeasure]=useState(false),[points,setPoints]=useState<number[][]>([]),[pan,setPan]=useState([0,0]);
 const drag=useRef<any>(null);
 useEffect(()=>{setZoom(1);setPoints([]);setPan([0,0])},[dataset.id,candidate?.id]);
 const width=dataset.width,height=dataset.height;
 const point=(e:any)=>{if(!measure)return;const r=e.currentTarget.getBoundingClientRect();setPoints(p=>p.length===2?[[((e.clientX-r.left)/r.width)*width,((e.clientY-r.top)/r.height)*height]]:[...p,[((e.clientX-r.left)/r.width)*width,((e.clientY-r.top)/r.height)*height]])};
 const distance=points.length===2?Math.hypot((points[1][0]-points[0][0])*dataset.resolution_m[0],(points[1][1]-points[0][1])*dataset.resolution_m[1]):null;
 return <div className="raster-workspace"><div className="raster-tools"><div className="segmented"><button className={mode==='compare'?'active':''} onClick={()=>setMode('compare')}><Layers2 size={14}/>2D comparison</button><button disabled={dataset.kind!=='bathymetry'} className={mode==='3d'?'active':''} onClick={()=>{setMode('3d');setMeasure(false);setPoints([])}}><Box size={14}/>3D bathymetry</button></div><span className="spacer"/><button title="Zoom in" onClick={()=>setZoom(Math.min(8,zoom*1.3))}><ZoomIn size={16}/></button><button title="Zoom out" onClick={()=>setZoom(Math.max(.5,zoom/1.3))}><ZoomOut size={16}/></button><button title="Reset view" onClick={()=>{setZoom(1);setPan([0,0]);setPoints([])}}><RotateCcw size={15}/></button><button title="Measure two points" className={measure?'active':''} onClick={()=>{setMeasure(!measure);setPoints([])}}><Ruler size={16}/></button><label className="contrast">Contrast<input aria-label="Image contrast" type="range" min="0.5" max="3" step=".1" value={contrast} onChange={e=>setContrast(+e.target.value)}/></label></div>
 {mode==='3d'?<Terrain dataset={dataset} candidate={candidate}/>:<div className="raster-pair">{[run.original_url,run.processed_url].map((url,i)=><div key={url} className="raster-pane"><div className="pane-label">{i===0?'Measured elevation · percentile stretch':`${run.parameters.method} · local residual`}<span>{dataset.resolution_m[0]} m / cell</span></div><div className={'raster-viewport '+(measure?'measuring':'')} onPointerDown={e=>{if(measure)return;drag.current=[e.clientX,e.clientY,...pan];e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={e=>{if(drag.current)setPan([drag.current[2]+e.clientX-drag.current[0],drag.current[3]+e.clientY-drag.current[1]])}} onPointerUp={()=>drag.current=null} onWheel={e=>setZoom(z=>Math.max(.5,Math.min(8,z*(e.deltaY<0?1.1:.9))))}><div className="raster-image" style={{transform:`translate(${pan[0]}px,${pan[1]}px) scale(${zoom})`,aspectRatio:`${width}/${height}`}} onClick={point}><img draggable="false" src={url} style={{filter:`contrast(${contrast})`}}/><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">{candidate&&<rect x={candidate.bbox_pixels[0]} y={candidate.bbox_pixels[1]} width={candidate.bbox_pixels[2]-candidate.bbox_pixels[0]} height={candidate.bbox_pixels[3]-candidate.bbox_pixels[1]} fill="none" stroke="#ffc38d" strokeWidth={2/zoom}/>} {points.map((p,i)=><circle key={i} cx={p[0]} cy={p[1]} r={4/zoom} fill="#fff"/>)}{points.length===2&&<line x1={points[0][0]} y1={points[0][1]} x2={points[1][0]} y2={points[1][1]} stroke="#fff" strokeWidth={2/zoom}/>}</svg></div></div></div>)}</div>}
 <div className="raster-footer"><span>{measure?(distance!==null?`${fmt(distance)} m planar distance · minimum cell uncertainty ±${fmt(dataset.resolution_m[0]*2)} m`:'Click two points on the raster to measure.'):`${dataset.width} × ${dataset.height} source cells · ${dataset.vertical_datum} · ${dataset.kind}`}</span><span>{Math.round(zoom*100)}%</span></div></div>
}
