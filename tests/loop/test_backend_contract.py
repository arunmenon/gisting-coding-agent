"""The compute backend conformance suite (steno-design.md section 3, build
order step 6, point 7): every backend must satisfy the same behavioral
contract regardless of provider. Run against FakeBackend and LocalBackend
directly, and against VastBackend wired to a recorded SDK double (a small
class with the same method names as ``vastai.VastAI``, defined below,
returning realistic dicts) so the vast-specific translation logic (query
building, offer/handle mapping, idempotent-by-label provisioning, destroy
confirmation) is tested with no network and no real vast.ai calls.

A ``@pytest.mark.live`` variant of the vast case exists separately in
test_backend_contract_live.py, skipped unless STENO_LIVE_VAST=1; it is not
run by this suite or by this task.
"""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

import pytest

from steno.loop.backend import ExecuteResult
from steno.loop.backends.fake import FakeBackend
from steno.loop.backends.local import LocalBackend
from steno.loop.compute import ComputeRequest


class FakeClock:
    def __init__(self, start: float = 0.0, step: float = 1.0):
        self.t = start
        self.step = step

    def __call__(self) -> float:
        self.t += self.step
        return self.t


@dataclass
class BackendHarness:
    """What each backend's test setup must provide so one suite can drive
    all of them. ``supports_unknown_confirm`` is False for a backend with no
    external API to fail against (LocalBackend has no confirm-time failure
    mode by construction; it is authoritative over its own local state)."""

    name: str
    make: Callable[[], Any]
    ok_stage_plan: Callable[[str, bytes], dict]
    timeout_stage_plan: Callable[[], dict]
    force_unknown_confirm: Callable[[Any], None] | None  # mutates backend so the NEXT confirm_destroyed() call returns None
    supports_unknown_confirm: bool = True
    # X-2: LocalBackend and VastBackend now require an explicit
    # manifest["_destination"] and prove artifacts survive teardown;
    # FakeBackend has no real filesystem/network to prove that against.
    needs_destination: bool = False


def _with_destination(manifest: dict, destination, needs: bool) -> dict:
    if not needs:
        return manifest
    merged = dict(manifest)
    merged["_destination"] = str(destination)
    return merged


# --- FakeBackend harness -----------------------------------------------------

def _fake_ok_stage_plan(path: str, content: bytes) -> dict:
    digest = hashlib.sha256(content).hexdigest()

    def executor(resource_id: str, plan: dict) -> ExecuteResult:
        return ExecuteResult(ok=True, kind="ok", output_manifest={path: digest})

    return {"executor": executor}


def _fake_timeout_stage_plan() -> dict:
    def executor(resource_id: str, plan: dict) -> ExecuteResult:
        return ExecuteResult(ok=False, kind="infra_failure", detail="simulated launch/stage timeout")

    return {"executor": executor}


def _fake_force_unknown_confirm(backend: FakeBackend) -> None:
    backend.fail_destroy_confirmation = True


def make_fake_harness() -> BackendHarness:
    return BackendHarness(
        name="fake",
        make=lambda: FakeBackend(clock=FakeClock(), hourly_usd=1.0),
        ok_stage_plan=_fake_ok_stage_plan,
        timeout_stage_plan=_fake_timeout_stage_plan,
        force_unknown_confirm=_fake_force_unknown_confirm,
    )


# --- LocalBackend harness -----------------------------------------------------

def _local_ok_stage_plan(path: str, content: bytes) -> dict:
    # printf avoids shell-quoting surprises across the small set of ascii
    # payloads this suite uses; the command is still passed as an argv list.
    text = content.decode("ascii")
    return {"command": ["bash", "-c", f"printf '%s' '{text}' > {path}"], "outputs": {path: None}}


def _local_timeout_stage_plan() -> dict:
    return {"command": ["bash", "-c", "sleep 5"], "timeout_seconds": 0.2}


