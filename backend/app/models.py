from typing import Literal, Optional
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Priority = Literal["yield", "water", "soil", "income", "risk"]
Strategy = Literal["current_practice", "water_saving", "soil_recovery"]
Status = Literal["PASS", "FAIL", "UNKNOWN"]
EvaluationStatus = Literal["PASS", "FAIL", "NEEDS_INPUT", "DATA_UNAVAILABLE"]

class FarmProfile(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    current_crop: str = Field(min_length=1, max_length=100)
    farm_area_ha: float = Field(gt=0, le=100000)
    soil_ph: float | None = Field(default=None, ge=3.5, le=9)
    soil_salinity_ec: float | None = Field(default=None, ge=0)
    irrigation_water_ec: float | None = Field(default=None, ge=0)
    irrigation_available: bool | None = None
    freshwater_availability: Literal["unknown", "limited", "adequate"] = "unknown"
    drainage_available: bool | None = None
    water_control_available: bool | None = None
    inoculation_confirmed: bool | None = None
    farmer_priority: Priority = "yield"
    planning_month: int | None = Field(default=None, ge=1, le=12)
    planting_date: date | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self

    @field_validator("current_crop")
    @classmethod
    def current_crop_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("current_crop must not be blank")
        return value

    def missing_evidence(self, crop_id: str | None = None) -> list[str]:
        missing=[]
        if self.latitude is None or self.longitude is None: missing.append("latitude and longitude")
        if self.planting_date is None: missing.append("planting_date")
        if self.soil_ph is None: missing.append("soil_ph field measurement")
        if self.soil_salinity_ec is None: missing.append("soil_salinity_ec field measurement")
        if self.irrigation_available is None: missing.append("irrigation_available")
        if self.freshwater_availability == "unknown": missing.append("freshwater_availability")
        if self.irrigation_available is True and self.irrigation_water_ec is None: missing.append("irrigation_water_ec field measurement")
        if crop_id in {"rice", "soybean", "maize", "mung_bean"} and self.drainage_available is None: missing.append("drainage_available")
        if crop_id in {"rice", "soybean"} and self.water_control_available is None: missing.append("water_control_available")
        if crop_id == "soybean" and self.inoculation_confirmed is None: missing.append("inoculation_confirmed")
        return missing

class CropProfile(BaseModel):
    crop_id: str
    crop_name: str
    temperature_min_c: float | None = None
    temperature_max_c: float | None = None
    rainfall_min_mm: float | None = None
    rainfall_max_mm: float | None = None
    soil_ph_min: float | None = None
    soil_ph_max: float | None = None
    growth_duration_days: int | None = Field(default=None, ge=0)
    source_reference: str

class RotationScenario(BaseModel):
    farm: FarmProfile
    strategy: Strategy
    candidate_crop_ids: list[str] = Field(default_factory=list, max_length=20)

class SuitabilityAssessment(BaseModel):
    temperature: Status
    rainfall_window: Status
    water: Status
    soil: Status
    salinity: Status

    def __getitem__(self, key: str): return getattr(self, key)
    def __iter__(self): return iter(type(self).model_fields)

class RotationRecommendation(BaseModel):
    sequence: list[str]
    crop_id: str
    crop_name: str
    strategy: Strategy
    eligibility: Status
    score: float | None
    growth_duration_days: int | None
    hard_constraints_pass: Status
    suitability: SuitabilityAssessment
    rationale: list[str]
    warnings: list[str]
    sources: list[str]
    water_balance: dict[str, object] | None = None
    climate_suitability: Optional["EvaluationResult"] = None
    farm_suitability: Optional["EvaluationResult"] = None
    final_decision: Literal["PASS", "FAIL"] | None = None

class EvaluationResult(BaseModel):
    status: EvaluationStatus
    reasons: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    calculations: dict[str, object] = Field(default_factory=dict)
    provenance: list[str] = Field(default_factory=list)

class RejectedAlternative(BaseModel):
    crop_id: str
    sequence: list[str]
    eligibility: Status
    reasons: list[str]
    sources: list[str]

class Provenance(BaseModel):
    climate_source: str
    climate_period: str | None
    climate_source_url: str | None
    soil_status: str | None
    forecast_available: bool
    evaluated_location: dict[str, float] | None = None
    availability: dict[str, str] = Field(default_factory=dict)
    observation_time: str | None = None
    warnings: list[str] = Field(default_factory=list)
    rule_set: str | None = None
    supported_scope: str | None = None
    applicability_reason: str | None = None

    def __getitem__(self, key: str): return getattr(self, key)
    def __iter__(self): return iter(type(self).model_fields)

class ScoringMetadata(BaseModel):
    weights: dict[str, float]
    score_definition: str
    threshold_time_basis: dict[str, str]
    annual_rainfall_policy: str
    window_rainfall_policy: str

    def __getitem__(self, key: str): return getattr(self, key)
    def __iter__(self): return iter(type(self).model_fields)

class RotationCompareResponse(BaseModel):
    recommendations: list[RotationRecommendation]
    rejected_alternatives: list[RejectedAlternative]
    missing_data_warnings: list[str]
    warnings: list[str]
    provenance: Provenance
    scoring: ScoringMetadata

RotationRecommendation.model_rebuild()
