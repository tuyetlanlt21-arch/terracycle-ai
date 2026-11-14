# DS-VAL-03 — Scientific Consistency & Generalizability Audit

## Executive conclusion

**Pilot-limited GO; multi-region NO-GO trước demo nếu không có guardrail khu vực.**

Trong phạm vi Long Xuyên/An Giang pilot, engine có nhiều cơ chế bảo thủ: thiếu evidence giữ `UNKNOWN`, score giữ `null`, annual rainfall không bị dùng như seasonal test, salinity/pH/water có rationale và provenance. Tuy nhiên entry point hiện tại không nhận region, latitude/longitude, evidence profile hoặc rule-set version từ người dùng. `compare_rotation()` luôn nạp các file cố định trong repository: một catalog, một ruleset, một climate summary và một soil profile. Vì vậy hệ thống hiện không thể biết người dùng đang ở ngoài pilot và có thể trả recommendation theo pilot evidence cho khu vực khác.

Đây là giới hạn tổng quát hóa có mức **Major**; chưa có bằng chứng cho một lỗi ngưỡng khoa học cụ thể đủ để kết luận các ngưỡng hiện tại sai trong pilot.

## Evidence đã audit

- DS modules: `datascience/power.py`, `soilgrids.py`, `ecocrop.py`, `rotation_rules.py`, `rotation_engine.py`.
- Decision engine: `backend/app/services/decision.py`.
- Schemas/API: `backend/app/models.py`, `backend/app/main.py`, `frontend/src/types.ts`.
- Evidence: `data/reference/crop_catalog.json`, `data/reference/rotation_rules.json`, `data/processed/power/*`, `data/processed/soil/soilgrids_profile.json`.
- Reports: DS-VAL-01 và DS-VAL-02.

## 1. Scientific rule inventory

| Rule/dimension | Current implementation | Unit/basis | Applicability |
|---|---|---|---|
| Crop temperature | Mean `temperature_avg_c` over sourced growth window; optimal → PASS, outside optimal but inside absolute → UNKNOWN, outside absolute → FAIL | °C; daily NASA POWER aggregate | General screening pattern, but crop thresholds and calendar are evidence-dependent |
| Crop duration/window | Uses catalog `growth_duration.max_days`; requires complete daily coverage; no imputation | days | General data-quality rule; duration is crop/source/region dependent |
| Rainfall | Daily `precipitation_mm_day` is summed and reported, but `rainfall_window` remains UNKNOWN because catalog values are annual | mm/day → mm over window; catalog mm/year | Conservative and scientifically consistent as implemented; not a seasonal water-balance model |
| Soil pH | Optimal range PASS; absolute range only UNKNOWN outside optimal; missing UNKNOWN | dimensionless pH | General screening rule; threshold is crop/source/context dependent |
| Soil salinity EC | Parses catalog strings such as `low (<4 dS/m)`; `EC >= limit` → FAIL; missing UNKNOWN | dS/m | Unit is explicit in catalog/rationale; threshold is crop-specific and source-dependent |
| Irrigation-water EC | Field is nonnegative and required when irrigation is reported available; missing can make water UNKNOWN | Schema has no unit metadata; code does not compare numeric EC to a crop threshold | Input capture only; not a scientific suitability rule yet |
| Water availability | No crop seasonal requirement → UNKNOWN; no irrigation + limited freshwater → FAIL; unknown/incomplete access → UNKNOWN | crop metadata mm/season, explicitly not irrigation demand | General decision guardrail, but not a field water balance |
| Soil pH / salinity source | Farmer/local fields are used; SoilGrids profile status is only provenance | SoilGrids does not provide salinity EC in this design | Appropriate separation of modeled soil vs local EC, but no field-level location linkage |
| Crop sequence | Supported transitions from rules; unsupported transitions FAIL; overlaps fail in DS primitive | sequence/date/duration | Transition rules are strongly pilot/context dependent |
| Strategies | Current, water-saving and soil-recovery rank using catalog metadata; feasibility remains separate | categorical metadata | Ranking can generalize only with region-valid catalog/rules |
| Score | `null` unless all required dimensions pass and rainfall status is PASS | score policy says null unless all required time/water/soil dimensions PASS | Conservative; currently no normal positive score path in backend because rainfall status is always UNKNOWN |
| Provenance | Crop sources and response-level NASA/soil/forecast fields are emitted | URLs, period, source status | Useful but not sufficient to prove region applicability or field-level evidence |