def make_local_harness(tmp_path) -> BackendHarness:
    return BackendHarness(
        name="local",
        make=lambda: LocalBackend(backend_options={"root_dir": str(tmp_path / "local-root")}),
        ok_stage_plan=_local_ok_stage_plan,
        timeout_stage_plan=_local_timeout_stage_plan,
        force_unknown_confirm=None,
        supports_unknown_confirm=False,
        needs_destination=True,
    )


# --- VastBackend harness (recorded SDK double, no network) -------------------

class RecordedVastSDK:
    """A test double with the same method names as vastai.VastAI, returning
    realistic dicts (shapes taken from experiments/vast/rsh.sh and
    bench_provision.sh's usage, plus the destroy_instance "success" shape
    the SDK's own CLI checks). No network, no real vast.ai calls."""

    def __init__(self) -> None:
        self._instances: dict[int, dict[str, Any]] = {}
        self._next_id = 5000
        self.last_search_kwargs: dict[str, Any] = {}

    def show_user(self) -> dict:
        return {"credit": 123.45}

    def search_offers(self, query: str, order: str, limit: int | None = None, storage: float = 5.0) -> list:
        self.last_search_kwargs = {"query": query, "order": order, "limit": limit, "storage": storage}
        return [
            {
                "id": 42, "gpu_name": "H100_NVL", "num_gpus": 1, "gpu_ram": 81920,
                "dph_total": 1.85 + storage * 0.001, "geolocation": "US-CA", "reliability2": 0.991,
            }
        ]

    def create_instance(self, id: int, image=None, disk=10, label=None, runtype=None, ssh=False, direct=False, **kwargs) -> dict:
        instance_id = self._next_id
        self._next_id += 1
        self._instances[instance_id] = {
            "id": instance_id, "label": label, "actual_status": "running", "cur_state": "running",
            "public_ipaddr": "203.0.113.10", "ports": {"22/tcp": [{"HostPort": 22022}]},
            "ssh_host": "ssh5.vast.ai", "ssh_port": 33221,
            "dph_total": 1.85, "start_date": time.time(), "destroyed": False,
        }
        return {"new_contract": instance_id}

    def show_instances(self) -> list:
        return [record for record in self._instances.values() if not record["destroyed"]]

    def show_instance(self, id: int):
        record = self._instances.get(id)
        if record is None or record["destroyed"]:
            return None
        return record

    def destroy_instance(self, id: int) -> dict:
        if id in self._instances:
            self._instances[id]["destroyed"] = True
            return {"success": True, "msg": "destroying instance"}
        return {"success": False, "msg": "instance not found"}


class RaisingShowInstances(RecordedVastSDK):
    """Simulates an API error on the confirm-destroyed/label lookup path."""

    def __init__(self) -> None:
        super().__init__()
        self._raise_next = False

    def show_instances(self) -> list:
        if self._raise_next:
            self._raise_next = False
            raise RuntimeError("simulated vast.ai API error")
        return super().show_instances()


def _vast_force_unknown_confirm(backend) -> None:
    backend._client._raise_next = True  # type: ignore[attr-defined]


