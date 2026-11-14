# DS-VAL-02 — Scenario-Based Validation (Cần Giờ)

## Phạm vi

Đã chạy 6 scenario × 3 strategy = 18 lượt đánh giá qua `backend.app.services.decision.compare_rotation()`. Farm inputs là synthetic fixtures để kiểm thử; không phải quan trắc thực địa Cần Giờ. Bộ rules hiện tại có pilot context Long Xuyên/An Giang, vì vậy kết quả được xem là kiểm tra tính nhất quán của rule engine, không phải khuyến nghị địa phương đã được hiệu chuẩn.

Files:

- Fixture: `datascience/tests/fixtures/ds_val_02_can_gio.json`
- Automated tests: `datascience/tests/test_ds_val_02_scenarios.py`
- Entry point: `compare_rotation(RotationScenario(...))`

## Expected behavior theo bằng chứng/rules

- EC salinity `>= 4 dS/m` là FAIL đối với crop có catalog limit `low (<4 dS/m)`.
- pH trong optimal range là PASS; ngoài optimal nhưng còn trong absolute range là UNKNOWN, không tự động FAIL.
- Thiếu water/soil/planting evidence là UNKNOWN; không dùng rainfall để thay thế irrigation demand.
- Annual rainfall reference không được so sánh với seasonal precipitation.
- Score chỉ có khi toàn bộ căn cứ cần thiết để score là PASS; UNKNOWN giữ score `null`.
- Boundary `pH=5.5` của rice là PASS; boundary `EC=4.0` là FAIL vì rule dùng `>=`.

## Matrix và actual output

Trong bảng, target là `rice` để so sánh nhất quán giữa ba strategy. `FAIL` được trả ở `rejected_alternatives`; vì contract hiện tại `RejectedAlternative` chỉ có `reasons/sources`, không có `suitability`, `rationale` hay `score`. Các strategy vẫn được chạy đầy đủ; ranking có thể đưa crop khác lên trước nhưng không thay đổi rule assertion của target.

| Scenario | Expected | Current Practice | Water Saving | Soil Recovery | Severity |
|---|---|---|---|---|---|
| SC-01 high salinity | rice FAIL, salinity FAIL, score null | rice rejected FAIL; reason salinity | rice rejected FAIL; reason salinity | rice rejected FAIL; reason salinity | PASS; no defect |
| SC-02 limited water | rice FAIL, water FAIL, score null | rice rejected FAIL; reason water | rice rejected FAIL; reason water | rice rejected FAIL; reason water | PASS; no defect |
| SC-03 pH 7.5 | rice UNKNOWN, soil UNKNOWN, score null | rice recommendation UNKNOWN; soil outside optimal warning | same target behavior | same target behavior | PASS; no defect |
| SC-04 favorable inputs | temperature/soil/salinity PASS; rainfall basis remains unknown; score null | rice recommendation PASS hard eligibility; score null; rainfall context rationale | same target behavior | same target behavior | PASS; no defect |
| SC-05 missing critical data | UNKNOWN; score null; warnings required | rice UNKNOWN; planting/soil/water warnings | same target behavior | same target behavior | PASS; no defect |
| SC-06 pH/EC boundary | pH 5.5 PASS, EC 4.0 FAIL; score null | rice rejected FAIL; salinity reason | same target behavior | same target behavior | PASS; no defect |

All 18 runs also verified:

- `sequence == [current_crop, target_crop]`.
- Provenance identifies `NASA POWER` and `forecast_available == false`.
- Response-level warnings are present.
- UNKNOWN recommendations carry warnings or response missing-data warnings.
- FAIL alternatives are present in `rejected_alternatives` with sources/reasons.
- Strategy-specific ranking/rationale remains metadata-based; no numeric water saving, yield, nitrogen gain or soil restoration claim is inferred.

## Test result

Command:

```powershell
$env:PYTHONPATH='backend;.'
python -m pytest -q datascience/tests backend/tests -p no:cacheprovider
```

Result: **65 passed, 0 failed, 2 dependency warnings**.

The DS-VAL-02 file contributes 19 passing tests: 18 matrix evaluations and one fixture cardinality/source-policy check. The 2 warnings are existing Starlette/httpx deprecations and are Minor maintenance items, not DS/business failures.

## Defect classification

| Severity | Finding | Status |
|---|---|---|
| Critical | No critical scientific or safety failure found in these six synthetic scenarios. | None |
| Major | No major failure found. | None |
| Minor | Existing `StarletteDeprecationWarning` from `fastapi.testclient`/httpx compatibility. | Open maintenance item; unrelated to scenario logic |
| Observation | Cần Giờ is not the source context in `rotation_rules.json`; rules are Long Xuyên/An Giang pilot-context rules. | Limitation, not auto-fixed |
| Contract limitation | Rejected alternatives omit suitability dimensions, rationale and score by current API contract, so rejected assertions use reasons/sources only. | Pending contract/product decision; contract not changed |

## Chưa thể xác minh

- Không thể xác minh tính đại diện agronomic của Cần Giờ vì không có field measurements, salinity time series, irrigation balance, crop yield ground truth hoặc local validated calendars trong scope này.
- Không gọi NASA POWER/SoilGrids live; climate/soil behavior được đánh giá từ dữ liệu repo và fixture, không gọi là quan trắc Cần Giờ.
- Chưa có BE deployment, FE rendering, browser/network failure, auth/CORS hoặc end-to-end integration test.
- Chưa xác minh boundary cho tất cả crop thresholds; SC-06 kiểm tra rice boundary theo catalog hiện tại.
- Chưa đánh giá calibrated score vì engine chủ động trả `null` khi rainfall-window không scoreable.

Không sửa FE/BE/API contract/thuật toán khoa học và không commit/push.

