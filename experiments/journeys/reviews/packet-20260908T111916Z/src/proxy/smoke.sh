#!/bin/bash
# One non-streaming and one streaming Messages API call through the tap, with a tool definition.
set -u
BODY='{"model":"qwen3.8-27b","max_tokens":200,"system":"You are a terse assistant.","tools":[{"name":"get_time","description":"Get the current time in a city","input_schema":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}],"messages":[{"role":"user","content":"What time is it in Prague? Use the tool."}]}'
echo "== non-streaming =="; curl -s -m 120 localhost:8081/v1/messages -H 'content-type: application/json' -H 'anthropic-version: 2023-06-01' -H 'x-api-key: dummy' -d "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps({'stop':d.get('stop_reason'),'usage':d.get('usage'),'content':[{k:v for k,v in b.items() if k!='thinking'} for b in d.get('content',[])]},indent=1)[:1200]); print('ERROR' if d.get('type')=='error' else '')"
echo "== streaming =="; curl -s -N -m 120 localhost:8081/v1/messages -H 'content-type: application/json' -H 'anthropic-version: 2023-06-01' -H 'x-api-key: dummy' -d "${BODY%\}},\"stream\":true}" | grep -cE "^event:"; echo "events above"
echo "== tap log =="; tail -2 "$(dirname "$0")/../logs/requests.jsonl" | python3 -c "
import sys,json
for l in sys.stdin:
    d=json.loads(l); print({k:d.get(k) for k in ['id','status','stream','ttft_s','latency_s']}, 'resp keys:', list((d.get('response') or {}).keys()))"
