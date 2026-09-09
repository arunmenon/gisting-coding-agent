"""vLLM logits processor that forbids sampling any gist token id (belt and braces beside the zeroed
lm_head rows). Use: vllm serve <gisted ckpt> --logits-processors mask_gist_logits.GistMaskLogitsProcessor
with PYTHONPATH containing this file and GIST_META pointing at gist_meta.json."""
import json
import os

try:
    from vllm.v1.sample.logits_processor import LogitsProcessor as _Base
except Exception:  # older layouts
    _Base = object


def _first_gist_id():
    meta_path = os.environ.get("GIST_META")
    if meta_path and os.path.exists(meta_path):
        return json.load(open(meta_path))["first_gist_id"]
    return int(os.environ.get("GIST_FIRST_ID", "248077"))


class GistMaskLogitsProcessor(_Base):
    def __init__(self, vllm_config=None, device=None, is_pin_memory=None):
        self.first_gist_id = _first_gist_id()

    def is_argmax_invariant(self) -> bool:
        return False

    def update_state(self, batch_update) -> None:
        pass

    def apply(self, logits):
        logits[:, self.first_gist_id:] = float("-inf")
        return logits
