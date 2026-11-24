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
- Done: roadmap #2 (merged, PR #41), the reverse DCF. Haavard built the `reverse dcf` sheet
  (a copy of the DCF with a margin shift and a growth shift, and two Goal Seek results). `solve_for_target`
  and `reverse_dcf` in `valuation.py` match them; the search range and tolerance are in `assumptions.py`.
  A "What the market price implies" section under the DCF numbers gives the average operating margin, and
  separately the average revenue growth, that would make the DCF equal the market price, against the model's
  and against the company's history. Uses the page's WACC, terminal growth and sliders. 23 new tests; 454
  tests pass. Checked on live data (First Solar, Adobe, Coca-Cola, Nvidia) and in the running app.
- Done: roadmap #3 (merged, PR #42), a second sensitivity table. Haavard read the price on the
  `reverse dcf` sheet at six pairs of shifts (C55:E60; Excel's Data Table would not fill). A table under the
  WACC heatmap gives the price at operating margins of -10 to +10 points and revenue growth of -4 to +4
  points, labelled with the average each gives, coloured against the market price, centred on the page's
  current settings so the middle is the DCF price. `margin_growth_table` in `valuation.py` matches the six
  readings; the steps are in `assumptions.py`. 17 new tests; 471 tests pass. Checked in the running app.
- Done: roadmap #5b (merged, PR #43), the company on trailing twelve months. Haavard built the
  `ttm` sheet (Adobe's four quarters to 31 Aug 2026). EV/Sales, EV/EBITDA, P/E and the operating margin in
  the Overview and in the peers table's own row now use the last four quarters, like the peers' figures;
  free cash flow yield, net debt over EBITDA, revenue growth, the History and the DCF stay on the last
  fiscal year, and the page says which is which. `trailing_total` and `ttm_overview` in `valuation.py` match
  the sheet; `fetch_yahoo_ttm`, `ttm_in_dollars` and `get_ttm` in `data.py`; `apply_ttm` in `app.py`. Handles a
  quarter with no figures yet (Nvidia) and a missing long-term debt line (First Solar). Falls back to the
  fiscal year, and says so, if Yahoo lacks the quarters. 27 new tests; 498 tests pass. Checked on live data
  (First Solar, Adobe, Coca-Cola, Nvidia, Apple).
- Done: roadmap #5c (merged, PR #44), peers by profile. Suggested peers are now the 5 whose
  operating margin and revenue growth are closest to the company's (within a tenth to ten times its size),
  not the closest in size, and a company whose industry gives fewer than 2 suitable peers (Apple, Microsoft)
  is topped up from its wider sector, with a note. `profile_distance` and the new `closest_peers` ranking in
  `valuation.py`; revenue growth in the quotes, `fetch_sector_candidates` and the top-up in `suggest_peers` in
  `data.py`; `PEER_SECTOR_CANDIDATES_TO_CHECK` in `assumptions.py`; the note and captions in `app.py`. A
  screening rule, so no Excel step. 33 new or changed tests; 525 tests pass. Checked on live data (Coca-Cola,
  Pfizer, First Solar, Apple, Microsoft, Nvidia, Exxon).
- Done: roadmap #7 (merged, PR #45), quality numbers. Haavard added the quality block to the
  `history` sheet (rows 24-35). A last row of the Overview gives ROIC (debt + equity - cash as invested capital;
  a tax benefit counts as no tax), cash conversion (reported free cash flow over net income), interest cover and
  the share count change over the history; the History table gets a cash conversion row. `quality_numbers` and
  its small functions in `valuation.py` match the sheet; `stockholders_equity` joins the data package (Yahoo; typed
  into Adobe's snapshot). "Not available", "No interest" and "Not meaningful" where they apply. 35 new tests; 553
  tests pass. Checked on live data (seven companies) and in the running app.
- Done: hardening against Yahoo (merged, PR #46) limiting the live app (it refused the server on 18
  and 20 Nov 2026, though Yahoo answered from the developer's machine). A plain "Yahoo Finance isn't answering
  the app right now ... try again in a few minutes. Adobe still works from a frozen snapshot." replaces the
  list of missing fields; an empty quote is asked for once more after 2 seconds; and the history, the last
  twelve months and the suggested peers are remembered for 6 hours instead of 15 minutes, to cut the number of
  requests. No Excel step. 18 new tests; 571 tests pass. Not a full fix: see Open.
- Done (in the open pull request): roadmap #8, adjustments for one-off items. Haavard added the adjusted
  margin to `starting point` (rows 60-66) and the adjusted TTM figures to `ttm` (rows 27-33). A sidebar box,
  "One-off items" (not for Adobe), takes one yearly amount in $ millions, applied to the last fiscal year's EBIT
  and the last twelve months' operating income; the DCF, margins, EV/EBITDA, ROIC, interest cover, the reverse DCF
  and both sensitivity tables use it, while net income, the P/E, cash conversion, revenue growth and the History
  stay as reported, and a yellow note says so. `apply_adjustment`, `apply_adjustment_to_ttm` and `adjustment_note` in
  `app.py`; no new maths in `valuation.py`. 18 new tests; 589 tests pass. Checked on live First Solar (-$500m: DCF
  $156 against a price of $152) and in the running app.
- Done (in the open pull request): a second data source, Financial Modeling Prep, behind Yahoo. When Yahoo is not
  answering, the company's figures, history, last twelve months, suggested peers and the peers' multiples come from
  Financial Modeling Prep (a key in Streamlit's private settings; without one the backup is off), and Adobe's chain is
  live Yahoo, live Financial Modeling Prep, then the snapshot. Yahoo gets a five-minute cool-down after refusing, a
  real problem with a company (unknown ticker) is never sent to the backup, and the page names the provider it used.
  `requests==2.34.2` pinned. Free plan: US companies only, 250 requests a day. 61 new tests; 650 tests pass.
- Done (in the open pull request): roadmap #6, scenarios. Haavard built the `scenarios` sheet (bear -5 / -2
  points, base 0, bull +5 / +2, weights 25/50/25; Adobe bear $248.29, base $305.60, bull $370.49, weighted $307.50).
  `run_scenarios` in `valuation.py` matches its cells; a "Scenarios" section under "What the market price implies"
  shows a table of the three cases and the weighted price, with editable boxes in a closed sidebar box; probabilities
  that do not add to 100% get a plain warning. Defaults in `assumptions.py`. 23 new tests; 673 tests pass. Checked in
  the running app. The FMP live check and key replacement are still to do (see Open).
- Done (in the open pull request): a normal tax rate and an adjusted beta. Haavard built both in `starting point` (rows
  68-73: a negative last-year rate becomes 21%; rows 75-84: adjusted beta = 2/3 x observed + 1/3 x 1, Pfizer 0.297 to
  0.5313). `tax_rate_used` and `adjusted_beta` in `valuation.py` match the cells; `NORMAL_TAX_RATE`, `BETA_WEIGHT_ON_OBSERVED` and
  `MARKET_BETA` are in `assumptions.py`. Applies to every company except Adobe (Adobe's base case stays $305.60). The page
  shows both betas and says when a tax rate was replaced. Pfizer's DCF goes from $96 to $65 against a market price of $28.
  17 new tests, 4 updated; 690 tests pass.
- Done: the cash flow check (merged, pull request 51). Investigating Pfizer (DCF $65, market $28) found no bug:
  about $7bn of costs sit between its operating profit and its pre-tax income and the model cannot see them.
  Haavard built the check in `history` rows 37-49; `free_cash_flow_check` in `valuation.py` matches it, the limit
  (1.25) is in `assumptions.py`, and the History section warns when the model's free cash flow for the last year
  is more than 25% above the reported one (Pfizer 1.83; nine other real companies are quiet). 13 new tests; 703
  tests pass.
- Done: a company whose DCF cannot be built still gets its overview and history. Ford
  (operating profit -9.2bn, pre-tax profit -11.8bn) used to get only the error "no pre-tax profit"; now the page shows
  the reason in red and then the Overview and History sections, and skips everything that needs a DCF (the DCF, what
  the market price implies, scenarios, assumptions, WACC, charts, sensitivity tables and peer multiples). The same
  goes for a discount rate at or below terminal growth. A bad ticker or missing data still gets only the error. No
  new maths, so no Excel step. 705 tests pass (one test rewritten, two added). Merged (pull request 52).
- Done: P/S added to the multiples, and counted in the middle price. Haavard built it
  in the `Multiples` sheet (G7:G13 peer P/S and median, row 30 the implied price, C35:C37 now over H27:H30, C66
  Adobe's own P/S). `price_from_ps` and `run_multiples` in `valuation.py` match the cells: P/S median 4.97x, price
  $286.03, the middle of the four prices $377.05 (was $420.52), DCF vs multiples -18.9% (was -27.3%). Yahoo's and
  Financial Modeling Prep's peer lookups both give P/S (FMP's `priceToSalesRatioTTM`, checked live against Yahoo:
  Apple 10.396 on both), the peer table has a P/S column, and a peer can be flagged "P/S outlier". Adobe's
  frozen snapshot has the four P/S of 20 Nov 2026, the other three columns are from April. 710 tests pass.
  Merged (pull request 53).
- Done: forward P/E added, the fifth multiple, counted in the middle price. Haavard built it in
  the `Multiples` sheet (rows 68-77: the peers' forward P/E, their median 14.25 and Adobe's next-year EPS 27.41; row 31 the
  price; C35:C37 now over H27:H31). `price_from_forward_pe` and `run_multiples` in `valuation.py` match the cells:
  forward P/E price $390.59, the middle of the five prices $390.59 (was $377.05), DCF vs multiples -21.8% (was
  -18.9%). Yahoo supplies both the peers' forward P/E and the company's own next-year EPS for free (so no FMP requests),
  converted to dollars at the share price's rate; the page says "No estimate" when there is none, and a peer can be flagged
  "Forward P/E outlier". With Yahoo down the FMP backup gives no forward P/E (it would cost requests). 723 tests pass.
  Merged (pull request 54).
- Done: #11, part 1 of 3, news and management (merged, pull request 55). A "News and management" section at the end of
  the page, for every company that loads (Ford too): the 5 most recent Yahoo headlines as links, with publisher and date,
  and Yahoo's top 5 officers with titles. Headlines and names are shown safely (formatting characters escaped, only
  https links), and if Yahoo cannot give them the section says so and the page carries on. No maths, so no Excel step.
  756 tests pass (33 new).
- Done: redesign Phase 1 of 5, the design system (merged, pull request 56). Haavard asked for a much more professional
  look (answer first, football field and other charts, tabs, polish). Phase 1 changes only how things look: a dark navy
  theme in `.streamlit/config.toml` (colours, rounded corners, the Inter font, chart colours) and a new `theme.py` that
  holds the same six-colour palette as Python constants, the card styling (rounded, bordered, soft shadow), a readable-text
  chooser, and `money_short` ($1.2B). The heatmap tint now works on dark (its strongest tint is capped so the text stays at
  4.5 contrast). `test_theme.py` (36 tests) checks every colour for readability, that the two files agree, and the number
  format. No valuation logic or text changed: all 756 earlier tests pass unchanged; 792 pass in all. Haavard chose: dark
  navy (replacing the earlier light-theme decision), one pull request per phase, existing number formats kept (the new
  style only in new visuals), English.
- Done: redesign Phase 2 of 5, the "answer first" header (merged, pull request 57). The top of the page now shows the
  company's name with a ticker badge and a verdict badge (UNDERVALUED / FAIRLY VALUED / OVERVALUED, from the DCF upside
  against the market price with a 15% limit; NO VERDICT when no DCF could be built), four cards (current price, DCF
  value per share, upside or downside as an arrow, a sign and a colour, and the middle of the five multiples prices),
  a line saying what the verdict rests on and that it is not advice, and a 12-month price sparkline. Plotly 7.1.0 is a
  new pinned dependency (first used for the sparkline; Phase 3's charts need it too). `valuation.verdict` and
  `assumptions.VERDICT_THRESHOLD`; `data.get_price_history`; header builders and the Plotly look in `theme.py`. Haavard chose:
  add Plotly now, a ticker badge instead of a logo (Yahoo has none), and the verdict from the DCF upside alone. Two old
  assertions that looked for a "Adobe Inc. (ADBE)" text line now look in the header (the old line was a duplicate and is
  gone); nothing else in the old tests changed. 846 tests pass (54 new).
- Done: redesign Phase 3a of 5, the DCF charts (merged, pull request 58). A new "Where the price sits" football field (one bar
  per method: the DCF across the WACC and growth table in the accent colour, the five multiples across the middle half of the
  peers, and the 52-week range, with a tick at each middle value, a dashed line at the market price and a one-sentence
  headline), and the "Behind the number" section rebuilt in Plotly: a waterfall from the DCF's parts to the equity value and
  the price, free cash flow (reported history in grey, forecast in blue, operating margin as a line), and a ring for the
  terminal value's share (red above 75%). Each chart has a headline sentence. Built Excel first: `Multiples` rows 80-89
  (`QUARTILE` ranges and the DCF range). `valuation.quartile_range`, `table_range`, `trading_range`, `football_field`,
  `methods_above_price` and `run_multiples`' new "price_ranges" match the cells. Haavard chose: two pull requests for Phase 3,
  the middle half of the peers for the bars, and the sensitivity table's range for the DCF bar. 897 tests pass (51 new).
- Done: redesign Phase 3b of 5, the sensitivity heatmaps and the peer charts (merged, pull request 59). Both sensitivity tables are
  now Plotly heatmaps: each cell shows its price and the upside against the market price with an arrow, green above and red below, a
  dashed line where the model equals the market price, a blue frame on the base case, and the exact prices in a closed box underneath.
  The WACC axis is now 7 rows, 3 points either way (so a high-beta company like NVIDIA, at 13.3%, shows 10-16%), and a pairing with
  no answer (growth at or above the WACC) stays blank instead of stopping the table. The peers get a sorted bar chart (a switch picks the
  multiple) and a scatter of EV/EBITDA against operating margin, each under a sentence. The football field's DCF bar keeps the workbook's
  narrow WACC range on purpose (a wide one would run Coca-Cola from $24 to $450). `valuation.sensitivity_table` takes
  `blank_impossible`, plus `upside_grid`, `cells_above_price` and a `table_range` that skips blanks. Haavard chose: 7 rows 3 points each way,
  one bar chart with a switch, and operating margin for the scatter. 943 tests pass (45 new); one test of the old all-or-nothing
  low-WACC behaviour was rewritten on purpose.
- Done: redesign Phase 4a of 5, the layout (merged, pull request 60). The page now has five tabs under the answer-first header:
  Overview (the football field, the overview, the history, news and management), DCF (the DCF cards, what the market implies,
  scenarios, assumptions, the WACC build, the charts behind the number), Multiples, Sensitivity (both heatmaps) and
  Explanations (every term of the glossary, grouped by where it is used). The overview is grouped by what the numbers say (what
  the market pays, growth and profitability, cash, debt and shareholders) at three cards a row, and now also shows P/S and forward
  P/E. The sidebar has four headings (Company, Assumptions, Peers, One-off items). A company with no DCF gets only the Overview and
  Explanations tabs. 959 tests pass (16 new). Peer table lookups in 13 tests now find the table by its columns instead of its
  position, and two order checks were updated on purpose (the Overview tab comes before the DCF tab; news is the last section of the
  Overview tab, not of the page).
- Done: redesign Phase 4b of 5, a ? on every multiple, card and chart (merged, pull request 61). The header's four cards and the
  verdict badge, the DCF cards, the five overview multiples, the five price boxes on the Multiples tab and the middle and gap
  boxes, the price chart and every chart headline (football field, waterfall, free cash flow, terminal value ring, both heatmaps,
  peer bars, scatter) now show an explanation when hovered. Where the glossary has the term the ? shows Haavard's glossary wording;
  the rest come from `HELP_TEXTS` in `explanations.py`, drafted by Claude from Haavard's own explanations for him to review (their
  fixed limits, such as the verdict's 15%, are filled in from `assumptions.py`). P/S and forward P/E are in the glossary in Haavard's
  exact words (`docs/glossary.md`, copied from his message). The closed "What do these terms mean?" boxes are gone, and the
  Explanations tab has a "Reading the page" section with the same help texts. 1010 tests pass (47 new).
- Done: redesign Phase 5 of 5, the polish, which finishes the redesign (merged, pull request 62). Loading messages ("Loading NVDA..."
  while a company is fetched, and a second one under the header while its history is). A friendlier not-found page: the original
  message plus a "Things to check" card (Apple is AAPL, an exchange ending for shares listed elsewhere, a few tickers to try), and
  "What you can do" instead when the data source was not answering. The DCF tab no longer repeats the header (it keeps the DCF price
  and the WACC and gains the terminal growth rate), "What the market price implies" no longer repeats the market price, and the
  verdict line under the name is one short sentence. The "Starting point, not a forecast" box is a calmer blue note. The two History
  charts are Plotly in the house style, each with a headline and a ?. Every page ends with a sources line and then the not-advice
  note, and the browser tab has an icon. 1038 tests pass (26 new); 11 old tests were repointed on purpose (eight read the "Market
  price" card that is now only in the header, two unpacked the old warning box, one checked the old verdict wording).
- Done: searching for a company by name, merged as pull request 63 (Haavard's idea, 20 Nov 2026, after the Nordnet search). A "Search by
  company name" box sits under the ticker box: typing part of a name and pressing Enter lists the matching companies as buttons
  ("Microsoft Corporation · MSFT · NASDAQ", at most 6), and one click puts the ticker in the ticker box and loads that company. When a
  ticker is not found, the page also offers "Did you mean one of these?" for what was typed (the mistyped "appl" offers Apple first).
  It uses Yahoo Finance's free search, keeps only company shares (futures, funds and duplicates are dropped, foreign listings stay
  with their exchange shown), is remembered for 15 minutes, leaves Yahoo alone while it is cooling down, and if it cannot search says
  so and the page still works. `data.search_companies`, `assumptions.SEARCH_*`. No maths, so no Excel step. 1069 tests pass (31 new);
  two sidebar assertions were updated on purpose (the sidebar now has two text boxes, and keeps its Company heading).
- Done (in the open pull request): an "Analyst view", from Haavard's wish for someone else's analysis instead of writing his own thesis
  (the thesis page was dropped before any code was kept). A section on the Overview tab, under the football field, with Yahoo
  Finance's analyst consensus: the rating and how many analysts (Adobe: hold, 33), the mean price target against today's price
  (+22.6%), the range of targets, a one-bar split of buy, hold and sell with a ? and a sentence that compares the target with the
  model's DCF value; and a new grey "Analysts" bar on the football field (low to high, tick at the mean), which does not count as a
  valuation method in its headline. Targets are converted to dollars at the share price's rate (Aker's kroner, Shell's pence);
  a company with thin coverage (Aker: 4) works, one with none (a small Oslo company) says so, and a failed lookup says so without
  stopping the page. These are other people's opinions and the section says that. `data.get_analyst_view`,
  `valuation.football_field(analyst_targets=...)`. No maths of ours, so no Excel step. 1135 tests pass (66 new).
- Done (in the open pull request): #11 part 2, a "Macro backdrop" at the end of the Overview tab: the 10-year Treasury yield, the
  Fed funds rate and US inflation (12 months) from FRED, each with its date and a ? help. Context only: nothing in the valuation
  uses it, and the page says the numbers are US ones. Needs `FRED_API_KEY` (Haavard put it in Streamlit Cloud's Secrets on
  20 Nov 2026, not in the local file, so the real FRED answer has not been seen on this computer: the first real look is the live
  app after the merge). One number failing leaves the other two; no key says so. `data.fetch_fred_latest`, `get_macro_backdrop`,
  `app.draw_macro_backdrop`. No maths, so no Excel step. 1158 tests pass (23 new; three layout tests updated on purpose because
  the Overview tab has one more section).
- Done (in the open pull request "the big three", commit 1 of 3): a shareable link. The page's address now holds the company, the
  growth and margin sliders, terminal growth, the typed-in WACC, the one-off amount and the peers, is rewritten after every
  change and read once when a visit begins. A bad or out-of-range value in an address is ignored. Checked in a real browser
  (opened a link, typed KO, reloaded the new address: same view). `app.settings_from_link`, `link_from_state`, `load_link`,
  `write_link`. No maths, so no Excel step. 1195 tests pass (37 new). The scenario boxes are not in the link.
  A linked visit logs one harmless line in the server log ("widget ... also had its value set via the Session State API").
- Done (in the open pull request "the big three", commit 2 of 3): a Compare tab. Type a second ticker and see the two companies
  side by side: a table (price, DCF value and upside, verdict, multiples value, WACC, terminal value share, market value,
  margin, growth, P/E, EV/EBITDA, free cash flow yield) and a bar chart of how far each valuation method is from each company's
  own market price. Both get the same sliders and typed-in WACC, each its own figures and peers; a second company that lost
  money still gets a column. The second ticker is part of the shareable link. Only shown when the first company has a DCF.
  `app.value_for_compare`, `compare_column`, `comparison_table`, `method_upsides`, `compare_figure`, `draw_compare`.
  No maths of its own (it reuses valuation.py), so no Excel step. The tab-order test was updated on purpose.
- Done (in the open pull request "the big three", commit 3 of 3): an optional live risk-free rate. A sidebar tick box (off by
  default) swaps the typed-in 5.29% for today's 10-year Treasury yield from FRED, for the page's company and for the Compare
  tab's second company; the WACC table names the source and date; the sidebar warns that Damodaran's equity risk premium was
  worked out with his own rate. Matched to the Excel model exactly: with `WACC!C8` typed as 4.50%, WACC 10.1812% and price
  $336.1776 (Haavard's two numbers, 20 Nov 2026), in `test_valuation.py` and on the page. Part of the shareable link.
  `data.risk_free_from_macro`, `app.draw_live_risk_free`, `apply_live_risk_free`. The "show the gap" idea is done (the sidebar
  note gives both rates).
- Done (merged, #67 "Cream on dark: new colours and type"): the redesign's build, pull request 1 of 6. The navy
  palette is now cream on dark brown with a brass accent, tabular figures everywhere, Inter in two weights, thin lines instead
  of shadows and a brass focus ring. `theme.py`, `.streamlit/config.toml`, `test_theme.py`; help texts say "gold" instead of
  "blue". New `lessons.md` holds Haavard's feedback. Design canvas: "Valuation Lab redesign" in Claude Design.
- Done (merged, #68 "One large number and a slider strip"): redesign pull request 2 of 6. The header leads with
  the DCF value per share at 56 px and its upside, with the market price and the multiples value to the right; the three
  sliders sit in a strip under the header, the WACC and the live risk-free boxes behind a "WACC and rates" button. CLAUDE.md
  now says Claude merges once the tests pass.
- Done (merged, #69 "True minus signs and one chart template"): redesign pull request 3 of 6. Negative numbers
  use the true minus sign (−) everywhere the page formats a number; every Plotly chart shares one template; peers and history
  are bronze in charts; the margin axis shows one decimal (no more 37%, 37%, 38%).
- Done (merged, #70 "Section labels and finding headlines on every tab"): redesign pull request 4 of 6. Each
  section starts with a small label and its finding as a 20 px heading; quieter tabs; plain tables at 13 px with numbers on the
  right; waterfall totals in sand; no bold in the heatmap tables.
- Done (merged, #71 "Calm notes, empty states and the error page"): redesign pull request 5 of 6. The source
  note sits under the header as a small outlined line with a dot; other notes are calm cards; an empty section shows its
  reason in a dashed card; the error page has the top bar instead of a big title.
- Done (merged, #72 "The phone layout"): redesign pull request 6 of 6, the last of the build. 16 px gutter, the
  large number and its upside side by side, the sliders stacked in the strip, no sideways scrolling at 390 px.
- Done (merged, #73 "Clearer sensitivity heatmaps"): polish A of 7. The dashed break-even line follows the
  cell edges instead of crossing the numbers; each cell has the price over a smaller upside; the column labels sit on top
  like a spreadsheet, the row title in the corner, the base case's labels in gold; cells near the market price stay
  almost neutral; long labels go on two lines and the upside shrinks on a phone.
- Done (merged, #74 "One calm style for every table"): polish B of 7. Every table is a plain table with
  lines between the rows only, numbers on the right, small taupe capitals for headers; the scenarios' "vs market price"
  has an arrow, a sign and sage or terracotta; the company's row in the peer table is gold; the WACC and the peer median
  sit under a taupe total line. The four interactive grids (assumptions, sensitivity numbers, peers, compare) are now
  plain tables too.
- Done (merged, #75 "Less grey text: notes behind How to read this"): polish C of 7. Fifteen sections kept
  their finding in front and moved their notes on method (what the colours mean, where figures come from) into a small
  closed "How to read this" line; no text was removed.
- Done (merged, #76 "The multiples tab: answer first, then five even cards"): polish D of 7. The middle
  price and DCF vs multiples come first, then the five multiple prices in one row of equal cards (two to a row on a
  phone) instead of 3, 2 and 2.
- Done (merged, #77 "Search in the top bar, and no sidebar"): polish E of 7. The app's name, the ticker box
  and the name search sit in one bar at the top; Scenarios, Peers and One-off items are buttons beside "WACC and rates"
  under the sliders; the share-the-view note moved to the footer. The sidebar is gone.
- Dropped: polish F, the "About this project" box. Haavard decided against it on 24 Nov 2026; its pull request (#79)
  was closed without merging.
- Done (merged, #78 "Tabs that read as questions"): polish G of 7. The six tabs are named as the questions
  they answer, in order: Where does the price sit? What is it worth? What do peers say? How sure are we? How does it
  compare? What do the terms mean? The names live in one place, `TAB_LABELS` in `app.py`. The polish round is done.
- Done (in the open pull request "Ask Yahoo less often"): Yahoo was limiting the live app (24 Nov 2026: the name
  search failed and BORR fell back to FMP, whose free plan does not cover it). Haavard chose the free fix: the name
  search, the analysts' view, the one-year price chart and the news are now remembered for 6 hours instead of 15
  minutes, and after Yahoo says no the page leaves it alone for 15 minutes instead of 5. If blocks keep happening, the
  next step is a paid FMP plan (about $20-30 a month, key in Streamlit secrets), which Haavard has not chosen.
- Done (in the open pull request "Source notes no longer overlap"): under the header, the line saying where the figures
  came from was half covered by the "Starting point" note below it (seen on BORR, 24 Nov 2026). Streamlit gives every
  caption a -1rem bottom margin; the source box now sets it to 0.
- Done: the plain sentence under the price (first-visit upgrade 1 of 3, 24 Nov 2026). Under the headline cards the
  page says, for example, "If Adobe Inc. grows revenue by 8.10% a year for the next five years, with an average
  operating margin of 37.65%, the model says one share is worth $305.60, 21.5% above today's market price of $251.47."
  It rewrites itself as the sliders move. `average_rate` in `valuation.py` does the averaging; `price_story` in `app.py`
  writes the words. Upgrades 2 (an "About the company" card) and 3 (slider hints and "Try this" presets) come next.
- Done: the "About" card (first-visit upgrade 2 of 3, 24 Nov 2026). Under the header, a bordered card names the
  company's sector, industry, full-time employees and headquarters, and the first two sentences of what it does, from
  Yahoo's profile. `fetch_yahoo_profile` and `get_company_profile` in `data.py` fetch it; `draw_company_profile` in
  `app.py` draws it, and the page remembers it for six hours. When Yahoo cannot give it, the card is left out. Not the
  "About this project" panel Haavard turned down.
- Done: slider hints and "Try this" buttons (first-visit upgrade 3 of 3, 24 Nov 2026). Under each slider a short
  hint says what it means and how many dollars one more percentage point moves the price (Adobe's base case: margin
  +1 pt ≈ +$7.25 a share). `price_change_per_point` in `valuation.py` works it out; `SLIDER_HINT_POINT` is in
  `assumptions.py`. Under the buttons, "Bear case", "Bull case" and "Back to base" move the sliders; the bear and bull
  shifts are the Scenarios box's, so they give the scenarios sheet's $248.29 and $370.49.
- Done: the "About" card is now one closed line (Haavard's pick, 24 Nov 2026), "About Adobe Inc. · Technology · ...",
  that opens to the description, so the sliders sit higher on the page. `profile_label` in `app.py` writes the line.
  Comparable transactions comes next, in its own thread.
- Next: check the macro numbers on the live app after the merge; the live FMP check with Yahoo switched
  off; the small items below. CLAUDE.md still needs Haavard's edits (the theme line, and rows for theme.py and test_theme.py).
- Open:
  - Ideas from Haavard (20 Nov 2026): (1) group the overview by type of multiple: done in Phase 4a; (2) a ? help on every
    multiple and every chart, like the overview has: done in Phase 4b; (3) search
    by company name that lists several matching tickers, like Nordnet's search: done (price and day change in the list would cost
    extra requests, so the list shows name, ticker and exchange only).
  - CLAUDE.md still says "Light theme in config.toml, colours only" under "Already decided", and lists `.streamlit/config.toml`
    as "Theme settings only" with no row for `theme.py` or `test_theme.py`. Haavard changes his own rules file: the lines
    to update are given in the pull request description.
  - P/S and forward P/E have no glossary entries yet: Haavard writes the wording in `docs/glossary.md`, then it goes into
    `explanations.py` and the multiples box (it holds EV/Sales, EV/EBITDA and P/E today).
  - Forward P/E uses analysts' adjusted EPS, which can sit far above GAAP EPS (Adobe 27.41 against 17.91). Fine for
    forward against forward, but the price from it leans on analysts' optimism; also only next year, not further out.
  - News and management are built (part 1); "management changes" cannot be shown, because Yahoo gives only today's officers
    and nothing is stored. The macro factors (interest rates, inflation, oil; the Federal Reserve's free FRED service
    needs its own key; rates feed straight into the WACC) are part 2 of #11, and the thesis page that gathers everything
    is part 3.
  - For a loss-maker the page still shows the "Starting point, not a forecast" warning and, if Yahoo has no interest
    expense, the cost-of-debt warning, both about a forecast that is not drawn. Harmless, but could be hidden.
  - Pfizer's DCF price is still $65 against a market price of $28 (20 Nov 2026). Investigated: no bug, but the model
    cannot see about $7bn of costs between its operating profit and its pre-tax income, nor a possible patent cliff (the
    market implies about -13.6% revenue growth a year). The History section now warns about the cash flow gap; typing
    -7000 into the one-off box takes the DCF to $42. What the $7bn is can be read in the 10-K's "other (income)/deductions".
  - The live app has a backup for Yahoo now (Financial Modeling Prep), but only for US companies, and the free plan's 250
    requests a day would run out after roughly twenty fresh companies. The key is in Streamlit Cloud's Secrets. It was
    shown in a screenshot and in chat on 20 Nov 2026; Haavard says he replaced it with a new one (in
    `.streamlit/secrets.toml` and in Streamlit Cloud) on 20 Nov 2026. On 20 Nov 2026 the new key worked
    against the real service (one `ratios-ttm` request for Apple answered, and its P/S matched Yahoo's). Still to do: the full live
    check with Yahoo switched off, to prove every step of the backup chain.
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
