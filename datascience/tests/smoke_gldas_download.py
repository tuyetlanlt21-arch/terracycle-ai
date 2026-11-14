"""Real GLDAS smoke test. Run: python -m datascience.tests.smoke_gldas_download"""
from __future__ import annotations
import logging, sys, traceback
from pathlib import Path
from datascience import gldas

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        logging.info("stage=Earthdata login START"); gldas.login(); logging.info("stage=Earthdata login PASS")
        logging.info("stage=CMR discovery START"); granules = gldas.discover("2025-01-01", "2025-01-01"); logging.info("stage=CMR discovery PASS granules=%d", len(granules))
        logging.info("stage=download START"); files = gldas.download(granules[:1], Path("data/raw/gldas/smoke")); logging.info("stage=download PASS files=%d", len(files))
        logging.info("stage=NetCDF validation START"); frame = gldas.extract_file(files[0]); logging.info("stage=NetCDF validation PASS rows=%d", len(frame)); print("PASS: GLDAS smoke test", files[0]); return 0
    except Exception as exc:
        logging.error("stage=GLDAS smoke FAIL type=%s error=%s", type(exc).__name__, str(exc)[:300]); traceback.print_exc(); print(f"FAIL: {type(exc).__name__}: {str(exc)[:300]}"); return 1
if __name__ == "__main__": sys.exit(main())
