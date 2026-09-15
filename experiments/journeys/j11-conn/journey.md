# Journey 11: the ceiling that was ours, not the hardware's

*In everyday terms.* We had claimed a restaurant's kitchen could only ever serve one hundred tables at once, and we built a whole theory on that number. It turns out the kitchen was fine. The doorway we were sending orders through only fit one hundred at a time, and we had installed that doorway ourselves.

**The uncertainty this retires.** Whether the "100 resident sessions in both arms" observation on the H200, which the paper's turnover mechanism rested on, measured the serving engine or measured our own load generator.

## The question
With the load generator's client connection limit removed, does the engine hold more than 100 concurrent sequences?

## What we believed going in
The paper argued that the resident-session ceiling is set by the model's recurrent-state cache, independent of prompt length, and offered as evidence that on an H200 both arms held exactly 100 sessions at 83 percent key-value cache usage while throughput differed by a factor of 1.7. From that we concluded the gist wins by turnover rather than by fitting more sessions. An external review pointed out that the load generator constructs its HTTP session with library defaults, and that the default caps simultaneous connections at exactly 100.

## What we ran
The same H200 NVL 143 GB card class, the same tuned server configuration, and the same 8:1 checkpoint as the original measurement, rebuilt on the box and verified identical by row count and row-norm shift. Eight runs: both arms, at 128 and 256 requested sessions, with the client connection limit set explicitly to 100, which reproduces the original condition, and to 512, which removes it. Three-minute measurement windows after a thirty-second warm-up. The load generator now takes the limit as an argument and records it in every run file, so no future run can be silently capped.

## What the GPU showed us

| Connection cap | Arm | Sessions asked | Resident | Throughput | Cache | Preemptions |
|---|---|---:|---:|---:|---:|---:|
| 100 | full | 128 | 100 | 59.7 | 0.955 | 0 |
| 100 | full | 256 | 100 | 67.3 | 0.868 | 0 |
| 100 | gist | 128 | 100 | 74.0 | 0.873 | 0 |
| 100 | gist | 256 | 100 | 88.3 | 0.822 | 0 |
| 512 | full | 128 | 123 | 47.0 | 0.997 | 12 |
| 512 | full | 256 | 126 | 46.3 | 0.997 | 16 |
| 512 | gist | 128 | 128 | 80.7 | 0.973 | 0 |
| 512 | gist | 256 | 137 | 56.7 | 0.999 | 38 |

Throughput is requests per minute. Zero request errors in all eight runs.

The capped rows reproduce the original artifact exactly: precisely 100 resident whether 128 or 256 sessions are offered, in both arms, with the cache 82 to 96 percent full, meaning the engine had spare capacity it was never permitted to use. With the cap lifted, residency rises to 123, 126, 128 and 137. The ceiling is not 100 and never was.

Two further things the lifted runs show. The cache reaches 99.7 percent and preemptions begin, so the real constraint is the cache filling, which is prompt-length dependent, exactly the mechanism the paper replaced. And the gist arm sustains more resident sessions than the full arm at the same offered load, 137 against 126, which is the headcount effect the paper had abandoned.

The throughput ratio also changes with the cap. Capped, gist over full reads 1.24 and 1.31. Uncapped, it reads 1.72 at 128 sessions and 1.22 at 256, where the gist arm is itself preempting heavily. The capped measurement was not a conservative version of the truth; it was a different measurement.

## What we now understand differently
The paper's mechanism claim is withdrawn. We did not measure a recurrent-state residency ceiling, we measured our own client. The earlier finding that "both arms hold the same number of sessions" was manufactured by the instrument, and the turnover story built on it has no support. The honest position returns to something closer to what we first believed and then talked ourselves out of: the gist holds more sessions resident before the cache saturates, and the size of that advantage depends on how close the cache is to full.

Every number in the paper's residency section, and every high-concurrency point at 128 sessions and above in the earlier benchmark, was taken through the same capped client and cannot be read as a hardware result.

The instrument defect is fixed rather than noted. The load generator now sets its connection limit explicitly, defaults to unlimited, and writes the limit into every result file.

## What it cost
1.03 GPU-hours on an H200 NVL at $3.97 per hour, $4.09. A first attempt was destroyed by a false liveness check in our own provisioner seven minutes after creation, $0.47. Total $4.56.
