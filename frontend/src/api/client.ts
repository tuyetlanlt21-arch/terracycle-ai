import type { ClimateSummary, CompareResponse, ScenarioRequest } from '../types';
const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
async function json<T>(path: string, options?: RequestInit): Promise<T> {
 const res = await fetch(BASE + path, options);
 if (!res.ok) throw new Error('API ' + res.status + ': ' + (await res.text()).slice(0, 160));
 return await res.json() as T;
}
export const api = {
 demo: () => json<ScenarioRequest>('/api/demo'),
 climate: () => json<ClimateSummary>('/api/climate/summary'),
 compare: (body:ScenarioRequest) => json<CompareResponse>('/api/scenarios/compare', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),
};
