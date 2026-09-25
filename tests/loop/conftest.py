import sys
from pathlib import Path

# Make the repository root importable as `steno` without requiring installation.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    # Registers the `live` marker used by test_backend_contract_live.py's
    # VastBackend case (wave 2, build order step 6, point 7), which makes
    # real vast.ai API calls and is skipped unless STENO_LIVE_VAST=1 is set.
    config.addinivalue_line("markers", "live: makes real network/provider calls; skipped by default")
