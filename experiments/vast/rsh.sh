#!/bin/bash
# Shared remote helper (ALWAYS use this, never ad-hoc ssh in the interactive tool shell, which is zsh
# and does not word-split $VARS). Usage:
#   vast/rsh.sh pick  <instance_id>            -> prints "HOST PORT" of the first endpoint that answers (direct, then proxy)
#   vast/rsh.sh run   <host> <port> '<cmd>'     -> run a remote command (bounded retries, errors shown)
#   vast/rsh.sh put   <host> <port> <src...> <dest>  -> scp files/dirs (bounded retries, errors shown)
set -u
O=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -o LogLevel=ERROR)
TRIES="${RSH_TRIES:-8}"; PAUSE="${RSH_PAUSE:-15}"
case "${1:-}" in
  pick)
    IID=$2; PY=$(dirname "$0")/../.venv/bin/python3; KEY=$(cat ~/.vast_api_key)
    for i in $(seq 1 60); do   # up to 30 min: hosts pulling a large image can take >20 min to become reachable
      read DH DP PH PP ST <<< "$($PY -c "
from vastai import VastAI; v=VastAI(api_key=open(__import__('os').path.expanduser('~/.vast_api_key')).read().strip()); i=[x for x in v.show_instances() if x['id']==$IID]
if not i: print('- - - - gone')
else:
    x=i[0]; pm=(x.get('ports') or {}).get('22/tcp') or []
    print((x.get('public_ipaddr') or '-'), (pm[0]['HostPort'] if pm else '-'), (x.get('ssh_host') or '-'), (x.get('ssh_port') or '-'), (x.get('actual_status') or '?')+':'+str(x.get('status_msg') or '')[:40].replace(' ','_'))")"
      [ $((i % 4)) -eq 1 ] && echo "  [rsh] pick try $i/60 direct=$DH:$DP proxy=$PH:$PP status=$ST" >&2
      for ep in "$DH $DP" "$PH $PP"; do set -- $ep; [ "$1" != "-" ] && [ "$2" != "-" ] && ssh "${O[@]}" -p "$2" "root@$1" 'echo ready' 2>/dev/null | grep -q ready && { echo "$1 $2"; exit 0; }; done
      sleep 30
    done; echo "no endpoint answered for $IID" >&2; exit 1 ;;
  run)  H=$2; P=$3; shift 3; n=1; while ! ssh "${O[@]}" -p "$P" "root@$H" "$@"; do echo "  [rsh] run attempt $n/$TRIES failed" >&2; [ $n -ge $TRIES ] && exit 1; n=$((n+1)); sleep $PAUSE; done ;;
  put)  H=$2; P=$3; shift 3; n=1; DEST="${@: -1}"; SRC=("${@:1:$#-1}"); while ! scp -q "${O[@]}" -P "$P" -r "${SRC[@]}" "root@$H:$DEST"; do echo "  [rsh] put attempt $n/$TRIES failed" >&2; [ $n -ge $TRIES ] && exit 1; n=$((n+1)); sleep $PAUSE; done ;;
  *) echo "usage: rsh.sh pick|run|put ..." >&2; exit 2 ;;
esac