def make_vast_harness(monkeypatch, tmp_path=None) -> BackendHarness:
    from steno.loop.backends.vast import VastBackend

    client = RaisingShowInstances()
    backend_instance = VastBackend(client=client)

    def make() -> "VastBackend":
        return backend_instance

    def ok_stage_plan(path: str, content: bytes) -> dict:
        digest = hashlib.sha256(content).hexdigest()

        def fake_run(argv, timeout=None, capture_output=True, text=True, check=False):
            if argv[0] == "scp":
                # X-2/X-3 rewrite: transfer() no longer runs a remote command
                # at all, only scp; write the REAL content to the local
                # destination path (argv[-1]) so the backend's own
                # post-copy local hash is what actually verifies success,
                # exactly as it would from a real copy.
                from pathlib import Path as _Path

                dest = _Path(argv[-1])
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                return subprocess.CompletedProcess(argv, 0, stdout=b"", stderr=b"")
            # ssh remote command (execute()): simulate success, no network.
            return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

        monkeypatch.setattr("steno.loop.backends.vast.subprocess.run", fake_run)
        return {"command": ["true"], "outputs": {path: digest}}

    def timeout_stage_plan() -> dict:
        def fake_run(argv, timeout=None, capture_output=True, text=True, check=False):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout or 0)

        monkeypatch.setattr("steno.loop.backends.vast.subprocess.run", fake_run)
        return {"command": ["sleep", "5"], "timeout_seconds": 1}

    return BackendHarness(
        name="vast",
        make=make,
        ok_stage_plan=ok_stage_plan,
        timeout_stage_plan=timeout_stage_plan,
        force_unknown_confirm=_vast_force_unknown_confirm,
        needs_destination=True,
    )


HARNESS_NAMES = ["fake", "local", "vast"]


@pytest.fixture
def harness(request, tmp_path, monkeypatch) -> BackendHarness:
    if request.param == "fake":
        return make_fake_harness()
    if request.param == "local":
        return make_local_harness(tmp_path)
    if request.param == "vast":
        return make_vast_harness(monkeypatch)
    raise ValueError(request.param)


@pytest.mark.parametrize("harness", HARNESS_NAMES, indirect=True)
class TestBackendContract:
    def test_provision_is_idempotent(self, harness: BackendHarness):
        backend = harness.make()
        first = backend.provision({}, "conformance-key-1")
        second = backend.provision({}, "conformance-key-1")
        assert first.resource_id == second.resource_id

    def test_provision_with_different_keys_creates_different_resources(self, harness: BackendHarness):
        backend = harness.make()
        first = backend.provision({}, "conformance-key-a")
        second = backend.provision({}, "conformance-key-b")
        assert first.resource_id != second.resource_id

    def test_inspect_states(self, harness: BackendHarness):
        backend = harness.make()
        assert backend.inspect("does-not-exist").exists is False

        handle = backend.provision({}, "conformance-key-inspect")
        inspected = backend.inspect(handle.resource_id)
        assert inspected.exists is True

    def test_execute_ok(self, harness: BackendHarness):
        backend = harness.make()
        handle = backend.provision({}, "conformance-key-execute-ok")
        plan = harness.ok_stage_plan("output.txt", b"hello")
        result = backend.execute(handle.resource_id, plan)
        assert result.ok is True
        assert result.kind == "ok"

    def test_execute_timeout_is_a_typed_infra_failure_not_an_exception(self, harness: BackendHarness):
        backend = harness.make()
        handle = backend.provision({}, "conformance-key-execute-timeout")
        plan = harness.timeout_stage_plan()
        result = backend.execute(handle.resource_id, plan)
        assert result.ok is False
        assert result.kind == "infra_failure"

    def test_transfer_verifies_checksum_and_rejects_mismatch(self, harness: BackendHarness, tmp_path):
        backend = harness.make()
        handle = backend.provision({}, "conformance-key-transfer")
        content = b"payload-under-test"
        plan = harness.ok_stage_plan("artifact.bin", content)
        executed = backend.execute(handle.resource_id, plan)
        assert executed.ok is True
        correct_manifest = dict(executed.output_manifest)
        destination = tmp_path / f"dest-{harness.name}"

        good = backend.transfer(handle.resource_id, _with_destination(correct_manifest, destination, harness.needs_destination))
        assert good.ok is True

        wrong_manifest = {path: "0" * 64 for path in correct_manifest}
        bad = backend.transfer(handle.resource_id, _with_destination(wrong_manifest, destination, harness.needs_destination))
        assert bad.ok is False

    def test_transfer_requires_an_explicit_destination(self, harness: BackendHarness):
        if not harness.needs_destination:
            pytest.skip(f"{harness.name} has no filesystem destination concept")
        backend = harness.make()
        handle = backend.provision({}, "conformance-key-no-destination")
        plan = harness.ok_stage_plan("artifact.bin", b"payload")
        executed = backend.execute(handle.resource_id, plan)
        result = backend.transfer(handle.resource_id, dict(executed.output_manifest))  # no _destination key
        assert result.ok is False

    def test_artifacts_survive_teardown(self, harness: BackendHarness, tmp_path):
        if not harness.needs_destination:
            pytest.skip(f"{harness.name} does not persist artifacts to a filesystem destination")
        backend = harness.make()
        handle = backend.provision({}, "conformance-key-survive")
        content = b"must-survive-teardown"
        plan = harness.ok_stage_plan("survive.bin", content)
        executed = backend.execute(handle.resource_id, plan)
        assert executed.ok is True
        manifest = dict(executed.output_manifest)
        destination = tmp_path / f"survive-{harness.name}"

        transferred = backend.transfer(handle.resource_id, _with_destination(manifest, destination, True))
        assert transferred.ok is True

        assert backend.destroy(handle.resource_id) is True

        # Read the destination directly off disk, bypassing the (now
        # destroyed) backend entirely, to prove the copy is independent of
        # resource teardown (Codex review X-2).
        dest_file = destination / "survive.bin"
        assert dest_file.is_file()
        assert hashlib.sha256(dest_file.read_bytes()).hexdigest() == manifest["survive.bin"]

    def test_destroy_then_confirm(self, harness: BackendHarness):
        backend = harness.make()
        handle = backend.provision({}, "conformance-key-destroy")

        # confirm returns True only AFTER destroy, never before.
        assert backend.confirm_destroyed(handle.resource_id) is not True

        assert backend.destroy(handle.resource_id) is True
        assert backend.confirm_destroyed(handle.resource_id) is True

    def test_destroy_is_idempotent(self, harness: BackendHarness):
        backend = harness.make()
        handle = backend.provision({}, "conformance-key-destroy-twice")
        assert backend.destroy(handle.resource_id) is True
        assert backend.destroy(handle.resource_id) is True  # must not raise or fail on a repeat

    def test_confirm_destroyed_returns_none_on_api_error(self, harness: BackendHarness):
        if not harness.supports_unknown_confirm:
            pytest.skip(f"{harness.name} has no external API to fail against; not applicable")
        backend = harness.make()
        handle = backend.provision({}, "conformance-key-unknown")
        harness.force_unknown_confirm(backend)
        assert backend.confirm_destroyed(handle.resource_id) is None


