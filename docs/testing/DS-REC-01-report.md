# DS-REC-01 — Recommendation Quality Audit

Date: 2026-11-14

## Audit setup

The Rotation Engine was run at the verified Long Xuyên pilot point
(`10.383333, 105.45`) with the same profile for all strategies:

- current crop: rice
- planting date: 2024-11-01
- soil pH: 6.0
- soil salinity EC: 1.0 dS/m
- irrigation-water EC: 0.5 dS/m
- irrigation available: true
- freshwater availability: adequate
- candidates: rice, maize, mung bean, soybean

NASA POWER supplied the stored pilot daily series. The E2E report records the
live location/provenance result; SoilGrids was location-matched but its stored
profile contained only null values (`no_data`).

## Findings by strategy

### Current Practice

- Ranking puts rice first as `rice → rice`, because continuation is explicitly
  ranked first.
- Rice has PASS temperature, soil pH, salinity, water-access and calendar
  dimensions, but rainfall-window is UNKNOWN. Its final eligibility is now
  UNKNOWN and score is null.
- Mung bean is returned as UNKNOWN: the rice→mung transition is supported and
  temperature/soil/salinity pass, but its planting calendar and seasonal water
  requirement are not verified.
- Soybean is returned as UNKNOWN: rice→soybean is supported, but no verified
  Long Xuyên soybean calendar exists and rainfall-window remains UNKNOWN.
- Maize is rejected: no rice→maize transition rule exists. This is a rule
  failure, not a climate failure.

### Water Saving

- Soybean ranks first because its sourced drought sensitivity (`low-medium`) is
  better than rice (`high`), followed by rice and mung bean.
- The ranking is metadata-based only and does not claim a measured water
  saving. All assessable candidates remain UNKNOWN or null-score because the
  rainfall window is not a verified crop threshold; mung bean also lacks a
  seasonal water requirement.
- Maize remains rejected for the unsupported rice→maize transition.

### Soil Recovery

- Mung bean ranks first because it is a sourced legume, followed by soybean;
  rice is ranked after legumes.
- This is a ranking preference, not proof of nitrogen benefit. The catalog
  explicitly makes rhizobia/inoculation and field management conditional.
- Mung bean remains UNKNOWN due to missing water requirement/calendar evidence.
- Soybean remains UNKNOWN due to missing calendar/rainfall-window evidence.
- Maize remains rejected for the unsupported transition.

The strategies therefore differ in ranking logic and rationale, not merely in
display name. Their suitability dimensions are intentionally conservative and
their scores are all null for this scenario.

## Quality issues found

### Fixed — Critical

`rainfall_status` was present in the response suitability object and was used
to gate score calculation, but was omitted from the `statuses` set used for
eligibility. A candidate could therefore have `rainfall_window=UNKNOWN` and
still receive `eligibility=PASS`.

The fix includes `rainfall_status` in the hard eligibility aggregation. No
rainfall threshold was added. Existing tests now confirm unknown evidence does
not become PASS.

### SoilGrids no_data — Informational / handled

The SoilGrids artifact is location-matched but contains null pixel means. It
does not provide pH/EC evidence to the engine. Farmer-provided pH and EC remain
separate inputs; no SoilGrids values are substituted. This appropriately keeps
missing evidence explicit.

### Score behavior — Accepted limitation

The score is null unless every required suitability dimension is PASS and the
rainfall window is PASS. Current policy deliberately leaves rainfall-window
UNKNOWN because annual catalog rainfall ranges cannot be compared with a
seasonal daily sum. Therefore 100 is not reached in this audit. The declared
weights (`temperature=0.4`, `water=0.3`, `soil=0.3`) are metadata only and are
not applied to a partial score; this is consistent with the score definition
but should be documented as a future scoring-model decision.

### FAIL versus UNKNOWN — Accepted distinction

- Unsupported rice→maize transition is a genuine FAIL under the verified rule
  set.
- Missing calendars, missing seasonal water requirement and missing rainfall
  basis are UNKNOWN, not FAIL.
- Temperature outside an absolute catalog range and explicit salinity limit
  violations remain evidence-backed FAIL conditions.

## Recommended minimal follow-up

1. Keep the rainfall eligibility fix and add a regression test for
   `rainfall_window=UNKNOWN => eligibility!=PASS`.
2. Preserve null scores until DS supplies a sourced, seasonally valid scoring
   basis; do not force the declared weights into an unsupported partial score.
3. Add verified crop calendars and seasonal water evidence only when sourced
   for the Long Xuyên pilot; do not infer mung bean/soybean windows from rice.
4. If future product work needs numeric ranking among UNKNOWN candidates,
   introduce a separately documented evidence-completeness score rather than
   relabeling suitability as PASS.

## Test result and recommendation

```text
python -m pytest datascience/tests backend/tests -q -p no:cacheprovider
125 passed, 2 warnings
```

Recommendation quality status: **GO for evidence-audit/demo use at the
Long Xuyên pilot point**, with UNKNOWN/null-score states shown prominently.

It is **NO-GO for presenting these outputs as agronomic prescriptions** until
crop-specific calendars, seasonal water evidence and a justified score model
are available. No new data, threshold or rotation rule was created in this
audit.
