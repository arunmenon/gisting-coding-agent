# Third recheck: Steno build wave 1, final items

Read-only. Emit to stdout. Very brief.

Your second recheck (`experiments/journeys/reviews/steno-build-wave1/codex-recheck2.md`) left W-6/N-2 (run lock race), W-8 (gates not failing closed for `invariance: all_calls` and NaN thresholds) and W-14 (inline system-message `name` and `cache_control` dropped) partly closed. Fixes: the lock is now an fcntl.flock advisory lock held for the process lifetime (`steno/loop/state.py`); `_evaluate_gate` in `steno/loop/runner.py` now fails closed on every declared field; `_system_parts` in `steno/span/adapters/claude_code.py` records inline system-message fields. W-16 remains deliberately partial.

For W-6, N-2, W-8, W-14, re-run your reproductions and give one line each: `<id>: closed | partly closed | open | regressed. <evidence>`. List any new blocking or major defect. End with exactly: `Commit wave 1: yes` or `Commit wave 1: no, because ...`.
