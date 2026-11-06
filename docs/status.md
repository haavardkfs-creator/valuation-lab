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
- Done: Phase 5, step 2 — three sidebar sliders in `app.py` (growth shift, margin shift,
  terminal growth), ranges in `assumptions.py`, four range tests. Merged and live.
- Done: Phase 5, step 3 — `run_full_dcf` accepts an optional `wacc_override`, checked
  against all 25 cells of the workbook's sensitivity table. Merged.
- Done: Phase 5, step 4 — the sensitivity heatmap: a 5x5 table of prices by WACC and
  terminal growth, tinted against the market price, centred on the exact WACC so its middle
  cell is $305.60. `sensitivity_table` in `valuation.py`, checked against the workbook
  table. `pandas==3.1.1` pinned in `requirements.txt`. Merged and live.
- Done: Phase 5, step 5 — a "Set the WACC myself" tick box and WACC slider in the sidebar.
  Unticked, the model's exact WACC is used. The heatmap stays centred on the model's WACC.
  Merged and live.
- Done (in the open pull request): Phase 5, step 6 — a "Behind the number" section with two
  charts: revenue and free cash flow for FY2026-30, and the two parts of enterprise value
  (five forecast years and terminal value). Checked in real Streamlit.
- Next: Phase 5, last piece: the plain-language panel under every metric
  (`explanations.py`, drafted from `docs/glossary.md`; Haavard reviews the wording).
- Open:
  - After a deploy that changes a file the app imports (for example `assumptions.py`), the
    live app can crash with an `AttributeError` because the server still holds the old copy
    in memory. This happened after the WACC slider merge. Fix: Manage app, the three dots,
    Reboot app. It is not a code bug.
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
