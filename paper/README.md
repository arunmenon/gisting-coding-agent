# Paper build

Sources for the Gisting a Coding Agent whitepaper and executive deck.

Use a Python environment with Pillow, BeautifulSoup, python-docx and python-pptx. This checkout has those packages in `experiments/.venv/`.

```sh
cd paper
../experiments/.venv/bin/python draw_figs.py --serving-only
../experiments/.venv/bin/python build_neurips.py
../experiments/.venv/bin/python build_deck.py
../experiments/.venv/bin/python build_pptx.py
../experiments/.venv/bin/python build_docx.py
```

- `draw_figs.py` renders PNGs and updates `paper_figs/figs.json`. Omit `--serving-only` to rebuild every figure.
- `build_neurips.py` builds the paper HTML and refreshes `Gisting-NeurIPS-paper.html` in the repository root.
- `build_deck.py` builds the deck HTML and refreshes `Gisting-CTO-deck.html` in the repository root.
- `build_pptx.py` writes the editable `Gisting-CTO-deck.pptx` in the repository root.
- `build_docx.py` converts the paper HTML to `Gisting-NeurIPS-paper.docx` in the repository root and checks its image and table counts against the HTML.

Inputs and outputs resolve relative to these scripts, without session-specific scratch paths. Generated local HTML copies under `paper/` are intermediate files; the root HTML files are the published artifacts.
