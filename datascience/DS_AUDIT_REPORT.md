# FULL DATA SCIENCE AUDIT — TerraCycle AI / SaltShift

Ngày audit: 2026-11-14
Phạm vi: DS-01 NASA POWER, DS-02 GPM IMERG, DS-03 GLDAS, DS-04 Integration, DS-05 Salt Risk Engine.

## 1. Executive Summary

Các module DS-01 đến DS-05 đều chạy được trên dữ liệu/cached output hiện có và toàn bộ test suite hiện tại PASS: **36 tests passed**. DS-04 đã được kiểm tra bằng ba CSV NASA thực tế và tạo được 7 ngày tích hợp từ 2025-01-01 đến 2025-01-07. DS-05 tạo được historical rule-based assessment có thể tái lập và giải thích.

Tuy nhiên, đây chưa phải production-ready scientific risk model. Bằng chứng dữ liệu thực tế hiện chỉ bao phủ 7 ngày cho IMERG và GLDAS; các ngưỡng/trọng số DS-05 chưa được hiệu chuẩn bằng thiệt hại thực tế hoặc chuyên gia nghề muối; chưa có nguồn forecast; và data confidence của DS-05 đang là giá trị MVP cố định 85 thay vì được tính đầy đủ từ quality metadata.

## 2. Bảng trạng thái

| Module | Trạng thái | Bằng chứng chính |
|---|---|---|
| DS-01 POWER | PASS cho output 2025 hiện có; PARTIAL về scientific audit | 365 records, 9 cột, metadata và quality report; tests POWER PASS |
| DS-02 IMERG | PASS cho cached 7 ngày; PARTIAL về full-year/integration | 7 granules, 25 cells/ngày, mm/day, không missing/duplicate; downloader thật không được audit lại trong turn này |
| DS-03 GLDAS | PASS cho cached 7 ngày; PARTIAL về full-year/subsetting | 56 granules, 7 ngày, 1 cell đại diện; flux và Kelvin conversion được ghi nhận |
| DS-04 Integration | PASS cho 7 ngày | 7 rows, 0 missing/duplicate/null, ba chuỗi mưa được giữ riêng |
| DS-05 Risk Engine | PASS cho Historical MVP; BLOCKED cho production scientific validation | 7 assessments, tests và sensitivity PASS; giả định chưa hiệu chuẩn |

## 3. Audit từng module

### DS-01 — NASA POWER

Source code: `datascience/power.py`; tests: `datascience/tests/test_power.py`; output: `data/processed/power/can_gio_daily_2025.csv`, `metadata.json`.

- Endpoint chính thức là NASA POWER daily point API.
- Request thực tế ghi tọa độ `10.41, 106.96`, khoảng `20250101–20251231`, community `AG` và sáu biến yêu cầu.
- Output có đúng 365 records và schema 9 cột.
- Đơn vị trong metadata: nhiệt độ `C`, mưa `mm/day`, RH `%`, bức xạ `kW-hr/m^2/day` và được đặt tên CSV tương ứng `kwh_m2_day`.
- Fill values `-999/-9999` được đổi thành null; không nội suy.
- Có timeout/retry, kiểm tra response structure, range RH, mưa và bức xạ.
- Hạn chế: test chủ yếu kiểm tra parser/normalizer bằng fixture; metadata hiện không chứa raw response hoặc checksum. Output hiện không có missing, duplicate.

**Đánh giá:** PASS cho data contract hiện có; PARTIAL cho kiểm chứng scientific/full provenance độc lập.

### DS-02 — GPM IMERG Final Run V07

Source: `datascience/imerg.py`; tests: `test_imerg.py`, smoke script; output: `data/processed/imerg/*`.

- Collection `GPM_3IMERGDF`, version `07`, bbox `[106.7,10.2,107.2,10.7]`.
- Metadata thực tế ghi 7 granules, 7 ngày, 25 grid cells/ngày, `mm/day`, min `0`, max `13.305`, mean `0.7933`.
- Raw files là daily NetCDF4 `.nc4`; ngày được chuẩn hóa theo ngày UTC.
- Fill/missing được xử lý trong extraction; không coi missing là zero.
- Spatial aggregation của DS-04 là mean trên 25 cell/ngày. Đây là aggregation phù hợp với vùng bbox đã khai báo, nhưng là đại diện vùng theo grid, không phải ranh giới hành chính hay từng ruộng muối.
- CMR discovery dùng REST pagination `page_size=100`, không dùng lỗi `earthaccess.search_data(page_size=0)`.
- Downloader dùng Earthaccess/session chính thức và kiểm tra NetCDF/HDF5.
- Hạn chế: output thực tế chỉ chứng minh 7 ngày; chưa có bằng chứng cached cho toàn bộ năm 2025. Test suite có nhiều mock; test mock không thay thế xác minh NASA end-to-end.

