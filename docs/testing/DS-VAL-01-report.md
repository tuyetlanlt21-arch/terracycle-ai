# DS-VAL-01 — Independent DS Validation Report

## Phạm vi và entry point

Giai đoạn 1 được thực hiện độc lập với tiến độ runtime của Backend/Frontend và không gọi NASA POWER/SoilGrids live.

- Decision entry point thực tế: `backend.app.services.decision.compare_rotation(scenario)`.
- Input contract: `RotationScenario` chứa `FarmProfile`, `strategy` và `candidate_crop_ids` trong `backend/app/models.py`.
- DS reusable primitives: `datascience.rotation_engine.assess_climate_window`, `assess_sequence`, `validate_sequence`, `rank_strategy`.
- NASA POWER CLI: `python -m datascience.power --latitude ... --longitude ... --start YYYYMMDD --end YYYYMMDD`.
- Cách chạy validation từ repo root:

  ```powershell
  $env:PYTHONPATH='backend;.'
  python -m pytest -q datascience/tests backend/tests -p no:cacheprovider
  python -m compileall -q datascience backend
  ```

## Test matrix

| Nhóm | Nội dung xác minh | Test coverage | Kết quả |
|---|---|---|---|
| FarmProfile | Required/range/enum/date validation | `test_farm_profile_rejects_invalid_values` | PASS |
| FarmProfile | Null optional soil, water và planting fields | `test_farm_profile_accepts_null_optional_measurements` | PASS |
| Strategies | Current Practice, Water Saving, Soil Recovery | `test_all_strategies_return_contract_fields_and_strategy_rationale` | PASS |
| Status | PASS, FAIL, UNKNOWN; unsupported/overlap/transition | Existing DS tests + `test_transition_status_and_unsupported_candidate_are_explicit` | PASS |
| Score | Không score khi evidence chưa đủ | `test_unknown_evidence_is_not_scored_and_warnings_are_actionable` + existing backend tests | PASS |
| Climate | Growth-window temperature and incomplete daily coverage | Existing `test_ds_rotation_engine.py`, backend rotation tests | PASS |
| Rainfall-window | Daily precipitation được tổng hợp; annual rainfall không dùng làm seasonal pass/fail | Existing backend tests + DS climate tests | PASS |
| Water/soil | Water availability, soil pH, salinity EC, missing values | `test_unknown_evidence...`, `test_failures...` | PASS |
| Rationale/warnings | Strategy rationale và missing-data warnings có nội dung | `test_all_strategies...`, `test_unknown_evidence...` | PASS |
| Rejected alternatives | Hard failure được reject kèm reasons và sources | `test_failures_are_rejected_with_reasons_and_no_recommendation` | PASS |
| Evidence/provenance | Deduplicated source URLs; NASA historical/forecast flag; scoring policy | `test_evidence_sources_are_deduplicated_and_provenance_is_present` | PASS |
| JSON contract | Top-level và recommendation fields khớp Pydantic/API response hiện tại | `test_json_output_matches_current_api_contract` | PASS |
| POWER ingestion | Fill values/null, validation, leap day, cross-year window | `datascience/tests/test_power.py` | PASS |
| Soil/knowledge base | Null preservation, catalog/rule source checks | `datascience/tests/test_knowledge_base.py` | PASS |

## Kết quả chạy thực tế

**PASS — 46 passed, 0 failed.**

`compileall` cũng PASS cho `datascience` và `backend`.

Có 2 warning mức thấp từ dependency: `StarletteDeprecationWarning` do `httpx` compatibility trong `fastapi.testclient`. Đây không phải lỗi nghiệp vụ hoặc lỗi DS; xử lý dependency có thể để ở maintenance riêng.

## Những phần đã xác minh

- FarmProfile không nhận giá trị ngoài range/enum/date; null optional không bị biến thành giá trị giả.
- Ba strategy chỉ ảnh hưởng ranking/rationale theo metadata nguồn; không tạo claim định lượng về tiết kiệm nước hay phục hồi đất.
- UNKNOWN không bị nâng thành PASS; score là `null` khi thiếu rainfall-window, water, soil hoặc evidence bắt buộc.
- Annual ECOCROP rainfall chỉ là context; không bị so sánh với seasonal precipitation.
- Missing daily climate coverage, missing soil/water data và mung-bean seasonal water gap đều được giữ minh bạch.
- Salinity vượt ngưỡng nguồn là hard FAIL; transition không có rule và crop ngoài catalog bị reject.
- Rationale, warnings, missing-data warnings, rejected alternatives và provenance được phát ra trong output.
- JSON serialization khớp response contract hiện tại: `recommendations`, `rejected_alternatives`, `missing_data_warnings`, `warnings`, `provenance`, `scoring`.
- Evidence hiện được biểu diễn bằng danh sách `sources` deduplicated và provenance ở response level; không tự thêm field vào API contract.

## Phần chưa thể xác minh ở giai đoạn 1

- Integration với Backend process/HTTP deployment, database, auth, CORS runtime và frontend rendering chưa được kiểm thử end-to-end.
- NASA POWER live availability/retry behavior và SoilGrids live service chưa được gọi; chỉ kiểm thử normalize/adapter bằng payload fixture và dữ liệu đã lưu trong repo.
- Không xác minh được production payloads, browser behavior, network timeout UX hoặc FE mapping ngoài contract/type hiện có.
- Không đánh giá calibration/ground truth agronomy, yield uplift, irrigation volume, ET0 hay nitrogen gain vì các đại lượng này không được mô hình hóa trong scope hiện tại.

## Thay đổi trong DS-VAL-01

- Thêm `datascience/tests/test_ds_val_01.py` với các test độc lập nêu trên.
- Thêm báo cáo này.
- Không sửa Frontend, Backend implementation, API contract hoặc thuật toán khoa học; không commit/push.