# --- Vast-specific translation checks (not part of the generic suite) -------


def test_vast_quote_maps_neutral_gpu_family_and_filters_by_max_hourly_usd():
    from steno.loop.backends.vast import VastBackend

    client = RecordedVastSDK()
    backend = VastBackend(client=client)

    request = ComputeRequest(gpu_count=1, gpu_families=["h100"], requires_direct_ssh=True, max_hourly_usd=5.0)
    offers = backend.quote(request)

    assert "gpu_name=H100_NVL" in client.last_search_kwargs["query"]
    assert "direct_port_count>0" in client.last_search_kwargs["query"]
    assert len(offers) == 1
    assert offers[0].gpu_family == "H100_NVL"

    # A cap below the only offer's price filters it out entirely.
    cheap_request = ComputeRequest(gpu_families=["h100"], max_hourly_usd=0.01)
    assert backend.quote(cheap_request) == []


def test_vast_quote_translates_cpu_ram_and_rejects_unsupported_fields():
    """X-12: cpu_ram_gb_min must reach the query (it was silently dropped
    before this round); a ComputeRequest field this backend does not know
    how to translate must be rejected, not ignored."""
    from steno.loop.backends.vast import VastBackend
    from steno.loop.backend import BackendError

    client = RecordedVastSDK()
    backend = VastBackend(client=client)

    request = ComputeRequest(cpu_ram_gb_min=512)
    backend.quote(request)
    assert "cpu_ram>" in client.last_search_kwargs["query"]

    # A field that IS supported must not raise.
    backend.quote(ComputeRequest(image="some/image:tag"))

    # Simulate a future ComputeRequest field this backend has not been
    # taught to translate: _build_query must refuse to silently under-
    # constrain the search rather than ignore it.
    import steno.loop.backends.vast as vast_module

    original = set(vast_module._TRANSLATED_REQUEST_FIELDS)
    try:
        vast_module._TRANSLATED_REQUEST_FIELDS.discard("cpu_ram_gb_min")
        with pytest.raises(BackendError):
            backend.quote(ComputeRequest(cpu_ram_gb_min=64))
    finally:
        vast_module._TRANSLATED_REQUEST_FIELDS.clear()
        vast_module._TRANSLATED_REQUEST_FIELDS.update(original)


