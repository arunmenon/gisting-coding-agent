"""Compute backend registry (steno-design.md section 3, build order step 6).

The runner and CLI resolve a backend by the name a spec's ``compute.backend``
field gives, never by importing a provider module directly. Every provider
lives in its own file here (``fake.py``, ``local.py``, ``vast.py``, and any
future ``<provider>.py``); nothing outside a provider's own module imports
that provider's SDK.

Adding a backend for a new provider (for example an internal cluster):

1. Write ``steno/loop/backends/<provider>.py`` implementing
   ``steno.loop.backend.ComputeBackend`` (quote, provision, inspect, execute,
   transfer, cost, destroy, confirm_destroyed, plus ``name``/``capabilities``).
   All provider-specific imports (an SDK, a CLI wrapper) live only in this file.
2. At the bottom of that file, call
   ``register_backend("<provider>", <YourBackend>)`` (a class works as the
   factory: ``create_backend`` calls it with ``backend_options``).
3. Import the module once from this package's ``__init__.py`` (see the
   built-in backends below) so registration happens on import of
   ``steno.loop.backends``. A backend whose SDK might not be installed should
   be registered behind a guarded import (see ``vast.py``'s pattern) so a
   missing optional dependency never breaks the registry for the others.
4. Reference it from a spec as ``compute: {backend: "<provider>", request:
   {...}, backend_options: {...}}``.
"""

from __future__ import annotations

from typing import Any, Callable

_REGISTRY: dict[str, Callable[..., Any]] = {}


class UnknownBackendError(KeyError):
    """Raised by create_backend() for a name with no registered factory."""


def register_backend(name: str, factory: Callable[..., Any]) -> None:
    """Register ``factory`` (typically a ComputeBackend subclass) under
    ``name``. Re-registering the same name overwrites the previous factory
    (useful for tests that substitute a double); it is never an error."""
    _REGISTRY[name] = factory


def create_backend(name: str, backend_options: dict[str, Any] | None = None, **kwargs: Any) -> Any:
    """Instantiate the backend registered under ``name``.

    ``backend_options`` is the spec's opaque, provider-specific dict (see
    compute.py's module docstring); it is passed through untouched. Extra
    keyword arguments (for example an injected ``clock`` for FakeBackend, or
    a test double for VastBackend) are passed alongside it.
    """
    try:
        factory = _REGISTRY[name]
    except KeyError as error:
        raise UnknownBackendError(
            f"no backend registered as {name!r}; known backends: {sorted(_REGISTRY)}"
        ) from error
    return factory(backend_options=backend_options or {}, **kwargs)


def registered_backend_names() -> list[str]:
    return sorted(_REGISTRY)


# Register the built-in backends. FakeBackend and LocalBackend have no
# optional dependency and always register. VastBackend needs the `vastai`
# package; its module guards that import so a missing optional dependency
# never breaks registration of the others (build order step 6, point 6).
from .fake import FakeBackend  # noqa: E402
from .local import LocalBackend  # noqa: E402


def _create_fake_backend(*, backend_options: dict[str, Any] | None = None, clock=None, hourly_usd: float = 1.0, **kwargs: Any) -> FakeBackend:
    """Registry factory for FakeBackend (Codex review X-17): the class itself
    requires a ``clock`` positional argument, which `create_backend("fake")`
    (and the CLI's `quote` command) has no way to supply. This factory
    default to `time.time` so the registry interface actually works, while
    still letting a caller inject a deterministic clock (as tests do) via
    the same `clock=` keyword FakeBackend itself accepts.
    """
    import time as _time

    return FakeBackend(clock=clock or _time.time, hourly_usd=hourly_usd, backend_options=backend_options)


register_backend("fake", _create_fake_backend)
register_backend("local", LocalBackend)

try:
    from .vast import VastBackend  # noqa: E402

    register_backend("vast", VastBackend)
except ImportError:
    pass  # vastai not installed; `create_backend("vast", ...)` will raise UnknownBackendError
