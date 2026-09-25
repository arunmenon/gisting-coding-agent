"""X-15: BenchmarkExecutor/ServeExecutor must validate marker order, invocation boundaries (one
chain_start), the eight expected B6 combinations, duplicates, and completion markers before
reporting success -- not just that some success-shaped markers exist somewhere in the file."""
from steno.loop.executors.j11 import BENCHMARK, SERVE
from steno.loop.executors.markers import parse_state_text

GOOD_HEADER = "2026-01-01T00:00:00Z conn_chain_start deadline=3h\n"
CKPT_BUILT = "2026-01-01T00:01:00Z ckpt_built (ok)\n"
SERVER_UP = "2026-01-01T00:02:00Z server_up len=40960 seqs=256 util=0.92 batched=16384\n"


def _b6_line(ts, conn, arm, c, max_running=100.0):
    return "%s B6 conn=%d arm=%s c=%d rpm=50.0 max_running=%s kv_max=0.9 preempt=0.0 ok=100 err=0\n" % (ts, conn, arm, c, max_running)


ALL_EIGHT = "".join(
    _b6_line("2026-01-01T00:%02d:00Z" % (10 + i), conn, arm, c)
    for i, (conn, arm, c) in enumerate(
        (conn, arm, c) for conn in (100, 512) for arm in ("full", "gist8") for c in (128, 256)
    )
)


def _good_benchmark_text():
    return (GOOD_HEADER + CKPT_BUILT + SERVER_UP + ALL_EIGHT
            + "2026-01-01T00:30:00Z B6_done\n2026-01-01T00:30:01Z BENCH_DONE\n")


def test_benchmark_accepts_complete_well_ordered_run():
    markers = parse_state_text(_good_benchmark_text())
    result = BENCHMARK.result_from_markers(markers)
    assert result.ok is True, result.detail


def test_benchmark_rejects_missing_chain_start():
    text = _good_benchmark_text().replace(GOOD_HEADER, "")
    markers = parse_state_text(text)
    result = BENCHMARK.result_from_markers(markers)
    assert result.ok is False
    assert "chain_start" in result.detail


def test_benchmark_rejects_two_chain_starts():
    text = GOOD_HEADER + _good_benchmark_text()
    markers = parse_state_text(text)
    result = BENCHMARK.result_from_markers(markers)
    assert result.ok is False
    assert "chain_start" in result.detail


def test_benchmark_rejects_too_few_combinations():
    text = GOOD_HEADER + CKPT_BUILT + SERVER_UP + _b6_line("2026-01-01T00:10:00Z", 100, "full", 128)
    text += "2026-01-01T00:30:00Z B6_done\n2026-01-01T00:30:01Z BENCH_DONE\n"
    markers = parse_state_text(text)
    result = BENCHMARK.result_from_markers(markers)
    assert result.ok is False
    assert "missing" in result.detail


def test_benchmark_rejects_duplicate_combination():
    text = _good_benchmark_text() + _b6_line("2026-01-01T00:29:00Z", 100, "full", 128)
    markers = parse_state_text(text)
    result = BENCHMARK.result_from_markers(markers)
    assert result.ok is False
    assert "duplicate" in result.detail.lower()


def test_benchmark_rejects_bench_done_before_a_result():
    # BENCH_DONE appears before the eight results are all in: an incomplete run masquerading as done.
    lines = _good_benchmark_text().splitlines(keepends=True)
    bench_done_line = next(l for l in lines if "BENCH_DONE" in l)
    lines.remove(bench_done_line)
    lines.insert(3, bench_done_line)  # right after server_up, before any B6 result
    markers = parse_state_text("".join(lines))
    result = BENCHMARK.result_from_markers(markers)
    assert result.ok is False


def test_benchmark_rejects_missing_b6_done():
    text = _good_benchmark_text().replace("2026-01-01T00:30:00Z B6_done\n", "")
    markers = parse_state_text(text)
    result = BENCHMARK.result_from_markers(markers)
    assert result.ok is False
    assert "B6_done" in result.detail


def test_serve_rejects_server_up_before_ckpt_built():
    text = GOOD_HEADER + SERVER_UP + CKPT_BUILT
    markers = parse_state_text(text)
    result = SERVE.result_from_markers(markers)
    assert result.ok is False
    assert "out-of-order" in result.detail


def test_serve_accepts_well_ordered_pair():
    text = GOOD_HEADER + CKPT_BUILT + SERVER_UP
    markers = parse_state_text(text)
    result = SERVE.result_from_markers(markers)
    assert result.ok is True


def test_serve_rejects_missing_chain_start():
    text = CKPT_BUILT + SERVER_UP
    markers = parse_state_text(text)
    result = SERVE.result_from_markers(markers)
    assert result.ok is False
    assert "chain_start" in result.detail