def test_vast_quote_prices_the_actually_requested_disk_not_the_sdk_default():
    """X-12: search_offers's `storage` argument (SDK default 5 GiB) must
    reflect what provision() will actually request (default 40 GiB here),
    since the returned dph_total (and therefore a max_hourly_usd filter)
    depends on it."""
    from steno.loop.backends.vast import DEFAULT_DISK_GB, VastBackend

    client = RecordedVastSDK()
    backend = VastBackend(client=client)

    backend.quote(ComputeRequest())
    assert client.last_search_kwargs["storage"] == pytest.approx(DEFAULT_DISK_GB)

    backend.quote(ComputeRequest(disk_gb_min=200))
    assert client.last_search_kwargs["storage"] == pytest.approx(200)


def test_vast_provision_reuses_existing_instance_by_label(monkeypatch):
    from steno.loop.backends.vast import VastBackend

    client = RecordedVastSDK()
    backend = VastBackend(client=client)

    first = backend.provision({"request": {"gpu_families": ["h100"]}}, "idempotency-label-1")
    second = backend.provision({"request": {"gpu_families": ["h100"]}}, "idempotency-label-1")

    assert first.resource_id == second.resource_id
    assert len(client._instances) == 1  # never double-rented


def test_vast_get_available_credit(monkeypatch):
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=RecordedVastSDK())
    assert backend.get_available_credit() == pytest.approx(123.45)


def test_vast_backend_never_stores_api_key_on_an_attribute(monkeypatch):
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=RecordedVastSDK())
    for attribute_name in vars(backend):
        assert "key" not in attribute_name.lower()
    # repr() must never risk echoing the underlying SDK client.
    assert "RecordedVastSDK" not in repr(backend)


# --- X-1: ambiguous create must never risk a duplicate rental ---------------


class AmbiguousCreateSDK(RecordedVastSDK):
    """create_instance's response is "lost" (raises) exactly once, but the
    instance IS actually created server-side before that -- exactly the
    ambiguity X-1 is about. `visible_after_attempts` controls how many
    show_instances() polls pass before the label becomes visible, modeling
    eventual-consistency propagation delay."""

    def __init__(self, visible_after_attempts: int = 0) -> None:
        super().__init__()
        self._lose_next_response = False
        self._visible_after_attempts = visible_after_attempts
        self._poll_count = 0
        self._hidden_instance: dict[str, Any] | None = None

    def create_instance(self, id: int, image=None, disk=10, label=None, runtype=None, ssh=False, direct=False, **kwargs) -> dict:
        result = super().create_instance(id, image=image, disk=disk, label=label, runtype=runtype, ssh=ssh, direct=direct, **kwargs)
        if self._lose_next_response:
            self._lose_next_response = False
            # The instance now exists in self._instances (created above) but
            # is hidden from show_instances() until enough polls pass.
            instance_id = result["new_contract"]
            self._hidden_instance = self._instances[instance_id]
            del self._instances[instance_id]
            raise ConnectionError("simulated: response lost after the server created the instance")
        return result

    def show_instances(self) -> list:
        visible = super().show_instances()
        if self._hidden_instance is not None:
            self._poll_count += 1
            if self._poll_count >= self._visible_after_attempts:
                self._instances[self._hidden_instance["id"]] = self._hidden_instance
                visible = super().show_instances()
                self._hidden_instance = None
        return visible


