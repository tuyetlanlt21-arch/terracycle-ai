export type Strategy='current_practice'|'water_saving'|'soil_recovery';
export type Status='PASS'|'FAIL'|'UNKNOWN';
export interface FarmProfile {current_crop:string; farm_area_ha:number; soil_ph:number|null; soil_salinity_ec:number|null; irrigation_water_ec:number|null; irrigation_available:boolean|null; freshwater_availability:'unknown'|'limited'|'adequate'; farmer_priority:'yield'|'water'|'soil'|'income'|'risk'; planting_date:string|null}
export interface Crop {crop_id:string; crop_name:string; source_references?:string[]; source_reference?:string}
export interface ClimateMonth {month:string; precipitation_sum_mm?:number|null; temperature_mean_c?:number|null; temperature_max_mean_c?:number|null; relative_humidity_mean_pct?:number|null; solar_radiation_mean_kwh_m2_day?:number|null; wind_speed_mean_m_s?:number|null; missing_count?:number}
export interface ClimateSummary {source?:string; status?:string; period?:{start:string;end:string}; forecast_available?:boolean; monthly_metrics?:ClimateMonth[]; seasonal_features?:Record<string,unknown>; units?:Record<string,string>; [key:string]:unknown}
export interface SoilProfile {status?:string; diagnostics?:{null_value_count?:number;coverage_interpretation?:string}; [key:string]:unknown}
export interface Recommendation {sequence:string[]; crop_id:string; crop_name:string; strategy:Strategy; eligibility:Status; score:number|null; growth_duration_days:number|null; hard_constraints_pass:Status; suitability:SuitabilityAssessment; rationale:string[]; warnings:string[]; sources:string[]}
export interface RejectedAlternative {crop_id:string; sequence:string[]; eligibility:Status; reasons:string[]; sources:string[]}
export interface SuitabilityAssessment {temperature:Status; rainfall_window:Status; water:Status; soil:Status; salinity:Status}
export interface Provenance {climate_source:string; climate_period:string|null; climate_source_url:string|null; soil_status:string|null; forecast_available:boolean}
export interface ScoringMetadata {weights:Record<string,number>; score_definition:string; threshold_time_basis:Record<string,string>; annual_rainfall_policy:string; window_rainfall_policy:string}
export interface CompareResponse {recommendations:Recommendation[]; rejected_alternatives:RejectedAlternative[]; missing_data_warnings:string[]; warnings:string[]; provenance:Provenance; scoring:ScoringMetadata}
