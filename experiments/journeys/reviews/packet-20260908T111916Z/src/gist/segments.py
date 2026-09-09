#!/usr/bin/env python3
"""Split the rendered static span into gistable segments and register gist tokens.

Segments: the system text split at the per-session dynamic characters (found by diffing the
system text across sessions in the tap log), plus the tools block the template renders from the
tools array. Each segment gets ceil(len/ratio) gist tokens with a contiguous id range.

Outputs (in gist/out/):
  segments.json   per segment: name, token ids, gist id range
  tokenizer/      tokenizer with <gist_N> registered as added special tokens
"""
import difflib
import re
import json
import math
import os
import sys

from transformers import AutoTokenizer

sys.path.insert(0, os.path.dirname(__file__))
from span import MODEL, load_dominant_request, to_openai_tools  # noqa: E402

OUT = os.environ.get("GIST_OUT") or os.path.join(os.path.dirname(__file__), "out")
RATIO = int(os.environ.get("GIST_RATIO", "4"))
TOOLS_RATIO = int(os.environ.get("GIST_TOOLS_RATIO", str(RATIO)))  # per-segment: the tool block may get more room than the rules


def all_system_texts(log_path):
    texts = {}
    with open(log_path) as log_file:
        for line in log_file:
            record = json.loads(line)
            request = record.get("request") or {}
            if not request.get("tools") or not request.get("system"):
                continue
            try:
                session = json.loads(request["metadata"]["user_id"])["session_id"]
            except (KeyError, TypeError, ValueError):
                session = "probe-%d" % len(texts)
            texts.setdefault(session, "".join(b.get("text", "") for b in request["system"] if b.get("type") == "text" and b.get("text")))
    return list(texts.values())


VERBATIM_LINE = re.compile(r"(?im)^.*(?:working directory|/private/|/Users/|/home/|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\b20\d\d-\d\d-\d\d\b|powered by the model).*$")


def dynamic_spans(texts):
    """Character ranges in texts[0] that differ from any other session's system text, plus whole lines
    that carry content the model must reproduce verbatim (paths, UUIDs, dates, served model name):
    a compressed summary cannot restore those exactly, so they stay as raw tokens."""
    base = texts[0]
    dynamic = set()
    for m in VERBATIM_LINE.finditer(base):
        dynamic.update(range(m.start(), m.end()))
    for other in texts[1:]:
        matcher = difflib.SequenceMatcher(None, base, other, autojunk=False)
        for tag, i1, i2, _, _ in matcher.get_opcodes():
            if tag != "equal":
                dynamic.update(range(i1, max(i2, i1 + 1)))
    ranges = []
    for index in sorted(dynamic):
        if ranges and ranges[-1][1] == index:
            ranges[-1][1] = index + 1
        else:
            ranges.append([index, index + 1])
    return ranges


