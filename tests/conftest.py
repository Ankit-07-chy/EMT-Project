import os
import sys
import tempfile
from pathlib import Path

# Every test writes into a throw-away data / models / report tree (see TDR_HOME in
# src/config.py), never into the project's real results.
os.environ.setdefault("TDR_HOME", tempfile.mkdtemp(prefix="tdr_pytest_"))

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
