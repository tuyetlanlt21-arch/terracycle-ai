# TerraCycle AI data sources

## An Giang pilot point

The pilot uses the Long Xuyên hydrological station coordinate `10.383333, 105.450000` (10°23′N, 105°27′E), documented in the Mekong Delta station table in the [RVO water strategy report](https://projects.rvo.nl/sites/default/files/rvo_website_content/opendata/iati/PVW/PVW4A20035_A.pdf). This is one pilot point for Long Xuyên and is not representative of the entire An Giang province.

## NASA POWER
NASA POWER Daily Point API is used for historical T2M, T2M_MAX, PRECTOTCORR, RH2M, ALLSKY_SFC_SW_DWN and WS2M. It is climate context, not a 48-hour forecast.

## ISRIC SoilGrids
The SoilGrids v2 REST adapter uses `https://rest.isric.org/soilgrids/v2.0/properties/query`. SoilGrids values are predictions with official scale factors; failures produce an explicit unavailable profile. Soil salinity EC and irrigation-water EC are never derived from SoilGrids.

## FAO ECOCROP
The catalog adapter references the FAO ECOCROP/GAEZ portal. No crop thresholds are included until a verified export or record is supplied. Salinity tolerance, nitrogen fixation and rotation compatibility require separate sources.