def main():
    log_paths = sys.argv[1:] or [os.path.join(os.path.dirname(__file__), "..", "logs", "requests.jsonl")]
    os.makedirs(OUT, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    system_text, tools = load_dominant_request(log_paths[0])   # first log defines the tool catalogue
    texts = []
    for log_path in log_paths:                                  # every log contributes system-text variants
        texts.extend(all_system_texts(log_path))
    ranges = dynamic_spans([system_text] + [t for t in texts if t != system_text])
    print("dynamic character ranges in system text:", [(a, b, system_text[a:b]) for a, b in ranges])

    segments = []
    cursor = 0
    for index, (start, end) in enumerate(ranges):
        segments.append({"name": "system_%d" % index, "text": system_text[cursor:start]})
        segments.append({"name": "dynamic_%d" % index, "text": system_text[start:end], "dynamic": True})
        cursor = end
    segments.append({"name": "system_%d" % len(ranges), "text": system_text[cursor:]})

    # Tools block exactly as the template renders it: render with and without tools, take the difference.
    with_tools = tokenizer.apply_chat_template([{"role": "system", "content": system_text}, {"role": "user", "content": "hi"}], tools=to_openai_tools(tools), add_generation_prompt=True, tokenize=False)
    without_tools = tokenizer.apply_chat_template([{"role": "system", "content": system_text}, {"role": "user", "content": "hi"}], add_generation_prompt=True, tokenize=False)
    matcher = difflib.SequenceMatcher(None, without_tools, with_tools, autojunk=False)
    inserted = [with_tools[j1:j2] for tag, _, _, j1, j2 in matcher.get_opcodes() if tag == "insert"]
    assert len(inserted) == 1, "expected the template to insert the tools block in one place, got %d" % len(inserted)
    tools_block = inserted[0]
    position = "before system text" if with_tools.index(tools_block) < with_tools.index(system_text[:200]) else "after system text"
    print("tools block: %d chars, placed %s; head=%r" % (len(tools_block), position, tools_block[:80]))
    segments.append({"name": "tools", "text": tools_block})
    preamble = with_tools[: with_tools.index(tools_block if position == "before system text" else system_text[:200])]
    print("template preamble before first static segment:", repr(preamble[:200]))

    MIN_STATIC_TOKENS = int(os.environ.get("GIST_MIN_SEGMENT", "32"))
    next_gist = 0
    total_static = 0
    for segment in segments:
        segment["ids"] = tokenizer.encode(segment["text"], add_special_tokens=False)
        if not segment.get("dynamic") and segment["name"] != "tools" and len(segment["ids"]) < MIN_STATIC_TOKENS:
            segment["dynamic"] = True  # too short to gist; kept verbatim like the dynamic pieces around it
        if segment.get("dynamic"):
            continue
        ratio = TOOLS_RATIO if segment["name"] == "tools" else RATIO
        segment["ratio"] = ratio
        count = math.ceil(len(segment["ids"]) / ratio)
        segment["gist_start"], segment["gist_count"] = next_gist, count
        next_gist += count
        total_static += len(segment["ids"])
    print("ratio %d:1 (tools %d:1) | static tokens %d | gist tokens %d" % (RATIO, TOOLS_RATIO, total_static, next_gist))
    for segment in segments:
        print("  %-10s tokens=%-6d %s" % (segment["name"], len(segment["ids"]), "" if segment.get("dynamic") else "gist[%d:%d)" % (segment["gist_start"], segment["gist_start"] + segment["gist_count"])))

    gist_tokens = ["<gist_%d>" % i for i in range(next_gist)]
    original_len = len(tokenizer)
    added = tokenizer.add_special_tokens({"additional_special_tokens": gist_tokens}, replace_extra_special_tokens=False)
    print("tokenizer len %d -> %d (added %d)" % (original_len, len(tokenizer), added))
    for probe in ("<gist_0>", "<gist_%d>" % (next_gist - 1), "a<gist_7>b"):
        ids = tokenizer.encode(probe, add_special_tokens=False)
        print("  %r -> %s -> %r / skip_special: %r" % (probe, ids, tokenizer.decode(ids), tokenizer.decode(ids, skip_special_tokens=True)))
    first_gist_id = tokenizer.convert_tokens_to_ids("<gist_0>")
    assert first_gist_id == original_len, (first_gist_id, original_len)
    assert tokenizer.convert_tokens_to_ids("<gist_%d>" % (next_gist - 1)) == original_len + next_gist - 1
    tokenizer.save_pretrained(os.path.join(OUT, "tokenizer"))
    json.dump({"ratio": RATIO, "tools_ratio": TOOLS_RATIO, "original_vocab_len": original_len, "first_gist_id": first_gist_id, "gist_count": next_gist,
               "embedding_rows": 248320, "segments": segments}, open(os.path.join(OUT, "segments.json"), "w"))
    print("wrote", os.path.join(OUT, "segments.json"), "and tokenizer/")


if __name__ == "__main__":
    main()
