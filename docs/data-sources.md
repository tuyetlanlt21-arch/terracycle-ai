# TerraCycle AI data sources

## An Giang pilot point

The pilot uses the Long Xuyên hydrological station coordinate `10.383333, 105.450000` (10°23′N, 105°27′E), documented in the Mekong Delta station table in the [RVO water strategy report](https://projects.rvo.nl/sites/default/files/rvo_website_content/opendata/iati/PVW/PVW4A20035_A.pdf). This is one pilot point for Long Xuyên and is not representative of the entire An Giang province.

## NASA POWER
NASA POWER Daily Point API is used for historical T2M, T2M_MAX, PRECTOTCORR, RH2M, ALLSKY_SFC_SW_DWN and WS2M. It is climate context, not a 48-hour forecast.

The packaged Long Xuyen pilot artifact at `data/processed/power/long_xuyen_pilot/` is an authentic API retrieval for 10.383333, 105.450000 covering 2020-01-01 through 2026-10-31. Its metadata contains the exact NASA POWER request URL and quality coverage. The daily CSV includes T2M, T2M_MIN, T2M_MAX, PRECTOTCORR, RH2M, WS2M, ALLSKY_SFC_SW_DWN and PS, which are used for the historical growing-window assessment. The bundle is not reused for other coordinates; they need their own location-matched retrieval.

## ISRIC SoilGrids
The SoilGrids v2 REST adapter uses `https://rest.isric.org/soilgrids/v2.0/properties/query`. SoilGrids values are predictions with official scale factors; failures produce an explicit unavailable profile. Soil salinity EC and irrigation-water EC are never derived from SoilGrids.

## FAO ECOCROP
The crop catalog includes sourced crop-level temperature, annual rainfall, soil-pH and growth-duration ranges from FAO ECOCROP records. These are general crop envelopes, not local field observations; annual rainfall is context only and is not compared directly with a seasonal total. Salinity tolerance, nitrogen fixation and rotation compatibility are separately sourced and retain explicit gaps where evidence is unavailable.

## FAO irrigation-water quality

The [FAO irrigation-water quality guidance](https://www.fao.org/4/t0234e/T0234E01.htm) provides general ECw screening bands: below 0.7 dS/m has no restriction, 0.7–3.0 dS/m has slight-to-moderate restrictions, and above 3.0 dS/m has severe restrictions. The middle band remains `UNKNOWN` unless field-specific management evidence is available; these broad bands do not replace local water testing or quantify water supply.
## Rice, soybean and mung-bean water references

Rice and soybean stage coefficients are reference values from [FAO crop-water guidance](https://www.fao.org/4/s2022e/s2022e07.htm) and [FAO Irrigation and Drainage Paper 56](https://www.fao.org/4/X0490E/x0490e0b.htm). They support indicative ETc calculations and do not establish local variety performance, irrigation supply, or rainfall suitability.

Mung bean (`Vigna radiata`) duration and qualitative rainfall notes come from [FAO ECOCROP](https://ecocrop.apps.fao.org/ecocrop/srv/en/cropView?id=2150). Its displayed stage Kc values and 193.8 mm consumptive-water result are from a single 65-day MI-6 lysimeter study in Sri Lanka ([study PDF](https://ours.ou.ac.lk/wp-content/uploads/2017/05/ENG-08-Formatted-C.pdf)). They are tagged out-of-region and are not used for PASS/FAIL. The crop catalog therefore keeps mung-bean seasonal water requirement and drought sensitivity unverified.

The UI collects planned planting and harvest dates. The backend sums historical NASA POWER daily precipitation across those inclusive dates. The rainfall total is reported as historical evidence only; annual ECOCROP ranges are never compared to it, and precipitation is not treated as ETc, effective rainfall, or a forecast.
