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
- Done: Phase 5, step 6 — a "Behind the number" section with two charts: revenue and free
  cash flow for FY2026-30, and the two parts of enterprise value (five forecast years and
  terminal value). Merged and live.
- Done: Phase 5, step 7 — `explanations.py` and a closed "What do these terms mean?" box
  under each of the four sections, using Haavard's glossary wording word for word
  (definition sentences only). `test_explanations.py` checks the wording against
  `docs/glossary.md`. Merged and live.
- Done: Phase 5, step 8 — the five new glossary entries (Upside vs market, Revenue growth,
  Operating margin, Peer median, DCF vs multiples) added to the boxes. Phase 5 is complete:
  sliders, WACC slider, sensitivity heatmap, charts, and a plain-language box under every
  section. Merged and live.
- Done: Phase 6 — README rewritten with the live link (https://valuation-l3b.streamlit.app),
  local-run steps and what is planned. Merged. Phases 0-6 are complete.
- Done: the live data source, step 1 — `live_source` in `data.py` takes today's share price
  and beta from Yahoo Finance (`yfinance==1.8.0`, pinned) and everything else from the
  snapshot. Registered as `"live"` in `SOURCES`. Twelve tests use fake Yahoo replies, never
  the internet. Merged.
- Done (merged): the live data source, step 2 — the app now uses it.
  `get_company_data_with_fallback` in `data.py` tries live and falls back to the snapshot;
  `app.py` remembers the answer for 15 minutes and shows a grey line (live) or a yellow
  warning (fell back) under the title. The page no longer shows exactly $305.60 at the
  default sliders, on purpose (see decisions). Five new tests; 166 tests pass.
- Done: the "starting point" sheet in `excel/valuation-lab.xlsx`, built by Haavard, and its
  write-up in `docs/model.md` ("Starting point for other companies"). It takes Adobe's FY2025
  ratios from `Projection`, fades revenue growth in a straight line to terminal growth over
  five years, and holds the other five ratios at last year's level. Merged.
- Done (in the open pull request): the Python for it. `last_year_ratios`,
  `fade_growth_rates` and `starting_point_assumptions` in `valuation.py`, and
  `STARTING_POINT_YEARS` in `assumptions.py`, with 19 new tests against the sheet's cells
  (C5:C10 and D17:H22). 185 tests pass. Nothing calls them yet: `data.py` and `app.py` are
  unchanged.
- Next: Haavard's call. The data package for other companies (`data.py`): last year's
  prior-year revenue, income tax, income before tax, capex and cash from working capital,
  first for Adobe from the snapshot, then from a live source. After that, a ticker box in the
  app. Other candidate: the optional Phase 7 (saving via Supabase).
- Open:
  - Decided, maths built, not yet used: for a company other than Adobe, the forecast
    assumptions start from that company's own last reported year (see `docs/decisions.md`,
    both 2026-11-06 entries). The data package still needs the new fields above, and the
    page must warn that a DCF suits stable, cash-generating companies.
  - A starting point is mechanical. It does not know about one-off years, margins that are
    still rising or falling, or a company whose last year was unusual. The page must say so.
  - After a deploy that changes a file the app imports (for example `assumptions.py`), the
    live app can crash with an `AttributeError` because the server still holds the old copy
    in memory. This happened after the WACC slider merge. Fix: Manage app, the three dots,
    Reboot app. It is not a code bug.
  - The workbook's sensitivity table (valuation sheet, rows 34–38) uses a rounded WACC of
    10.93% in its middle row, so it shows $305.48, not $305.60. Decided (see
    `docs/decisions.md`): the Phase 5 heatmap uses the exact WACC, so its centre cell is
    $305.60. It will not match the workbook's table in the middle row, on purpose.
  - The live source covers share price and beta only. Risk-free rate and equity risk
    premium (Damodaran) have no simple feed and stay typed in by hand, and the 10-K figures
    and peer multiples still come from the snapshot. `yfinance` is an unofficial Yahoo
    wrapper, so it can break or be rate-limited without warning. If that happens the app
    falls back to the snapshot and shows a yellow warning under the title.
  - The snapshot stores debt and cash as finished totals because `data.py` cannot add.
    A live source reading the 10-K's separate lines would need a small adding function in
    `valuation.py`.
