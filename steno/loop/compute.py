"""Provider-neutral compute request/offer/handle types (wave 2, build order
step 6; steno-design.md section 2, "Compute backends").

The runner and ``RunSpec`` must never know what a provider's query language,
offer shape, or SSH endpoint fields look like. A spec's ``compute`` block is:

    compute:
      backend: vast                # registry name (see backends/__init__.py)
      request: {...}                # ComputeRequest fields, generic across providers
      backend_options: {...}        # opaque, passed through untouched to the backend

``ComputeRequest`` is the only thing the runner and spec validate generically.
``backend_options`` is never inspected outside the named backend module: it is
where provider-specific extras live (for example vast's raw image tag or a
label prefix) without leaking a provider's vocabulary into the spec schema.

Backward compatibility: wave 1 specs (and this wave's tests) pass a flat
``compute`` dict with no ``request``/``backend_options`` split (for example
``{"backend": "fake"}``). Nothing here requires a ``request`` key to be
present; ``ComputeRequest.from_dict({})`` returns an all-optional, always-valid
request, and a backend that only needs its own flat dict (as FakeBackend does)
can keep reading the whole ``compute`` mapping unchanged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any


class ComputeRequestError(ValueError):
    """Raised by ComputeRequest.validate() with a clear message."""


@dataclass
class ComputeRequest:
    """A provider-neutral description of the compute a run needs.

    Every field is optional so an empty/omitted ``request`` (wave 1 specs) is
    always valid; a field only constrains provisioning when a caller sets it.
    ``gpu_families`` holds neutral names (``"h100"``, ``"h200"``, ``"a100"``,
    ...); mapping a neutral family to a provider's own vocabulary (vast's
    ``gpu_name`` values, for instance) happens only inside that provider's
    backend module, never here.
    """

    gpu_count: int | None = None
    gpu_memory_gb_min: float | None = None
    gpu_families: list[str] | None = None
    cpu_ram_gb_min: float | None = None
    disk_gb_min: float | None = None
    network_down_mbps_min: float | None = None
    image: str | None = None
    max_hourly_usd: float | None = None
    reliability_min: float | None = None
    requires_direct_ssh: bool = False

    def validate(self) -> None:
        """Raises ComputeRequestError on the first problem found."""
        _require_positive_int_or_none(self.gpu_count, "gpu_count")
        _require_positive_number_or_none(self.gpu_memory_gb_min, "gpu_memory_gb_min")
        _require_positive_number_or_none(self.cpu_ram_gb_min, "cpu_ram_gb_min")
        _require_positive_number_or_none(self.disk_gb_min, "disk_gb_min")
        _require_positive_number_or_none(self.network_down_mbps_min, "network_down_mbps_min")
        _require_positive_number_or_none(self.max_hourly_usd, "max_hourly_usd")

        if self.gpu_families is not None:
            if not isinstance(self.gpu_families, list) or not all(
                isinstance(name, str) and name.strip() for name in self.gpu_families
            ):
                raise ComputeRequestError("gpu_families must be a list of non-empty strings")

        if self.image is not None and (not isinstance(self.image, str) or not self.image.strip()):
            raise ComputeRequestError("image must be a non-empty string when given")

        if self.reliability_min is not None:
            if not isinstance(self.reliability_min, (int, float)) or isinstance(self.reliability_min, bool):
                raise ComputeRequestError("reliability_min must be a number")
            if not math.isfinite(self.reliability_min) or not (0.0 <= self.reliability_min <= 1.0):
                raise ComputeRequestError(f"reliability_min must be within [0, 1], got {self.reliability_min!r}")

        if not isinstance(self.requires_direct_ssh, bool):
            raise ComputeRequestError("requires_direct_ssh must be a boolean")

    @classmethod
    def from_dict(cls, document: dict[str, Any] | None) -> "ComputeRequest":
        document = document or {}
        known_fields = {f for f in cls.__dataclass_fields__}
        unknown = [key for key in document if key not in known_fields]
        if unknown:
            raise ComputeRequestError(f"unsupported compute.request field(s): {unknown}")
        return cls(**document)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gpu_count": self.gpu_count,
            "gpu_memory_gb_min": self.gpu_memory_gb_min,
            "gpu_families": self.gpu_families,
            "cpu_ram_gb_min": self.cpu_ram_gb_min,
            "disk_gb_min": self.disk_gb_min,
            "network_down_mbps_min": self.network_down_mbps_min,
            "image": self.image,
            "max_hourly_usd": self.max_hourly_usd,
            "reliability_min": self.reliability_min,
            "requires_direct_ssh": self.requires_direct_ssh,
        }


def _require_positive_number_or_none(value: Any, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ComputeRequestError(f"{field_name} must be a positive number when given, got {value!r}")


def _require_positive_int_or_none(value: Any, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ComputeRequestError(f"{field_name} must be a positive integer when given, got {value!r}")


@dataclass
class ComputeOffer:
    """A backend-neutral quote for one rentable resource.

    ``raw_provider_ref`` carries whatever the provider needs to act on this
    offer later (an offer id, a query fingerprint, ...). The runner and CLI
    must never interpret its contents; only the backend that produced it does.
    """

    offer_id: str
    gpu_family: str
    gpu_count: int
    gpu_memory_gb: float
    hourly_usd: float
    region: str = ""
    reliability: float | None = None
    raw_provider_ref: Any = None


@dataclass
class ResourceHandle:
    """What a backend hands back after provisioning: enough for the runner to
    reach and bill the resource, without knowing how it was provisioned."""

    resource_id: str
    backend_name: str
    host: str = ""
    port: int = 0
    user: str = "root"
    hourly_usd: float = 0.0


class UnsafeArtifactPathError(ValueError):
    """Raised by validate_relative_artifact_path() for a path that could
    escape its destination directory (Codex review X-3): an absolute path,
    a home-relative path, or one containing a '..' segment. Shared by every
    backend that copies artifacts by a manifest path (local.py, vast.py) so
    the containment rule is defined once, not per backend."""


def validate_relative_artifact_path(path: Any) -> str:
    """Returns ``path`` unchanged if it is safe to join onto a destination
    directory: a non-empty relative POSIX path with no ``..`` segment and no
    leading ``/`` or ``~``. Raises UnsafeArtifactPathError otherwise.

    This is deliberately strict rather than attempting to "resolve and
    check containment after the fact": a manifest path is caller-supplied
    data (a spec's stage output name), and the safest rule is the simplest
    one a caller can always satisfy for a legitimate relative artifact path.
    """
    if not isinstance(path, str) or not path:
        raise UnsafeArtifactPathError(f"artifact path must be a non-empty string, got {path!r}")
    if path.startswith("/") or path.startswith("~") or path.startswith("\\"):
        raise UnsafeArtifactPathError(f"artifact path must be relative, got {path!r}")
    parts = PurePosixPath(path).parts
    if not parts or any(part in ("..", "") for part in parts):
        raise UnsafeArtifactPathError(f"artifact path must not contain '..' or empty segments, got {path!r}")
    return path
