# Status

- Done: Phase 0 project skeleton — folders, rules, empty docs, CI that passes with no tests.
- Done: Phase 1 — the Excel model (`excel/valuation-lab.xlsx`) is built for Adobe, every
  formula is written up in `docs/model.md`, and the base case gives an implied share price
  of $305.60.
- Done (in the open pull request): Phase 2 — `valuation.py` holds all the valuation maths
  and `test_valuation.py` has 26 tests that match the Excel model's exact values, including
  the $305.60 implied price, WACC 10.9266% and the three multiples prices. The pytest
  exit-code-5 workaround is removed from `tests.yml`.
- Next: Phase 3 — `data.py`, built so the data source can be swapped later.
- Open:
  - `docs/model.md`, `docs/glossary.md` and `LEARNING.md` still have their old Phase 0
    placeholder text above the real content (e.g. "It is empty for now"). Haavard's call
    whether to tidy this.
  - The workbook's sensitivity table (valuation sheet, rows 34–38) uses a rounded WACC of
    10.93% in its middle row, so it shows $305.48, not $305.60. Phase 5's heatmap needs
    to decide which one it matches.
  - `run_full_dcf` covers the DCF only. The multiples are separate function calls; a
    single "run everything" function may be wanted for the app in Phase 4 or 5.
  - Tests have so far been run locally on Python 3.9 and pytest 8.4; CI uses Python 3.12
    and pytest 9.1.1, so the first pull request run is the first check on those.
