"""Keep pytest temporary files inside the writable repository workspace on Windows."""
from pathlib import Path
import tempfile

def pytest_configure(config):
    root = Path(__file__).resolve().parent / ".pytest-runs"
    root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(root)
    # Use a fresh run directory: the managed Windows workspace can deny
    # pytest's recursive cleanup of a reused basetemp after interrupted runs.
    config.option.basetemp = tempfile.mkdtemp(prefix="run-", dir=str(root))
