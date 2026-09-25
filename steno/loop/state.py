"""Persisted lifecycle for a Steno run: stage states and resource states.

Two separate state machines, per steno-design.md section 2 ("Lifecycle"):

  Stage:     pending -> running -> succeeded | failed | cancelled
  Resource:  requested -> provisioning -> ready -> active -> syncing
             -> sync_verified -> destroy_requested -> destroy_confirmed
             (plus a terminal destroy_unknown reachable from destroy_requested
              when the backend's confirm_destroyed call itself errors, since an
              API error means unknown, not destroyed)

State is persisted to ``runs/<run_id>/state.json`` after every transition,
written atomically (temp file then os.replace), plus an append-only
``events.jsonl`` audit trail. ``RunState.load`` resumes a run from disk.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any


class IllegalTransitionError(RuntimeError):
    """Raised when a transition is attempted that the state machine forbids."""


# --- Stage state machine -----------------------------------------------------

STAGE_PENDING = "pending"
STAGE_RUNNING = "running"
STAGE_SUCCEEDED = "succeeded"
STAGE_FAILED = "failed"
STAGE_CANCELLED = "cancelled"

STAGE_TERMINAL = {STAGE_SUCCEEDED, STAGE_FAILED, STAGE_CANCELLED}

_STAGE_TRANSITIONS = {
    STAGE_PENDING: {STAGE_RUNNING, STAGE_CANCELLED},
    STAGE_RUNNING: {STAGE_SUCCEEDED, STAGE_FAILED, STAGE_CANCELLED},
    STAGE_SUCCEEDED: set(),
    STAGE_FAILED: set(),
    STAGE_CANCELLED: set(),
}


# --- Resource state machine --------------------------------------------------

RESOURCE_REQUESTED = "requested"
RESOURCE_PROVISIONING = "provisioning"
RESOURCE_READY = "ready"
RESOURCE_ACTIVE = "active"
RESOURCE_SYNCING = "syncing"
RESOURCE_SYNC_VERIFIED = "sync_verified"
RESOURCE_DESTROY_REQUESTED = "destroy_requested"
RESOURCE_DESTROY_CONFIRMED = "destroy_confirmed"
RESOURCE_DESTROY_UNKNOWN = "destroy_unknown"

# Only destroy_confirmed is a true terminal state now: destroy_unknown means
# "unknown," and unknown must stay recoverable (see the transition map below).
RESOURCE_TERMINAL = {RESOURCE_DESTROY_CONFIRMED}

_RESOURCE_TRANSITIONS = {
    RESOURCE_REQUESTED: {RESOURCE_PROVISIONING, RESOURCE_DESTROY_REQUESTED},
    RESOURCE_PROVISIONING: {RESOURCE_READY, RESOURCE_DESTROY_REQUESTED},
    RESOURCE_READY: {RESOURCE_ACTIVE, RESOURCE_DESTROY_REQUESTED},
    RESOURCE_ACTIVE: {RESOURCE_SYNCING, RESOURCE_ACTIVE, RESOURCE_DESTROY_REQUESTED},
    RESOURCE_SYNCING: {RESOURCE_SYNC_VERIFIED, RESOURCE_ACTIVE, RESOURCE_DESTROY_REQUESTED},
    RESOURCE_SYNC_VERIFIED: {RESOURCE_DESTROY_REQUESTED},
    RESOURCE_DESTROY_REQUESTED: {RESOURCE_DESTROY_CONFIRMED, RESOURCE_DESTROY_UNKNOWN},
    RESOURCE_DESTROY_CONFIRMED: set(),
    # destroy_unknown means "an API error occurred," not "destroyed": it must
    # stay recoverable so a resume can inspect the provider and retry
    # destruction, reaching destroy_confirmed only on provider evidence.
    RESOURCE_DESTROY_UNKNOWN: {RESOURCE_DESTROY_REQUESTED},
}


LOCK_FILENAME = "lock"


# Run-directory locks held by this process, keyed by lock path. The open file
# descriptor must stay open for the lifetime of the lock.
_HELD_LOCKS: dict[str, int] = {}


def acquire_run_lock(run_dir: str) -> str:
    """Claims sole ownership of run_dir for this process (W-6, N-2: one active
    owner per run directory). Raises RuntimeError if another process holds it.

    Uses an exclusive, non-blocking OS advisory lock (fcntl.flock) on the lock
    file rather than a PID file. The kernel grants it to exactly one process
    at a time and releases it automatically when the owning process exits or
    crashes, so there is no stale-lock reclaim path to race on. The owner's
    PID is written into the file for diagnostics only; it is never used to
    decide ownership. Re-acquiring within the same process is allowed.
    """
    import fcntl

    os.makedirs(run_dir, exist_ok=True)
    lock_path = os.path.join(run_dir, LOCK_FILENAME)
    if lock_path in _HELD_LOCKS:
        return lock_path

    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        raise RuntimeError(f"run directory {run_dir!r} is already owned by another active process")
    os.ftruncate(lock_fd, 0)
    os.write(lock_fd, str(os.getpid()).encode("utf-8"))
    _HELD_LOCKS[lock_path] = lock_fd
    return lock_path


def release_run_lock(run_dir: str) -> None:
    """Releases this process's lock on run_dir, if held. The lock file itself is
    left in place: deleting it would let a waiting process lock an unlinked
    file while a new one is created."""
    import fcntl

    lock_path = os.path.join(run_dir, LOCK_FILENAME)
    lock_fd = _HELD_LOCKS.pop(lock_path, None)
    if lock_fd is None:
        return
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write_json(path: str, payload: dict[str, Any]) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@dataclass
class RunState:
    """The full persisted lifecycle state for one run."""

    run_id: str
    run_dir: str
    stages: dict[str, str] = field(default_factory=dict)
    resources: dict[str, str] = field(default_factory=dict)
    resource_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    allocated_port: int | None = None
    idempotency_key: str | None = None
    completed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    # -- paths -----------------------------------------------------------
    @property
    def state_path(self) -> str:
        return os.path.join(self.run_dir, "state.json")

    @property
    def events_path(self) -> str:
        return os.path.join(self.run_dir, "events.jsonl")

    # -- construction / persistence --------------------------------------
    @classmethod
    def new(cls, run_id: str, run_dir: str, stage_names: list[str]) -> "RunState":
        state = cls(
            run_id=run_id,
            run_dir=run_dir,
            stages={name: STAGE_PENDING for name in stage_names},
        )
        os.makedirs(run_dir, exist_ok=True)
        state._record_event("run_created", {"run_id": run_id, "stages": stage_names})
        state.save()
        return state

    @classmethod
    def load(cls, run_dir: str) -> "RunState":
        state_path = os.path.join(run_dir, "state.json")
        with open(state_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return cls(
            run_id=payload["run_id"],
            run_dir=run_dir,
            stages=dict(payload.get("stages", {})),
            resources=dict(payload.get("resources", {})),
            resource_meta={k: dict(v) for k, v in payload.get("resource_meta", {}).items()},
            allocated_port=payload.get("allocated_port"),
            idempotency_key=payload.get("idempotency_key"),
            completed=bool(payload.get("completed", False)),
            extra=dict(payload.get("extra", {})),
        )

    @classmethod
    def exists(cls, run_dir: str) -> bool:
        return os.path.exists(os.path.join(run_dir, "state.json"))

    def save(self) -> None:
        payload = {
            "run_id": self.run_id,
            "stages": self.stages,
            "resources": self.resources,
            "resource_meta": self.resource_meta,
            "allocated_port": self.allocated_port,
            "idempotency_key": self.idempotency_key,
            "completed": self.completed,
            "extra": self.extra,
        }
        _atomic_write_json(self.state_path, payload)

    def _record_event(self, event_type: str, data: dict[str, Any]) -> None:
        os.makedirs(self.run_dir, exist_ok=True)
        record = {"time": _now_iso(), "type": event_type, **data}
        with open(self.events_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    # -- stage transitions -------------------------------------------------
    def stage_status(self, stage: str) -> str:
        return self.stages.get(stage, STAGE_PENDING)

    def transition_stage(self, stage: str, new_status: str) -> None:
        current = self.stages.get(stage, STAGE_PENDING)
        allowed = _STAGE_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise IllegalTransitionError(
                f"stage {stage!r}: illegal transition {current!r} -> {new_status!r}"
            )
        self.stages[stage] = new_status
        self._record_event("stage_transition", {"stage": stage, "from": current, "to": new_status})
        self.save()

    # -- resource transitions ------------------------------------------------
    def resource_status(self, resource_id: str) -> str:
        return self.resources.get(resource_id, RESOURCE_REQUESTED)

    def transition_resource(self, resource_id: str, new_status: str, **meta: Any) -> None:
        current = self.resources.get(resource_id, None)
        if current is None:
            if new_status != RESOURCE_REQUESTED:
                raise IllegalTransitionError(
                    f"resource {resource_id!r}: must start at {RESOURCE_REQUESTED!r}, "
                    f"got initial transition to {new_status!r}"
                )
            current = RESOURCE_REQUESTED
            self.resources[resource_id] = current
            self._record_event("resource_transition", {"resource": resource_id, "from": None, "to": current})
            self._merge_meta(resource_id, meta)
            self.save()
            return
        allowed = _RESOURCE_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise IllegalTransitionError(
                f"resource {resource_id!r}: illegal transition {current!r} -> {new_status!r}"
            )
        self.resources[resource_id] = new_status
        self._record_event("resource_transition", {"resource": resource_id, "from": current, "to": new_status})
        self._merge_meta(resource_id, meta)
        self.save()

    def _merge_meta(self, resource_id: str, meta: dict[str, Any]) -> None:
        if not meta:
            return
        existing = self.resource_meta.setdefault(resource_id, {})
        existing.update(meta)

    # -- whole-run completion -------------------------------------------------
    def mark_completed(self) -> None:
        self.completed = True
        self._record_event("run_completed", {})
        self.save()

    def is_run_complete(self) -> bool:
        return self.completed
