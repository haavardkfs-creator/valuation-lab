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
- Done: the Python for it. `last_year_ratios`, `fade_growth_rates` and
  `starting_point_assumptions` in `valuation.py`, and `STARTING_POINT_YEARS` in
  `assumptions.py`, with 19 new tests against the sheet's cells (C5:C10 and D17:H22). Merged.
- Done: `data.py`'s package carries last year's figures: `prior_year_revenue`, `income_tax`,
  `income_before_tax`, `capex` and `cash_from_working_capital`, filled in for Adobe in the
  snapshot with their 10-K pages, and tested through `last_year_ratios` and
  `starting_point_assumptions` against the sheet. Merged.
- Done: the cost of debt for other companies. Haavard added rows 24-27 to the `starting
  point` sheet (interest expense 263 / debt 6,210 = 4.24%), `estimate_pre_tax_cost_of_debt`
  in `valuation.py` matches C27, and `.gitignore` ignores Excel's `~$` lock files. Merged.
- Done: a `"yahoo"` data source in `data.py` that builds the whole package for any company
  from Yahoo's statements (`fetch_yahoo_statements`, `yahoo_source`). `interest_expense` joins
  the package; the 10-K cost of debt and the peer multiples are `OPTIONAL_FIELDS`;
  `valuation.financial_debt` adds current and long-term debt; the risk-free rate and equity
  risk premium are named constants dated 1 Nov 2026. Merged.
- Done: the ticker box. A "Company ticker" box in the sidebar (opens on ADBE). Adobe is
  unchanged. Any other company gets the starting point from its own last year, the estimated
  cost of debt, numbered years ("Year 1-5"), no peer multiples, and a yellow "starting point,
  not a forecast" warning. A ticker Yahoo does not know, a company with no pre-tax profit, or a
  WACC at or below terminal growth shows a plain red error and the footer. `test_app.py` runs
  the page with fake Yahoo data. Merged and live.
