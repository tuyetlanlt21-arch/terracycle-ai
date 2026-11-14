export type Strategy='current_practice'|'water_saving'|'soil_recovery';
export type Status='PASS'|'FAIL'|'UNKNOWN';
export interface FarmProfile {current_crop:string; farm_area_ha:number; soil_ph:number|null; soil_salinity_ec:number|null; irrigation_water_ec:number|null; irrigation_available:boolean|null; freshwater_availability:'unknown'|'limited'|'adequate'; farmer_priority:'yield'|'water'|'soil'|'income'|'risk'; planting_date:string|null}
export interface Crop {crop_id:string; crop_name:string; source_references?:string[]; source_reference?:string}
export interface ClimateSummary {source?:string; status?:string; period?:{start:string;end:string}; forecast_available?:boolean; monthly_metrics?:unknown[]; [key:string]:unknown}
export interface SoilProfile {status?:string; diagnostics?:{null_value_count?:number;coverage_interpretation?:string}; [key:string]:unknown}
export interface Recommendation {sequence:string[]; crop_id:string; crop_name:string; strategy:Strategy; eligibility:Status; score:number|null; growth_duration_days:number|null; hard_constraints_pass:Status; suitability:Record<string,Status>; rationale:string[]; warnings:string[]; sources:string[]}
export interface RejectedAlternative {crop_id:string; sequence:string[]; eligibility:Status; reasons:string[]; sources:string[]}
export interface CompareResponse {recommendations:Recommendation[]; rejected_alternatives:RejectedAlternative[]; missing_data_warnings:string[]; warnings:string[]; provenance:{forecast_available:boolean; climate_period?:string; soil_status?:string; [key:string]:unknown}; scoring:Record<string,unknown>}
