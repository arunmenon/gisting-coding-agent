"""Stage executors for Journey 11 (`experiments/journeys/j11-conn`), the smallest end-to-end
journey, migrated onto the run loop's `stage_executors` seam per steno-design.md build order
step B7. Wave 2 is dry-run only: these executors wrap the *existing* on-box script
(`experiments/vast/conn_chain.sh`) rather than rewriting its logic. Each one declares:

  - `required_inputs`: local files that must exist before this stage could run for real.
  - `remote_command`: the command this stage would run on the provisioned box, copy-pasted from
    the existing script rather than re-derived, so it cannot silently drift from what the box
    actually runs.
  - `expected_artifacts`: files and STATE markers a completed run leaves behind.
  - `result_from_markers(markers)`: turns the chain script's STATE markers (`markers.py`) into a
    typed `steno.loop.backend.ExecuteResult`, with metrics on success.

J11 is a serving/benchmark journey: it has no training data and nothing resembling the
"invariance report" span analysis is normally gating. `steno.loop.spec` (owned by another wave's
change and not modified here) still requires `span` in the same spec as `serve`/`benchmark`
(`STAGES_REQUIRING_SPAN`), and validates it fail-closed. Rather than weaken that validation,
`SpanReportExecutor` below is a real stage that reports two distinct things under two distinct
metric names, per the Codex wave-2 review's X-10 finding:

  - `checkpoint_share`: the static/compressible token fraction of the checkpoint identity file
    J11 actually served (`experiments/gist/out_r8v2/segments.json`). This is checkpoint
    *composition*, not a measured invariance result -- it says "this is how the checkpoint was
    built," nothing about whether live traffic actually stayed within that structure.
  - `share`: the measured static-span share, which only exists if a provenance-bearing
    `steno.span.cli report`-shaped file (schema `steno-span-report/...`, `pass: true`) is found at
    `span_report_path`. No such report exists for J11 today (it is a serving-only journey with no
    captures collected through the tap), so by default this executor **fails closed**: `report()`
    returns `ok=False` with `checkpoint_share` in `metrics` but no `share` key at all, rather than
    ever substituting one for the other. See the README's "span for a serving-only journey"
    section for the wave-3 path to a real report.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..backend import ExecuteResult
from .markers import Marker

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _repo_path(*parts: str) -> str:
    return os.path.join(REPO_ROOT, *parts)


# The checkpoint identity file conn_chain.sh actually serves: `rm -rf /root/gist/out &&
# cp -r /root/gist/out_r8v2 /root/gist/out`, an 8:1 ratio gist checkpoint.
R8V2_SEGMENTS_PATH = _repo_path("experiments", "gist", "out_r8v2", "segments.json")
CORPUS_FULL_PATH = _repo_path("experiments", "bench", "corpus", "reqs_full.jsonl")
CORPUS_GIST8_PATH = _repo_path("experiments", "bench", "corpus", "reqs_gist8.jsonl")
DEFAULT_STATE_PATH = _repo_path("experiments", "journeys", "j11-conn", "results", "STATE")
# No provenance-bearing span report has been collected for J11 (a serving-only journey with no
# tap captures); this path does not exist today, so SpanReportExecutor fails closed by default.
DEFAULT_SPAN_REPORT_PATH = _repo_path("experiments", "journeys", "j11-conn", "results", "span_report.json")

CHAIN_SCRIPT = "experiments/vast/conn_chain.sh"

# The eight (conn, arm, c) combinations conn_chain.sh's default configuration sweeps
# (CONNS="100 512", arms full/gist8, CONCS="128 256"). A benchmark run is only accepted as
# complete once exactly this set of combinations was recorded, per X-15.
EXPECTED_B6_COMBINATIONS = frozenset(
    (conn, arm, c)
    for conn in (100, 512)
    for arm in ("full", "gist8")
    for c in (128, 256)
)


def _single_chain_start_violation(markers: List[Marker]) -> Optional[str]:
    """Returns a reason string if `markers` does not contain exactly one `chain_start` marker
    (an ambiguous invocation boundary: either no run is recorded, or more than one run's STATE
    lines have been concatenated together), else None."""
    chain_starts = [m for m in markers if m.kind == "chain_start"]
    if len(chain_starts) != 1:
        return "expected exactly one chain_start marker (one coherent chain invocation), found %d" % len(chain_starts)
    return None


@dataclass
class StagePlan:
    """What `dryrun.py` prints for one stage: never executed, purely descriptive."""

    name: str
    required_inputs: List[str]
    remote_command: str
    expected_artifacts: List[str]
    gate: Dict[str, Any] = field(default_factory=dict)

    def missing_inputs(self) -> List[str]:
        return [path for path in self.required_inputs if not os.path.isfile(path)]


class SpanReportExecutor:
    """A no-op stage (nothing remote to run). Reports `checkpoint_share` (checkpoint composition,
    always computable from the segment map on disk) and, only when a provenance-bearing span
    report exists, `share` (the measured static-span result). Per X-10, these are never
    conflated: a gate written against `share` must see the stage fail closed, not a passing
    checkpoint-composition number wearing the wrong name."""

    name = "span"
    plan = StagePlan(
        name="span",
        required_inputs=[R8V2_SEGMENTS_PATH],
        remote_command="(no-op: reports checkpoint_share from the checkpoint's segment map, "
                        "and share only if a provenance-bearing span report is found)",
        expected_artifacts=[],
    )

    def __init__(self, span_report_path: str = DEFAULT_SPAN_REPORT_PATH) -> None:
        self.span_report_path = span_report_path

    def _checkpoint_share_metrics(self) -> Tuple[Optional[Dict[str, float]], Optional[ExecuteResult]]:
        """Returns (metrics, None) on success or (None, ExecuteResult) if the checkpoint's own
        segment map could not even be read (an infra_failure, distinct from "no span evidence")."""
        try:
            with open(R8V2_SEGMENTS_PATH) as handle:
                segments = json.load(handle)
        except OSError as error:
            return None, ExecuteResult(ok=False, kind="infra_failure", detail="could not read %s: %s" % (R8V2_SEGMENTS_PATH, error))

        static_tokens = 0
        gist_tokens = 0
        dynamic_tokens = 0
        for segment in segments.get("segments", []):
            token_count = len(segment.get("ids", []))
            if segment.get("dynamic"):
                dynamic_tokens += token_count
            elif "gist_count" in segment:
                static_tokens += token_count
                gist_tokens += segment["gist_count"]
            else:
                dynamic_tokens += token_count

        total_tokens = static_tokens + dynamic_tokens
        checkpoint_share = (static_tokens / total_tokens) if total_tokens else 0.0
        return {
            "checkpoint_share": checkpoint_share,
            "gist_ratio": float(segments.get("ratio", 0)),
            "gist_token_count": float(gist_tokens),
        }, None

    def _provenance_share(self, report: Any) -> Optional[float]:
        """Extracts a measured share from a real `steno.span.analysis` report shape (schema
        `steno-span-report/...`): the fraction of preamble characters, across every cohort and
        part, that were fixed/compressible rather than unresolved. Returns None if `report` does
        not look like a genuine passing report (wrong/missing schema, `pass` not True, or no
        cohorts to compute a ratio from) -- never guesses a number from a partial shape."""
        if not isinstance(report, dict):
            return None
        if not str(report.get("schema_version", "")).startswith("steno-span-report"):
            return None
        if report.get("pass") is not True:
            return None
        cohorts = report.get("cohorts")
        if not isinstance(cohorts, list) or not cohorts:
            return None
        fixed_total = 0
        char_total = 0
        for cohort in cohorts:
            for part in cohort.get("parts", []):
                fixed_total += part.get("fixed_char_count", 0)
                char_total += part.get("total_char_count", 0)
        if char_total == 0:
            return None
        return fixed_total / char_total

    def report(self) -> ExecuteResult:
        checkpoint_metrics, failure = self._checkpoint_share_metrics()
        if failure is not None:
            return failure

        if not os.path.isfile(self.span_report_path):
            return ExecuteResult(
                ok=False, kind="task_failure",
                detail="no provenance-bearing span report at %s; checkpoint_share is composition, "
                       "not measured share, and is not accepted as a substitute (fail closed)" % self.span_report_path,
                metrics=checkpoint_metrics,
            )

        try:
            with open(self.span_report_path) as handle:
                report = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            return ExecuteResult(ok=False, kind="infra_failure",
                                  detail="could not read span report %s: %s" % (self.span_report_path, error),
                                  metrics=checkpoint_metrics)

        share = self._provenance_share(report)
        if share is None:
            return ExecuteResult(
                ok=False, kind="task_failure",
                detail="span report at %s is not a usable provenance-bearing report (schema/pass/cohorts)" % self.span_report_path,
                metrics=checkpoint_metrics,
            )

        metrics = dict(checkpoint_metrics)
        metrics["share"] = share
        return ExecuteResult(ok=True, kind="ok", detail="share measured from %s" % self.span_report_path, metrics=metrics)

    def __call__(self, resource_id: str, stage_plan: dict) -> ExecuteResult:
        return self.report()


class ServeExecutor:
    """Wraps conn_chain.sh's download + checkpoint-build + `start_server` sequence. Success is
    `ckpt_built` followed by `server_up`; any `*_FAILED` marker before those two ends the stage as
    an infra_failure with that marker as the reason, per the task's mapping."""

    name = "serve"
    plan = StagePlan(
        name="serve",
        required_inputs=[R8V2_SEGMENTS_PATH],
        remote_command=(
            "bash %s (download Qwen/Qwen3.8-27B, cp -r /root/gist/out_r8v2 /root/gist/out, "
            "prepare_checkpoint.py, apply_gist_delta_bench.sh, export_rows.py, then "
            "start_server 40960 256 0.92 16384 via supervise_bench.sh)" % CHAIN_SCRIPT
        ),
        expected_artifacts=["STATE marker: ckpt_built", "STATE marker: server_up"],
    )

    def result_from_markers(self, markers: List[Marker]) -> ExecuteResult:
        boundary_violation = _single_chain_start_violation(markers)
        if boundary_violation:
            return ExecuteResult(ok=False, kind="infra_failure", detail=boundary_violation)

        failures = [m for m in markers if m.kind == "infra_failure"]
        server_up = next((m for m in markers if m.kind == "server_up"), None)
        ckpt_built = next((m for m in markers if m.kind == "ckpt_built"), None)

        # A failure marker that appears before server_up (or if server_up never happened at all)
        # is this stage's failure; a failure later in the file (during B6) belongs to benchmark.
        for failure in failures:
            if server_up is None or markers.index(failure) < markers.index(server_up):
                return ExecuteResult(ok=False, kind="infra_failure", detail=failure.fields.get("detail", failure.raw))

        if ckpt_built is None or server_up is None:
            return ExecuteResult(ok=False, kind="infra_failure",
                                  detail="no ckpt_built/server_up marker pair found in STATE")

        # X-15: server_up claims the checkpoint that ckpt_built is supposed to have just built;
        # accepting server_up recorded *before* ckpt_built would accept a server that was never
        # shown to be serving that checkpoint.
        if markers.index(server_up) < markers.index(ckpt_built):
            return ExecuteResult(ok=False, kind="infra_failure",
                                  detail="server_up marker appeared before ckpt_built (out-of-order evidence)")

        return ExecuteResult(
            ok=True, kind="ok",
            detail=ckpt_built.fields.get("detail", ""),
            metrics={
                "max_model_len": float(server_up.fields["max_model_len"]),
                "max_num_seqs": float(server_up.fields["max_num_seqs"]),
                "gpu_util": server_up.fields["gpu_util"],
                "max_batched": float(server_up.fields["max_batched"]),
            },
        )

    def __call__(self, resource_id: str, stage_plan: dict) -> ExecuteResult:
        raise NotImplementedError(
            "ServeExecutor does not execute anything remote in this wave; wire it to a real "
            "backend (steno.loop.backend.VastBackend, still a stub) in a later wave. Use "
            "result_from_markers() to replay an existing STATE file instead."
        )


