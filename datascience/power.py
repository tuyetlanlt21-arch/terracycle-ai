"""NASA POWER daily CSV ingestion helpers. Offline processing; this module does not fetch an API automatically."""
import csv
from pathlib import Path

MISSING = {-999.0, -9999.0}
PARAMETERS = ("PRECTOTCORR", "T2M", "RH2M", "ALLSKY_SFC_SW_DWN", "WS2M")

def parse_power_daily_csv(path: str | Path) -> list[dict]:
    """Accept NASA POWER daily CSV, including its leading -BEGIN HEADER- block."""
    with open(path, encoding="utf-8-sig", newline="") as source:
        lines = source.readlines()
    header_index = next((i for i, line in enumerate(lines) if line.strip().startswith("YEAR,MO,DY")), None)
    if header_index is None:
        raise ValueError("No NASA POWER daily CSV header found (YEAR,MO,DY)")
    result = []
    for row in csv.DictReader(lines[header_index:]):
        if not row.get("YEAR"):
            continue
        normalized = {"date": f'{int(row["YEAR"]):04d}-{int(row["MO"]):02d}-{int(row["DY"]):02d}'}
        for parameter in PARAMETERS:
            raw = row.get(parameter)
            value = None if raw in (None, "") else float(raw)
            normalized[parameter] = None if value in MISSING else value
        result.append(normalized)
    return result
