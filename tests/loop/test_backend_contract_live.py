"""The VastBackend conformance case against the real vast.ai API.

Skipped unless STENO_LIVE_VAST=1 is set. This wave's build agent does NOT run
this file: read-only quote() was exercised once by hand instead (see the
wave's report). Kept here so a future session can opt in deliberately, never
by accident (a bare `pytest tests/loop` never touches vast.ai).

Only quote() (read-only: search_offers, show_user) is exercised live even
when enabled; provision/destroy against the real API are deliberately left
out of this automated file so no CI or casual run can ever rent or destroy a
real instance. A human wanting the full lifecycle against a real box should
do that by hand, watching it, per this repo's cost-safety conventions.
"""

from __future__ import annotations

import os

import pytest

from steno.loop.compute import ComputeRequest

pytestmark = pytest.mark.live

_LIVE = os.environ.get("STENO_LIVE_VAST") == "1"


@pytest.mark.skipif(not _LIVE, reason="set STENO_LIVE_VAST=1 to run real vast.ai API calls")
def test_vast_quote_against_the_real_api():
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend()
    request = ComputeRequest(gpu_count=1, gpu_memory_gb_min=24, max_hourly_usd=0.5)
    offers = backend.quote(request)
    assert isinstance(offers, list)


@pytest.mark.skipif(not _LIVE, reason="set STENO_LIVE_VAST=1 to run real vast.ai API calls")
def test_vast_credit_lookup_against_the_real_api():
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend()
    credit = backend.get_available_credit()
    assert isinstance(credit, float)