## 2. Consistency audit

### Consistent / supported by repository evidence

1. **PASS/FAIL/UNKNOWN semantics are conservative.** Missing soil pH, EC, water access, planting date or climate window does not become PASS. This matches `rotation_rules.json` scoring policy and DS-VAL-01/02 observations.
2. **Salinity and irrigation-water salinity are not conflated.** Soil salinity EC is farmer/local input; SoilGrids notes explicitly exclude salinity EC and irrigation-water EC. This is scientifically safer than deriving EC from SoilGrids.
3. **Rainfall time basis is explicit.** NASA daily precipitation is summed for a growth window, but annual ECOCROP rainfall is not compared to that sum. The result stays UNKNOWN rather than claiming seasonal suitability.
4. **Historical climate is not presented as forecast.** Response provenance sets `forecast_available: false`, and warnings state NASA POWER is historical context.
5. **Hard failures are separated from unknown evidence.** Salinity at/above the structured `<4 dS/m` limit and unavailable water under the coded condition can reject an alternative; incomplete evidence remains UNKNOWN.
6. **Source preservation is present.** Catalog and transition URLs are included in recommendation/rejection sources, and source lists are deduplicated.

### Inconsistencies or material gaps

1. **The stored `WEIGHTS` do not currently score recommendations.** `WEIGHTS={temperature:0.4, water:0.3, soil:0.3}` is exposed as scoring metadata, but the implementation only assigns a score when every hard status and `rainfall_status` are PASS; `rainfall_status` is unconditionally UNKNOWN. This is internally conservative, but the presence of weights may imply a calibrated score that is not actually produced.
2. **`irrigation_water_ec` has no unit or threshold semantics in the schema.** It is constrained only to nonnegative numbers. The decision code checks whether it is missing when irrigation is available, but never evaluates its numeric value against a sourced crop/water limit. It must not be described as water-quality suitability.
3. **Climate provenance is not linked to the requested location at decision time.** `compare_rotation()` reads the fixed `climate_summary.json` and fixed daily CSV; the `FarmProfile` has no coordinates/region. The output period and source URL do not establish that the climate file belongs to the farmer's location.
4. **Soil provenance is response-level only.** The engine reads the fixed `soilgrids_profile.json` status but does not load a location-specific SoilGrids profile into suitability calculations. Farmer-entered pH/EC can therefore be used without a machine-checkable location/evidence timestamp.
5. **Calendar rules are pilot-specific but not marked as such in response.** Rice windows cite An Giang-specific material; non-rice calendars are explicitly unavailable. The response does not expose a rule-set geography or applicability status.
6. **Rejected alternatives lose dimensional detail at contract level.** A rejected item has reasons and sources but no suitability map, warnings or score. The engine does carry rationale into `reasons`, but consumers cannot distinguish which dimension failed without parsing free text.
7. **Location is not part of API contract.** `FarmProfile` includes no `region`, `latitude`, `longitude`, `country` or `pilot_context`. The frontend type mirrors this omission.

## 3. Geographic applicability

### Explicitly Long Xuyên/An Giang-specific

- Pilot coordinate and scope in `docs/data-sources.md`, catalog `pilot_context`, and rules `pilot`.
- Rice planting windows sourced from an An Giang decision/document.
- Transition evidence and crop constraints are described for the Long Xuyên/Mekong Delta pilot context.
- The stored climate/soil artifacts are repository-level artifacts, not dynamically selected by the request location.

These rules must not be silently treated as Cần Giờ, another Vietnamese province, or another country rules.

### Potentially reusable beyond the pilot, only with local evidence

- Unit-aware NASA POWER normalization, fill-value handling, date continuity checks and no-imputation policy.
- General pH/temperature range evaluation pattern.
- General distinction between PASS, FAIL and UNKNOWN.
- General provenance/source URL preservation.
- General sequence validation for chronology/overlap.

Reusable patterns do not make the current numeric thresholds, planting calendar, transitions, salinity limits or water rules geographically portable.

