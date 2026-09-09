#!/usr/bin/env python3
"""Stub Messages API server: logs each request to a JSONL file and replies end_turn immediately.
For probing what Claude Code sends under different flags, at zero model cost."""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
LOG = sys.argv[1] if len(sys.argv) > 1 else "logs/stub.jsonl"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8083
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try: req = json.loads(body)
        except Exception: req = None
        with open(LOG, "a") as f: f.write(json.dumps({"path": self.path, "request": req}) + "\n")
        if self.path.endswith("count_tokens"):
            out = json.dumps({"input_tokens": 100}).encode()
        else:
            out = json.dumps({"id": "msg_stub", "type": "message", "role": "assistant", "model": "stub", "content": [{"type": "text", "text": "ok"}],
                              "stop_reason": "end_turn", "usage": {"input_tokens": 100, "output_tokens": 1}}).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(out))); self.end_headers(); self.wfile.write(out)
HTTPServer(("127.0.0.1", PORT), H).serve_forever()
