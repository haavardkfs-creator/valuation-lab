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
- Done: the seven base case forecast assumptions live in `assumptions.py`, each with its
  Excel cell, checked by `test_assumptions.py`. Merged.
- Done: `run_multiples` in `valuation.py` runs the whole multiples comparison in one call,
  with three tests matching the Excel Multiples sheet. Merged.
- Done (in the open pull request): Phase 4 code — `app.py` shows Adobe's DCF ($305.60 vs
  market $251.47) and multiples ($333.58 / $420.52 / $463.54), with the disclaimer footer.
  Not yet run inside real Streamlit (this machine has Python 3.9 only); the numbers were
  checked with a stand-in for `streamlit`.
- Next: run the app for real, then deploy it to Streamlit Community Cloud (Haavard does the
  deploy), then Phase 6 puts the live link in the README.
- Open:
  - `README.md` still says "Phase 0 ... No valuation or app code exists yet" and "Nothing to
    run yet". It needs updating once the app is deployed (Phase 6).
  - `docs/model.md`, `docs/glossary.md` and `LEARNING.md` still have their old Phase 0
    placeholder text above the real content (e.g. "It is empty for now"). Haavard's call
    whether to tidy this.
  - The workbook's sensitivity table (valuation sheet, rows 34–38) uses a rounded WACC of
    10.93% in its middle row, so it shows $305.48, not $305.60. Phase 5's heatmap needs
    to decide which one it matches.
  - A live data source is not built yet. Plan: its own pull request, starting with share
    price and beta, then plugged into `SOURCES` in `data.py`. Risk-free rate and equity
    risk premium (Damodaran) have no simple feed and stay typed in by hand.
  - The snapshot stores debt and cash as finished totals because `data.py` cannot add.
    A live source reading the 10-K's separate lines would need a small adding function in
    `valuation.py`.
