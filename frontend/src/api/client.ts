import type {ClimateSummary,CompareResponse,Crop,FarmProfile,SoilProfile,Strategy} from '../types';
const BASE=import.meta.env.VITE_API_BASE_URL||'http://localhost:8000';
async function json<T>(path:string,options?:RequestInit):Promise<T>{const response=await fetch(BASE+path,options);if(!response.ok)throw new Error(`API ${response.status}: ${(await response.text()).slice(0,180)}`);return response.json() as Promise<T>}
export const api={
 climate:()=>json<ClimateSummary>('/api/climate/summary'),
 crops:()=>json<{records:Crop[]}>('/api/crops'),
 soil:()=>json<SoilProfile>('/api/soil/profile'),
 compare:(farm:FarmProfile,strategy:Strategy,candidate_crop_ids:string[])=>{if(farm.latitude===null||farm.longitude===null)throw new Error('Farm location is required: choose a map point or enter both coordinates.');if(farm.latitude<-90||farm.latitude>90)throw new Error('Latitude must be between -90 and 90.');if(farm.longitude<-180||farm.longitude>180)throw new Error('Longitude must be between -180 and 180.');return json<CompareResponse>('/api/rotations/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({farm,strategy,candidate_crop_ids})})},
};
