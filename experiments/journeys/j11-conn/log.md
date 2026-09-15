# J11: connector-ceiling test (remediation of review finding F-4-1)

Program: gisting for coding agents. Journey 11. Date 2026-09-15.
Triggered by: `experiments/journeys/reviews/review-20260915T073918Z-codex.md`, finding
F-4-1, severity blocking.

## 1. Why this ran

The paper claimed a mechanism: on the hybrid model, the number of sessions a GPU can hold
resident is set by the recurrent-state cache, whose per-sequence cost does not depend on
prompt length. The evidence offered was a J10 B5 probe on an H200 in which both arms held
**exactly 100 resident sequences** at 83 percent KV usage with zero preemptions, while
throughput differed 85.5 to 50.0 requests per minute. From that the paper concluded the
gist wins by *turnover*, not by fitting more sessions.

The external reviewer observed that `experiments/bench/loadgen.py` constructed its HTTP
session as `aiohttp.ClientSession()` with no connector argument, and that aiohttp's default
`TCPConnector` limit is exactly 100 simultaneous connections. The observation "100 resident"
would then be a property of the load generator, not the hardware.

This journey decides that question.

## 2. Hypothesis and decision rule

Stated before the run, in `experiments/vast/conn_chain.sh`:

- If maximum resident sequences stays at or near 100 with the client cap lifted, the
  ceiling is real and the mechanism claim survives.
- If it exceeds 100, the ceiling is an instrument artifact and the mechanism claim must be
  withdrawn.

The chain computes and prints this verdict itself, from its own result files, so the
outcome is not a matter of post-hoc reading.

## 3. Instrument fix applied before the run

`experiments/bench/loadgen.py`, committed at `18bcb0d`:

- Added `make_session(a)`, which builds `aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=a.conn_limit, limit_per_host=a.conn_limit))`.
- Added `--conn-limit`, default `0`, which in aiohttp means unlimited. The library default
  of 100 is now never used implicitly.
- `conn_limit` is written into every run summary, so no future result file can be silently
  capped without the cap being visible in the record.

Both `closed_loop` and `open_loop` use the new session builder.

## 4. Design

Deliberately minimal, one variable.

| Element | Value |
|---|---|
| Hardware | H200 NVL 143,771 MB, single GPU, Washington US |
| Server | vLLM, context 40,960, max sequences 256, utilisation 0.92, batched tokens 16,384, prefix caching on |
| Checkpoint | 8:1 (`out_r8v2`), rebuilt on the box from the same maps and rows as J10 |
| Arms | `full` (`reqs_full.jsonl`), `gist8` (`reqs_gist8.jsonl`) |
| Offered concurrency | 128, 256 |
| Client connection cap | 100 (reproduces the confound), 512 (removes it) |
| Warm-up | 30 s, excluded from all statistics |
| Measurement window | 180 s |
| Output length | fixed 200 tokens, `ignore_eos` |
| Runs | 8 (2 caps x 2 arms x 2 concurrencies), 1 repeat each |

Order of execution was cap-major, then arm, then concurrency, so any drift in host
condition over the hour would affect both caps rather than one. Each arm was prewarmed with
an 8-session, 30-second pass at unlimited cap before its measured runs.

Server configuration is identical to J10 B5, and the checkpoint build reported the same
signature as J10 (`wrote 2171 gist rows ... mean row change 0.8264 (max 1.3579) | row norm
before 0.467 after 0.960`), which establishes that the model under test is the same one the
original measurement served.

## 5. Chronology, verbatim from the box

Attempt 1, instance 51097059, H200 NVL at $3.89/hr:

```
2026-09-15T08:03:14Z created instance 51097059 (offer 46122989, $3.89/hr) label=j11-conn
2026-09-15T08:03:51Z ssh up: 209.90.228.18:50917
2026-09-15T08:03:54Z shipping scripts
2026-09-15T08:06:46Z shipping corpus
2026-09-15T08:07:58Z shipped; launching chain
2026-09-15T08:08:01Z conn_chain_start        (on-box marker: the chain WAS running)
2026-09-15T08:08:03Z download_attempt_1      (on-box marker: work had begun)
2026-09-15T08:10:29Z ABORT: chain or watchdog not running after launch -> destroying instance 51097059
2026-09-15T08:10:38Z destroy verified
```