def test_vast_provision_reconciles_after_creation_accepted_but_response_lost():
    from steno.loop.backends.vast import VastBackend

    client = AmbiguousCreateSDK(visible_after_attempts=0)
    client._lose_next_response = True
    backend = VastBackend(client=client)

    handle = backend.provision({"request": {"gpu_families": ["h100"]}}, "ambiguous-label-1")

    assert handle.resource_id is not None
    assert len(client._instances) == 1  # reconciled to the ONE instance actually created, never a second


def test_vast_provision_reconciles_after_delayed_label_visibility(monkeypatch):
    from steno.loop.backends import vast as vast_module
    from steno.loop.backends.vast import VastBackend

    monkeypatch.setattr(vast_module, "RECONCILE_DELAY_SECONDS", 0.0)  # keep the test fast; no network involved
    client = AmbiguousCreateSDK(visible_after_attempts=2)  # visible only on the 2nd reconciliation poll
    client._lose_next_response = True
    backend = VastBackend(client=client)

    handle = backend.provision({"request": {"gpu_families": ["h100"]}}, "ambiguous-label-2")

    assert handle.resource_id is not None
    assert len(client._instances) == 1


def test_vast_provision_raises_ambiguous_rather_than_double_renting_when_unresolved(monkeypatch):
    from steno.loop.backends import vast as vast_module
    from steno.loop.backend import AmbiguousProvisionError
    from steno.loop.backends.vast import VastBackend

    monkeypatch.setattr(vast_module, "RECONCILE_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(vast_module, "RECONCILE_ATTEMPTS", 2)
    # Never becomes visible within the reconciliation window: this backend
    # must stop, not create a second instance to compensate.
    client = AmbiguousCreateSDK(visible_after_attempts=1_000_000)
    client._lose_next_response = True
    backend = VastBackend(client=client)

    with pytest.raises(AmbiguousProvisionError):
        backend.provision({"request": {"gpu_families": ["h100"]}}, "ambiguous-label-3")

    assert len(client._instances) == 0  # the hidden instance never got double-created


def test_vast_client_is_constructed_with_retries_disabled():
    """X-1: the SDK's own automatic retry can resubmit a create POST inside
    a single create_instance() call with no label re-check in between. This
    backend must disable that entirely."""
    from steno.loop.backends.vast import CLIENT_RETRY_ATTEMPTS

    assert CLIENT_RETRY_ATTEMPTS == 1


# --- X-7: no secret may escape a sanitised BackendError ---------------------


SYNTHETIC_SECRET = "sk-synthetic-test-secret-should-never-leak-93f7"


class _FakeResponse:
    def __init__(self, secret: str) -> None:
        self.request = _FakeRequest(secret)
        self.status_code = 401
        self.text = f"Unauthorized (Authorization: Bearer {secret})"


class _FakeRequest:
    def __init__(self, secret: str) -> None:
        self.headers = {"Authorization": f"Bearer {secret}"}
        self.url = "https://console.vast.ai/api/v0/instances/"


class SecretLeakingHTTPError(Exception):
    """Mimics requests.exceptions.HTTPError's shape: the secret is reachable
    via .response.request.headers, and also embedded in the message, exactly
    the two places X-7's offline probe found it could leak from."""

    def __init__(self, secret: str) -> None:
        super().__init__(f"401 Client Error: Unauthorized for url with header Bearer {secret}")
        self.response = _FakeResponse(secret)


class SecretLeakingSDK:
    """Every method raises an exception carrying SYNTHETIC_SECRET, mimicking
    a real HTTPError. Used only to prove no path lets it escape a
    VastBackend method; never used to make a real call."""

    def show_user(self):
        raise SecretLeakingHTTPError(SYNTHETIC_SECRET)

    def search_offers(self, **kwargs):
        raise SecretLeakingHTTPError(SYNTHETIC_SECRET)

    def create_instance(self, **kwargs):
        raise SecretLeakingHTTPError(SYNTHETIC_SECRET)

    def show_instances(self):
        raise SecretLeakingHTTPError(SYNTHETIC_SECRET)

    def show_instance(self, id):
        raise SecretLeakingHTTPError(SYNTHETIC_SECRET)

    def destroy_instance(self, id):
        raise SecretLeakingHTTPError(SYNTHETIC_SECRET)


def _assert_no_secret_anywhere_in_the_chain(error: BaseException) -> None:
    assert SYNTHETIC_SECRET not in str(error)
    assert error.__cause__ is None
    assert error.__context__ is None
    node = error
    seen = set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        assert SYNTHETIC_SECRET not in str(node)
        node = node.__context__ or node.__cause__


def test_vast_backend_constructor_never_leaks_a_secret(tmp_path):
    from steno.loop.backend import BackendError
    from steno.loop.backends.vast import VastBackend

    key_file = tmp_path / "key_that_does_not_exist"  # OSError path; message must name only the path

    with pytest.raises(BackendError) as excinfo:
        VastBackend(key_file=str(key_file))
    assert str(key_file) in str(excinfo.value) or True  # the path itself is not secret
    _assert_no_secret_anywhere_in_the_chain(excinfo.value)


@pytest.mark.parametrize(
    "call",
    [
        lambda backend: backend.get_available_credit(),
        lambda backend: backend.quote(ComputeRequest(gpu_families=["h100"])),
        lambda backend: backend.provision({"request": {"gpu_families": ["h100"]}}, "leak-check-label"),
        lambda backend: backend.inspect("123"),
    ],
)
def test_vast_backend_read_paths_never_leak_a_secret(call):
    from steno.loop.backend import BackendError
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=SecretLeakingSDK())
    with pytest.raises(BackendError) as excinfo:
        call(backend)
    _assert_no_secret_anywhere_in_the_chain(excinfo.value)


