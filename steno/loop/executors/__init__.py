"""Stage executors for migrated journeys (steno-design.md build order step B7).

Wave 2 migrates exactly one journey, J11 (`experiments/journeys/j11-conn`), onto the
`steno.loop.runner`'s `stage_executors` seam, dry-run only: nothing in this package makes a
network call, provisions anything, or runs a remote command. See `README.md` in this directory
for what "migrate" means here and `dryrun.py` for the command that exercises it.
"""