Attempt 2, instance 51099475, H200 NVL at $3.97/hr:

```
2026-09-15T08:38:05Z created instance 51099475 (offer 48497455, $3.97/hr) label=j11-conn-r2
2026-09-15T08:41:22Z ssh up: ssh3.vast.ai:19474
2026-09-15T08:41:26Z shipping scripts
2026-09-15T08:42:58Z shipping corpus
2026-09-15T08:43:46Z shipped; launching chain
2026-09-15T08:43:49Z conn_chain_start deadline=3h cfg=40960,256,0.92,16384 concs='128 256' conns='100 512' dur=180s
2026-09-15T08:43:52Z download_attempt_1
2026-09-15T08:44:04Z LAUNCHED chain + watchdog on 51099475 after 5m
2026-09-15T08:51:08Z ckpt_built (wrote 2171 gist rows into model-00003-of-00018.safetensors | mean row change 0.8264 (max 1.3579) | row norm before 0.467 after 0.960)
2026-09-15T08:53:10Z server_up len=40960 seqs=256 util=0.92 batched=16384
2026-09-15T08:58:00Z B6 conn=100 arm=full  c=128 rpm=59.7 max_running=100.0 kv_max=0.955 preempt=0.0 ok=179 err=0
2026-09-15T09:03:19Z B6 conn=100 arm=full  c=256 rpm=67.3 max_running=100.0 kv_max=0.868 preempt=0.0 ok=202 err=0
2026-09-15T09:07:53Z B6 conn=100 arm=gist8 c=128 rpm=74.0 max_running=100.0 kv_max=0.873 preempt=0.0 ok=222 err=0
2026-09-15T09:13:18Z B6 conn=100 arm=gist8 c=256 rpm=88.3 max_running=100.0 kv_max=0.822 preempt=0.0 ok=265 err=0
2026-09-15T09:17:44Z B6 conn=512 arm=full  c=128 rpm=47.0 max_running=123.0 kv_max=0.997 preempt=12.0 ok=141 err=0
2026-09-15T09:23:37Z B6 conn=512 arm=full  c=256 rpm=46.3 max_running=126.0 kv_max=0.997 preempt=16.0 ok=139 err=0
2026-09-15T09:28:16Z B6 conn=512 arm=gist8 c=128 rpm=80.7 max_running=128.0 kv_max=0.973 preempt=0.0 ok=242 err=0
2026-09-15T09:33:29Z B6 conn=512 arm=gist8 c=256 rpm=56.7 max_running=137.0 kv_max=0.999 preempt=38.0 ok=170 err=0
2026-09-15T09:33:29Z B6_done
2026-09-15T09:33:29Z BENCH_DONE
```

Results synced, instance destroyed 09:40Z, destruction verified against `show_instances`.

## 6. Complete results

Every measured quantity from all eight runs. Throughput is requests per minute over the
180 s window; latencies in seconds; `resident` is the maximum sampled
`vllm:num_requests_running`; `kv` is `vllm:kv_cache_usage_perc`; `queue`, `prefill` and
`decode` are engine-counter deltas in seconds summed across requests.

| cap | arm | asked | rpm | resident | kv max | kv mean | preempt | ok | err | e2e p50 | e2e p95 | ttft p50 | ttft p95 | prefix hit | prompt med | queue s | prefill s | decode s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 100 | full | 128 | 59.67 | 100 | 0.955 | 0.695 | 0 | 179 | 0 | 106.3 | 182.0 | 30.8 | 123.4 | 0.794 | 25677 | 3812 | 1491 | 19511 |
| 100 | full | 256 | 67.33 | 100 | 0.868 | 0.660 | 0 | 202 | 0 | 85.0 | 249.9 | 20.9 | 209.9 | 0.840 | 25977 | 3420 | 2235 | 25182 |
| 100 | gist8 | 128 | 74.00 | 100 | 0.873 | 0.644 | 0 | 222 | 0 | 81.4 | 170.2 | 28.8 | 109.4 | 0.589 | 11128 | 3540 | 1493 | 17931 |
| 100 | gist8 | 256 | 88.33 | 100 | 0.822 | 0.646 | 0 | 265 | 0 | 70.6 | 250.5 | 11.8 | 210.9 | 0.626 | 11917 | 2917 | 2352 | 26217 |
| 512 | full | 128 | 47.00 | 123 | 0.997 | 0.773 | 12 | 141 | 0 | 89.6 | 122.8 | 27.0 | 43.2 | 0.796 | 25016 | 6295 | 1386 | 20889 |
| 512 | full | 256 | 46.33 | 126 | 0.997 | 0.821 | 16 | 139 | 0 | 225.9 | 236.9 | 146.2 | 183.9 | 0.791 | 28070 | 42204 | 2164 | 33222 |
| 512 | gist8 | 128 | 80.67 | 128 | 0.973 | 0.759 | 0 | 242 | 0 | 86.6 | 97.4 | 22.5 | 28.4 | 0.596 | 11144 | 5121 | 1696 | 23312 |
| 512 | gist8 | 256 | 56.67 | 137 | 0.999 | 0.831 | 38 | 170 | 0 | 189.9 | 199.0 | 113.1 | 137.5 | 0.580 | 11828 | 35918 | 2072 | 32484 |

