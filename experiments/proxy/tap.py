#!/usr/bin/env python3
"""Logging passthrough proxy between Claude Code and a vLLM server that speaks the
Anthropic Messages API. This is the E0 tap: every request and response is written to a
JSONL file in exactly the form the engine saw it, with timing.

Usage:
    python tap.py --listen 127.0.0.1:8081 --upstream http://127.0.0.1:8000 --log logs/requests.jsonl

Point Claude Code at it with ANTHROPIC_BASE_URL=http://127.0.0.1:8081 (see claude-env.sh).
Stdlib only, no dependencies.
"""
import argparse
import http.client
import json
import os
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

HOP_BY_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
    "trailers", "transfer-encoding", "upgrade", "host", "accept-encoding", "content-length",
}

log_lock = threading.Lock()
EFFORT_REMAP = {"high": "medium", "max": "xhigh"}
NORMALIZE = []  # list of (old, new) applied to the system text before gist anchoring
GIST = None  # set by --gist: {"tools": "<gist_..>" string, "segments": [gisted system segments]}


def load_gist(segments_path):
    spec = json.load(open(segments_path))
    tools = next(s for s in spec["segments"] if s["name"] == "tools")
    gisted = [s for s in spec["segments"] if s["name"].startswith("system_") and not s.get("dynamic")]
    to_str = lambda s: "".join("<gist_%d>" % i for i in range(s["gist_start"], s["gist_start"] + s["gist_count"]))
    return {"tools": to_str(tools), "segments": [(s["text"], to_str(s)) for s in gisted], "tools_hash": spec.get("tools_hash")}


def gist_system_text(system_text):
    """Replace each gisted system segment (an anchor) with its gist string; keep everything else.
    Tolerant: an anchor not found (repo/git text drifted) is left raw rather than aborting the whole
    swap. At least the tools gist and one system anchor must apply, or the caller passes through."""
    out, cursor, applied = [], 0, 0
    for anchor, gist_string in GIST["segments"]:
        pos = system_text.find(anchor, cursor)
        if pos < 0:
            continue  # this segment drifted; leave its text raw where it naturally sits
        out.append(system_text[cursor:pos]); out.append(gist_string)
        cursor = pos + len(anchor); applied += 1
    out.append(system_text[cursor:])
    if applied == 0:
        raise ValueError("no system anchor matched")
    return "".join(out)


def write_log_record(log_path, record):
    with log_lock:
        with open(log_path, "a") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def parse_sse_events(raw_bytes):
    """Turn the raw SSE byte stream into a list of (event_name, data_dict)."""
    events = []
    for block in raw_bytes.decode("utf-8", errors="replace").split("\n\n"):
        event_name = None
        data_lines = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
        if data_lines:
            try:
                events.append((event_name, json.loads("\n".join(data_lines))))
            except json.JSONDecodeError:
                events.append((event_name, {"_raw": "\n".join(data_lines)}))
    return events


def summarize_stream(events):
    """Reassemble the assistant message from streamed events: text, tool_use blocks, usage, stop."""
    content_blocks = []
    usage = {}
    stop_reason = None
    for event_name, data in events:
        event_type = data.get("type", event_name)
        if event_type == "message_start":
            usage.update(data.get("message", {}).get("usage", {}))
        elif event_type == "content_block_start":
            block = dict(data.get("content_block", {}))
            if block.get("type") == "tool_use":
                block["_partial_json"] = ""
            else:
                block.setdefault("text", "")
            content_blocks.append(block)
        elif event_type == "content_block_delta" and content_blocks:
            delta = data.get("delta", {})
            index = data.get("index", len(content_blocks) - 1)
            if index >= len(content_blocks):
                continue
            target = content_blocks[index]
            if delta.get("type") == "text_delta":
                target["text"] = target.get("text", "") + delta.get("text", "")
            elif delta.get("type") == "input_json_delta":
                target["_partial_json"] += delta.get("partial_json", "")
            elif delta.get("type") == "thinking_delta":
                target["thinking"] = target.get("thinking", "") + delta.get("thinking", "")
        elif event_type == "message_delta":
            usage.update(data.get("usage", {}))
            stop_reason = data.get("delta", {}).get("stop_reason", stop_reason)
    for block in content_blocks:
        if "_partial_json" in block:
            raw = block.pop("_partial_json")
            try:
                block["input"] = json.loads(raw) if raw else {}
                block["input_json_valid"] = True
            except json.JSONDecodeError:
                block["input_raw"] = raw
                block["input_json_valid"] = False
    return {"content": content_blocks, "usage": usage, "stop_reason": stop_reason}


class TapHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    upstream = None  # (scheme, netloc)
    log_path = None

    def log_message(self, format, *args):  # quieter default access log
        sys.stderr.write("%s %s\n" % (self.address_string(), format % args))

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        request_id = uuid.uuid4().hex[:12]
        started_at = time.time()
        body_length = int(self.headers.get("Content-Length") or 0)
        request_body = self.rfile.read(body_length) if body_length else b""

        request_json = None
        if request_body:
            try:
                request_json = json.loads(request_body)
            except json.JSONDecodeError:
                request_json = None

        # Qwen3.8 accepts reasoning effort xhigh/medium/low only; Claude Code sends "high" (and can send "max").
        # Remap here so the served model never sees an unsupported value. Original is kept in the log record.
        original_effort = None
        if request_json and self.path.startswith("/v1/messages") and isinstance(request_json.get("output_config"), dict):
            original_effort = request_json["output_config"].get("effort")
            if original_effort not in (None, "xhigh", "medium", "low"):
                request_json["output_config"]["effort"] = EFFORT_REMAP.get(original_effort, "medium")
                request_body = json.dumps(request_json).encode("utf-8")

        # Gist mode: replace the static span in the top-level system blocks with gist tokens. The tools
        # array stays in the request (the engine's tool-call parser needs it); the serving chat template
        # skips rendering the tool block when it sees gist tokens in the system content.
        gist_applied = False
        if GIST is not None and request_json and self.path.startswith("/v1/messages") and request_json.get("system") and request_json.get("tools"):
            system = request_json["system"]
            system_text = system if isinstance(system, str) else "".join(b.get("text", "") for b in system if b.get("type") == "text" and b.get("text"))
            for old, new in NORMALIZE:
                system_text = system_text.replace(old, new)
            import hashlib
            live_hash = hashlib.sha256(json.dumps(request_json["tools"], sort_keys=False, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            if GIST.get("tools_hash") and live_hash != GIST["tools_hash"]:
                sys.stderr.write("gist: tool catalogue hash mismatch, passthrough\n"); request_json = request_json  # explicit no-op: served raw
            try:
                if GIST.get("tools_hash") and live_hash != GIST["tools_hash"]:
                    raise ValueError("catalogue hash mismatch")
                gisted = GIST["tools"] + gist_system_text(system_text)
                request_json["system"] = [{"type": "text", "text": gisted}]
                request_body = json.dumps(request_json).encode("utf-8")
                gist_applied = True
            except ValueError as error:  # span not found: pass through untouched, but log it
                sys.stderr.write("gist: span anchor not found, passthrough (%s)\n" % error)

        forward_headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}
        forward_headers["Content-Length"] = str(len(request_body))
        forward_headers["Connection"] = "close"

        scheme, netloc = self.upstream
        connection_class = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        connection = connection_class(netloc, timeout=3600)
        try:
            connection.request(self.command, self.path, body=request_body, headers=forward_headers)
            upstream_response = connection.getresponse()
        except Exception as error:
            self.send_error(502, "upstream error: %s" % error)
            write_log_record(self.log_path, {
                "id": request_id, "ts": started_at, "path": self.path, "error": str(error),
                "request": request_json,
            })
            return

        is_stream = bool(request_json and request_json.get("stream"))
        first_byte_at = None
        first_token_at = None
        captured = bytearray()

        self.send_response(upstream_response.status)
        for header_name, header_value in upstream_response.getheaders():
            if header_name.lower() in HOP_BY_HOP_HEADERS or header_name.lower() == "content-length":
                continue
            self.send_header(header_name, header_value)

        if is_stream and upstream_response.status == 200:
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            while True:
                chunk = upstream_response.read1(65536) if hasattr(upstream_response, "read1") else upstream_response.read(65536)
                if not chunk:
                    break
                now = time.time()
                if first_byte_at is None:
                    first_byte_at = now
                if first_token_at is None and b"content_block_delta" in chunk:
                    first_token_at = now
                captured.extend(chunk)
                self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        else:
            payload = upstream_response.read()
            first_byte_at = time.time()
            captured.extend(payload)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            self.wfile.flush()
        connection.close()
        finished_at = time.time()

        record = {
            "id": request_id,
            "ts": started_at,
            "path": self.path,
            "status": upstream_response.status,
            "stream": is_stream,
            "ttfb_s": (first_byte_at - started_at) if first_byte_at else None,
            "ttft_s": (first_token_at - started_at) if first_token_at else None,
            "latency_s": finished_at - started_at,
            "request": request_json,
            "original_effort": original_effort,
            "gist_applied": gist_applied,
        }
        if self.path.startswith("/v1/messages") and upstream_response.status == 200:
            if is_stream:
                record["response"] = summarize_stream(parse_sse_events(bytes(captured)))
            else:
                try:
                    record["response"] = json.loads(bytes(captured))
                except json.JSONDecodeError:
                    record["response_raw"] = captured.decode("utf-8", errors="replace")[:4000]
        else:
            record["response_raw"] = captured.decode("utf-8", errors="replace")[:4000]
        write_log_record(self.log_path, record)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", default="127.0.0.1:8081")
    parser.add_argument("--upstream", default="http://127.0.0.1:8000")
    parser.add_argument("--log", default=os.path.join(os.path.dirname(__file__), "..", "logs", "requests.jsonl"))
    parser.add_argument("--gist", default=None, help="segments.json; enables gist substitution of the static span")
    parser.add_argument("--normalize", action="append", default=[], help="old=new replacement applied to the system text before anchoring (repeatable)")
    args = parser.parse_args()
    global GIST, NORMALIZE
    NORMALIZE = [tuple(item.split("=", 1)) for item in args.normalize]
    if args.gist:
        GIST = load_gist(args.gist)
        print("gist mode: tools gist %d tokens, %d system segments" % (GIST["tools"].count("<gist_"), len(GIST["segments"])))

    upstream_parts = urlsplit(args.upstream)
    TapHandler.upstream = (upstream_parts.scheme, upstream_parts.netloc)
    TapHandler.log_path = os.path.abspath(args.log)
    os.makedirs(os.path.dirname(TapHandler.log_path), exist_ok=True)

    host, port = args.listen.rsplit(":", 1)
    server = ThreadingHTTPServer((host, int(port)), TapHandler)
    print("tap listening on http://%s -> %s, logging to %s" % (args.listen, args.upstream, TapHandler.log_path))
    server.serve_forever()


if __name__ == "__main__":
    main()
