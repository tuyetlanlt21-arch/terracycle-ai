export type Stage = 'concentrating' | 'crystallizing' | 'ready';
export interface SaltField { id: string; name: string; area_m2: number; stage: Stage; days_to_harvest: number; expected_value_vnd: number; protection_cost_vnd: number; protection_available: boolean; }
export interface ScenarioRequest { fields: SaltField[]; rain_mm: number; hours_until_rain: number; available_workers: number; available_budget_vnd: number; }
export interface ActionOption { action: 'harvest_early'|'protect'|'continue'|'postpone'; field_id: string; priority: number; rationale: string[]; estimated_cost_vnd: number; assumption: string; }
export interface CompareResponse { scenario: { rain_mm:number; hours_until_rain:number }; actions: ActionOption[]; warnings: string[]; provenance: { climate_source:string; source_type:string; forecast_available:boolean }; }
export interface ClimateSummary { station: string; years: string; source: string; status: string; monthly: Array<{month:number; mean_rain_mm:number; mean_temp_c:number}>; }