Zero request errors in all eight runs. Machine-readable copy in `results_table.md`;
raw files in `results/B6_*.json`.

## 7. What the numbers establish

### 7.1 The 100-sequence ceiling is an instrument artifact. Decisive.

At cap 100, maximum residency is exactly 100.0 in all four runs, in both arms, whether 128
or 256 sessions are offered. At cap 512 it is 123, 126, 128, 137. The J10 B5 observation is
reproduced exactly under the capped condition and disappears under the uncapped one.

Corroborating detail that was visible in J10 and missed: under the cap, KV usage maxima were
0.822 to 0.955 and preemptions were zero, meaning the engine had unused capacity it was
never offered work for. A genuine hardware ceiling would show the cache full.

### 7.2 The real binding constraint is KV saturation, which is prompt-length dependent.

At cap 512, KV maxima are 0.997, 0.997, 0.973, 0.999 and preemptions appear (12, 16, 0, 38).
The engine stops admitting because the KV cache is full, not because a prompt-length
independent recurrent-state pool is exhausted. This is the mechanism the paper explicitly
replaced.

### 7.3 The gist holds more sessions resident than the full prompt.

At 256 offered sessions with the cap lifted: 137 resident for the gist against 126 for the
full prompt. The "fits more sessions" effect the paper abandoned is present in the data.
Single run per cell; treat the magnitude as indicative, the direction as observed.

### 7.4 Lifting the cap reduced throughput in three of four cells. Important and awkward.

| arm | asked | rpm at cap 100 | rpm at cap 512 | change |
|---|---:|---:|---:|---:|
| full | 128 | 59.67 | 47.00 | -21% |
| full | 256 | 67.33 | 46.33 | -31% |
| gist8 | 128 | 74.00 | 80.67 | +9% |
| gist8 | 256 | 88.33 | 56.67 | -36% |

The 100-connection cap was acting as accidental admission control. Holding requests at the
client kept the engine off the preemption cliff; removing it let the server over-admit and
thrash. Consequences, both of which must be stated wherever these numbers appear:

- The J10 high-concurrency throughput figures are **not** simply understated by the cap.
  In three of four cells here, the cap **flattered** throughput. J10's high-concurrency
  points measured a client-throttled system, and the direction of the bias is not uniform.
- Lifting a client cap is not a free improvement. A deployed system needs explicit
  admission control. That is a real operational finding, not a caveat.

### 7.5 The arm ratio moves with the cap, so ratios at high concurrency are not portable.

Gist over full: 1.24 and 1.31 at cap 100 (c=128, c=256); 1.72 and 1.22 at cap 512. The
capped measurement is not a conservative version of the uncapped one. It is a different
measurement.

## 8. Confounds and limitations of J11 itself

Recorded so that this journey is not over-read in turn.

1. **Single run per cell.** No repeats, no dispersion estimate. Residency is a maximum of a
   5-second sampler, so the exact values 123 / 126 / 128 / 137 are lower bounds on a
   sampled quantity, not precise ceilings. The finding that residency exceeds 100 is robust
   to this; the specific numbers are not.
2. **Prefix hit-rate asymmetry between arms, unexplained and material.** The full arm runs
   at 0.79 to 0.84 prefix cache hit rate, the gist arm at 0.58 to 0.63, consistently across
   all eight runs. The full prompt shares far more cached prefix than the gist does. This
   favours the full arm and is present in the J10 data too. It was not controlled for in
   either journey, and it complicates every arm-to-arm throughput comparison in the program.
