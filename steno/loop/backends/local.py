"""LocalBackend: "provisions" a local working directory and runs stages as
subprocesses (steno-design.md section 3, build order step 6, point 5).

Exists to prove the ComputeBackend contract is not vast-shaped: it has no
network, no SSH, no billing meter, and still satisfies every method the
runner drives a backend through. Also useful on its own for developing and
debugging a spec's stage plans without renting anything.

No provider import here because there is no provider; everything is stdlib
(subprocess, shutil, hashlib, json).

Codex review (steno-build-wave2) fixes in this revision:
  - X-9: resource/idempotency-key metadata is now persisted to a registry
    file under `root_dir`, so reconstructing a LocalBackend over the same
    root_dir (a process restart) recovers an existing resource instead of
    losing it or double-provisioning it. `destroy()` verifies the directory
    is actually gone (not `ignore_errors=True` papering over a failed
    removal) before recording the resource as destroyed; `confirm_destroyed`
    cross-checks the filesystem against the persisted flag.
  - X-2: `transfer()` now requires an explicit `_destination` (no more silent
    "success" when nothing was copied), and hashes the DESTINATION file
    after copying (not just the source) before reporting success, so success
    actually proves the artifact survives resource teardown.
  - X-3: every manifest/output path is validated as a safe relative path
    (`compute.validate_relative_artifact_path`) before being joined onto a
    directory, rejecting absolute paths and `..` traversal.
  - X-6: `execute()` rejects a stage_plan with neither `command` nor
    `executor` (`backend.stage_plan_has_work`) instead of silently
    reporting a no-op success.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from ..backend import ComputeBackend, ExecuteResult, InspectResult, TransferResult, stage_plan_has_work
from ..compute import ComputeOffer, ComputeRequest, ResourceHandle, validate_relative_artifact_path

DEFAULT_STAGE_TIMEOUT_SECONDS = 600
REGISTRY_FILENAME = "_steno_local_registry.json"


class LocalBackend(ComputeBackend):
    """Runs stages as local subprocesses in a per-resource directory.

    ``backend_options`` recognises one key: ``root_dir`` (where per-resource
    directories, and the persisted registry file, live; defaults to a fresh
    tempdir per backend instance -- pass an explicit, stable ``root_dir`` to
    get restart recovery). A stage_plan's ``command`` (a list[str] argv,
    never a shell string) is run with ``cwd`` set to the resource's
    directory; its ``timeout_seconds`` (default 600) bounds execution.
    ``transfer()`` requires an explicit ``manifest["_destination"]`` (a local
    directory) and hashes the copied file there, not just the source, before
    reporting success.
    """

    name = "local"
    capabilities: dict[str, Any] = {"credit_lookup": False}

    def __init__(self, *, backend_options: dict[str, Any] | None = None) -> None:
        options = backend_options or {}
        self._root_dir = Path(options.get("root_dir") or tempfile.mkdtemp(prefix="steno-local-"))
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self._root_dir / REGISTRY_FILENAME
        self._registry = self._load_registry()

    # --- persisted registry (X-9) -----------------------------------------

    def _load_registry(self) -> dict[str, Any]:
        if self._registry_path.is_file():
            try:
                with open(self._registry_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict) and isinstance(data.get("resources"), dict) and isinstance(data.get("keys"), dict):
                    return data
            except (OSError, json.JSONDecodeError):
                pass  # a corrupt or unreadable registry starts fresh rather than crashing the backend
        return {"resources": {}, "keys": {}}

    def _save_registry(self) -> None:
        # Atomic write (temp file + os.replace), matching state.py's pattern,
        # so a crash mid-write never leaves a half-written registry.
        fd, tmp_path = tempfile.mkstemp(dir=str(self._root_dir), prefix=".registry-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._registry, handle)
            os.replace(tmp_path, self._registry_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _resource_dir(self, resource_id: str) -> Path:
        return self._root_dir / resource_id

    def quote(self, request: ComputeRequest) -> list[ComputeOffer]:
        return [
            ComputeOffer(
                offer_id="local-0",
                gpu_family=(request.gpu_families or ["none"])[0],
                gpu_count=request.gpu_count or 0,
                gpu_memory_gb=request.gpu_memory_gb_min or 0.0,
                hourly_usd=0.0,
                region="localhost",
                reliability=1.0,
                raw_provider_ref=None,
            )
        ]

    def provision(self, compute: dict[str, Any], idempotency_key: str) -> ResourceHandle:
        existing_id = self._registry["keys"].get(idempotency_key)
        if existing_id is not None:
            record = self._registry["resources"].get(existing_id)
            if record is not None and not record.get("destroyed"):
                # Reconcile: a restart may have recovered the registry but
                # lost the directory itself (for example a half-finished
                # provision before the previous process died); recreate it
                # rather than treating a missing directory as "gone".
                self._resource_dir(existing_id).mkdir(parents=True, exist_ok=True)
                return ResourceHandle(resource_id=existing_id, backend_name=self.name, host="localhost", hourly_usd=0.0)

        resource_id = f"local-{uuid.uuid4().hex[:12]}"
        self._resource_dir(resource_id).mkdir(parents=True, exist_ok=True)
        self._registry["resources"][resource_id] = {
            "idempotency_key": idempotency_key, "destroyed": False, "created_at": time.time(),
        }
        self._registry["keys"][idempotency_key] = resource_id
        self._save_registry()
        return ResourceHandle(resource_id=resource_id, backend_name=self.name, host="localhost", hourly_usd=0.0)

    def inspect(self, resource_id: str) -> InspectResult:
        record = self._registry["resources"].get(resource_id)
        if record is None:
            return InspectResult(resource_id=resource_id, exists=False, reachable=False, status_text="unknown")
        exists = not record.get("destroyed") and self._resource_dir(resource_id).is_dir()
        return InspectResult(
            resource_id=resource_id, exists=exists, reachable=exists,
            status_text="destroyed" if not exists else "ready",
        )

    def execute(self, resource_id: str, stage_plan: dict[str, Any]) -> ExecuteResult:
        record = self._registry["resources"].get(resource_id)
        if record is None or record.get("destroyed") or not self._resource_dir(resource_id).is_dir():
            return ExecuteResult(ok=False, kind="infra_failure", detail="resource does not exist")

        executor = stage_plan.get("executor")
        if executor is not None:
            return executor(resource_id, stage_plan)

        # X-6: a plan naming neither an executor nor a command is not a
        # legitimate no-op for a real backend; report the missing work
        # rather than a false success.
        if not stage_plan_has_work(stage_plan):
            return ExecuteResult(
                ok=False, kind="infra_failure",
                detail="stage_plan has neither 'command' nor 'executor'; nothing to run",
            )

        command = stage_plan["command"]
        timeout = stage_plan.get("timeout_seconds", DEFAULT_STAGE_TIMEOUT_SECONDS)
        try:
            completed = subprocess.run(
                list(command), cwd=str(self._resource_dir(resource_id)), timeout=timeout,
                capture_output=True, text=True, check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecuteResult(ok=False, kind="infra_failure", detail=f"stage command timed out after {timeout}s")
        except OSError as error:
            return ExecuteResult(ok=False, kind="infra_failure", detail=f"failed to launch stage command: {type(error).__name__}: {error}")
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
            return ExecuteResult(ok=False, kind="task_failure", detail=f"exit {completed.returncode}: {detail}")

        output_manifest: dict[str, str] = {}
        for path in stage_plan.get("outputs", {}):
            validate_relative_artifact_path(path)
            source = self._resource_dir(resource_id) / path
            if source.is_file():
                output_manifest[path] = _sha256_file(source)
        return ExecuteResult(ok=True, kind="ok", output_manifest=output_manifest)

    def transfer(self, resource_id: str, manifest: dict[str, Any]) -> TransferResult:
        record = self._registry["resources"].get(resource_id)
        resource_dir = self._resource_dir(resource_id)
        if record is None or record.get("destroyed") or not resource_dir.is_dir():
            return TransferResult(ok=False, detail="resource no longer exists; cannot transfer from a destroyed box")

        # X-2: an artifact destination is required. Without one, "success"
        # would mean nothing was ever retrieved off the resource, which is
        # indistinguishable from data loss once the resource is destroyed.
        destination = manifest.get("_destination")
        if not destination:
            return TransferResult(ok=False, detail="transfer requires an explicit manifest['_destination'] local directory")
        destination_dir = Path(destination)

        paths = {k: v for k, v in manifest.items() if k != "_destination"}
        mismatched: list[str] = []
        copied: dict[str, str] = {}
        for rel_path, expected_hash in paths.items():
            try:
                validate_relative_artifact_path(rel_path)
            except Exception:
                mismatched.append(rel_path)
                continue
            source = resource_dir / rel_path
            if not source.is_file():
                mismatched.append(rel_path)
                continue
            dest_path = destination_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest_path)
            # X-2: hash the DESTINATION after copying, not the source; this
            # is what proves the artifact actually landed intact, not merely
            # that the source once matched (which teardown could then erase
            # without this ever having been verified against the copy).
            actual_hash = _sha256_file(dest_path)
            if actual_hash != expected_hash:
                mismatched.append(rel_path)
                continue
            copied[rel_path] = actual_hash
        if mismatched:
            return TransferResult(ok=False, manifest=copied, detail=f"missing or mismatched: {mismatched}")
        return TransferResult(ok=True, manifest=copied)

    def cost(self, resource_id: str) -> float:
        del resource_id
        return 0.0

    def destroy(self, resource_id: str) -> bool:
        record = self._registry["resources"].get(resource_id)
        if record is None:
            return True
        if record.get("destroyed"):
            return True
        directory = self._resource_dir(resource_id)
        shutil.rmtree(directory, ignore_errors=True)
        if directory.exists():
            # X-9: do not report destruction that did not actually happen
            # (a permission error or an open file handle can make rmtree a
            # partial no-op even with ignore_errors=True).
            return False
        record["destroyed"] = True
        self._save_registry()
        return True

    def confirm_destroyed(self, resource_id: str) -> bool | None:
        record = self._registry["resources"].get(resource_id)
        if record is None:
            return True
        if not record.get("destroyed"):
            return False
        # Cross-check the persisted flag against the filesystem: if the
        # directory somehow still exists, evidence contradicts the flag, so
        # report False (still exists) rather than trusting stale bookkeeping.
        return not self._resource_dir(resource_id).exists()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
