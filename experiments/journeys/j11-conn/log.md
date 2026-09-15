# J11: connector-ceiling test (review finding F-4-1)

Question: with the load generator's client connection cap removed, does the engine hold
more than 100 concurrent sequences on the H200? If yes, the "recurrent-state residency
ceiling" and the turnover mechanism claimed in the paper must be withdrawn.

Design: same tuned config as B5 (40960 / 256 seqs / 0.92 / 16384), both arms,
concurrency 128 and 256, client cap set explicitly to 100 (reproduces the confound)
and 512 (removes it). 180 s measurement, 30 s warm-up, 8 runs.

```
[ ] 1. loadgen conn-limit fix committed (default unlimited, cap recorded per run)
[ ] 2. provisioner takes CHAIN_SRC + MIN_CREDIT
[ ] 3. offer selected, instance created, ledger row written
[ ] 4. chain launched, checkpoint built, server up
[ ] 5. B6 runs complete
[ ] 6. results synced
[ ] 7. instance destroyed, ledger closed
[ ] 8. journey.md written
```

## Operations log
2026-09-15T08:03:14Z created instance 51097059 (offer 46122989, $3.89/hr) label=j11-conn
2026-09-15T08:03:14Z waiting for ssh on 51097059
2026-09-15T08:03:51Z ssh up: 209.90.228.18:50917
2026-09-15T08:03:54Z shipping scripts
2026-09-15T08:06:46Z shipping corpus
2026-09-15T08:07:58Z shipped; launching chain
2026-09-15T08:10:29Z ABORT: chain or watchdog not running after launch -> destroying instance 51097059
2026-09-15T08:10:38Z destroy verified

### 2026-09-15 08:03-08:10Z — attempt 1 aborted by a false liveness check
Instance 51097059 (H200 NVL, $3.89/hr) created, ssh up in 37s, files shipped, chain launched
and confirmed running by its own marker file (`conn_chain_start` 08:08:01Z, `download_attempt_1`
08:08:03Z). The provisioner nonetheless destroyed it at 08:10:38Z.

Cause: the post-launch check was `pgrep -f 'bench_[c]hain'`, hardcoded to the old chain name.
This run used CHAIN_SRC=vast/conn_chain.sh, so the pattern could never match. Two compounding
defects: (1) the check was coupled to a filename that had just been made configurable; (2)
rsh.sh retries any non-zero exit as a transport failure, so a legitimately false boolean was
retried eight times and then read as a dead box.

Fix: liveness is now established from the chain's own `chain_start` marker in /root/STATE,
polled for up to 80s, which is what actually matters and is chain-name independent. The
watchdog check returns a printed token (WD_OK / WD_MISSING) so a false result is not retried
as a dropped link. Cost of the defect: $0.47 and one relaunch.
