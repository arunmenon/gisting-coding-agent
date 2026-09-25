"""Steno run loop: the declarative `steno run <spec>` engine (wave 1, local only).

Wave 1 scope: run spec parsing and validation, a persisted lifecycle for stages
and rented resources, a compute backend protocol with a fake backend for tests,
the runner that drives a spec through the lifecycle, an append-only spend
ledger, and a small CLI. See steno-design.md section 2 and steno-loop/README.md.
"""
