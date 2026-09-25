#!/usr/bin/env python3
"""Turn tap logs into distillation examples.

Each logged /v1/messages turn becomes one example with:
  teacher_ids   chat-template render of (system, tools, messages) exactly as the engine saw it
  student_ids   the same, with each static segment replaced by its gist token ids and the
                dynamic pieces (effort line, cwd) kept verbatim
  response_ids  the assistant output for that turn (reasoning + text + tool calls), reconstructed
                from the logged content blocks in the template's own tool-call format
  response_start offsets so the KL is taken over response positions only
The teacher and student share response_ids; only the prefix differs.

The Anthropic-format messages are converted to the OpenAI chat format vLLM feeds the template
(tool_use -> assistant tool_calls, tool_result -> role=tool).
"""
import json
import os
import sys

from transformers import AutoTokenizer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from span import to_openai_tools  # noqa: E402

GIST_OUT = os.environ.get("GIST_OUT") or os.path.join(HERE, "out")
TOKENIZER_DIR = os.path.join(GIST_OUT, "tokenizer")
SEGMENTS = json.load(open(os.path.join(GIST_OUT, "segments.json")))

# --- B3 enforcement (opt-in): only imported/used when a bundle path is passed to main(). Guarded
# sys.path insert of the repo root, same pattern as experiments/proxy/tap.py, so plain dataset
# building (no bundle argument) never depends on steno/ being importable.
_REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def load_bundle_context(bundle_path):
    """Loads the bundle, checks that the artifacts this build actually uses -- the global
    SEGMENTS map and the tokenizer file under TOKENIZER_DIR -- are the ones this bundle
    identifies (W-X4: a valid bundle alone proves nothing about which map/tokenizer were loaded
    next to it), and returns (bundle, gate) where gate(request_dict) -> (ok, reason) checks one
    request. Raises ValueError if the bundle, the segment map, or the tokenizer are not bound
    together; that is meant to stop the whole build, not be caught per-example."""
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    from steno.span.adapters.claude_code import ClaudeCodeAdapter
    from steno.span.enforce import bind_segments_to_bundle, bind_tokenizer_to_bundle, check_request_against_bundle, load_bundle

    bundle = load_bundle(bundle_path)

    segments_ok, segments_reasons = bind_segments_to_bundle(SEGMENTS, bundle)
    if not segments_ok:
        raise ValueError("segment map at %s is not bound to bundle %s: %s" % (
            os.path.join(GIST_OUT, "segments.json"), bundle_path, "; ".join(segments_reasons)))

    tokenizer_file = os.path.join(TOKENIZER_DIR, "tokenizer.json")
    tokenizer_ok, tokenizer_reason = bind_tokenizer_to_bundle(tokenizer_file, bundle)
    if not tokenizer_ok:
        raise ValueError("tokenizer at %s is not bound to bundle %s: %s" % (tokenizer_file, bundle_path, tokenizer_reason))

    adapter = ClaudeCodeAdapter()

    def gate(request):
        try:
            call = adapter.parse_request({"path": "/v1/messages", "request": request})
        except Exception as error:
            return False, "adapter could not parse request: %r" % (error,)
        ok, reasons = check_request_against_bundle(call, bundle)
        return ok, ("ok" if ok else "; ".join(reasons))

    return bundle, gate


def system_text_as_served(request):
    """vLLM's Anthropic adapter: top-level system block texts, then inline role=system messages
    (billing headers stripped), all concatenated with no separator."""
    parts = []
    system = request.get("system")
    if isinstance(system, str):
        parts.append(system)
    elif system:
        parts.extend(b.get("text", "") for b in system if b.get("type") == "text" and b.get("text"))
    for message in request.get("messages") or []:
        if message.get("role") != "system":
            continue
        content = message.get("content")
        if isinstance(content, str):
            if not content.startswith("x-anthropic-billing-header"):
                parts.append(content)
        else:
            parts.extend(b.get("text", "") for b in content if b.get("type") == "text" and b.get("text") and not b["text"].startswith("x-anthropic-billing-header"))
    return "".join(parts)


def anthropic_to_openai_messages(messages):
    out = []
    for message in messages:
        role = message["role"]
        content = message.get("content")
        if role == "system":
            continue  # merged into the leading system block by the adapter
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if role == "user":
            # Adapter order: tool_result blocks become role=tool messages appended as encountered;
            # text blocks collect into the user message which is appended after the loop.
            parts = []
            for block in content:
                if block.get("type") == "text" and block.get("text"):
                    parts.append({"type": "text", "text": block["text"]})
                elif block.get("type") == "tool_result":
                    inner = block.get("content")
                    if isinstance(inner, list):
                        inner = "\n".join(b.get("text", "") for b in inner if isinstance(b, dict) and b.get("type") == "text")
                    out.append({"role": "tool", "tool_call_id": block.get("tool_use_id") or "", "content": inner or ""})
            if parts:
                out.append({"role": "user", "content": parts[0]["text"] if len(parts) == 1 else parts})
            continue
        if role == "assistant":
            entry = {"role": "assistant", "content": "", "tool_calls": []}
            for block in content:
                if block.get("type") == "text":
                    entry["content"] += block["text"]
                elif block.get("type") == "thinking" and block.get("thinking") is not None:
                    entry["reasoning"] = entry.get("reasoning", "") + block["thinking"]
                elif block.get("type") == "tool_use":
                    entry["tool_calls"].append({"id": block.get("id") or "call_0", "type": "function", "function": {"name": block.get("name") or "", "arguments": block.get("input") or {}}})
            if not entry["tool_calls"]:
                del entry["tool_calls"]
            out.append(entry)
    return out


