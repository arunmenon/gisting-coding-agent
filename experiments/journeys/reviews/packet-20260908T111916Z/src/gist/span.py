#!/usr/bin/env python3
"""Reconstruct the static span exactly as the chat template renders it, from a tap log.

Takes the dominant system text and tools array from logs/requests.jsonl, converts the tools to
the OpenAI function format vLLM uses, renders through the checkpoint's chat template with a
bare user turn, and returns the token ids of the prefix that precedes the user turn.
"""
import json
import os

from transformers import AutoTokenizer

MODEL = "Qwen/Qwen3.8-27B"


def load_dominant_request(log_path):
    counts = {}
    example = {}
    with open(log_path) as log_file:
        for line in log_file:
            record = json.loads(line)
            request = record.get("request") or {}
            if not request.get("tools") or not request.get("system"):
                continue
            system_text = "".join(b.get("text", "") for b in request["system"] if b.get("type") == "text" and b.get("text"))  # adapter joins with no separator
            key = json.dumps(request["tools"], sort_keys=False)
            counts[key] = counts.get(key, 0) + 1
            example.setdefault(key, (system_text, request["tools"]))
    key = max(counts, key=counts.get)
    return example[key]


def to_openai_tools(anthropic_tools):
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("input_schema", {})}} for t in anthropic_tools]


def render_prefix_ids(tokenizer, system_text, openai_tools, user_marker="hi"):
    """Token ids of everything before the user turn: system + tools as the template lays them out."""
    with_user = tokenizer.apply_chat_template(
        [{"role": "system", "content": system_text}, {"role": "user", "content": user_marker}],
        tools=openai_tools, add_generation_prompt=True, tokenize=False)
    bare = tokenizer.apply_chat_template([{"role": "user", "content": user_marker}], add_generation_prompt=True, tokenize=False)
    # The user turn text is identical in both renders; the static prefix is everything before it.
    user_turn_text = bare[bare.index("<|im_start|>user"):]
    assert with_user.endswith(user_turn_text), "template layout assumption broken"
    prefix_text = with_user[: len(with_user) - len(user_turn_text)]
    return tokenizer.encode(prefix_text, add_special_tokens=False), prefix_text


if __name__ == "__main__":
    import sys
    log_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "logs", "requests.jsonl")
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    system_text, tools = load_dominant_request(log_path)
    ids, text = render_prefix_ids(tokenizer, system_text, to_openai_tools(tools))
    print("rendered static prefix tokens:", len(ids), "(vLLM /tokenize gave 21109 for the same span)")
    print("first 20 ids:", ids[:20]); print("head:", text[:160].replace("\n", "\\n"))
    print("tail:", text[-160:].replace("\n", "\\n"))
