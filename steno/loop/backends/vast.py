"""VastBackend: the vast.ai compute backend (steno-design.md section 3, build
order step 6, point 6). Uses the ``vastai`` SDK and the call shapes already
proven in this repo (experiments/vast/bench_provision.sh,
experiments/vast/rsh.sh): search_offers with a query string and order,
create_instance(id=..., image=..., disk=..., label=..., runtype=...),
show_instances, destroy_instance(id=...), a direct-port SSH endpoint from
``public_ipaddr`` plus ``ports['22/tcp'][0]['HostPort']``, with the proxy
``ssh_host``/``ssh_port`` fallback only when no direct port answers (the ssh
proxy can deny a valid key; see experiment-journey field notes).

This is the ONLY module in steno/loop that imports ``vastai``. Importing it
without the package installed raises ImportError at import time, which
steno/loop/backends/__init__.py catches so the registry still works for the
other backends.

The API key is read from a key file (default ``~/.vast_api_key``) once, only
inside this class, and is never assigned to an attribute or otherwise made
printable: it lives in a local variable for exactly as long as it takes to
construct the SDK client, then falls out of scope.

Codex review (steno-build-wave2) fixes in this revision:
  - X-1: the installed SDK's own request-level retry (default 3 attempts,
    retried transparently inside one create_instance() call, with no label
    re-check between attempts) is disabled for this client (`retry=1`), so a
    single provision() call can never silently resubmit the creation POST.
    If create_instance() still raises, or returns a response this backend
    cannot interpret, provision() reconciles by label (accounting for
    possible propagation delay) rather than assuming failure and creating
    again; if reconciliation cannot resolve the ambiguity, it raises
    AmbiguousProvisionError instead of ever risking a second rental.
  - X-7: every SDK call goes through `_call`/`_call_with_deadline`, which
    catches any exception and raises a sanitised `BackendError` built only
    from the call's name and the exception's *type* (never `str(error)`, the
    exception object, or its __cause__/__context__ chain, any of which can
    carry the API credential -- confirmed empirically for vast.ai's
    HTTPError, which retains it in `error.response.request.headers`).
  - X-8: `show_instances()`/`show_instance()`/`destroy_instance()` responses
    are validated for shape before being trusted; `None` or a malformed
    response is treated as "unknown" (raises BackendError), never as
    absence or as acknowledged destruction. `destroy()` checks the response
    body's `success` field rather than "didn't raise".
  - X-3: no path or command is ever handed to a shell. `execute()` builds
    one already-quoted remote command string (`shlex.join`) and passes it as
    a single ssh argv element, so ssh cannot re-split it on the remote side.
    `transfer()` no longer runs any remote command at all (see X-2); scp's
    remote path segment is quoted with `shlex.quote`. Every manifest/output
    path is validated as a safe relative path
    (`compute.validate_relative_artifact_path`) before use.
  - X-2: `transfer()` requires an explicit `_destination`, scp's the file
    down, and hashes the LOCAL destination copy (not a remote `sha256sum`)
    before reporting success, so success actually proves survival past
    resource teardown.
  - X-6: `execute()` rejects a stage_plan with neither `command` nor
    `executor` (`backend.stage_plan_has_work`).
  - X-12: `quote()` now translates `cpu_ram_gb_min` too, and passes the
    intended disk allocation as `search_offers`'s `storage` argument so the
    returned `dph_total` reflects the storage this backend will actually
    request (the SDK's own default is 5 GiB; provisioning here defaults to
    40 GiB), and rejects any ComputeRequest field it does not know how to
    translate rather than silently ignoring it.
  - X-13: `execute()`/`transfer()` enforce one overall deadline that covers
    BOTH endpoint resolution (an SDK call, which can block for a while: this
    client's own per-request timeout) AND the subprocess call, instead of
    only bounding the subprocess.

No network calls are made anywhere in this module's own tests; the
conformance suite drives it through a recorded SDK double
(tests/loop/test_backend_contract.py's RecordedVastSDK).
"""

from __future__ import annotations

import shlex
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import fields
from pathlib import Path
from typing import Any

