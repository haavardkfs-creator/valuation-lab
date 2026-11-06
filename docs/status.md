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
- Done: Phase 4 — `app.py` shows Adobe's DCF ($305.60 vs market $251.47) and multiples
  ($333.58 / $420.52 / $463.54), with the disclaimer footer. Merged, run for real in
  Streamlit (Python 3.12.10, Streamlit 1.64.0), and deployed to Streamlit Community Cloud
  at https://valuation-l3b.streamlit.app. Every merge to `main` now goes live there.
- Done: Phase 5, step 1 — `shift_rates` in `valuation.py` moves every year of a growth or
  margin list by the same amount, with five tests. Merged.
- Done (in the open pull request): Phase 5, step 2 — three sidebar sliders in `app.py`
  (growth shift, margin shift, terminal growth), ranges in `assumptions.py`, four range
  tests. Checked in real Streamlit: base case $305.60, growth +1 point gives $318.18.
- Next: Phase 5, as separate pull requests: a WACC slider (needs an override in
  `valuation.py`), the sensitivity heatmap (exact WACC, see `docs/decisions.md`), the
  charts, and the plain-language panel under every metric.
- Open:
  - `README.md` still says "Phase 0 ... No valuation or app code exists yet" and "Nothing to
    run yet". It gets the live link and a rewrite in Phase 6.
  - `docs/model.md`, `docs/glossary.md` and `LEARNING.md` still have their old Phase 0
    placeholder text above the real content (e.g. "It is empty for now"). Haavard's call
    whether to tidy this.
  - The workbook's sensitivity table (valuation sheet, rows 34–38) uses a rounded WACC of
    10.93% in its middle row, so it shows $305.48, not $305.60. Decided (see
    `docs/decisions.md`): the Phase 5 heatmap uses the exact WACC, so its centre cell is
    $305.60. It will not match the workbook's table in the middle row, on purpose.
  - A live data source is not built yet. Plan: its own pull request, starting with share
    price and beta, then plugged into `SOURCES` in `data.py`. Risk-free rate and equity
    risk premium (Damodaran) have no simple feed and stay typed in by hand.
  - The snapshot stores debt and cash as finished totals because `data.py` cannot add.
    A live source reading the 10-K's separate lines would need a small adding function in
    `valuation.py`.
