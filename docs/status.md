# Status

- Done: Phase 0 project skeleton — folders, rules, empty docs, CI that passes with no tests.
- Done: Phase 1 — the Excel model (`excel/valuation-lab.xlsx`) is built for Adobe, every
  formula is written up in `docs/model.md`, and the base case gives an implied share price
  of $305.60.
- Done: Phase 2 — `valuation.py` holds all the valuation maths and `test_valuation.py` has
  26 tests that match the Excel model's exact values, including the $305.60 implied price,
  WACC 10.9266% and the three multiples prices. Merged, and CI passes on Python 3.12.
- Done: Phase 3 — `data.py` supplies Adobe's figures from a
  frozen snapshot of the Excel model's numbers, through a source that can be swapped. Merged.
  `test_data.py` checks every figure against Excel and proves that data fed into
  `valuation.py` still gives $305.60 and the three multiples prices.
- Done (in the open pull request): the seven base case forecast assumptions now live in
  `assumptions.py`, each with its Excel cell, checked by `test_assumptions.py`.
- Next: Phase 4 — the smallest possible Streamlit app, deployed early.
- Open:
  - `docs/model.md`, `docs/glossary.md` and `LEARNING.md` still have their old Phase 0
    placeholder text above the real content (e.g. "It is empty for now"). Haavard's call
    whether to tidy this.
  - The workbook's sensitivity table (valuation sheet, rows 34–38) uses a rounded WACC of
    10.93% in its middle row, so it shows $305.48, not $305.60. Phase 5's heatmap needs
    to decide which one it matches.
  - `run_full_dcf` covers the DCF only. The multiples are separate function calls; a
    single "run everything" function may be wanted for the app in Phase 4 or 5.
  - A live data source is not built yet. Plan: its own pull request, starting with share
    price and beta, then plugged into `SOURCES` in `data.py`. Risk-free rate and equity
    risk premium (Damodaran) have no simple feed and stay typed in by hand.
  - The snapshot stores debt and cash as finished totals because `data.py` cannot add.
    A live source reading the 10-K's separate lines would need a small adding function in
    `valuation.py`.
