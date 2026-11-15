import {useEffect,useMemo,useState} from 'react';
import {ArrowUpRight} from 'lucide-react';
import {Landing} from './Landing';
import {FarmGlobe} from './FarmGlobe';
import {api} from './api/client';
import {StrategyCard as EvidenceStrategyCard} from './StrategyCard';
import {DataProvenance} from './DataProvenance';
import type {ClimateSummary,CompareResponse,Crop,DataSourceCatalog,FarmProfile,SoilProfile,Strategy} from './types';
import {PILOT_LOCATION} from './pilot';
import './rotation.css';

const strategies:Strategy[]=['current_practice','water_saving','soil_recovery'];
export default function App(){
 const [landing,setLanding]=useState(()=>!location.hash||location.hash==='#landing');
 useEffect(()=>{
   const onHashChange=()=>{
     const id=location.hash.slice(1);
     setLanding(!id||id==='landing');
     requestAnimationFrame(()=>{
       if(!id||id==='landing') window.scrollTo(0,0);
       else document.getElementById(id)?.scrollIntoView();
     });
   };
   window.addEventListener('hashchange',onHashChange);
   return ()=>window.removeEventListener('hashchange',onHashChange);
 },[]);
 const [farm,setFarm]=useState<FarmProfile>({current_crop:'',farm_area_ha:1,soil_ph:null,soil_salinity_ec:null,irrigation_water_ec:null,irrigation_available:null,freshwater_availability:'unknown',drainage_available:null,water_control_available:null,inoculation_confirmed:null,farmer_priority:'yield',planning_month:null,planting_date:null,latitude:PILOT_LOCATION.latitude,longitude:PILOT_LOCATION.longitude});
 const [crops,setCrops]=useState<Crop[]>([]); const [climate,setClimate]=useState<ClimateSummary|null>(null); const [climateLoading,setClimateLoading]=useState(false); const [soil,setSoil]=useState<SoilProfile|null>(null); const [results,setResults]=useState<Partial<Record<Strategy,CompareResponse>>>({});
 const [dataSources,setDataSources]=useState<DataSourceCatalog|null>(null); const [sourceError,setSourceError]=useState(''); const [locationDetailsVisible,setLocationDetailsVisible]=useState(false);
 const [loading,setLoading]=useState(true); const [busy,setBusy]=useState(false); const [error,setError]=useState('');
 useEffect(()=>{Promise.all([api.crops(),api.soil()]).then(([cropData,soilData])=>{setCrops(cropData.records||[]);setSoil(soilData);setLoading(false)}).catch(e=>{setError(String(e));setLoading(false)})},[]);
 useEffect(()=>{api.dataSources().then(setDataSources).catch(e=>setSourceError(String(e)))},[]);
 const availableIds=useMemo(()=>crops.map(c=>c.crop_id),[crops]);
 const climateDate=(value:string|undefined,fallback:string)=>value&&/^\d{8}$/.test(value)?`${value.slice(0,4)}-${value.slice(4,6)}-${value.slice(6,8)}`:fallback;
 const climateStart=climateDate(climate?.period?.start,'2020-01-01');
 const climateEnd=climateDate(climate?.period?.end,new Date().toISOString().slice(0,10));
 const edit=(key:keyof FarmProfile,value:string)=>setFarm(previous=>({...previous,[key]:['farm_area_ha','planning_month','soil_ph','soil_salinity_ec','irrigation_water_ec','latitude','longitude'].includes(key)?(value===''?null:Number(value)):value} as FarmProfile));
 const editBoolean=(key:'irrigation_available'|'drainage_available'|'water_control_available'|'inoculation_confirmed',value:string)=>setFarm(previous=>({...previous,[key]:value===''?null:value==='true'}));
 const locationError=()=>farm.latitude===null||farm.longitude===null?'Enter both farm latitude and longitude, or choose a point on the map.':!Number.isFinite(farm.latitude)||farm.latitude<-90||farm.latitude>90?'Latitude must be between -90 and 90.':!Number.isFinite(farm.longitude)||farm.longitude<-180||farm.longitude>180?'Longitude must be between -180 and 180.':'';
 void locationError;
 useEffect(()=>{const handler=(event:Event)=>{const detail=(event as CustomEvent<{latitude?:number;longitude?:number}>).detail;setLocationDetailsVisible(true);setFarm(previous=>({...previous,latitude:Number.isFinite(detail?.latitude)?detail.latitude??previous.latitude:previous.latitude,longitude:Number.isFinite(detail?.longitude)?detail.longitude??previous.longitude:previous.longitude}));};window.addEventListener('terracycle-location',handler);return()=>window.removeEventListener('terracycle-location',handler)},[]);
 useEffect(()=>{
  const {latitude,longitude}=farm;
  if(landing||latitude===null||longitude===null){setClimate(null);setClimateLoading(false);return}
  let current=true;
  setClimate(null);setClimateLoading(true);
  const timer=window.setTimeout(()=>{
   api.climate(latitude,longitude).then(data=>{if(current)setClimate(data)}).catch(()=>{if(current)setClimate(null)}).finally(()=>{if(current)setClimateLoading(false)});
  },250);
  return()=>{current=false;window.clearTimeout(timer)};
 },[landing,farm.latitude,farm.longitude]);
 useEffect(()=>{const provenance=results.current_practice?.provenance;if(provenance)window.dispatchEvent(new CustomEvent('terracycle-provenance',{detail:provenance}))},[results.current_practice]);
 function validate(){if(farm.soil_ph!==null&&(!Number.isFinite(farm.soil_ph)||farm.soil_ph<3.5||farm.soil_ph>9))return 'Soil pH must be between 3.5 and 9.0.';if([farm.soil_salinity_ec,farm.irrigation_water_ec].some(value=>value!==null&&(!Number.isFinite(value)||value<0)))return 'EC measurements must be non-negative.';if(!farm.current_crop||!farm.farm_area_ha||farm.farm_area_ha<=0)return 'Current crop and a positive farm area are required.';if(!farm.planting_date)return 'Planting date is required for time-dependent historical climate assessment.';if(farm.planting_date<climateStart||farm.planting_date>climateEnd)return `Choose a planting date within available historical climate coverage (${climateStart} to ${climateEnd}); future dates are not forecastable.`;return ''}
 async function compare(){if(busy)return;const validation=validate();if(validation){setError(validation);return}setBusy(true);setError('');setResults({});try{const response=await api.compareAll(farm,availableIds);setResults(response.results);requestAnimationFrame(()=>document.getElementById('rotation-results')?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}))}catch(e){setError(String(e))}finally{setBusy(false)}}
 return <main><nav className="nav"><div className="brand"><img className="mark" src={import.meta.env.BASE_URL + "terracycle-logo.svg"} alt="" /><span>TerraCycle AI<span className="brand-sub"> / FIELD SHIFT</span></span></div><div className="nav-links"><a href="#landing" aria-current={landing ? 'page' : undefined}>Landing</a><a href="#farm-profile-title" aria-current={!landing && location.hash!=='#data-provenance' ? 'page' : undefined}>Farm Profile</a><a href="#data-provenance">Data sources</a></div></nav>
 {landing && <div id="landing"><Landing/></div>}
 <div hidden={landing}>
 <div className="mission-grid"><div className="mission-content">
 <section className="farm-profile" aria-labelledby="farm-profile-title"><div className="farm-profile-inner"><div className="farm-profile-form"><div className="farm-signal">02 / FARM PROFILE • NASA EARTH OBSERVATION SYNC</div><h2 id="farm-profile-title">Describe your farm.</h2><p className="farm-description">Unknown measurements remain unknown. They are never inferred from satellite or climate data.</p>
 {loading?<p>Loading climate, soil and crop evidence…</p>:<><div className="scenario"><label>Current crop<select value={farm.current_crop} onChange={e=>edit('current_crop',e.target.value)}><option value="">Select a crop</option>{crops.map(c=><option key={c.crop_id} value={c.crop_id}>{c.crop_name}</option>)}</select></label><label>Farm area (ha)<input type="number" min="0.01" step="0.01" value={farm.farm_area_ha} onChange={e=>edit('farm_area_ha',e.target.value)}/></label><label>Planting date<input type="date" min={climateStart} max={climateEnd} value={farm.planting_date||''} onChange={e=>edit('planting_date',e.target.value)}/></label><label>Farmer priority<select value={farm.farmer_priority} onChange={e=>edit('farmer_priority',e.target.value)}><option value="yield">Yield</option><option value="water">Water</option><option value="soil">Soil</option><option value="income">Income</option><option value="risk">Risk</option></select></label></div>
 <details className="farm-optional"><summary>Local Soil &amp; Irrigation Metrics (Optional)</summary><div className="scenario"><label>Soil pH <span className="field-help">optional — leave blank if unknown</span><input type="number" min="3.5" max="9" step="0.1" value={farm.soil_ph??''} placeholder="Unknown" onChange={e=>edit('soil_ph',e.target.value)}/></label><label>Soil salinity EC <span className="field-help">optional farmer/local measurement</span><input type="number" min="0" step="0.01" value={farm.soil_salinity_ec??''} placeholder="Unknown" onChange={e=>edit('soil_salinity_ec',e.target.value)}/></label><label>Irrigation-water EC <span className="field-help">optional farmer/local measurement</span><input type="number" min="0" step="0.01" value={farm.irrigation_water_ec??''} placeholder="Unknown" onChange={e=>edit('irrigation_water_ec',e.target.value)}/></label><label>Irrigation available<select value={farm.irrigation_available===null?'':String(farm.irrigation_available)} onChange={e=>editBoolean('irrigation_available',e.target.value)}><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label></div><div className="scenario"><label>Freshwater availability<select value={farm.freshwater_availability} onChange={e=>edit('freshwater_availability',e.target.value)}><option value="unknown">Unknown</option><option value="limited">Limited</option><option value="adequate">Adequate</option></select></label><label>Drainage available<select value={farm.drainage_available===null?'':String(farm.drainage_available)} onChange={e=>editBoolean('drainage_available',e.target.value)}><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Water control available<select value={farm.water_control_available===null?'':String(farm.water_control_available)} onChange={e=>editBoolean('water_control_available',e.target.value)}><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label><label>Legume inoculation confirmed<select value={farm.inoculation_confirmed===null?'':String(farm.inoculation_confirmed)} onChange={e=>editBoolean('inoculation_confirmed',e.target.value)}><option value="">Unknown</option><option value="true">Yes</option><option value="false">No</option></select></label></div></details>
 <div className="run"><button type="button" disabled={busy} onClick={compare}>{busy?'Assessing…':'Compare three strategies'} <ArrowUpRight size={18}/></button><span>Historical observations only · no future forecast.</span></div></>}
 {error&&<div className="error" role="alert">{error}</div>}</div></div></section></div><aside className="mission-visual">{!landing && <FarmGlobe priority={farm.farmer_priority} crop={farm.current_crop}/>}</aside></div>
 <div className="workspace">
 {Object.keys(results).length>0&&<section className="results" id="rotation-results"><div className="section-head"><div><div className="eyebrow dark">03 / ROTATION REPORT</div><h2>Evidence-led options.</h2><p>PASS is eligible, UNKNOWN needs missing evidence, and FAIL is rejected.</p></div></div><div className="result-grid">{strategies.map(strategy=><EvidenceStrategyCard key={strategy} strategy={strategy} response={results[strategy]} dataSources={dataSources?.sources||[]}/>)}</div></section>}
 <DataProvenance farm={farm} crops={crops} climate={climate} climateLoading={climateLoading} soil={soil} dataSources={dataSources} sourceError={sourceError} locationDetailsVisible={locationDetailsVisible}/></div></div><footer>TerraCycle AI &middot; NASA Space Apps Field Shift &middot; Historical evidence, not a forecast.</footer></main>
}


