"""Hygiene checks on the fixture and on this package's own source (W-17, W-18).

These are cheap, repo-wide scans, not adapter behaviour tests: they exist so a future edit to
the fixture (or to any authored .py/.md file under steno/span or tests/span) cannot silently
reintroduce a source identifier or an em dash without a test failing."""
import json
import os
import re

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "claude_code_captures.jsonl")
SOURCE_CAPTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "experiments", "journeys", "j1-e0-tap", "results", "requests.jsonl",
)

UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
REQUEST_ID_RE = re.compile(r'"id"\s*:\s*"([0-9a-fA-F]{12})"')
# Any hex-looking string of 16+ characters that contains at least one a-f letter. Requiring a
# letter (not just "16+ hex-valid characters") deliberately excludes plain long decimal numbers
# (timestamps, counters) that would otherwise match `[0-9a-f]{16,}` purely because 0-9 are valid
# hex digits too; those are not identifiers, and treating every long integer in the capture as
# one would make this check fail on ordinary numeric noise instead of catching real identifiers
# such as the 64-character device_id inside metadata.user_id or a 16-character tool-use id.
HEX16_WITH_LETTER_RE = re.compile(r"\b(?=[0-9a-fA-F]{16,}\b)[0-9a-fA-F]*[a-fA-F][0-9a-fA-F]*\b")
EM_DASH = chr(0x2014)  # written via chr() so this file itself never contains the literal character


def _collect_source_ids(source_path):
    """Every UUID-shaped string, every 16+ character hex-with-a-letter token (device ids,
    tool-use ids, signatures), and every top-level capture "id" in the source capture. This is
    deliberately broad: it is meant to catch anything identifier-shaped, not just the specific
    fields a sanitiser script remembered to handle (W-17's original failure mode)."""
    with open(source_path) as handle:
        text = handle.read()
    return set(UUID_RE.findall(text)) | set(HEX16_WITH_LETTER_RE.findall(text)) | set(REQUEST_ID_RE.findall(text))


def test_fixture_contains_no_identifier_from_the_source_capture():
    if not os.path.isfile(SOURCE_CAPTURE_PATH):
        import pytest
        pytest.skip("source capture not present locally: %s" % SOURCE_CAPTURE_PATH)

    source_ids = _collect_source_ids(SOURCE_CAPTURE_PATH)
    assert source_ids, "sanity check: the source capture should contain at least one id to compare against"

    with open(FIXTURE_PATH) as handle:
        fixture_text = handle.read()

    leaked = sorted(source_id for source_id in source_ids if source_id in fixture_text)
    assert not leaked, "source capture identifier(s) leaked into the sanitised fixture: %s" % leaked


def test_fixture_contains_no_metadata_device_id_from_the_source_capture():
    """Regression for the specific leak Codex found: metadata.user_id's device_id is a 64-char
    hex string, not a UUID, so the UUID-only check in the previous round missed it. Checked
    directly (not only via the broad hex scan above) so this failure mode has its own name."""
    if not os.path.isfile(SOURCE_CAPTURE_PATH):
        import pytest
        pytest.skip("source capture not present locally: %s" % SOURCE_CAPTURE_PATH)

    device_ids = set()
    with open(SOURCE_CAPTURE_PATH) as handle:
        for line in handle:
            record = json.loads(line)
            try:
                metadata = json.loads(record["request"]["metadata"]["user_id"])
            except Exception:
                continue
            device_id = metadata.get("device_id")
            if device_id:
                device_ids.add(device_id)

    assert device_ids, "sanity check: the source capture should contain at least one device_id"

    with open(FIXTURE_PATH) as handle:
        fixture_text = handle.read()

    leaked = sorted(device_id for device_id in device_ids if device_id in fixture_text)
    assert not leaked, "source device_id(s) leaked into the sanitised fixture: %s" % leaked


def test_fixture_session_ids_are_synthetic_and_relationships_are_preserved():
    """The fixture must still have multiple sessions with more than one call each (the
    relationship the source capture had), just under synthetic ids."""
    sessions = {}
    with open(FIXTURE_PATH) as handle:
        for line in handle:
            record = json.loads(line)
            try:
                session_id = json.loads(record["request"]["metadata"]["user_id"])["session_id"]
            except Exception:
                session_id = None
            sessions.setdefault(session_id, 0)
            sessions[session_id] += 1

    assert len(sessions) >= 2
    assert all(count >= 1 for count in sessions.values())
    assert any(count > 1 for count in sessions.values()), "at least one synthetic session should keep multiple turns"
    for session_id in sessions:
        assert UUID_RE.fullmatch(session_id), "session id %r is not a well-formed (synthetic) uuid" % session_id


def _iter_authored_files():
    package_root = os.path.join(os.path.dirname(__file__), "..", "..", "steno", "span")
    tests_root = os.path.dirname(__file__)
    for root_dir in (package_root, tests_root):
        for dirpath, _dirnames, filenames in os.walk(root_dir):
            if "__pycache__" in dirpath:
                continue
            for filename in filenames:
                if filename.endswith((".py", ".md")):
                    yield os.path.join(dirpath, filename)


def test_no_em_dash_in_authored_python_or_markdown_files():
    offenders = []
    for path in _iter_authored_files():
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if EM_DASH in text:
            offenders.append(path)
    assert not offenders, "em dash (U+2014) found in authored file(s): %s" % offenders


def test_no_em_dash_in_the_fixture():
    with open(FIXTURE_PATH, encoding="utf-8") as handle:
        text = handle.read()
    assert EM_DASH not in text