- Done: capex fades. Haavard changed row 21 of the `starting point`
  sheet and added a worked example (rows 29-32: capex 35%, D&A 12%, fading to 12%). In Python,
  `fade_capex_pcts` steps capex down to the D&A level in equal steps, and never pushes it up
  (Adobe's 0.75% against D&A of 3.44% stays flat); `starting_point_assumptions` uses it. 5 new
  tests against the sheet's cells; 235 tests pass. On real data Microsoft moves from a DCF price
  79% below the market to 48% below.
- Done: working capital fades to zero, and currency. Aker ASA (AKER.OL) showed kroner with dollar
  signs, and Novo Nordisk and Shell mixed currencies (statements in DKK with a USD price;
  statements in USD with a price in pence). The `"yahoo"` source now asks Yahoo for the
  statement currency, the price currency and the exchange rate for each, and converts every
  money figure and the share price to US dollars (`valuation.convert_currency`); pence go
  through pounds. The page says what was converted and at what rate. Ratios do not change.
  Also fixed: a low-WACC company could crash the page through the heatmap; it now says why the
  table is missing. New tests for kroner, DKK/USD, pence, a missing rate and the low-WACC page.
  Working capital: Haavard changed row 22 of the `starting point` sheet so it fades to zero
  over the five years (replacing "hold at last year's level"), and `fade_working_capital_pcts`
  in `valuation.py` matches it. On real data (6 Nov 2026): Coca-Cola goes from a DCF price 74%
  below the market to 28% below, Aker from 31% below to 2% above. Adobe's page is unchanged.
  251 tests pass.
- Done: the fallback cost of debt (merged, PR #29). Haavard added rows 34-58 to the
  `starting point` sheet (risk-free 5.29% + BBB credit spread 1.11% = 6.40%, plus an Apple
  worked example). `fallback_pre_tax_cost_of_debt` in `valuation.py` and `CREDIT_SPREAD` in
  `data.py` match it. When Yahoo has no interest expense, `yahoo_source` uses the fallback and
  the page shows a yellow note. Apple's WACC is 10.010% with it and 10.002% with its own AA
  rating, a gap of 0.009 points. 9 new tests; 260 tests pass.
- Done: the low-WACC caution (merged, PR #30). Haavard added "Terminal value checks"
  to the `valuation` sheet (rows 30-32: terminal value share 70.0%, WACC minus terminal growth
  8.4 points). `terminal_value_share` and `wacc_minus_terminal_growth` in `valuation.py` match
  them; the limits (75% and 4 points) are in `assumptions.py`. The page says what share of the
  value is terminal value and shows a yellow caution when a limit is crossed (Coca-Cola: both;
  Microsoft: the share; Adobe and Apple: none). 11 new tests; 271 tests pass.
- Done: peer medians that skip missing peers (merged, PR #31). Haavard built a worked
  example on the `Multiples` sheet (rows 41-49: PepsiCo, Keurig Dr Pepper, Mondelez, with
  Keurig's P/E blank on purpose). `usable_multiples` and `median_of_usable_multiples` in
  `valuation.py` match it; `MINIMUM_PEERS = 2` is in `assumptions.py`; `run_multiples` returns
  None for a multiple with too few peers. Adobe is unchanged. 13 new tests; 284 tests pass.
- Done: suggesting peers (merged, PR #32). `size_gap` and `closest_peers` in
  `valuation.py` pick the peers closest in size; `fetch_peer_candidates`, `fetch_peer_quote`,
  `peer_multiples` and `suggest_peers` in `data.py` look them up on Yahoo (swappable for tests);
  `PEER_CANDIDATES_TO_CHECK` (20), `PEER_BIGGEST_SIZE_GAP` (10) and `SUGGESTED_PEERS` (5) are in
  `assumptions.py`. On real data: Coca-Cola gets PEP, MNST, KDP; Apple none; Microsoft one. Nothing
  is on the page yet. 23 new tests; 307 tests pass.
- Done: the peer box (merged, PR #33). Other companies get a "Peer tickers" sidebar box,
  pre-filled with up to 5 suggested peers and editable (at most 8), and the "Peer multiples"
  section: three prices, the middle price, DCF vs multiples, and a table of the peers' multiples
  with dashes for missing ones. "Not enough peers" where a multiple has fewer than 2 usable peers.
  Adobe is unchanged. `MAX_TYPED_PEERS` (8) is in `assumptions.py`. Checked on live Yahoo data
  (Coca-Cola, Apple, Pfizer). 16 new tests; 323 tests pass.
- Done (in the open pull request): an overview of the stock. Haavard added "Adobe's overview" to the
  `Multiples` sheet (rows 52-64) and the peers' operating margins to the Coca-Cola example (G43:G46).
  `stock_overview` in `valuation.py` (market value, EV, EV/Sales, EV/EBITDA, P/E, operating margin,
  revenue growth, last-year free cash flow and its yield, net debt over EBITDA) matches the cells, and
  `median_of_available` matches G46. The page has an "Overview" section of eight numbers; the peers
  table now has the company's own row first, a "Peer median" row last and an "Op. margin" column
  (peers' margins come from Yahoo; for Adobe they are fetched live). "Not meaningful" where a number
  would mean nothing. 29 new or changed tests; 339 tests pass.
- Done (in the open pull request): roadmap #4, visible assumptions. A "What the model assumes"
  section under the Overview shows the actual growth, margin, tax rate, D&A, capex and working capital
  for each forecast year after the sliders, with the terminal growth, the WACC and the slider
  changes below. The growth and margin sliders are now in percentage points ("+0.0 pts"), which fixes
  the "-0 %" (stepping in 0.005 landed on -5e-18); `percent()` never writes -0.0%. 11 new tests;
  350 tests pass. Checked in the running app.
- Done (in the open pull request): roadmap #9, a transparent WACC. A "How the WACC is built" section
  shows every step of the WACC sheet with where each input comes from (typed in by hand, Yahoo Finance
  today, the 10-K, or an estimate) and a sentence that says why the number is what it is. New
  `capital_weights` and `wacc_breakdown` in `valuation.py` match the sheet's cells, and `wacc()` now
  uses `capital_weights`. `MARKET_FIGURES_SOURCE` in `data.py`. 9 new tests; 363 tests pass.
- Done (in the open pull request): roadmap #5a, warnings about the peers. A yellow warning when the
  company's operating margin is more than 10 points from its peers' middle; a "Flag" column and a line
  under the table for peers with a margin under 5% or a multiple more than 3 times, or under a third
  of, the peers' middle (flag only: they still count in the medians); and an honest label for the
  middle price ("Middle of the three prices", "Average of two prices" with a warning, "The only
  price"). `margin_gap`, `is_outlier` and `flag_peers` in `valuation.py`; the limits are in
  `assumptions.py`. Checked on live data (First Solar, Coca-Cola, Pfizer, Adobe). 26 new or changed
  tests; 389 tests pass.
- Done: roadmap #1a, history (merged, PR #39). Haavard added the `history` sheet (Adobe
  FY2022-FY2025, ratios as formulas). A "History" section under the Overview shows up to 5 years (Yahoo
  gives 4 or 5) of revenue, growth, operating income and margin, net income, reported free cash flow and
  its margin, diluted average shares and their yearly change, with two charts and notes on how reported
  free cash flow differs from the model's and on what the share count is. `fetch_yahoo_history`,
  `history_in_dollars` and `get_history` in `data.py`; `yearly_growth` and `ratios_by_year` in
  `valuation.py`. Checked in the running app (Adobe, First Solar). 26 new tests; 415 tests pass.
- Done: roadmap #1b (merged, PR #40), is the latest year typical? Haavard added the earlier
  average, the gap and the swing to the `history` sheet (C20:C22). `history_check` in `valuation.py`
  matches them; the limits (5 points, 15 points, at least 3 years) are in `assumptions.py`. The History
  section shows a yellow warning when the latest operating margin is more than 5 points above ("may be a
  peak") or below ("may be a bottom") the earlier average, and one when the margin has swung by more than
  15 points. Warnings only: the valuation is unchanged. Checked on live data (First Solar: both; Pfizer:
  the swing; Adobe, Coca-Cola, Apple: none). 16 new tests; 431 tests pass.
- Done (in the open pull request): roadmap #2, the reverse DCF. Haavard built the `reverse dcf` sheet
  (a copy of the DCF with a margin shift and a growth shift, and two Goal Seek results). `solve_for_target`
  and `reverse_dcf` in `valuation.py` match them; the search range and tolerance are in `assumptions.py`.
  A "What the market price implies" section under the DCF numbers gives the average operating margin, and
  separately the average revenue growth, that would make the DCF equal the market price, against the model's
  and against the company's history. Uses the page's WACC, terminal growth and sliders. 23 new tests; 454
  tests pass. Checked on live data (First Solar, Adobe, Coca-Cola, Nvidia) and in the running app.
- Next: roadmap #3, a second sensitivity table (operating margin by revenue growth), then #5b and so on,
  as below. Small items waiting for Haavard's decision: Pfizer's negative tax rate, the adjusted beta, the
  empty-Yahoo-reply retry, and drawing the overview and history even when the DCF cannot be built.
- Open:
  - A negative tax rate flows into the forecast. Pfizer's last-year tax rate is -3.54% (a tax
    benefit; seen on 18 Nov 2026 in the new WACC table), and the starting point holds the tax rate
    flat, so its forecast cash flows are too high and its after-tax cost of debt (4.32%) is above
    its pre-tax cost (4.18%). Together with its low beta this explains its DCF price. Needs a
    decision, for example floor the tax rate at zero or use a normal rate, built in Excel first.
  - A company that lost money last year gets only an error, so no overview and no history. For Ford
    (18 Nov 2026) the page says "A tax rate can't be worked out because the company made no pre-tax
    profit", because the starting point needs last year's tax rate, and nothing below it is drawn. The
    overview and the history do not need a tax rate and would help most here. Needs a decision: draw them
    even when the DCF cannot be built.
  - Low-beta companies get odd DCF prices: on 16 Nov 2026 Pfizer's WACC is 5.96% and its DCF
    price $94.96 against a market price of $28.89, and both terminal value cautions fire. The
    caution says so, but the cure is the planned adjusted beta.
  - Yahoo sometimes returns an empty quote to the live server: on 18 Nov 2026 NVDA showed "Yahoo
    Finance did not supply ... company_name, ... share_price, beta" and worked a few minutes later.
    Possible fix, not built: retry the quote once, and say "this is usually temporary, try again in
    a minute".
  - Even after the capex fade, Microsoft's DCF price is 48% below its market price ($278 vs
    $532, 6 Nov 2026). A starting point from one year is not a forecast, and a 17.8% grower
    fading to 2.5% over five years is a conservative path for it.
  - A starting point is mechanical. It does not know about one-off years, margins that are
    still rising or falling, or a company whose last year was unusual. The page must say so.
  - After a deploy that changes a file the app imports (for example `assumptions.py`), the
    live app can crash with an `AttributeError` because the server still holds the old copy
    in memory. This happened after the WACC slider merge. Fix: Manage app, the three dots,
    Reboot app. It is not a code bug.
  - The workbook's sensitivity table (valuation sheet, rows 37–41 since the terminal value checks were added above it) uses a rounded WACC of
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