from vastai import VastAI  # the only import of this package anywhere in steno/loop

from ..backend import (
    AmbiguousProvisionError,
    BackendError,
    ComputeBackend,
    ExecuteResult,
    InspectResult,
    TransferResult,
    stage_plan_has_work,
)
from ..compute import ComputeOffer, ComputeRequest, ResourceHandle, validate_relative_artifact_path

DEFAULT_KEY_FILE = "~/.vast_api_key"
DEFAULT_SSH_OPTIONS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "ConnectTimeout=20",
    "-o", "LogLevel=ERROR",
]
DEFAULT_EXECUTE_TIMEOUT_SECONDS = 600
DEFAULT_TRANSFER_TIMEOUT_SECONDS = 600
DEFAULT_DISK_GB = 40.0

# X-1: the installed SDK defaults to 3 attempts, resubmitting a create/PUT
# after a timeout or a 5xx/429 with no label re-check between attempts. This
# client disables that (a single attempt only); provision()'s own
# reconciliation-by-label is the only retry path for an ambiguous create.
CLIENT_RETRY_ATTEMPTS = 1

# X-1: how long, and how many times, provision() waits for a just-created
# instance's label to become visible via show_instances() before giving up
# and raising AmbiguousProvisionError instead of creating again.
RECONCILE_ATTEMPTS = 5
RECONCILE_DELAY_SECONDS = 1.0

# Neutral gpu_families (steno/loop/compute.py's ComputeRequest.gpu_families)
# mapped to vast.ai's own `gpu_name` query values. This table is the one and
# only place a neutral GPU name is translated into vast's vocabulary.
NEUTRAL_GPU_FAMILY_TO_VAST_GPU_NAME = {
    "h100": "H100_NVL",
    "h200": "H200",
    "a100": "A100_SXM4",
    "l40s": "L40S",
    "rtx4090": "RTX_4090",
}

# X-13: a small, lazily-created, process-wide thread pool used only to bound
# how long a single blocking SDK call is allowed to run against a caller's
# deadline. Shared across VastBackend instances (rather than one pool per
# instance) since the SDK itself has no per-call timeout override: an
# abandoned call still runs to completion in the background (bounded by the
# client's own 120s default request timeout), so pooling threads here is
# purely about returning control to the caller promptly, not cancellation.
_DEADLINE_POOL: ThreadPoolExecutor | None = None


def _get_deadline_pool() -> ThreadPoolExecutor:
    global _DEADLINE_POOL
    if _DEADLINE_POOL is None:
        _DEADLINE_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="vast-sdk-call")
    return _DEADLINE_POOL


def _raise_sanitized(description: str, error: BaseException) -> None:
    """Raises BackendError for a failed SDK call with NO retained reference
    to the original exception: not as ``__cause__`` (``from None``), and not
    as ``__context__`` either.

    X-7's offline probe found that ``raise BackendError(...) from None``
    alone is not enough: Python still populates the new exception's
    ``__context__`` with the exception being handled, `from None` only sets
    ``__suppress_context__`` (which hides it from a *printed* traceback, not
    from an introspecting caller or a logger that walks the chain). Since an
    SDK exception can carry the API credential in its own request/response
    object, the reference itself must be dropped, not just hidden from
    display: raising once inside a nested `except` to clear
    ``__context__`` before letting it propagate further does that.
    """
    sanitized = BackendError(f"vast.ai {description} failed ({type(error).__name__})")
    try:
        raise sanitized from None
    except BackendError:
        sanitized.__context__ = None
        raise


# X-12: every ComputeRequest field this backend knows how to translate into
# a vast.ai query clause (or otherwise account for, like `image`, which is
# not a search filter but IS used by provision()). A field set on the
# request that is not in this set is rejected rather than silently ignored,
# so a future ComputeRequest field added without updating this file fails
# loudly instead of quietly under-constraining the search.
_TRANSLATED_REQUEST_FIELDS = {
    "gpu_count", "gpu_memory_gb_min", "gpu_families", "cpu_ram_gb_min",
    "disk_gb_min", "network_down_mbps_min", "image", "max_hourly_usd",
    "reliability_min", "requires_direct_ssh",
}


