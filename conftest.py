"""Keep pytest temporary files inside the writable repository workspace on Windows."""
from pathlib import Path
import tempfile

def pytest_configure(config):
    root = Path(__file__).resolve().parent / ".pytest-runtime"
    root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(root)
    config.option.basetemp = str(root / "basetemp")
