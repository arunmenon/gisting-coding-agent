Verification: 30 tests passed; full suite blocked by read-only temporary-file restrictions. Lifecycle and lock reproductions used in-memory mocks.

W-2: closed. Inspection exceptions now reach cleanup in both reproductions (`steno/loop/runner.py:234`, `steno/loop/runner.py:273`).
W-6: partly closed. Pair-content changes alter identity; concurrent ownership remains reproducible (`steno/loop/spec.py:125`, `steno/loop/state.py:130`).
W-8: partly closed. Numeric gates work, but `invariance: all_calls` and NaN thresholds still permit success (`steno/loop/runner.py:292`).
W-13: closed. Frozen-map reproductions reject changed fixed instructions and arbitrary unresolved text (`steno/span/analysis.py:261`, `steno/span/analysis.py:273`).
W-14: partly closed. User/assistant extras survive; inline system-message `name` and `cache_control` still disappear (`steno/span/adapters/claude_code.py:177`).
W-15: closed. Signature/error preservation and truncated-stream detection reproductions pass (`steno/span/adapters/claude_code.py:324`).
W-16: partly closed. Rendering hashes required and empty collections accepted; enforcement explicitly deferred (`steno/span/manifest.py:176`, `steno/span/README.md:46`).
W-17: closed. Source-identifier and device-ID comparisons pass (`tests/span/test_fixture_hygiene.py:41`, `tests/span/fixtures/claude_code_captures.jsonl:1`).
N-1: closed. Unresolved frozen-map lines reject arbitrary replacement instructions (`steno/span/analysis.py:273`).
N-2: partly closed. Atomic creation added, but a contender reclaims the empty lock before PID publication; reproduction accepts both owners (`steno/loop/state.py:130`, `steno/loop/state.py:139`).

Commit wave 1: no, because concurrent ownership, ignored gates, and canonical system-message data loss remain.
