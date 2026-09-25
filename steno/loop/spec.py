"""The Steno run spec: schema ``steno-run/v1`` (steno-design.md section 2).

A run spec is the single declarative input to ``steno run <spec>``. It names the
harness/model pair, the inputs to consume, the stages to execute, the spend and
wall-clock budget, the gates that must pass, the compute backend to provision,
and the artifact store to sync results to.

Parsing accepts YAML when PyYAML is installed (guarded import) and JSON always,
using the file extension to choose the parser, with JSON as the fallback if
PyYAML is unavailable and the file is not clearly YAML. A ``.json`` spec never
depends on PyYAML.
"""

from __future__ import annotations

import math

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any

try:
    import yaml  # type: ignore

    _HAS_YAML = True
except ImportError:  # pragma: no cover - exercised only when PyYAML is absent
    yaml = None  # type: ignore
    _HAS_YAML = False


SCHEMA_NAME = "steno-run/v1"

# The full ordered stage list the design names. A spec's ``stages`` field must
# be a subsequence of this order (it may skip stages, but never reorder them).
KNOWN_STAGE_ORDER = ("preflight", "span", "data", "train", "serve", "evaluate", "benchmark")

# Stages that depend on the span segment map: none of these may run without a
# span stage in the same spec (steno-design.md: "span always runs first and
# gates the rest"). data is deliberately excluded: some journeys stage raw
# data without yet compressing it.
STAGES_REQUIRING_SPAN = ("train", "serve", "evaluate", "benchmark")

# Gate names the runner knows how to carry (evaluation of gate thresholds is
# not implemented in this wave; unsupported keys are rejected so a spec never
# silently promises a gate check that never happens).
KNOWN_GATE_KEYS = ("span", "evaluate", "benchmark")

# Emergency policies the runner knows how to honor on a failed artifact sync.
KNOWN_EMERGENCY_POLICIES = ("terminate_and_record_loss",)

# Input keys every run needs at least a value for (steno-design.md's example:
# captures, tasks, recipe). recipe is optional (not every stage set needs it).
REQUIRED_INPUT_KEYS = ("captures", "tasks")


class SpecValidationError(ValueError):
    """Raised by validate() with a clear, specific message for the failing field."""


