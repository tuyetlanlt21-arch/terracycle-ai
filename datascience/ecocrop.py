"""Normalize an operator-supplied FAO ECOCROP export without inventing thresholds."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

FIELDS = ["crop_id","crop_name","temperature_min_c","temperature_max_c","rainfall_min_mm","rainfall_max_mm","soil_ph_min","soil_ph_max","growth_duration_days","source_reference"]

def normalize_csv(source: Path) -> list[dict]:
    with source.open(encoding="utf-8-sig", newline="") as fh:
        rows=[]
        for raw in csv.DictReader(fh):
            row={k: raw.get(k) or None for k in FIELDS}; row["source_reference"] = row["source_reference"] or "https://ecocrop.apps.fao.org/ecocrop/srv/en/home"; rows.append(row)
        return rows

def run(source: Path | None, output: Path) -> dict:
    crops = normalize_csv(source) if source and source.exists() else []
    result={"source":"FAO ECOCROP via GAEZ / ECOCROP portal","source_reference":"https://www.fao.org/geospatial/data-and-tools/data-portals/ecocrop/en","status":"loaded" if crops else "unavailable_no_export_supplied","records":crops,"notes":["ECOCROP is a requirements reference, not a complete rotation model.","Salinity tolerance, nitrogen fixation and rotation compatibility require separate traceable references and are not inferred here.","No crop thresholds are fabricated."]}
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2), encoding="utf-8"); return result

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--source",type=Path); p.add_argument("--output",type=Path,default=Path("data/reference/crop_catalog.json")); a=p.parse_args(); run(a.source,a.output)
