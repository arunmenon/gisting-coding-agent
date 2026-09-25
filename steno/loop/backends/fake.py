"""FakeBackend: a test double compute backend. Not for production use.

Moved here from steno/loop/backend.py in wave 2 (build order step 6, point 4);
``steno.loop.backend`` re-exports this class so existing imports
(``from steno.loop.backend import FakeBackend``) keep working unchanged.

Simulates cost accrual over an injected clock, and can be configured to fail
specific operations so tests can exercise infra failure paths without any
real provisioning:
  - fail_sync: transfer() returns ok=False once (or every time if 'always').
  - unreachable_hosts: set of resource_ids that inspect()/execute() report
    as unreachable until made reachable again.
  - fail_destroy: destroy() returns False (the destroy *request* fails).
  - fail_destroy_confirmation: confirm_destroyed() raises to simulate an
    API error (translated by callers into destroy_unknown, never destroyed).
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from ..compute import ComputeOffer, ComputeRequest, ResourceHandle


class FakeBackend:
    name = "fake"
    capabilities: dict[str, Any] = {"credit_lookup": False}

    def __init__(
        self,
        clock: Callable[[], float],
        hourly_usd: float = 1.0,
        *,
        backend_options: dict[str, Any] | None = None,
    ) -> None:
        del backend_options  # accepted for registry compatibility; FakeBackend needs no options
        self._clock = clock
        self._hourly_usd = hourly_usd
        self._resources: dict[str, dict[str, Any]] = {}
        self._provisioned_keys: dict[str, str] = {}  # idempotency_key -> resource_id
        self.fail_sync = False
        self.unreachable_hosts: set[str] = set()
        self.fail_destroy = False
        self.fail_destroy_confirmation = False
        self._destroyed: set[str] = set()

    def quote(self, request: ComputeRequest) -> list[ComputeOffer]:
        gpu_family = (request.gpu_families or ["fake-gpu"])[0]
        return [
            ComputeOffer(
                offer_id="fake-offer-1",
                gpu_family=gpu_family,
                gpu_count=request.gpu_count or 1,
                gpu_memory_gb=request.gpu_memory_gb_min or 24.0,
                hourly_usd=self._hourly_usd,
                region="fake-region",
                reliability=1.0,
                raw_provider_ref=None,
            )
        ]

    def provision(self, compute: dict[str, Any], idempotency_key: str) -> ResourceHandle:
        existing = self._provisioned_keys.get(idempotency_key)
        if existing is not None:
            record = self._resources[existing]
            return ResourceHandle(
                resource_id=existing, backend_name=self.name, host=record["host"], port=record["port"],
                hourly_usd=self._hourly_usd,
            )
        resource_id = f"fake-{uuid.uuid4().hex[:12]}"
        self._resources[resource_id] = {
            "host": f"{resource_id}.fake",
            "port": 22,
            "created_at": self._clock(),
            "destroyed": False,
            "artifacts": {},  # path -> hash, only what execute() actually "wrote" to this resource
        }
        self._provisioned_keys[idempotency_key] = resource_id
        return ResourceHandle(
            resource_id=resource_id, backend_name=self.name,
            host=self._resources[resource_id]["host"], port=22, hourly_usd=self._hourly_usd,
        )

    def inspect(self, resource_id: str):
        from ..backend import InspectResult

        record = self._resources.get(resource_id)
        if record is None:
            return InspectResult(resource_id=resource_id, exists=False, reachable=False, status_text="unknown")
        reachable = resource_id not in self.unreachable_hosts and not record["destroyed"]
        return InspectResult(
            resource_id=resource_id,
            exists=not record["destroyed"],
            reachable=reachable,
            status_text="destroyed" if record["destroyed"] else ("unreachable" if not reachable else "ready"),
        )

    def execute(self, resource_id: str, stage_plan: dict[str, Any]):
        from ..backend import ExecuteResult

        if resource_id in self.unreachable_hosts:
            return ExecuteResult(ok=False, kind="infra_failure", detail="host unreachable")
        record = self._resources.get(resource_id)
        if record is None or record["destroyed"]:
            return ExecuteResult(ok=False, kind="infra_failure", detail="resource does not exist")
        # A stage executor callable may be attached to the plan by the runner's
        # caller; FakeBackend just runs it (or no-ops) and reports the outcome.
        executor = stage_plan.get("executor")
        if executor is not None:
            result = executor(resource_id, stage_plan)
        else:
            outputs = stage_plan.get("outputs", {})
            result = ExecuteResult(ok=True, kind="ok", output_manifest=dict(outputs))
        if result.ok:
            # Model the output as actually written to this resource, so a
            # later transfer() can only hand back what really exists there
            # (never fabricate verification for a destroyed or empty box).
            record["artifacts"].update(result.output_manifest)
        return result

    def transfer(self, resource_id: str, manifest: dict[str, Any]):
        from ..backend import TransferResult

        if resource_id in self.unreachable_hosts:
            return TransferResult(ok=False, detail="host unreachable during transfer")
        record = self._resources.get(resource_id)
        if record is None or record["destroyed"]:
            return TransferResult(ok=False, detail="resource no longer exists; cannot transfer from a destroyed box")
        if self.fail_sync:
            return TransferResult(ok=False, detail="simulated sync failure")
        stored = record["artifacts"]
        missing_or_mismatched = {k: v for k, v in manifest.items() if stored.get(k) != v}
        if missing_or_mismatched:
            return TransferResult(
                ok=False,
                detail=f"resource is missing or mismatches {list(missing_or_mismatched)}",
            )
        return TransferResult(ok=True, manifest={k: stored[k] for k in manifest})

    def cost(self, resource_id: str) -> float:
        record = self._resources.get(resource_id)
        if record is None:
            return 0.0
        end = record["created_at"] if record["destroyed"] else self._clock()
        elapsed_hours = max(0.0, (end - record["created_at"]) / 3600.0)
        return round(elapsed_hours * self._hourly_usd, 6)

    def destroy(self, resource_id: str) -> bool:
        if self.fail_destroy:
            return False
        record = self._resources.get(resource_id)
        if record is not None:
            record["destroyed"] = True
        return True

    def confirm_destroyed(self, resource_id: str) -> bool | None:
        if self.fail_destroy_confirmation:
            return None
        record = self._resources.get(resource_id)
        if record is None:
            return True
        return bool(record["destroyed"])
