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
