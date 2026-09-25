from steno.loop.executors.markers import parse_state_text

SUCCESS_TEXT = """
2026-09-15T08:43:49Z conn_chain_start deadline=3h cfg=40960,256,0.92,16384 concs='128 256' conns='100 512' dur=180s
2026-09-15T08:43:52Z download_attempt_1
2026-09-15T08:51:08Z ckpt_built (wrote 2171 gist rows into /root/qwen3.8-27b-gist/model-00003-of-00018.safetensors)
2026-09-15T08:53:10Z server_up len=40960 seqs=256 util=0.92 batched=16384
2026-09-15T08:58:00Z B6 conn=100 arm=full c=128 rpm=59.7 max_running=100.0 kv_max=0.955 preempt=0.0 ok=179 err=0
2026-09-15T09:33:29Z B6_done
2026-09-15T09:33:29Z BENCH_DONE
"""

FAILURE_TEXT = """
2026-09-15T08:43:49Z conn_chain_start deadline=3h
2026-09-15T08:43:52Z download_attempt_1
2026-09-15T08:44:00Z download_FAILED
"""

PARTIAL_TEXT = """
2026-09-15T08:43:49Z conn_chain_start deadline=3h
2026-09-15T08:51:08Z ckpt_built (wrote rows)
2026-09-15T08:53:10Z server_up len=40960 seqs=256 util=0.92 batched=16384
2026-09-15T08:58:00Z B6 conn=100 arm=full c=128 rpm=59.7 max_running=100.0 kv_max=0.955 preempt=0.0 ok=179 err=0
2026-09-15T09:03:19Z B6_FAILED conn=100 arm=full c=256
2026-09-15T09:33:29Z DEADLINE during B6
"""


def test_parses_success_markers():
    markers = parse_state_text(SUCCESS_TEXT)
    kinds = [m.kind for m in markers]
    assert kinds == ["chain_start", "download_attempt", "ckpt_built", "server_up", "b6_result", "b6_done", "bench_done"]

    b6 = next(m for m in markers if m.kind == "b6_result")
    assert b6.fields == {
        "conn": 100, "arm": "full", "c": 128, "rpm": 59.7, "max_running": 100.0,
        "kv_max": 0.955, "preempt": 0.0, "ok": 179, "err": 0,
    }

    server_up = next(m for m in markers if m.kind == "server_up")
    assert server_up.fields == {"max_model_len": 40960, "max_num_seqs": 256, "gpu_util": 0.92, "max_batched": 16384}

    ckpt_built = next(m for m in markers if m.kind == "ckpt_built")
    assert "gist rows" in ckpt_built.fields["detail"]


def test_parses_failure_marker():
    markers = parse_state_text(FAILURE_TEXT)
    kinds = [m.kind for m in markers]
    assert kinds == ["chain_start", "download_attempt", "infra_failure"]
    failure = markers[-1]
    assert failure.fields["reason"] == "download_FAILED"


def test_parses_partial_state_with_b6_failure_and_deadline():
    markers = parse_state_text(PARTIAL_TEXT)
    kinds = [m.kind for m in markers]
    assert kinds == ["chain_start", "ckpt_built", "server_up", "b6_result", "b6_failed", "infra_failure"]

    b6_failed = next(m for m in markers if m.kind == "b6_failed")
    assert b6_failed.fields == {"conn": 100, "arm": "full", "c": 256}

    deadline = next(m for m in markers if m.kind == "infra_failure")
    assert deadline.fields["reason"] == "deadline_exceeded"


def test_unrecognised_line_is_kept_as_unknown():
    markers = parse_state_text("2026-09-15T08:43:49Z some_future_marker_type foo=bar\n")
    assert len(markers) == 1
    assert markers[0].kind == "unknown"
    assert "some_future_marker_type" in markers[0].raw


def test_blank_lines_skipped():
    markers = parse_state_text("\n\n2026-09-15T08:43:49Z B6_done\n\n")
    assert len(markers) == 1
    assert markers[0].kind == "b6_done"