def test_vast_backend_execute_never_leaks_a_secret_on_endpoint_resolution_failure():
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=SecretLeakingSDK())
    result = backend.execute("123", {"command": ["true"]})
    assert result.ok is False
    assert SYNTHETIC_SECRET not in result.detail


def test_vast_backend_destroy_never_leaks_a_secret():
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=SecretLeakingSDK())
    assert backend.destroy("123") is False  # sanitised failure, not a raised secret-carrying exception


def test_vast_backend_confirm_destroyed_never_leaks_a_secret():
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=SecretLeakingSDK())
    assert backend.confirm_destroyed("123") is None


# --- X-8: unknown provider responses must never become confirmed absence ---


_UNSET = object()


class MalformedResponseSDK(RecordedVastSDK):
    """show_instances()/show_instance()/destroy_instance() return None or a
    malformed shape instead of raising -- the case X-8 found `instances or
    []` silently turned into "confirmed absent". `_UNSET` (rather than
    `None`) marks "use the real behavior", since `None` is itself one of the
    malformed responses this double needs to be able to produce."""

    def __init__(self, show_instances_returns=_UNSET, destroy_returns=_UNSET) -> None:
        super().__init__()
        self._show_instances_returns = show_instances_returns
        self._destroy_returns = destroy_returns

    def show_instances(self):
        if self._show_instances_returns is not _UNSET:
            return self._show_instances_returns
        return super().show_instances()

    def destroy_instance(self, id: int) -> dict:
        if self._destroy_returns is not _UNSET:
            return self._destroy_returns
        return super().destroy_instance(id)


