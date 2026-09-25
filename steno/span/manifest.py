"""Bundle identity for a harness adapter + model pairing.

Per steno-design.md, every artifact downstream of span analysis must eventually record the
identity of the harness adapter, the model, the tokenizer, the chat template, the tool catalogue
and the raw-value rules it was built against. This module keeps two distinct shapes rather than
one, because they answer different questions:

- `DiscoveryManifest`: what we know about a harness adapter's identity and (once discovery has
  run) its tool catalogue and raw-value rules. Deliberately incomplete-tolerant: a field may be
  `None` because discovery has not reached it yet. `None` and `[]` are not the same thing here --
  `None` means "not collected", `[]` means "collected, and it is genuinely empty" (some harness
  might really have zero declared raw-value rules; that is a fact worth recording, not an error).
- `DeployableBundle`: the identity a proxy or dataset builder must require before it is allowed
  to compress traffic. Every field is mandatory: a pinned model revision, a tokenizer hash, a
  template hash, and a tool catalogue and rule set that were actually collected (may still be
  `[]`, but never `None`).

**Scope note (W-16):** this module defines and validates both shapes; it does not implement
proxy or dataset-builder *enforcement*. Wiring `DeployableBundle.validate()` into
`experiments/proxy/tap.py` and the dataset builder, so a bundle missing any required field is
rejected rather than silently accepted, is explicitly deferred to a later wave. Build order step
B3 is therefore only partially closed by this module: bundle identity is defined and can be
computed and validated, but nothing in this repository yet refuses to serve or train on an
unpinned bundle. See `steno/span/README.md` for how this is tracked.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Optional

from .record import canonical_json, sha256_of


def _hash_file(path: str) -> str:
    if not os.path.isfile(path):
        raise FileNotFoundError("manifest: declared path does not exist: %s" % path)
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _hash_file_if_present(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return _hash_file(path)


@dataclass
class DiscoveryManifest:
    """What is known so far about a harness-adapter + model pairing. Only the adapter identity
    and model id are required; `tool_catalogue` and `raw_value_rules` may be `None` (not yet
    collected) while discovery is in progress."""

    harness_adapter_name: str
    harness_adapter_version: str
    model_id: str
    tool_catalogue: Optional[list] = None    # None = not collected; [] = collected, empty
    raw_value_rules: Optional[list] = None   # same convention

    harness_adapter_hash: str = field(default="", init=False)
    model_id_hash: str = field(default="", init=False)
    tool_catalogue_hash: Optional[str] = field(default=None, init=False)
    raw_value_rules_hash: Optional[str] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.compute()

    def compute(self) -> None:
        self.harness_adapter_hash = sha256_of({"name": self.harness_adapter_name, "version": self.harness_adapter_version})
        self.model_id_hash = sha256_of({"model_id": self.model_id})
        self.tool_catalogue_hash = sha256_of(self.tool_catalogue) if self.tool_catalogue is not None else None
        self.raw_value_rules_hash = sha256_of(self.raw_value_rules) if self.raw_value_rules is not None else None

    def validate(self) -> None:
        """Raises only on missing *identity* fields. A `None` tool catalogue or rule set is
        expected mid-discovery, not an error; use `completeness()` to check discovery progress
        and `DeployableBundle` when every field must be present."""
        missing = []
        if not self.harness_adapter_name or not self.harness_adapter_version:
            missing.append("harness_adapter_name/version")
        if not self.model_id:
            missing.append("model_id")
        if missing:
            raise ValueError("discovery manifest missing required identity field(s): %s" % ", ".join(missing))

    def completeness(self) -> dict:
        """Which optional-at-discovery-time collections have actually been collected (not
        None), as opposed to whether they happen to be empty."""
        return {
            "tool_catalogue_collected": self.tool_catalogue is not None,
            "raw_value_rules_collected": self.raw_value_rules is not None,
        }

    def to_dict(self) -> dict:
        return {
            "harness_adapter_name": self.harness_adapter_name,
            "harness_adapter_version": self.harness_adapter_version,
            "model_id": self.model_id,
            "harness_adapter_hash": self.harness_adapter_hash,
            "model_id_hash": self.model_id_hash,
            "tool_catalogue_hash": self.tool_catalogue_hash,
            "raw_value_rules_hash": self.raw_value_rules_hash,
            "completeness": self.completeness(),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def to_deployable(self, model_revision: str, tokenizer_path: str, template_path: str) -> "DeployableBundle":
        """Promotes this manifest to a DeployableBundle once the pieces discovery does not
        collect (a pinned model revision, a tokenizer file, a template file) are available.
        Raises via DeployableBundle.validate() below if tool_catalogue/raw_value_rules were
        never actually collected (still None)."""
        return DeployableBundle(
            harness_adapter_name=self.harness_adapter_name,
            harness_adapter_version=self.harness_adapter_version,
            model_id=self.model_id,
            model_revision=model_revision,
            tool_catalogue=self.tool_catalogue,
            raw_value_rules=self.raw_value_rules,
            tokenizer_path=tokenizer_path,
            template_path=template_path,
        )


@dataclass
class DeployableBundle:
    """The identity a proxy or dataset builder must require before compressing traffic against
    this pairing. Every field is mandatory, including a pinned model revision (not just a bare
    model id string, which can float) and real tokenizer/template files. `tool_catalogue` and
    `raw_value_rules` must have been collected (not `None`) but may be an empty list."""

    harness_adapter_name: str
    harness_adapter_version: str
    model_id: str
    model_revision: str
    tool_catalogue: Optional[list]
    raw_value_rules: Optional[list]
    tokenizer_path: Optional[str] = None
    template_path: Optional[str] = None

    harness_adapter_hash: str = field(default="", init=False)
    model_id_hash: str = field(default="", init=False)
    model_revision_hash: str = field(default="", init=False)
    tool_catalogue_hash: Optional[str] = field(default=None, init=False)
    raw_value_rules_hash: Optional[str] = field(default=None, init=False)
    tokenizer_hash: Optional[str] = field(default=None, init=False)
    template_hash: Optional[str] = field(default=None, init=False)
    bundle_sha: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.compute()

    def compute(self) -> None:
        self.harness_adapter_hash = sha256_of({"name": self.harness_adapter_name, "version": self.harness_adapter_version})
        self.model_id_hash = sha256_of({"model_id": self.model_id})
        self.model_revision_hash = sha256_of({"model_revision": self.model_revision}) if self.model_revision else ""
        self.tool_catalogue_hash = sha256_of(self.tool_catalogue) if self.tool_catalogue is not None else None
        self.raw_value_rules_hash = sha256_of(self.raw_value_rules) if self.raw_value_rules is not None else None
        # Unlike DiscoveryManifest, a deployable bundle's tokenizer/template are mandatory: a
        # missing path here is a validation failure, not a legitimate "not yet known" state, so
        # we hash only when a path was given and let validate() catch the absence explicitly.
        self.tokenizer_hash = _hash_file_if_present(self.tokenizer_path)
        self.template_hash = _hash_file_if_present(self.template_path)
        self.bundle_sha = sha256_of({
            "harness_adapter_hash": self.harness_adapter_hash,
            "model_id_hash": self.model_id_hash,
            "model_revision_hash": self.model_revision_hash,
            "tool_catalogue_hash": self.tool_catalogue_hash,
            "raw_value_rules_hash": self.raw_value_rules_hash,
            "tokenizer_hash": self.tokenizer_hash,
            "template_hash": self.template_hash,
        })

    def validate(self) -> None:
        """Raises naming every missing required field. `tool_catalogue`/`raw_value_rules` being
        `None` (never collected) is missing; being `[]` (collected, confirmed empty) is valid.
        Tokenizer and template hashes are required -- a deployable bundle with no pinned
        rendering identity is exactly the "legacy" shape steno-design.md says must be rejected."""
        missing = []
        if not self.harness_adapter_name or not self.harness_adapter_version:
            missing.append("harness_adapter_name/version")
        if not self.model_id:
            missing.append("model_id")
        if not self.model_revision:
            missing.append("model_revision")
        if self.tool_catalogue is None:
            missing.append("tool_catalogue_hash")
        if self.raw_value_rules is None:
            missing.append("raw_value_rules_hash")
        if not self.tokenizer_hash:
            missing.append("tokenizer_hash")
        if not self.template_hash:
            missing.append("template_hash")
        if missing:
            raise ValueError("deployable bundle missing required field(s): %s" % ", ".join(sorted(set(missing))))

    def to_dict(self) -> dict:
        return {
            "harness_adapter_name": self.harness_adapter_name,
            "harness_adapter_version": self.harness_adapter_version,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "harness_adapter_hash": self.harness_adapter_hash,
            "model_id_hash": self.model_id_hash,
            "model_revision_hash": self.model_revision_hash,
            "tool_catalogue_hash": self.tool_catalogue_hash,
            "raw_value_rules_hash": self.raw_value_rules_hash,
            "tokenizer_hash": self.tokenizer_hash,
            "template_hash": self.template_hash,
            "bundle_sha": self.bundle_sha,
        }

    def to_json(self) -> str:
        return canonical_json(self.to_dict())