def response_message(response):
    entry = {"role": "assistant", "content": "", "tool_calls": []}
    for block in response.get("content") or []:
        if block.get("type") == "text":
            entry["content"] += block.get("text", "")
        elif block.get("type") == "thinking" and block.get("thinking") is not None:
            entry["reasoning"] = entry.get("reasoning", "") + block["thinking"]
        elif block.get("type") == "tool_use":
            entry["tool_calls"].append({"id": block.get("id") or "call_0", "type": "function", "function": {"name": block.get("name") or "", "arguments": block.get("input") or {}}})
    if not entry["tool_calls"]:
        del entry["tool_calls"]
    return entry


def gist_prefix_text(system_text):
    """System text with each static segment replaced by its gist token string; dynamic pieces kept."""
    # Gisted system segments are anchors; everything between and after them is copied from the live text.
    gisted = [s for s in SEGMENTS["segments"] if s["name"].startswith("system_") and not s.get("dynamic")]
    out, cursor = [], 0
    for segment in gisted:
        start = system_text.index(segment["text"], cursor)
        out.append(system_text[cursor:start])
        out.append("".join("<gist_%d>" % i for i in range(segment["gist_start"], segment["gist_start"] + segment["gist_count"])))
        cursor = start + len(segment["text"])
    out.append(system_text[cursor:])  # dynamic tail: git block, inline system reminders
    return "".join(out)


def tools_gist_text():
    segment = next(s for s in SEGMENTS["segments"] if s["name"] == "tools")
    return "".join("<gist_%d>" % i for i in range(segment["gist_start"], segment["gist_start"] + segment["gist_count"]))


def build_example(tokenizer, record):
    request, response = record["request"], record["response"]
    system_text = system_text_as_served(request)
    openai_tools = to_openai_tools(request["tools"])
    history = anthropic_to_openai_messages(request["messages"])
    reply = response_message(response)

    teacher_prompt = tokenizer.apply_chat_template([{"role": "system", "content": system_text}] + history, tools=openai_tools, add_generation_prompt=True, tokenize=False)
    teacher_full = tokenizer.apply_chat_template([{"role": "system", "content": system_text}] + history + [reply], tools=openai_tools, add_generation_prompt=False, tokenize=False)
    assert teacher_full.startswith(teacher_prompt), "reply render does not extend the prompt render"
    response_text = teacher_full[len(teacher_prompt):]

    # Student: no tools array (its rendered block is replaced by the tools gist), system text gisted.
    # The template emits the tools block before the system text; we reproduce that order by hand.
    student_system = tools_gist_text() + gist_prefix_text(system_text)
    student_prompt = tokenizer.apply_chat_template([{"role": "system", "content": student_system}] + history, add_generation_prompt=True, tokenize=False)

    teacher_ids = tokenizer.encode(teacher_prompt, add_special_tokens=False)
    student_ids = tokenizer.encode(student_prompt, add_special_tokens=False)
    response_ids = tokenizer.encode(response_text, add_special_tokens=False)
    return {"teacher_ids": teacher_ids, "student_ids": student_ids, "response_ids": response_ids,
            "session": json.loads(request["metadata"]["user_id"])["session_id"], "turn_index": len(history)}


def main():
    log_path = sys.argv[1]
    out_path = sys.argv[2]
    bundle_path = sys.argv[3] if len(sys.argv) > 3 else None  # optional: opt-in B3 enforcement
    bundle_gate = load_bundle_context(bundle_path)[1] if bundle_path else None  # raises if bundle/segments/tokenizer aren't bound

    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_DIR)
    count = skipped = bundle_rejected = 0
    with open(out_path, "w") as out_file:
        for line in open(log_path):
            record = json.loads(line)
            if record.get("status") != 200 or not record.get("response") or not (record.get("request") or {}).get("tools"):
                continue
            if bundle_gate is not None:
                ok, reason = bundle_gate(record["request"])
                if not ok:
                    bundle_rejected += 1
                    if bundle_rejected <= 3:
                        print("bundle reject:", reason)
                    continue
            try:
                example = build_example(tokenizer, record)
            except Exception as error:
                skipped += 1
                if skipped <= 3:
                    print("skip:", repr(error)[:200])
                continue
            out_file.write(json.dumps(example) + "\n")
            count += 1
            if count <= 2 or count % 100 == 0:
                print("example %d: teacher %d student %d response %d tokens (prefix saved %d)" % (count, len(example["teacher_ids"]), len(example["student_ids"]), len(example["response_ids"]), len(example["teacher_ids"]) - len(example["student_ids"])))
    print("wrote", count, "examples, skipped", skipped,
          ("bundle_rejected %d" % bundle_rejected) if bundle_gate is not None else "(bundle enforcement off)",
          "->", out_path)


if __name__ == "__main__":
    main()
