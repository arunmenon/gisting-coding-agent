import json

from steno.loop.executors.j11 import BENCHMARK, DEFAULT_STATE_PATH, SERVE, SPAN, SpanReportExecutor
from steno.loop.executors.markers import parse_state_file
from steno.loop.runner import _evaluate_gate
from steno.loop.spec import load_spec

SPEC_PATH = "steno/loop/examples/j11-conn.json"


def test_spec_validates():
    spec = load_spec(SPEC_PATH)
    spec.validate()  # must not raise
    assert spec.stages == ["span", "serve", "benchmark"]
    # X-11: compute uses the neutral request/backend_options shape, no provider vocabulary.
    assert spec.compute["backend"] == "vast"
    assert "gpu_query" not in spec.compute
    assert spec.compute["request"]["gpu_families"] == ["h200"]
    assert spec.compute["backend_options"] == {}


def test_j11_replay_produces_recorded_benchmark_metrics():
    markers = parse_state_file(DEFAULT_STATE_PATH)

    serve_result = SERVE.result_from_markers(markers)
    assert serve_result.ok is True
    assert serve_result.kind == "ok"
    assert serve_result.metrics["max_num_seqs"] == 256.0

    benchmark_result = BENCHMARK.result_from_markers(markers)
    assert benchmark_result.ok is True
    assert benchmark_result.kind == "ok"

    resident_counts = {
        value for key, value in benchmark_result.metrics.items() if key.startswith("max_running__")
    }
    assert resident_counts == {100.0, 123.0, 126.0, 128.0, 137.0}
    assert benchmark_result.metrics["max_running_max"] == 137.0
    assert benchmark_result.metrics["b6_result_count"] == 8.0

    spec = load_spec(SPEC_PATH)
    gate_passed, gate_detail = _evaluate_gate("benchmark", spec.gates["benchmark"], benchmark_result.metrics)
    assert gate_passed is True, gate_detail


def test_span_fails_closed_without_a_provenance_report_but_reports_checkpoint_share():
    # X-10: no provenance-bearing span report exists for J11 by default, so the stage must fail
    # rather than pass a checkpoint-composition number off as the measured `share`.
    result = SPAN.report()
    assert result.ok is False
    assert result.kind == "task_failure"
    assert "share" not in result.metrics
    assert 0.0 < result.metrics["checkpoint_share"] <= 1.0
    assert result.metrics["gist_ratio"] == 8.0


def test_span_gate_on_checkpoint_share_passes_when_span_stage_ok(tmp_path):
    # The spec's gate targets checkpoint_share_min (what is actually evidenced by default); when
    # the span stage is ok (a provenance report is supplied), that gate must evaluate normally.
    report_path = tmp_path / "span_report.json"
    report_path.write_text(json.dumps({
        "schema_version": "steno-span-report/v2",
        "pass": True,
        "cohorts": [{"parts": [{"fixed_char_count": 90, "total_char_count": 100}]}],
    }))
    executor = SpanReportExecutor(span_report_path=str(report_path))
    result = executor.report()
    assert result.ok is True
    assert result.metrics["share"] == 0.9

    spec = load_spec(SPEC_PATH)
    gate_passed, gate_detail = _evaluate_gate("span", spec.gates["span"], result.metrics)
    assert gate_passed is True, gate_detail


def test_span_report_rejects_non_passing_report(tmp_path):
    report_path = tmp_path / "span_report.json"
    report_path.write_text(json.dumps({"schema_version": "steno-span-report/v2", "pass": False, "cohorts": []}))
    executor = SpanReportExecutor(span_report_path=str(report_path))
    result = executor.report()
    assert result.ok is False
    assert "share" not in result.metrics
