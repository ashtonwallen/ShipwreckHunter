import {useEffect,useRef,useState} from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import {Layers,Scan,LocateFixed,Plus,Minus} from 'lucide-react';
import {api} from './api';

export default function OceanMap({workspace,onSelect,onBounds,focus,refresh}:{workspace:any,onSelect:(kind:string,id:string)=>void,onBounds:(b:number[])=>void,focus:any,refresh:number}){
 const element=useRef<HTMLDivElement>(null),map=useRef<maplibregl.Map>(null),selectRef=useRef(onSelect),boundsRef=useRef(onBounds);
 selectRef.current=onSelect;boundsRef.current=onBounds;
 const [ready,setReady]=useState(false),[layers,setLayers]=useState({surveys:true,wrecks:true,candidates:true,bathymetry:true}),[menu,setMenu]=useState(false),[selecting,setSelecting]=useState(false),[error,setError]=useState(''),[pos,setPos]=useState('42.40° N   70.45° W');
 const regionMode=useRef(false),first=useRef<any>(null);
 useEffect(()=>{
  if(!element.current)return;
  const m=new maplibregl.Map({container:element.current,center:[-70.45,42.37],zoom:8.7,attributionControl:{compact:false},style:{version:8,sources:{land:{type:'geojson',data:'/data/media/land.geojson',attribution:'Coastline: Natural Earth (1:10 million; context only)'},ocean:{type:'raster',tiles:['https://services.arcgisonline.com/arcgis/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}'],tileSize:256,attribution:'Ocean basemap: Esri, GEBCO, NOAA, National Geographic'}},layers:[{id:'background',type:'background',paint:{'background-color':'#0b1d2c'}},{id:'bathymetry',type:'raster',source:'ocean',paint:{'raster-opacity':.65,'raster-saturation':-.35,'raster-brightness-max':.23}},{id:'land-fill',type:'fill',source:'land',paint:{'fill-color':'#172c39','fill-opacity':.93}},{id:'coastline',type:'line',source:'land',paint:{'line-color':'#3f6171','line-width':1}}]}});
  map.current=m;
  m.on('load',()=>{
   const empty={type:'FeatureCollection',features:[]} as any;
   for(const id of ['surveys','wrecks','candidates','region','datasets'])m.addSource(id,{type:'geojson',data:empty});
   m.addLayer({id:'surveys-fill',type:'fill',source:'surveys',paint:{'fill-color':'#48b4c2','fill-opacity':.035}});
   m.addLayer({id:'surveys',type:'line',source:'surveys',paint:{'line-color':'#428e9c','line-width':1,'line-opacity':.55}});
   m.addLayer({id:'datasets',type:'line',source:'datasets',paint:{'line-color':'#50dcc2','line-width':2}});
   m.addLayer({id:'wrecks',type:'circle',source:'wrecks',paint:{'circle-radius':['case',['==',['get','quality'],'High'],4,5],'circle-color':['case',['==',['get','quality'],'High'],'#6dafc9','#d3b278'],'circle-opacity':['case',['==',['get','quality'],'High'],.85,.18],'circle-stroke-width':1.3,'circle-stroke-color':['case',['==',['get','quality'],'High'],'#9fcbd8','#d3b278']}});
   m.addLayer({id:'candidates',type:'circle',source:'candidates',paint:{'circle-radius':6,'circle-color':'#e9a66d','circle-stroke-color':'#f4cda5','circle-stroke-width':1.5}});
   m.addLayer({id:'region-fill',type:'fill',source:'region',paint:{'fill-color':'#77d5c1','fill-opacity':.08}});
   m.addLayer({id:'region',type:'line',source:'region',paint:{'line-color':'#8cd9c8','line-width':2,'line-dasharray':[3,2]}});
   for(const id of ['wrecks','candidates','surveys-fill']){
    m.on('click',id,e=>{if(regionMode.current)return;const p=e.features?.[0]?.properties;if(p)selectRef.current(id==='surveys-fill'?'survey':id==='wrecks'?'wreck':'candidate',p.id||p.SURVEY_ID)});
    m.on('mouseenter',id,()=>{m.getCanvas().style.cursor='pointer'});m.on('mouseleave',id,()=>{m.getCanvas().style.cursor=regionMode.current?'crosshair':''});
   }
   for(const [name,lon,lat] of [['Boston',-71.06,42.36],['Gloucester',-70.66,42.63],['Provincetown',-70.19,42.05],['Stellwagen Bank',-70.3,42.33]] as [string,number,number][]){const el=document.createElement('div');el.className='place-label';el.textContent=name;new maplibregl.Marker({element:el,offset:[0,-12]}).setLngLat([lon,lat]).addTo(m)}
   setReady(true);
   const b=m.getBounds();boundsRef.current([b.getWest(),b.getSouth(),b.getEast(),b.getNorth()]);
  });
  m.on('error',()=>setError('Some basemap tiles are unavailable. Saved survey and wreck layers remain available.'));
  m.on('mousemove',e=>setPos(`${Math.abs(e.lngLat.lat).toFixed(3)}° ${e.lngLat.lat>0?'N':'S'}   ${Math.abs(e.lngLat.lng).toFixed(3)}° ${e.lngLat.lng>0?'E':'W'}`));
  m.on('moveend',()=>{if(first.current)return;const b=m.getBounds();boundsRef.current([b.getWest(),b.getSouth(),b.getEast(),b.getNorth()])});
  m.on('click',e=>{
   if(!regionMode.current)return;
   if(!first.current){first.current=e.lngLat;return;}
   const a=first.current,b=e.lngLat,bbox=[Math.min(a.lng,b.lng),Math.min(a.lat,b.lat),Math.max(a.lng,b.lng),Math.max(a.lat,b.lat)];
   (m.getSource('region') as any).setData({type:'FeatureCollection',features:[{type:'Feature',properties:{},geometry:{type:'Polygon',coordinates:[[[bbox[0],bbox[1]],[bbox[2],bbox[1]],[bbox[2],bbox[3]],[bbox[0],bbox[3]],[bbox[0],bbox[1]]]]}}]});
   boundsRef.current(bbox);regionMode.current=false;setSelecting(false);m.getCanvas().style.cursor='';
  });
  const observer=new ResizeObserver(()=>m.resize());observer.observe(element.current);
  return()=>{observer.disconnect();m.remove();map.current=null};
 },[]);
 useEffect(()=>{if(!ready)return;api('/map').then(d=>{(map.current?.getSource('wrecks') as any)?.setData(d.wrecks);(map.current?.getSource('surveys') as any)?.setData(d.surveys)}).catch(e=>setError(e.message))},[ready,refresh]);
 useEffect(()=>{
  if(!ready||!workspace)return;
  const latest=new Map();for(const r of [...workspace.runs].reverse())latest.set(r.dataset_id,r.id);
  const features=workspace.candidates.filter((c:any)=>latest.get(c.dataset_id)===c.run_id&&c.status!=='rejected').map((c:any)=>({type:'Feature',geometry:{type:'Point',coordinates:[c.lon,c.lat]},properties:{id:c.id,name:'Anomaly '+c.id.slice(-3)}}));
  (map.current?.getSource('candidates') as any)?.setData({type:'FeatureCollection',features});
  (map.current?.getSource('datasets') as any)?.setData({type:'FeatureCollection',features:workspace.datasets.map((d:any)=>{const b=d.bounds;return {type:'Feature',properties:{id:d.id},geometry:{type:'Polygon',coordinates:[[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]],[b[0],b[1]]]]}}})});
 },[workspace,ready]);
 useEffect(()=>{if(!ready)return;for(const [id,on] of Object.entries(layers)){map.current?.setLayoutProperty(id,'visibility',on?'visible':'none');if(id==='surveys')map.current?.setLayoutProperty('surveys-fill','visibility',on?'visible':'none')}},[layers,ready]);
 useEffect(()=>{if(!ready||!focus)return;if(focus.bounds)map.current?.fitBounds([[focus.bounds[0],focus.bounds[1]],[focus.bounds[2],focus.bounds[3]]],{padding:70,maxZoom:17});else if(focus.lon)map.current?.flyTo({center:[focus.lon,focus.lat],zoom:16})},[focus,ready]);
 return <div className="map-shell"><div ref={element} className="map"/><div className="map-title"><span className="live-dot"/> Massachusetts Bay <span className="muted">/ NOAA survey coverage</span></div>
  <div className="map-tools"><button title="Layers" onClick={()=>setMenu(!menu)}><Layers size={17}/></button><button title="Select region" className={selecting?'active':''} onClick={()=>{first.current=null;regionMode.current=!regionMode.current;setSelecting(regionMode.current);if(map.current)map.current.getCanvas().style.cursor=regionMode.current?'crosshair':''}}><Scan size={17}/></button><button title="Reset Massachusetts view" onClick={()=>map.current?.flyTo({center:[-70.45,42.37],zoom:8.7})}><LocateFixed size={17}/></button><button title="Zoom in" onClick={()=>map.current?.zoomIn()}><Plus size={17}/></button><button title="Zoom out" onClick={()=>map.current?.zoomOut()}><Minus size={17}/></button></div>
  {menu&&<div className="layer-menu">{Object.entries(layers).map(([id,on])=><label key={id}><input type="checkbox" checked={on} onChange={()=>setLayers({...layers,[id]:!on})}/>{id==='wrecks'?'Catalogue wrecks / hazards':id==='candidates'?'Screening candidates':id==='bathymetry'?'Regional bathymetry basemap':'NOAA survey footprints'}</label>)}<small>Basemap is context only; never analyzed for wrecks.</small></div>}
  {selecting&&<div className="map-hint">Click two opposite corners to select a region.</div>}
  {error&&<div className="map-error" onClick={()=>setError('')}>{error}</div>}
  <div className="map-legend"><span><i className="dot blue"/> Catalogue record</span><span><i className="dot hollow"/> Uncertain position*</span><span><i className="dot orange"/> Terrain candidate</span><span><i className="line-key"/> Survey footprint</span><small>*Symbol marks a reported location, not an accuracy radius. Catalogue records are not independently verified.</small></div><div className="coordinates">{pos}</div>
 </div>
}
