import sys
from pathlib import Path

# Make the repository root importable as `steno` without requiring installation, matching
# tests/loop/conftest.py and tests/span/conftest.py's pattern.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