class VastBackend(ComputeBackend):
    name = "vast"
    capabilities: dict[str, Any] = {"credit_lookup": True}

    def __init__(
        self,
        *,
        backend_options: dict[str, Any] | None = None,
        key_file: str = DEFAULT_KEY_FILE,
        client: Any | None = None,
    ) -> None:
        """``client`` lets tests substitute a recorded SDK double (see
        tests/loop/test_backend_contract.py) with the same method names as
        ``vastai.VastAI`` without ever touching a real key file or network."""
        self._options = backend_options or {}
        self._client = client if client is not None else self._build_client(key_file)
        self._created_at: dict[str, float] = {}

    @staticmethod
    def _build_client(key_file: str) -> VastAI:
        key_path = Path(key_file).expanduser()
        try:
            with open(key_path, "r", encoding="utf-8") as handle:
                api_key = handle.read().strip()
            return VastAI(api_key=api_key, retry=CLIENT_RETRY_ATTEMPTS)  # api_key never assigned to self
        except OSError as error:
            # A file-not-found/permission message names only the path, never
            # key contents; still routed through the same sanitised path.
            _raise_sanitized(f"reading key file {key_file!r}", error)
        except Exception as error:
            _raise_sanitized("constructing the vast.ai client", error)

    def __repr__(self) -> str:  # never let a default repr risk echoing the client/key
        return f"VastBackend(name={self.name!r})"

    # --- sanitised, deadline-bounded SDK call wrapper (X-7, X-13) ---------

    def _call(self, description: str, fn, *args: Any, **kwargs: Any) -> Any:
        """Calls an SDK method and translates ANY exception into a sanitised
        BackendError: never re-raises the original exception, never chains it,
        and never includes its message (only its type name), since an SDK
        exception (confirmed for vast.ai's HTTPError) can carry the API
        credential in its own request/response object."""
        try:
            return fn(*args, **kwargs)
        except Exception as error:
            _raise_sanitized(description, error)

    def _call_with_deadline(self, description: str, fn, deadline: float | None, *args: Any, **kwargs: Any) -> Any:
        """Like `_call`, but bounds wall-clock time against `deadline` (an
        absolute `time.monotonic()` value), not just the caller's own
        timeout on a *subsequent* subprocess call (X-13: endpoint resolution
        must count against the same stage deadline as execution)."""
        if deadline is None:
            return self._call(description, fn, *args, **kwargs)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"{description}: no time remaining before the stage deadline")
        future = _get_deadline_pool().submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=remaining)
        except FutureTimeoutError:
            raise TimeoutError(f"{description} exceeded its {remaining:.1f}s remaining deadline budget") from None
        except Exception as error:
            _raise_sanitized(description, error)

    # --- credit preflight (build order step 8) --------------------------

    def get_available_credit(self) -> float:
        response = self._call("show_user", self._client.show_user)
        if not isinstance(response, dict) or "credit" not in response:
            raise BackendError("vast.ai show_user returned a malformed response (unknown credit)")
        return float(response["credit"])

    # --- quote (X-12) -----------------------------------------------------

    def _requested_disk_gb(self, request: ComputeRequest) -> float:
        return request.disk_gb_min or float(self._options.get("disk", DEFAULT_DISK_GB))

    def _build_query(self, request: ComputeRequest) -> str:
        def _is_set(field_name: str, value: Any) -> bool:
            if field_name == "requires_direct_ssh":
                return bool(value)  # its "unset" value is False, not None
            return value is not None

        set_fields = {f.name for f in fields(request) if _is_set(f.name, getattr(request, f.name))}
        unsupported = set_fields - _TRANSLATED_REQUEST_FIELDS
        if unsupported:
            raise BackendError(f"VastBackend cannot translate ComputeRequest field(s) {sorted(unsupported)}")

        clauses = ["rentable=true", "verified=true"]
        if request.gpu_families:
            vast_names = [
                NEUTRAL_GPU_FAMILY_TO_VAST_GPU_NAME.get(name.lower(), name)
                for name in request.gpu_families
            ]
            # search_offers takes one query string; a multi-family request
            # cannot be expressed as an OR in vast's query language, so this
            # queries the first (preferred) family. A caller wanting a
            # fallback family issues a second quote() call.
            clauses.append(f"gpu_name={vast_names[0]}")
        if request.gpu_count:
            clauses.append(f"num_gpus={request.gpu_count}")
        if request.gpu_memory_gb_min:
            # vast.ai's search query field `gpu_ram` is denominated in GB
            # (confirmed empirically before this round: querying in MB,
            # matching the offer dict's own `gpu_ram` field, returned zero
            # results). Only `>` is used, matching this repo's proven query
            # shapes; a `min` bound rounds down slightly rather than
            # excluding the boundary value.
            clauses.append(f"gpu_ram>{max(0, request.gpu_memory_gb_min - 0.01)}")
        if request.cpu_ram_gb_min:
            # X-12: added this round. NOT network-verified this round (the
            # task rules forbid any network call); assumed to follow the
            # same GB-denominated-query / MB-denominated-result-field
            # convention confirmed for `gpu_ram` above, since vast.ai's
            # search DSL treats memory fields consistently elsewhere. Verify
            # empirically (a single read-only search_offers call, same as
            # the gpu_ram check) before relying on this in a real run.
            clauses.append(f"cpu_ram>{max(0, request.cpu_ram_gb_min - 0.01)}")
        if request.disk_gb_min:
            clauses.append(f"disk_space>{request.disk_gb_min}")
        if request.network_down_mbps_min:
            clauses.append(f"inet_down>{request.network_down_mbps_min}")
        if request.reliability_min is not None:
            clauses.append(f"reliability>{request.reliability_min}")
        if request.requires_direct_ssh:
            clauses.append("direct_port_count>0")
        extra_query = self._options.get("extra_query")
        if extra_query:
            clauses.append(extra_query)
        return " ".join(clauses)

    def quote(self, request: ComputeRequest) -> list[ComputeOffer]:
        query = self._build_query(request)
        limit = self._options.get("quote_limit", 20)
        # X-12: `storage` must match what provision() will actually request,
        # since the SDK's own default (5 GiB) understates the disk this
        # backend allocates (default 40 GiB), which understates dph_total
        # and can let an offer pass a max_hourly_usd filter it should fail.
        storage = self._requested_disk_gb(request)
        offers = self._call("search_offers", self._client.search_offers, query=query, order="dph_total", limit=limit, storage=storage)
        if offers is None:
            raise BackendError("vast.ai search_offers returned no response (unknown)")
        if not isinstance(offers, list):
            raise BackendError("vast.ai search_offers returned a malformed (non-list) response")
        result = []
        for offer in offers:
            if not isinstance(offer, dict) or "id" not in offer:
                continue  # skip a malformed row rather than fail the whole quote
            hourly = float(offer.get("dph_total", 0.0))
            if request.max_hourly_usd is not None and hourly > request.max_hourly_usd:
                continue
            result.append(
                ComputeOffer(
                    offer_id=str(offer.get("id")),
                    gpu_family=str(offer.get("gpu_name", "")),
                    gpu_count=int(offer.get("num_gpus", 1) or 1),
                    gpu_memory_gb=float(offer.get("gpu_ram", 0) or 0) / 1024.0,
                    hourly_usd=hourly,
                    region=str(offer.get("geolocation", "")),
                    reliability=offer.get("reliability2"),
                    raw_provider_ref=offer,
                )
            )
        return result

    # --- provision / inspect (X-1, X-8) ------------------------------------

    def _show_instances_validated(self, description: str = "show_instances") -> list[dict]:
        """Calls show_instances() and validates the response shape. Never
        returns None-as-empty (X-8): a malformed/None response raises
        BackendError so a caller cannot mistake "unknown" for "absent"."""
        instances = self._call(description, self._client.show_instances)
        if not isinstance(instances, list):
            raise BackendError(f"vast.ai {description} returned a malformed (non-list) response")
        return instances

    def _find_instance_by_label(self, label: str) -> dict[str, Any] | None:
        for instance in self._show_instances_validated():
            if isinstance(instance, dict) and instance.get("label") == label:
                return instance
        return None

    def _endpoint(self, instance: dict[str, Any]) -> tuple[str, int] | None:
        ports = (instance.get("ports") or {}).get("22/tcp") or []
        direct_host = instance.get("public_ipaddr")
        if direct_host and ports:
            return direct_host, int(ports[0]["HostPort"])
        proxy_host, proxy_port = instance.get("ssh_host"), instance.get("ssh_port")
        if proxy_host and proxy_port:
            return proxy_host, int(proxy_port)
        return None

    def provision(self, compute: dict[str, Any], idempotency_key: str) -> ResourceHandle:
        # Idempotency: a resumed run must never rent a second box for the
        # same key. The instance label IS the idempotency key.
        existing = self._find_instance_by_label(idempotency_key)
        if existing is not None:
            return self._handle_from_instance(existing)

        request = ComputeRequest.from_dict(compute.get("request"))
        backend_options = compute.get("backend_options", compute)
        offers = self.quote(request)
        if not offers:
            raise BackendError(f"no vast.ai offer matches request {request.to_dict()!r}")
        offer = offers[0]

        try:
            result = self._call(
                "create_instance", self._client.create_instance,
                id=int(offer.offer_id),
                image=request.image or backend_options.get("image"),
                disk=self._requested_disk_gb(request),
                label=idempotency_key,
                runtype=backend_options.get("runtype", "ssh"),
                ssh=True,
                direct=bool(request.requires_direct_ssh),
            )
        except BackendError:
            # X-1: the create call itself failed (raised). We cannot tell
            # whether the provider actually created the instance before the
            # failure (a lost response looks identical to a rejected
            # request). Reconcile by label before concluding anything, and
            # NEVER call create_instance again in this same attempt.
            return self._reconcile_or_raise(idempotency_key, "create_instance raised")

        instance_id = result.get("new_contract") if isinstance(result, dict) else None
        if not instance_id:
            # The call returned without raising, but the response does not
            # confirm creation either: same ambiguity as above.
            return self._reconcile_or_raise(idempotency_key, f"create_instance returned no new_contract: {result!r}")

        self._created_at[str(instance_id)] = time.time()
        instance = self._call("show_instance", self._client.show_instance, id=instance_id)
        if not isinstance(instance, dict):
            instance = {"id": instance_id}
        return self._handle_from_instance(instance, hourly_usd=offer.hourly_usd)

    def _reconcile_or_raise(self, idempotency_key: str, cause: str) -> ResourceHandle:
        """X-1: after an ambiguous create, poll show_instances() for the
        label (accounting for possible propagation delay) instead of either
        assuming failure (and creating again, risking a duplicate rental) or
        assuming success (and fabricating a handle). If reconciliation still
        cannot find the label, stop: raise AmbiguousProvisionError rather
        than ever calling create_instance a second time for this attempt."""
        for attempt in range(RECONCILE_ATTEMPTS):
            try:
                found = self._find_instance_by_label(idempotency_key)
            except BackendError:
                found = None
            if found is not None:
                return self._handle_from_instance(found)
            if attempt < RECONCILE_ATTEMPTS - 1:
                time.sleep(RECONCILE_DELAY_SECONDS)
        raise AmbiguousProvisionError(
            f"vast.ai provision() outcome unknown for label {idempotency_key!r} ({cause}); "
            f"reconciliation found no matching instance after {RECONCILE_ATTEMPTS} attempts. "
            "Refusing to create again: reconcile against the provider by hand before retrying."
        )

    def _handle_from_instance(self, instance: dict[str, Any], hourly_usd: float | None = None) -> ResourceHandle:
        endpoint = self._endpoint(instance)
        host, port = endpoint if endpoint else ("", 0)
        return ResourceHandle(
            resource_id=str(instance.get("id")),
            backend_name=self.name,
            host=host,
            port=port,
            user="root",
            hourly_usd=hourly_usd if hourly_usd is not None else float(instance.get("dph_total", 0.0) or 0.0),
        )

    def inspect(self, resource_id: str) -> InspectResult:
        try:
            numeric_id = int(resource_id)
        except (TypeError, ValueError):
            # Not a vast.ai instance id at all (never provisioned by us, or a
            # stale/foreign id): unknown, exactly like an id absent from
            # show_instances(). Never an exception; see the class contract.
            return InspectResult(resource_id=resource_id, exists=False, reachable=False, status_text="unknown")
        instance = self._call("show_instance", self._client.show_instance, id=numeric_id)
        if not instance:
            return InspectResult(resource_id=resource_id, exists=False, reachable=False, status_text="unknown")
        if not isinstance(instance, dict):
            raise BackendError("vast.ai show_instance returned a malformed response")
        status = str(instance.get("actual_status") or instance.get("cur_state") or "")
        reachable = status.lower() in {"running"} and self._endpoint(instance) is not None
        return InspectResult(resource_id=resource_id, exists=True, reachable=reachable, status_text=status)

    # --- execute / transfer (X-2, X-3, X-6, X-13) --------------------------

    def _resolve_endpoint_for(self, resource_id: str, deadline: float | None = None) -> tuple[str, int]:
        instance = self._call_with_deadline("show_instance", self._client.show_instance, deadline, id=int(resource_id))
        if not instance:
            raise BackendError(f"instance {resource_id} not found")
        if not isinstance(instance, dict):
            raise BackendError("vast.ai show_instance returned a malformed response")
        endpoint = self._endpoint(instance)
        if endpoint is None:
            raise BackendError(f"instance {resource_id} has no reachable endpoint yet")
        return endpoint

    def execute(self, resource_id: str, stage_plan: dict[str, Any]) -> ExecuteResult:
        executor = stage_plan.get("executor")
        if executor is not None:
            return executor(resource_id, stage_plan)

        # X-6: a plan naming neither an executor nor a command is not a
        # legitimate no-op for a real backend.
        if not stage_plan_has_work(stage_plan):
            return ExecuteResult(
                ok=False, kind="infra_failure",
                detail="stage_plan has neither 'command' nor 'executor'; nothing to run",
            )

        command = stage_plan["command"]
        timeout = stage_plan.get("timeout_seconds", DEFAULT_EXECUTE_TIMEOUT_SECONDS)
        # X-13: one deadline covers endpoint resolution AND the subprocess,
        # so a slow/blocked SDK lookup cannot silently consume the whole
        # stage timeout before the remote command even starts.
        deadline = time.monotonic() + timeout
        try:
            host, port = self._resolve_endpoint_for(resource_id, deadline=deadline)
        except TimeoutError as error:
            return ExecuteResult(ok=False, kind="infra_failure", detail=f"endpoint resolution exceeded the stage deadline: {error}")
        except Exception as error:
            return ExecuteResult(ok=False, kind="infra_failure", detail=f"could not resolve ssh endpoint: {type(error).__name__}: {error}")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ExecuteResult(ok=False, kind="infra_failure", detail=f"stage deadline ({timeout}s) exhausted before the command could run")

        # X-3: build ONE already-quoted remote command string and pass it as
        # a single ssh argv element. ssh always hands its trailing arguments
        # to a remote shell after joining them with plain spaces; passing an
        # unquoted argv list (as before) let a remote shell metacharacter in
        # any argument escape argument boundaries (confirmed offline: a path
        # like `artifact; echo injected` produced a second remote command).
        remote_command = shlex.join(str(part) for part in command)
        argv = ["ssh", *DEFAULT_SSH_OPTIONS, "-p", str(port), f"root@{host}", remote_command]
        try:
            completed = subprocess.run(argv, timeout=remaining, capture_output=True, text=True, check=False)
        except subprocess.TimeoutExpired:
            return ExecuteResult(ok=False, kind="infra_failure", detail=f"stage command timed out after {timeout}s (deadline-bounded)")
        except OSError as error:
            return ExecuteResult(ok=False, kind="infra_failure", detail=f"ssh failed to launch: {type(error).__name__}: {error}")
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
            return ExecuteResult(ok=False, kind="task_failure", detail=f"exit {completed.returncode}: {detail}")
        return ExecuteResult(ok=True, kind="ok", output_manifest=dict(stage_plan.get("outputs", {})))

    def transfer(self, resource_id: str, manifest: dict[str, Any]) -> TransferResult:
        # X-2: an explicit destination is required; without one nothing is
        # actually retrieved, and "success" would be indistinguishable from
        # data loss once the resource is destroyed.
        destination = manifest.get("_destination")
        if not destination:
            return TransferResult(ok=False, detail="transfer requires an explicit manifest['_destination'] local directory")
        destination_dir = Path(destination)

        paths = {k: v for k, v in manifest.items() if k != "_destination"}
        timeout = manifest.get("_timeout_seconds", DEFAULT_TRANSFER_TIMEOUT_SECONDS)
        deadline = time.monotonic() + timeout
        try:
            host, port = self._resolve_endpoint_for(resource_id, deadline=deadline)
        except Exception as error:
            return TransferResult(ok=False, detail=f"could not resolve ssh endpoint: {type(error).__name__}: {error}")

        mismatched: list[str] = []
        copied: dict[str, str] = {}
        for remote_path, expected_hash in paths.items():
            try:
                validate_relative_artifact_path(remote_path)
            except Exception as error:
                mismatched.append(remote_path)
                continue
            dest_path = destination_dir / remote_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                mismatched.append(remote_path)
                continue
            # X-3: quote the remote path segment. scp's legacy remote-copy
            # protocol can invoke a remote shell to interpret this path, so
            # an unquoted metacharacter here is exactly as dangerous as one
            # in a remote command string.
            remote_spec = f"root@{host}:{shlex.quote(remote_path)}"
            scp_argv = ["scp", "-q", *DEFAULT_SSH_OPTIONS, "-P", str(port), remote_spec, str(dest_path)]
            try:
                subprocess.run(scp_argv, timeout=remaining, check=True, capture_output=True)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
                mismatched.append(remote_path)
                continue
            if not dest_path.is_file():
                mismatched.append(remote_path)
                continue
            # X-2: hash the LOCAL destination copy, not a remote `sha256sum`
            # (which is both a shell-injection surface, X-3, and no proof
            # the bytes that actually landed locally are intact).
            actual_hash = _sha256_file(dest_path)
            if actual_hash != expected_hash:
                mismatched.append(remote_path)
                continue
            copied[remote_path] = actual_hash
        if mismatched:
            return TransferResult(ok=False, manifest=copied, detail=f"missing or mismatched: {mismatched}")
        return TransferResult(ok=True, manifest=copied)

    # --- cost / destroy (X-8) -----------------------------------------------

    def cost(self, resource_id: str) -> float:
        try:
            instance = self._call("show_instance", self._client.show_instance, id=int(resource_id))
        except BackendError:
            return 0.0  # cost() must never raise for an ordinary transient failure; see the contract
        if not isinstance(instance, dict):
            return 0.0
        dph_total = float(instance.get("dph_total", 0.0) or 0.0)
        started = instance.get("start_date") or self._created_at.get(resource_id)
        if not started:
            return 0.0
        elapsed_hours = max(0.0, (time.time() - float(started)) / 3600.0)
        return round(elapsed_hours * dph_total, 6)

    def destroy(self, resource_id: str) -> bool:
        try:
            response = self._call("destroy_instance", self._client.destroy_instance, id=int(resource_id))
        except BackendError:
            return False
        # X-8: validate the acknowledgement rather than treating "did not
        # raise" as success. The SDK's own CLI checks `response["success"]`;
        # a malformed (non-dict) response is also not an acknowledgement.
        return isinstance(response, dict) and bool(response.get("success"))

    def confirm_destroyed(self, resource_id: str) -> bool | None:
        try:
            instances = self._show_instances_validated()
        except BackendError:
            return None  # an API error, or a malformed response, means unknown, never destroyed (X-8)
        return not any(isinstance(instance, dict) and str(instance.get("id")) == str(resource_id) for instance in instances)


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