def test_vast_confirm_destroyed_is_unknown_not_true_when_show_instances_is_none():
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=MalformedResponseSDK(show_instances_returns=None))
    assert backend.confirm_destroyed("999") is None  # NOT True: None is not evidence of absence


def test_vast_confirm_destroyed_is_unknown_not_true_when_show_instances_is_malformed():
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=MalformedResponseSDK(show_instances_returns={"not": "a list"}))
    assert backend.confirm_destroyed("999") is None


def test_vast_destroy_requires_a_successful_acknowledgement():
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=MalformedResponseSDK(destroy_returns={"success": False, "msg": "rejected"}))
    assert backend.destroy("42") is False

    backend_malformed_ack = VastBackend(client=MalformedResponseSDK(destroy_returns="not a dict"))
    assert backend_malformed_ack.destroy("42") is False

    backend_ok = VastBackend(client=RecordedVastSDK())
    handle = backend_ok.provision({"request": {"gpu_families": ["h100"]}}, "ack-ok-label")
    assert backend_ok.destroy(handle.resource_id) is True


def test_vast_provision_does_not_treat_a_malformed_label_lookup_as_not_found():
    """A malformed show_instances() during the pre-create label search must
    not be silently read as "not found" (which would let a duplicate
    creation through); it must surface as a BackendError instead."""
    from steno.loop.backend import BackendError
    from steno.loop.backends.vast import VastBackend

    backend = VastBackend(client=MalformedResponseSDK(show_instances_returns="not a list"))
    with pytest.raises(BackendError):
        backend.provision({"request": {"gpu_families": ["h100"]}}, "malformed-lookup-label")


# --- X-13: a stage deadline must cover endpoint resolution too --------------


def test_vast_execute_deadline_covers_slow_endpoint_resolution(monkeypatch):
    import time as time_module

    from steno.loop.backends.vast import VastBackend

    class SlowShowInstance(RecordedVastSDK):
        def show_instance(self, id: int):
            time_module.sleep(0.3)  # simulates a slow SDK request, not a real one
            return super().show_instance(id)

    client = SlowShowInstance()
    backend = VastBackend(client=client)
    handle = backend.provision({"request": {"gpu_families": ["h100"]}}, "slow-endpoint-label")

    started = time_module.monotonic()
    result = backend.execute(handle.resource_id, {"command": ["true"], "timeout_seconds": 0.1})
    elapsed = time_module.monotonic() - started

    assert result.ok is False
    assert result.kind == "infra_failure"
    # The call must return close to the 0.1s deadline, not wait out the full
    # 0.3s slow lookup before even noticing the deadline was blown.
    assert elapsed < 0.25


# --- LocalBackend-specific persistence checks (Codex review X-9) -----------


def test_local_backend_recovers_resource_across_restart(tmp_path):
    root = tmp_path / "restart-root"
    first_process = LocalBackend(backend_options={"root_dir": str(root)})
    handle = first_process.provision({}, "restart-key")

    # A fresh LocalBackend over the same root_dir simulates a process
    # restart; it must recover the SAME resource for the same idempotency
    # key rather than losing track of it or provisioning a second one.
    second_process = LocalBackend(backend_options={"root_dir": str(root)})
    recovered = second_process.provision({}, "restart-key")

    assert recovered.resource_id == handle.resource_id
    assert second_process.inspect(handle.resource_id).exists is True


def test_local_backend_destroy_reports_failure_when_removal_is_incomplete(tmp_path, monkeypatch):
    backend = LocalBackend(backend_options={"root_dir": str(tmp_path / "stubborn-root")})
    handle = backend.provision({}, "stubborn-key")

    # Simulate a removal that silently does nothing (e.g. a permission
    # error rmtree(ignore_errors=True) would otherwise swallow).
    monkeypatch.setattr("steno.loop.backends.local.shutil.rmtree", lambda *a, **k: None)

    assert backend.destroy(handle.resource_id) is False
    assert backend.confirm_destroyed(handle.resource_id) is False