## 4. Generalization limitations and overconfidence risk

The current system **cannot detect an out-of-pilot user** because there is no location input at the decision/API layer. A user outside Long Xuyên can receive a response with:

- `climate_source: NASA POWER` and a period, but no location match;
- pilot crop/rule evidence and a normal-looking recommendation;
- `forecast_available: false`, which correctly describes forecast status but does not describe geographic validity;
- an eligibility status that may look actionable even when local calendar/transition evidence is absent.

The engine is not maximally overconfident on missing dimensions—many outputs are UNKNOWN and scores are null—but it is still **geographically overconfident by omission**: the response has no explicit `pilot-only` or `location evidence unavailable` state. This is a product/scientific safety issue, not evidence that the underlying pilot thresholds are wrong.

## 5. Risk classification

| Severity | Finding | Impact |
|---|---|---|
| Critical | No Critical defect established by repository audit. | No demonstrated catastrophic computation or unsafe unit conversion |
| Major | No region/coordinates in input or output; fixed pilot artifacts are used for every request. | Out-of-pilot recommendations cannot be blocked or labeled; multi-region demo is not scientifically defensible |
| Major | Pilot-specific calendars/transitions have no runtime applicability guard. | A valid Long Xuyên rule can appear portable to another geography |
| Major | Irrigation-water EC is accepted but not scientifically evaluated and has no unit field. | Users may infer water-quality screening that the engine does not perform |
| Minor | Response-level provenance lacks location, evidence version/hash and field-level linkage. | Auditing/reproducibility is weaker than needed for multi-region use |
| Minor | Scoring weights are exposed although score is currently always null under the rainfall policy. | UX/API may imply calibrated ranking/score that is not available |
| Minor | Rejected alternatives lack structured suitability/warning fields. | FE/QA cannot inspect rejected dimensions without parsing reasons |

## 6. Recommended improvements (not implemented)

These are recommendations only; no code or contract was changed in this audit.

1. Add a location/applicability guard at the product boundary: identify the active region and rule-set geography, and return an explicit UNKNOWN/blocked state when no region-specific evidence bundle exists. Do not silently reuse Long Xuyên rules.
2. Version evidence bundles by region and crop/rule source, including source URLs, retrieval date, period, coordinates and content hash. Propagate the bundle identity into provenance.
3. Separate portable algorithm primitives from region-specific data: load catalog, calendar, transition and climate artifacts from an evidence bundle selected by region, rather than fixed module paths.
4. Define the semantics and unit of irrigation-water EC before using it in suitability. Until a sourced crop/water threshold exists, keep numeric water-EC suitability UNKNOWN and state that clearly.
5. Keep annual rainfall context separate from seasonal water demand. If a future scoring model is introduced, require sourced seasonal water-balance inputs and validate units before assigning a numeric score.
6. Expose structured applicability/missing-evidence diagnostics in the existing product design only after API review; do not overload `sources` or infer geography from prose.
7. Add out-of-pilot test cases: no region, unsupported region, region with climate but no calendar, and region with crop data but no local transition evidence. Expected result should be UNKNOWN/blocked, never a silent pilot recommendation.
8. Add a scientific review gate for any new regional thresholds; do not derive them from the Long Xuyên values or from generic annual rainfall.

## 7. Go/No-Go assessment

| Use case | Decision | Conditions |
|---|---|---|
| Long Xuyên/An Giang pilot screening with explicit pilot labeling | **GO with limitations** | Keep historical-context disclaimer, UNKNOWN/null-score behavior and pilot scope visible |
| Cần Giờ or another Vietnamese region as a scientific recommendation | **NO-GO** | No local rule/evidence bundle and no location applicability guard |
| General-purpose multi-region product demo | **NO-GO** | Add region-aware evidence selection and explicit out-of-coverage behavior first |
| Demonstrating reusable DS primitives only | **GO** | Present as framework/data-quality demonstration, not agronomic recommendation |

## Verification status

This audit made no changes to Frontend, Backend, API contract, algorithm, thresholds or data. No commit or push was performed. The existing automated suite remains the evidence baseline; DS-VAL-03 itself is a static scientific consistency/generalizability audit and does not claim new field validation.

