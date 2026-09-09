# Paper build

Sources for the "Gisting a Coding Agent" whitepaper.

- `build_neurips.py` — generates `gisting-neurips.html` from inline content + `paper_figs/figs.json`.
- `draw_figs.py` — renders the figures (Pillow) into `paper_figs/*.png`.
- `build_docx.py` — converts the generated HTML into the Word document (python-docx + bs4).
- `paper_figs/` — figure PNGs and their base64 embedding (`figs.json`).

Note: the scripts contain absolute output paths from the session scratchpad; adjust the
`D`/output paths before re-running. Deliverables (`Gisting-NeurIPS-paper.{docx,html}`) live in the repo root.
