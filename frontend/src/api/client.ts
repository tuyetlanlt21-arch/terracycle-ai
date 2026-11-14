import type {ClimateSummary,CompareResponse,Crop,FarmProfile,SoilProfile,Strategy} from '../types';
const BASE=import.meta.env.VITE_API_BASE_URL||'http://localhost:8000';
async function json<T>(path:string,options?:RequestInit):Promise<T>{const response=await fetch(BASE+path,options);if(!response.ok)throw new Error(`API ${response.status}: ${(await response.text()).slice(0,180)}`);return response.json() as Promise<T>}
export const api={
 climate:()=>json<ClimateSummary>('/api/climate/summary'),
 crops:()=>json<{records:Crop[]}>('/api/crops'),
 soil:()=>json<SoilProfile>('/api/soil/profile'),
 compare:(farm:FarmProfile,strategy:Strategy,candidate_crop_ids:string[])=>json<CompareResponse>('/api/rotations/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({farm,strategy,candidate_crop_ids})}),
};
