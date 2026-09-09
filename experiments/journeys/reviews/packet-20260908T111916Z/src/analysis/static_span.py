#!/usr/bin/env python3
"""E0 analysis over the tap log (logs/requests.jsonl).

For every /v1/messages request it extracts the system blocks and the tools array, finds the
span that is byte-identical across all requests (the gistable static span), tokenizes it with
the Qwen tokenizer, and reports the static share per turn and integrated over sessions.

Sessions are grouped by the first user message text (Claude Code keeps it constant within a
session). Context length per turn comes from vLLM's own usage.input_tokens where present.
"""
import argparse
import collections
import json
import os
import statistics
import sys

from huggingface_hub import snapshot_download
from tokenizers import Tokenizer


def load_records(log_path):
    records = []
    with open(log_path) as log_file:
        for line in log_file:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("path", "").startswith("/v1/messages") and record.get("request") and not record["path"].endswith("count_tokens"):
                records.append(record)
    return records


def system_text(request):
    system = request.get("system")
    if system is None:
        return ""
    if isinstance(system, str):
        return system
    return "\n".join(block.get("text", "") for block in system if isinstance(block, dict))


def tools_json(request):
    return json.dumps(request.get("tools") or [], sort_keys=False, separators=(",", ":"), ensure_ascii=False)


def common_prefix(strings):
    if not strings:
        return ""
    shortest = min(strings, key=len)
    for index, character in enumerate(shortest):
        if any(s[index] != character for s in strings):
            return shortest[:index]
    return shortest


def session_key(request):
    # Claude Code puts its session id in metadata.user_id (a JSON string); fall back to first user text.
    try:
        return json.loads(request["metadata"]["user_id"])["session_id"]
    except (KeyError, TypeError, ValueError):
        pass
    messages = request.get("messages") or []
    for message in messages:
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                return content[:200]
            for block in content or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    return block.get("text", "")[:200]
    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=os.path.join(os.path.dirname(__file__), "..", "logs", "requests.jsonl"))
    parser.add_argument("--tokenizer", default="Qwen/Qwen3.8-27B")
    parser.add_argument("--dump-span", default=None, help="write the static span text to this path")
    parser.add_argument("--vllm", default=None, help="vLLM base URL; if given, count the rendered span via /tokenize")
    parser.add_argument("--served-name", default="qwen3.8-27b")
    args = parser.parse_args()

    records = load_records(args.log)
    if not records:
        print("no /v1/messages records in", args.log)
        sys.exit(1)

    tokenizer_dir = snapshot_download(args.tokenizer, allow_patterns=["tokenizer.json", "tokenizer_config.json"])
    tokenizer = Tokenizer.from_file(os.path.join(tokenizer_dir, "tokenizer.json"))
    count = lambda text: len(tokenizer.encode(text, add_special_tokens=False).ids)

    system_texts = [system_text(r["request"]) for r in records]
    tools_texts = [tools_json(r["request"]) for r in records]
    static_system = common_prefix(system_texts)
    distinct_tools = collections.Counter(tools_texts)
    static_tools = distinct_tools.most_common(1)[0][0]

    static_system_tokens = count(static_system)
    static_tools_tokens = count(static_tools)
    static_tokens = static_system_tokens + static_tools_tokens
    if args.vllm:
        # Exact count as the engine renders it: system + tools through the chat template, minus a bare user turn.
        import urllib.request
        def vllm_count(messages, tools=None):
            body = {"model": args.served_name, "messages": messages, "add_generation_prompt": True}
            if tools:
                body["tools"] = tools
            request = urllib.request.Request(args.vllm.rstrip("/") + "/tokenize", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
            return json.loads(urllib.request.urlopen(request, timeout=120).read())["count"]
        openai_tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t.get("input_schema", {})}} for t in json.loads(static_tools)]
        bare = vllm_count([{"role": "user", "content": "hi"}])
        rendered_system = vllm_count([{"role": "system", "content": static_system}, {"role": "user", "content": "hi"}]) - bare
        rendered_static = vllm_count([{"role": "system", "content": static_system}, {"role": "user", "content": "hi"}], openai_tools) - bare
        print("vLLM-rendered: system %d, tools %d, STATIC SPAN %d (local tokenizer estimate was %d)" % (rendered_system, rendered_static - rendered_system, rendered_static, static_tokens))
        static_tokens = rendered_static

    print("requests:", len(records))
    print("distinct system texts:", len(set(system_texts)), "| distinct tools arrays:", len(distinct_tools))
    print("static system prefix tokens:", static_system_tokens, "| tools JSON tokens (dominant variant):", static_tools_tokens)
    print("STATIC SPAN TOKENS (system prefix + tools):", static_tokens)
    per_request_system = [count(t) for t in system_texts]
    print("full system tokens per request: min %d median %d max %d" % (min(per_request_system), statistics.median(per_request_system), max(per_request_system)))
    print("dynamic system tail tokens (median):", statistics.median(per_request_system) - static_system_tokens)

    sessions = collections.defaultdict(list)
    for record in records:
        sessions[session_key(record["request"])].append(record)

    print("\nsessions:", len(sessions))
    print("%-8s %-6s %-10s %-10s %-10s %-8s %-8s" % ("session", "turns", "ctx_med", "ctx_max", "int_share", "ttft_med", "lat_med"))
    integrated_shares = []
    for index, (key, turns) in enumerate(sessions.items()):
        contexts = []
        for turn in turns:
            usage = (turn.get("response") or {}).get("usage") or {}
            input_tokens = (usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0)
            if input_tokens:
                contexts.append(input_tokens)
        if not contexts:
            continue
        integrated_share = static_tokens * len(contexts) / sum(contexts)
        integrated_shares.append(integrated_share)
        ttfts = [t["ttft_s"] for t in turns if t.get("ttft_s")]
        latencies = [t["latency_s"] for t in turns if t.get("latency_s")]
        print("%-8d %-6d %-10d %-10d %-10.2f %-8.2f %-8.2f" % (
            index, len(turns), statistics.median(contexts), max(contexts), integrated_share,
            statistics.median(ttfts) if ttfts else 0, statistics.median(latencies) if latencies else 0))
    if integrated_shares:
        print("\nINTEGRATED STATIC SHARE across sessions: mean %.2f median %.2f" % (statistics.mean(integrated_shares), statistics.median(integrated_shares)))
        print("E0 gate (>= 0.25):", "PASS" if statistics.median(integrated_shares) >= 0.25 else "FAIL")

    tool_calls = 0
    invalid_tool_json = 0
    tool_names = collections.Counter()
    for record in records:
        for block in (record.get("response") or {}).get("content") or []:
            if block.get("type") == "tool_use":
                tool_calls += 1
                tool_names[block.get("name")] += 1
                if block.get("input_json_valid") is False:
                    invalid_tool_json += 1
    print("\ntool calls:", tool_calls, "| invalid JSON:", invalid_tool_json, "| top tools:", tool_names.most_common(8))

    if args.dump_span:
        with open(args.dump_span, "w") as span_file:
            span_file.write(static_system)
            span_file.write("\n\n=== TOOLS ===\n")
            span_file.write(static_tools)
        print("static span written to", args.dump_span)


if __name__ == "__main__":
    main()