class BenchmarkExecutor:
    """Wraps conn_chain.sh's B6 sweep (conn-limit x arm x concurrency). Reports one metric set
    per combination plus an aggregate `max_running_max`, so a spec's `benchmark` gate can check
    either a specific combination or the overall ceiling."""

    name = "benchmark"
    plan = StagePlan(
        name="benchmark",
        required_inputs=[CORPUS_FULL_PATH, CORPUS_GIST8_PATH],
        remote_command=(
            "bash %s's B6 loop: for conn in 100 512; for arm in full gist8; for c in 128 256: "
            "loadgen.py --conn-limit $conn --concurrency $c --arm $arm --duration 180" % CHAIN_SCRIPT
        ),
        expected_artifacts=[
            "experiments/journeys/j11-conn/results/B6_conn*_*_c*_r1.json",
            "STATE marker: B6_done", "STATE marker: BENCH_DONE",
        ],
        gate={},
    )

    def result_from_markers(self, markers: List[Marker]) -> ExecuteResult:
        boundary_violation = _single_chain_start_violation(markers)
        if boundary_violation:
            return ExecuteResult(ok=False, kind="infra_failure", detail=boundary_violation)

        results = [m for m in markers if m.kind == "b6_result"]
        failed = [m for m in markers if m.kind == "b6_failed"]
        infra_failures = [m for m in markers if m.kind == "infra_failure"]

        if not results and not failed:
            return ExecuteResult(ok=False, kind="infra_failure", detail="no B6 results found in STATE")

        if failed or infra_failures:
            reasons = [m.raw for m in failed] + [m.fields.get("detail", m.raw) for m in infra_failures]
            return ExecuteResult(ok=False, kind="infra_failure", detail="; ".join(reasons))

        # X-15: reject duplicate combinations before trusting any metric derived from them -- a
        # repeated (conn, arm, c) means the STATE file recorded the same run twice (or two runs'
        # output got concatenated), and averaging or overwriting silently would hide that.
        combo_of = lambda m: (m.fields["conn"], m.fields["arm"], m.fields["c"])
        seen_combos: Dict[tuple, int] = {}
        for m in results:
            combo = combo_of(m)
            seen_combos[combo] = seen_combos.get(combo, 0) + 1
        duplicates = [combo for combo, count in seen_combos.items() if count > 1]
        if duplicates:
            return ExecuteResult(ok=False, kind="task_failure",
                                  detail="duplicate B6 combination(s) recorded: %s" % (duplicates,))

        found_combos = set(seen_combos)
        missing = EXPECTED_B6_COMBINATIONS - found_combos
        unexpected = found_combos - EXPECTED_B6_COMBINATIONS
        if missing or unexpected:
            return ExecuteResult(
                ok=False, kind="task_failure",
                detail="B6 combinations do not match the expected set: missing=%s unexpected=%s" % (
                    sorted(missing), sorted(unexpected)),
            )

        b6_done_markers = [m for m in markers if m.kind == "b6_done"]
        bench_done_markers = [m for m in markers if m.kind == "bench_done"]
        last_result_index = max(markers.index(m) for m in results)

        if len(b6_done_markers) != 1:
            return ExecuteResult(ok=False, kind="task_failure",
                                  detail="expected exactly one B6_done marker, found %d" % len(b6_done_markers))
        if markers.index(b6_done_markers[0]) < last_result_index:
            return ExecuteResult(ok=False, kind="task_failure",
                                  detail="B6_done marker appeared before all eight B6 result markers")

        if len(bench_done_markers) != 1:
            return ExecuteResult(ok=False, kind="task_failure",
                                  detail="expected exactly one BENCH_DONE marker, found %d" % len(bench_done_markers))
        if markers.index(bench_done_markers[0]) < markers.index(b6_done_markers[0]):
            return ExecuteResult(ok=False, kind="task_failure",
                                  detail="BENCH_DONE marker appeared before B6_done")

        metrics: Dict[str, float] = {}
        max_running_values = []
        for m in results:
            key_suffix = "conn%d_%s_c%d" % (m.fields["conn"], m.fields["arm"], m.fields["c"])
            metrics["max_running__%s" % key_suffix] = m.fields["max_running"]
            metrics["rpm__%s" % key_suffix] = m.fields["rpm"]
            metrics["kv_max__%s" % key_suffix] = m.fields["kv_max"]
            metrics["preempt__%s" % key_suffix] = m.fields["preempt"]
            max_running_values.append(m.fields["max_running"])
        metrics["max_running_max"] = max(max_running_values)
        metrics["b6_result_count"] = float(len(results))
        metrics["b6_total_ok"] = float(sum(m.fields["ok"] for m in results))
        metrics["b6_total_err"] = float(sum(m.fields["err"] for m in results))

        return ExecuteResult(ok=True, kind="ok", detail="%d B6 combinations recorded" % len(results), metrics=metrics)

    def __call__(self, resource_id: str, stage_plan: dict) -> ExecuteResult:
        raise NotImplementedError(
            "BenchmarkExecutor does not execute anything remote in this wave; see ServeExecutor's "
            "docstring. Use result_from_markers() to replay an existing STATE file instead."
        )


SPAN = SpanReportExecutor()
SERVE = ServeExecutor()
BENCHMARK = BenchmarkExecutor()

STAGE_EXECUTORS = {"span": SPAN, "serve": SERVE, "benchmark": BENCHMARK}
STAGE_PLANS = {"span": SPAN.plan, "serve": SERVE.plan, "benchmark": BENCHMARK.plan}
