import type {ClimateSummary,CompareResponse,Crop,FarmProfile,SoilProfile,Strategy} from '../types';
import { requestJson, resolveApiBase } from './request.mjs';
const BASE=resolveApiBase(import.meta.env.VITE_API_BASE_URL,import.meta.env.DEV);
async function json<T>(path:string,options?:RequestInit):Promise<T>{if(!BASE)throw new Error('API URL is not configured. Set VITE_API_BASE_URL to the backend HTTPS URL.');return requestJson<T>(path,{baseUrl:BASE,requestOptions:options})}
export const api={
 climate:(latitude:number,longitude:number)=>json<ClimateSummary>(`/api/climate/summary?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`),
 crops:()=>json<{records:Crop[]}>('/api/crops'),
 soil:()=>json<SoilProfile>('/api/soil/profile'),
 compare:(farm:FarmProfile,strategy:Strategy,candidate_crop_ids:string[])=>{if(farm.latitude===null||farm.longitude===null)throw new Error('Farm location is required: choose a map point or enter both coordinates.');if(farm.latitude<-90||farm.latitude>90)throw new Error('Latitude must be between -90 and 90.');if(farm.longitude<-180||farm.longitude>180)throw new Error('Longitude must be between -180 and 180.');return json<CompareResponse>('/api/rotations/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({farm,strategy,candidate_crop_ids})})},
};