def _hash_file_contents(path: str) -> str | None:
    """Returns a hex sha256 of path's contents, or None if path is not a
    readable local file (a digest string like "sha256:abc" is not a path and
    correctly yields None here, unchanged from before)."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def _identity_value(value: Any) -> Any:
    """For an input value that names an existing local file, returns its
    content hash (and path, so a rename is still visible) instead of the bare
    path; every other value (a digest string, a number, a nested dict such as
    ``recipe``) passes through unchanged."""
    if isinstance(value, str):
        file_hash = _hash_file_contents(value)
        if file_hash is not None:
            return {"path": value, "sha256": file_hash}
        return value
    return value


@dataclass
class RunSpec:
    """The parsed and validated contents of a run spec file."""

    schema: str
    pair: str
    inputs: dict[str, Any] = field(default_factory=dict)
    stages: list[str] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    gates: dict[str, Any] = field(default_factory=dict)
    compute: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    source_path: str | None = None

    @property
    def run_id_hint(self) -> str:
        """A filesystem-friendly hint derived from the pair, for naming run directories.

        This is a naming hint only. It must never be used as (part of) a
        provisioning idempotency key: two separate runs of the same pair would
        collide and could be handed the same rented resource (see steno/loop's
        README, "Run identity"). The runner mints a unique run_id instead.
        """
        base = os.path.splitext(os.path.basename(self.pair))[0] if self.pair else "run"
        return base

    def identity_digest(self) -> str:
        """A stable hash of the fields that must not change across a resume:
        pair, inputs, stages and gates. Used to reject an incompatible resume
        against an existing run directory (see runner.py).

        The pair field and any input value that names an existing local file
        are hashed by their *contents*, not just their path string: editing
        the pinned pair manifest or a referenced input file in place, while
        the run directory still exists, must be caught as an identity change
        too, not only a change to the path itself.
        """
        pair_identity: Any = self.pair
        pair_hash = _hash_file_contents(self.pair) if isinstance(self.pair, str) else None
        if pair_hash is not None:
            pair_identity = {"path": self.pair, "sha256": pair_hash}

        hashed_inputs = {key: _identity_value(value) for key, value in self.inputs.items()}

        canonical = json.dumps(
            {"pair": pair_identity, "inputs": hashed_inputs, "stages": self.stages, "gates": self.gates},
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def validate(self) -> None:
        """Raise SpecValidationError on the first problem found, with a clear message.

        Checks performed, in order:
          1. schema name matches this module's supported schema.
          2. pair is a non-empty string.
          3. stages is a non-empty list, drawn only from KNOWN_STAGE_ORDER, in
             an order consistent with KNOWN_STAGE_ORDER (a valid subsequence),
             with no duplicates, and with span first whenever span is present.
          4. budget: max_usd, max_hours, min_credit, cleanup_reserve_usd are all
             present and positive numbers; cleanup_reserve_usd < max_usd;
             max_attempts_per_stage is a positive integer.
          5. artifacts.store is present and non-empty (the required artifact
             store destination).
        """
        if self.schema != SCHEMA_NAME:
            raise SpecValidationError(
                f"unsupported schema {self.schema!r}, expected {SCHEMA_NAME!r}"
            )

        if not isinstance(self.pair, str) or not self.pair.strip():
            raise SpecValidationError("pair must be a non-empty string naming the pair manifest")

        self._validate_stages()
        self._validate_inputs()
        self._validate_gates()
        self._validate_budget()
        self._validate_artifacts()

    def _validate_inputs(self) -> None:
        if not isinstance(self.inputs, dict) or not self.inputs:
            raise SpecValidationError("inputs must be a non-empty object")
        missing = [key for key in REQUIRED_INPUT_KEYS if not self.inputs.get(key)]
        if missing:
            raise SpecValidationError(f"inputs missing required key(s): {missing}")

    def _validate_gates(self) -> None:
        if not isinstance(self.gates, dict):
            raise SpecValidationError("gates must be an object")
        for gate_name, gate_fields in self.gates.items():
            if isinstance(gate_fields, dict):
                for field_name, field_value in gate_fields.items():
                    if isinstance(field_value, float) and not math.isfinite(field_value):
                        raise SpecValidationError(f"gates.{gate_name}.{field_name} must be a finite number, got {field_value!r}")
        unsupported = [key for key in self.gates if key not in KNOWN_GATE_KEYS]
        if unsupported:
            raise SpecValidationError(
                f"unsupported gate(s) {unsupported}: this wave only carries {list(KNOWN_GATE_KEYS)} "
                "(gate evaluation is not implemented, but an unrecognised gate name is rejected "
                "rather than silently ignored)"
            )

    def _validate_stages(self) -> None:
        if not isinstance(self.stages, list) or not self.stages:
            raise SpecValidationError("stages must be a non-empty list")

        unknown = [s for s in self.stages if s not in KNOWN_STAGE_ORDER]
        if unknown:
            raise SpecValidationError(
                f"unknown stage(s) {unknown}: stages must be drawn from {list(KNOWN_STAGE_ORDER)}"
            )

        seen = set()
        for stage in self.stages:
            if stage in seen:
                raise SpecValidationError(f"stage {stage!r} listed more than once")
            seen.add(stage)

        # stages must be an order-preserving subsequence of KNOWN_STAGE_ORDER
        last_index = -1
        for stage in self.stages:
            index = KNOWN_STAGE_ORDER.index(stage)
            if index <= last_index:
                raise SpecValidationError(
                    f"stages must follow the order {list(KNOWN_STAGE_ORDER)}; "
                    f"{stage!r} is out of order"
                )
            last_index = index

        if "span" in self.stages and self.stages[0] != "span" and self.stages[0] != "preflight":
            raise SpecValidationError("span must be the first non-preflight stage when present")
        if "span" in self.stages:
            non_preflight = [s for s in self.stages if s != "preflight"]
            if non_preflight and non_preflight[0] != "span":
                raise SpecValidationError("span must be the first stage after preflight when present")

        dependents_present = [s for s in self.stages if s in STAGES_REQUIRING_SPAN]
        if dependents_present and "span" not in self.stages:
            raise SpecValidationError(
                f"stage(s) {dependents_present} require a span stage in the same spec "
                "(span always gates the rest; see steno-design.md section 2)"
            )

    def _validate_budget(self) -> None:
        budget = self.budget
        if not isinstance(budget, dict):
            raise SpecValidationError("budget must be an object")

        required_positive = ("max_usd", "max_hours", "min_credit", "cleanup_reserve_usd")
        for field_name in required_positive:
            if field_name not in budget:
                raise SpecValidationError(f"budget.{field_name} is required")
            value = budget[field_name]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise SpecValidationError(f"budget.{field_name} must be a positive number, got {value!r}")

        if budget["cleanup_reserve_usd"] >= budget["max_usd"]:
            raise SpecValidationError(
                "budget.cleanup_reserve_usd must be below budget.max_usd "
                f"(got {budget['cleanup_reserve_usd']} >= {budget['max_usd']})"
            )

        max_attempts = budget.get("max_attempts_per_stage", 1)
        if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or max_attempts <= 0:
            raise SpecValidationError(
                f"budget.max_attempts_per_stage must be a positive integer, got {max_attempts!r}"
            )

    def _validate_artifacts(self) -> None:
        artifacts = self.artifacts
        if not isinstance(artifacts, dict):
            raise SpecValidationError("artifacts must be an object")
        store = artifacts.get("store")
        if not isinstance(store, str) or not store.strip():
            raise SpecValidationError("artifacts.store is required (the durable artifact destination)")
        policy = artifacts.get("emergency_policy")
        if policy not in KNOWN_EMERGENCY_POLICIES:
            raise SpecValidationError(
                f"artifacts.emergency_policy must be one of {list(KNOWN_EMERGENCY_POLICIES)}, got {policy!r}"
            )


def _looks_like_yaml(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in (".yaml", ".yml")


def parse_spec_text(text: str, *, prefer_yaml: bool) -> dict[str, Any]:
    """Parse spec text as YAML (if available and preferred) or JSON.

    JSON is a valid subset of many practical YAML documents; we still try JSON
    first only when not preferring YAML, to keep the ``.json`` extension path
    entirely free of the PyYAML dependency, per spec.
    """
    if prefer_yaml and _HAS_YAML:
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise SpecValidationError("spec document must parse to a mapping/object")
        return loaded
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as error:
        if _HAS_YAML:
            loaded = yaml.safe_load(text)
        else:
            raise SpecValidationError(
                f"spec is not valid JSON and PyYAML is not installed to try YAML: {error}"
            ) from error
    if not isinstance(loaded, dict):
        raise SpecValidationError("spec document must parse to a mapping/object")
    return loaded


def load_spec(path: str) -> RunSpec:
    """Load a run spec from disk (YAML or JSON) and return it unvalidated.

    Call ``.validate()`` on the result before acting on it; loading and
    validating are kept separate so callers (like the CLI) can report parse
    errors distinctly from validation errors.
    """
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    document = parse_spec_text(text, prefer_yaml=_looks_like_yaml(path))
    return spec_from_dict(document, source_path=path)


def spec_from_dict(document: dict[str, Any], *, source_path: str | None = None) -> RunSpec:
    """Build a RunSpec from an already-parsed mapping (used by load_spec and tests)."""
    return RunSpec(
        schema=document.get("schema", ""),
        pair=document.get("pair", ""),
        inputs=document.get("inputs", {}) or {},
        stages=list(document.get("stages", []) or []),
        budget=document.get("budget", {}) or {},
        gates=document.get("gates", {}) or {},
        compute=document.get("compute", {}) or {},
        artifacts=document.get("artifacts", {}) or {},
        raw=document,
        source_path=source_path,
    )
