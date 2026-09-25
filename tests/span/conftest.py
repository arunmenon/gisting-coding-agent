import json
import os

import pytest

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "claude_code_captures.jsonl")


@pytest.fixture
def fixture_raws():
    with open(FIXTURE_PATH) as handle:
        return [json.loads(line) for line in handle]