3. **Two concurrencies only.** 128 and 256. Where residency saturates between 100 and 137,
   and whether it would rise further at higher offered load, is not measured.
4. **The c=256 uncapped cells are in a thrashing regime** (queue-time deltas of 42,204 s and
   35,918 s, against 3,420 s and 2,917 s capped). Throughput there is not a capacity
   measurement of anything useful; it is a measurement of overload behaviour.
5. **One hardware class.** H200 NVL only. The H100 B2 probe in J10 reported 54 and 66
   resident with KV at 100 percent, which is below the cap and therefore not directly
   affected by this defect. That probe's *residency* numbers survive; its surrounding
   interpretation does not, because it was used to support a ceiling claim that the H200
   data was supposed to establish.
6. **No quality measurement.** As in J10. Nothing here speaks to whether output is correct.

## 9. Provisioning incident, attempt 1

Instance 51097059 was created, shipped, and launched successfully. Its own state file shows
`conn_chain_start` at 08:08:01Z and `download_attempt_1` at 08:08:03Z. The provisioner
destroyed it at 08:10:38Z regardless.

Cause: the post-launch liveness check was `pgrep -f 'bench_[c]hain'`, hardcoded to the
previous chain's filename. This run set `CHAIN_SRC=vast/conn_chain.sh`, so the pattern could
not match a healthy process. Two defects compounded:

1. The check was coupled to a filename that had been made configurable earlier in the same
   session, and the coupling was not updated.
2. `vast/rsh.sh` retries any non-zero exit status as a transport failure. A correctly
   returned "false" was therefore retried eight times and then interpreted as an unreachable
   box.

Fix, committed at `a0abd5f`: liveness is established by polling for the chain's own
`chain_start` marker in `/root/STATE` for up to 80 seconds, which is chain-name independent
and tests the thing that matters. The watchdog check now prints `WD_OK` or `WD_MISSING` so a
legitimately false result is not retried as a dropped link.

Cost of the defect: $0.47 and a 28-minute delay. No data lost.

Generalisable lesson for the experiment-journey skill: a liveness check must assert the
*condition*, never a process name, and a boolean carried over a retrying transport must be
returned as a printed token rather than an exit status.

## 10. Cost

| Item | Hours | Cost |
|---|---:|---:|
| Instance 51097059, H200 NVL @ $3.89/hr, aborted | 0.12 | $0.47 |
| Instance 51099475, H200 NVL @ $3.97/hr, complete | 1.03 | $4.09 |
| **Total** | **1.15** | **$4.56** |

Credit before 20.39, after 15.60. Both instances destroyed and verified. No live program
instances remain.

## 11. Artifacts

| Path | Contents |
|---|---|
| `results/B6_conn{100,512}_{full,gist8}_c{128,256}_r1.json` | 8 raw run files, full per-request records |
| `results/STATE` | on-box milestone log including the chain's own verdict block |
| `results/progress.log` | per-run summary and engine counters as printed on the box |
| `results_table.md` | the table in section 6 |
| `journey.md` | reader-facing account |
| `../../vast/conn_chain.sh` | the on-box chain, including the pre-registered decision rule |
| `../../bench/loadgen.py` | fixed load generator |

## 12. Checklist

```
[x] 1.  loadgen conn-limit fix committed (default unlimited, cap recorded per run)  18bcb0d
[x] 2.  provisioner takes CHAIN_SRC + MIN_CREDIT                                    18bcb0d
[x] 3.  offer selected, instance created, ledger row written                        08:38Z
[x] 4.  chain launched, checkpoint built, server up                                 08:53Z
[x] 5.  B6 runs complete, 8/8, zero errors                                          09:33Z
[x] 6.  results synced                                                              09:35Z
[x] 7.  instance destroyed, verified, ledger closed                                 09:40Z
[x] 8.  journey.md written                                                          dc5063d
[x] 9.  provisioning incident recorded and fixed                                    a0abd5f
[x] 10. remediation work order issued to the reviewer  reviews/findings-20260915-j11-remediation.md
[ ] 11. write-ups corrected (paper, deck, pptx, docx, cto-note, email-note, README)
[ ] 12. requester has seen the entry
```