**Đánh giá:** PASS cho cached 7-day data contract; PARTIAL cho coverage production năm 2025.

### DS-03 — GLDAS Noah 2.1

Source: `datascience/gldas.py`; tests: `test_gldas.py`, smoke script; output: `data/processed/gldas/*`.

- Product `GLDAS_NOAH025_3H`, version `2.1`, 3-hourly, 0.25°, NetCDF.
- Quality report ghi 56 file cho 7 ngày, 7 ngày có dữ liệu, 1 grid cell, không duplicate/missing.
- Đơn vị được kiểm tra trong NetCDF: `Evap_tavg` và `Rainf_tavg` là `kg m-2 s-1`; nhiệt độ `K`; humidity `kg kg-1`; wind `m s-1`; radiation `W m-2`.
- Water flux được nhân `10800` giây/timestep rồi cộng theo UTC day; Tair trừ `273.15`; trạng thái/radiation được spatial/time mean theo logic module.
- Chọn cell dựa trên tọa độ nằm trong bbox và spatial mean; cell GLDAS là 0.25°, không đại diện từng ruộng.
- Có checkpoint/resume và kiểm tra chữ ký HDF5/NetCDF4.
- Evapotranspiration là ước lượng mô hình bề mặt đất, không phải phép đo bốc hơi trực tiếp từ ruộng muối.
- Hạn chế: server-side subsetting chưa được xác minh; cached evidence chỉ 7 ngày; chưa có test độc lập đối chiếu toàn bộ 56 file với số timestep kỳ vọng ngoài quality report.

**Đánh giá:** PASS cho cached 7-day processing; PARTIAL cho full-year và server-side subsetting.

### DS-04 — Data Integration

Source: `datascience/integrate.py`; tests: `test_integrate.py`; output: `data/processed/integrated/*`.

- Merge theo `date` sau khi chuẩn hóa UTC calendar date.
- Khoảng giao thực tế là 7 ngày.
- Output có 7 rows, date unique, không null, không missing.
- Mưa được giữ riêng: `precipitation_power_mm_day`, `precipitation_imerg_mm_day`, `precipitation_gldas_mm_day`; không cộng các nguồn.
- IMERG được mean theo grid cell/ngày; POWER là point; GLDAS là spatial mean 0.25°.
- Không impute, không interpolate; inner join loại bỏ ngày không đủ ba nguồn và quality report ghi missing days.
- Đã sửa trong DS-04: `imerg_grid_cells` hiện đếm số cặp `(latitude, longitude)` duy nhất, không còn nhân số unique latitude với longitude.
- Chưa có validation chặt chẽ về source provenance path trong report và chưa có full-year common-period test.

**Đánh giá:** PASS cho 7-day integration; MEDIUM issue về cách đếm cell và PARTIAL về mở rộng dài hạn.

### DS-05 — Salt Risk Engine

Source: `datascience/salt_risk.py`; tests: `test_salt_risk.py`; output: `data/processed/risk/*`.

Engine là rule-based historical assessment. Không có forecast, machine learning hay dữ liệu độ mặn giả.

Configuration MVP hiện tại:

```text
weights:
  rain_exposure: 0.55
  evaporation_conditions: 0.20
  production_vulnerability: 0.25
rain thresholds mm/day:
  low: 0.1, moderate: 1.0, high: 5.0, critical: 10.0
stage vulnerability:
  preparation: 20, evaporation: 45, crystallization: 80, harvesting: 60
data_confidence_complete: 85
```

Score:

```text
raw = 0.55 * rain_exposure + 0.20 * evaporation_conditions
      + 0.25 * production_vulnerability
score = raw * 0.85
```

Rain Exposure dùng giá trị lớn nhất giữa ba nguồn mưa, không cộng chúng. Evaporation Conditions cộng điểm phạt cho RH cao, solar thấp và GLDAS evapotranspiration thấp. Production Vulnerability lấy theo stage. Đây là quy tắc MVP minh bạch, chưa phải ngưỡng đã được ngành muối xác nhận.

## 4. Kiểm tra độc lập DS-05

Phép tính độc lập bằng `assess_row()` trên CSV tích hợp cho stage `evaporation` cho kết quả:

| Ngày | Score | Level |
|---|---:|---|
| 2025-01-01 | 38.89 | MODERATE |
| 2025-01-02 | 38.89 | MODERATE |
| 2025-01-03 | 38.89 | MODERATE |
| 2025-01-04 | 24.65 | LOW |
| 2025-01-05 | 9.56 | LOW |
| 2025-01-06 | 9.56 | LOW |
| 2025-01-07 | 12.96 | LOW |

01/01, 02/01 và 03/01 cùng score vì:

- Rain Exposure đều rơi vào cùng band `MODERATE` với score 50.
- RH đều trong cùng band `75–<85`, solar trong band `12–<16`, GLDAS ET trên ngưỡng hỗ trợ drying.
- Stage đều là `evaporation`, vulnerability = 45.
- Vì công thức chỉ dùng band, thay đổi nhỏ trong cùng band không đổi score.

Sensitivity đã kiểm tra: ngày 01/01 tăng IMERG từ `1.289` lên `12 mm/day` làm score tăng từ `38.89` lên `62.26`; Rain Exposure tăng từ 50 lên 100. Monotonicity và boundary tests PASS.

Các stage trên ngày 01/01:

| Stage | Score | Level |
|---|---:|---|
| preparation | 33.58 | MODERATE |
| evaporation | 38.89 | MODERATE |
| crystallization | 46.33 | MODERATE |
| harvesting | 42.08 | MODERATE |

Missing required input trả `INSUFFICIENT_DATA`; giá trị âm mưa/ET bị reject; recommendations đều có điều kiện và nêu rõ không bảo đảm tránh thiệt hại.

## 5. Các phát hiện

### HIGH

1. **Phạm vi dữ liệu NASA thực tế chưa đủ production năm 2025 cho IMERG/GLDAS.** Output đang chứng minh 7 ngày, không chứng minh 365 ngày. Không được suy rộng risk engine thành đánh giá cả năm.
2. **DS-05 chưa được hiệu chuẩn khoa học/nghiệp vụ.** Threshold, weight, stage vulnerability và confidence 85 là giả định MVP. Chưa có nhãn thiệt hại, nhật ký ruộng, số đo độ mặn hoặc đánh giá chuyên gia.

### MEDIUM

1. Data confidence DS-05 vẫn là hằng số 85, nhưng hiện đã ghi rõ trong metadata là `MVP_DATA_QUALITY_SCORE_NOT_PROBABILITY`; không phải confidence thống kê.
2. DS-05 chọn max mưa giữa POWER/IMERG/GLDAS là chính sách bảo thủ chưa được validation, dù không cộng mưa.
3. Bản ghi CSV DS-05 serialize list/dict thành string; JSON report giữ cấu trúc tốt hơn cho REST API.

### LOW

1. Các quality report chưa đồng nhất hoàn toàn về checksum, retrieval timestamp và schema version.
2. Tests hiện kiểm tra logic tốt nhưng phần lớn integration/network tests vẫn là mock hoặc phụ thuộc dữ liệu cache.

## 6. Kết quả test và kiểm tra output

Đã chạy:

```text
37 passed in 2.03s
```

Đã kiểm tra output thực tế:

- DS-01: 365 rows, 0 duplicate, 0 missing theo metadata.
- DS-02: 7 ngày, 25 cells/ngày, 0 duplicate/missing theo metadata.
- DS-03: 56 granules, 7 ngày, 1 cell, 0 duplicate/missing theo report.
- DS-04: 7 rows, 7 unique dates, 0 null.
- DS-05: 7 rows, status `OK`, score reproducible.

Regression tests mới: kiểm tra grid-cell pair counting với grid không hình chữ nhật và kiểm tra semantics của data confidence.

Không tải lại dữ liệu NASA lớn và không tạo dữ liệu giả trong audit.

## 7. Acceptance checklist

| Tiêu chí | Kết quả |
|---|---|
| Đọc được nguồn NASA | PASS cho các output cache hiện có |
| Đơn vị và conversion được ghi rõ | PASS |
| Missing/duplicate validation | PASS trên 7-day outputs; chưa đủ full-year |
| Integration theo ngày | PASS |
| Không cộng các nguồn mưa | PASS |
| Risk score tái lập | PASS |
| Missing risk input không thành LOW | PASS |
| Recommendations theo stage | PASS |
| Forecast | NOT CLAIMED |
| Scientific calibration | NOT VERIFIED |
| Production-ready risk model | FAIL / NOT READY |

## 8. Kết luận và bước tiếp theo

- **DS hoàn chỉnh cho Historical MVP?** Có, trong phạm vi 7 ngày đã có dữ liệu thật và rule engine minh bạch.
- **Đủ cơ sở để Risk Score đáng tin cậy như quyết định nghiệp vụ?** Chưa. Score hiện là chỉ báo MVP, không phải xác suất thiệt hại hay khuyến cáo khoa học đã hiệu chuẩn.
- **Có thể đánh dấu toàn bộ DS DONE?** Chỉ có thể đánh dấu DONE ở mức code/Historical MVP; không được gọi production-ready hoặc full-year validated.
- **Cần làm tiếp:** tải/xác minh toàn bộ khoảng thời gian yêu cầu cho IMERG/GLDAS; sửa đếm cell theo cặp tọa độ; truyền quality metadata vào confidence; thu thập nhật ký mưa/độ mặn/thiệt hại và review ngưỡng với chuyên gia nghề muối; nếu cần forecast thì tích hợp nguồn dự báo riêng và tách forecast assessment khỏi historical assessment.

Không có thay đổi Backend, Frontend, Database hoặc API. Không commit/push.
