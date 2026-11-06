# Decisions

One dated paragraph per decision, and the reason.

## 2026-09-15 — Project skeleton and rules

Set up the Phase 0 skeleton before any valuation or app code: README, CLAUDE.md, docs
folder, `.streamlit/config.toml`, `.github` templates and workflow, and `.claude`
commands. Reason: the project needs a working structure, phase plan, and guard rails in
place before real code starts, so every later pull request has somewhere to record status
and decisions instead of living only in chat. Python 3.12, a light theme, and
`streamlit`/`pytest` pinned to their current versions were decided by Haavard ahead of
this session.

## 2026-09-15 — pytest exit code 5 treated as a pass

`pytest` exits with code 5 when it finds no test files at all, which would make the
GitHub Actions workflow show red before any tests exist. Reason: Phase 0 has no code to
test yet — `test_valuation.py` doesn't arrive until Phase 2 — so the workflow explicitly
treats exit code 5 as success, with a comment in `tests.yml` marking it as a temporary
workaround. Remove this workaround once Phase 2 adds real tests.

## 2026-11-04 — Phase 2: shape of valuation.py and where the base case lives

`valuation.py` is a set of small functions, one per formula line in `docs/model.md`, plus
`run_full_dcf`, which calls them in order and returns every intermediate number in a
dictionary. Two small helpers were added beyond the agreed list: `discount_factor`, shared
by both present-value functions, and `peer_median`, which uses Python's built-in
`statistics` module (no new dependency). Reason: small functions can each be checked
against one Excel cell, and the app can later call only `run_full_dcf`. No number is
hard-coded in `valuation.py`; the base case inputs live in a labelled block at the top of
`test_valuation.py`, each with a comment naming its Excel cell and source, so no new files
were needed. The cost of debt in that block is the exact Excel value (4.1642276…%), not the
rounded 4.16%, so the tests match the workbook to many decimal places.

## 2026-11-04 — pytest exit code 5 workaround removed

`test_valuation.py` now exists, so `tests.yml` runs plain `pytest` again. Reason: with real
tests present, a run that finds no tests would mean something is broken and should show
red, not pass quietly. This closes the 2026-09-15 workaround above.

## 2026-11-05 — Phase 3: data.py starts with a frozen snapshot, and test_data.py is added

`data.py` holds a written list of the figures every data source must supply
(`PACKAGE_FIELDS`), one first source (`snapshot_source`, Adobe's numbers exactly as typed
into the Excel model, frozen on 4 Nov 2026), a registry of sources (`SOURCES`), and
`get_company_data`, which fetches from the chosen source and checks the package is
complete. Reason for a snapshot first, not a live feed: a live source needs a new
dependency and its numbers would move, so they would stop matching the $305.60 Excel
answer and no test could pin them. A live source comes later as its own pull request and
plugs into `SOURCES` without changing `valuation.py`. The package holds facts only; growth,
margins, tax rate, D&A %, capex %, working capital % and terminal growth are judgments and
stay out (they become the sliders in Phase 5). Because `data.py` must not calculate, debt
(6,210) and cash and investments (6,595) are stored as finished totals with a comment
showing the sum. Tests for `data.py` go in a new file, `test_data.py`, which is not in
CLAUDE.md's folder table: one test file per module keeps each easy to find. It imports the
base case assumptions from `test_valuation.py` so they stay in one named place.

## 2026-11-05 — The forecast assumptions get their own file, assumptions.py

The seven forecast assumptions (revenue growth, operating margins, tax rate, D&A %, capex %,
working capital % and terminal growth) move out of `test_valuation.py` into a new file,
`assumptions.py`, one named constant each, with the Excel cell it came from. A matching
`test_assumptions.py` checks each value against Excel and runs them through `valuation.py`
to confirm the $305.60 answer. Neither file is in CLAUDE.md's folder table. Reason: the app
needs these numbers in one named place, and they fit nowhere else: they are judgments, so
not `data.py` (facts only), and they are numbers, so not `valuation.py` (maths only). Only
the single base case is held; slider ranges and scenarios wait for Phase 5. The base case
block in `test_valuation.py` stays as it is, on purpose: those tests keep their own copy of
the Excel values so they fail if `assumptions.py` ever drifts.

## 2026-11-05 — run_multiples added to valuation.py before the app is built

The Phase 4 app will show the multiples as well as the DCF. The multiples steps (three peer
medians, three prices, the middle price and the gap to the DCF) were only chained together
inside tests, so `app.py` would have had to repeat that chaining, which breaks guard rail 5
(the app draws, it does not compute). `valuation.py` now has `run_multiples`, which does
the chaining and returns every number in a dictionary, the same way `run_full_dcf` does for
the DCF. Reason: the app calls one function per part of the valuation and only draws what
comes back. It is its own pull request ahead of the app, one idea per pull request. No new
files: the tests went into `test_valuation.py`, which already holds the base case.

## 2026-11-05 — Phase 4: the first app shows Adobe's DCF and multiples, nothing else

`app.py` fetches Adobe's figures with `data.get_company_data`, takes the assumptions from
`assumptions.py`, calls `run_full_dcf` and `run_multiples`, and shows the results as number
tiles under two headings, with the "learning project, not investment advice" footer
(guard rail 13). Its only own functions are two display formatters (`dollars`, `percent`),
`run_valuation` (which calls `valuation.py` in the right order and does no maths) and three
drawing functions. Left out on purpose and left for Phase 5: sliders, charts, the
sensitivity heatmap, explanation panels, and a ticker box. The company is a named constant
(`TICKER = "ADBE"`) because the snapshot only holds Adobe. No test file for `app.py` was
added: the numbers it shows come from functions that are already tested against Excel, and
a page test would be a new file outside CLAUDE.md's folder table. Deployment to Streamlit
Community Cloud is done by Haavard after this is merged.

## 2026-11-05 — The Phase 5 heatmap uses the exact WACC, not the rounded 10.93%

The Excel sensitivity table (valuation sheet, rows 34–38) builds its middle row from a
rounded WACC of 10.93%, so its centre cell shows $305.48, while the model's own answer is
$305.60 (WACC 10.9266%). The Phase 5 heatmap will be centred on the exact WACC, so its
centre cell equals the headline price. Reason: two different numbers for the same base case
on one page would be confusing, and the rounding in the workbook was a typing shortcut, not
a modelling choice. The cost: the heatmap's middle row will differ from the workbook's table
by a few tenths of a dollar, and a test for it cannot copy that row from Excel directly. No
code was changed by this decision; it only settles the question for Phase 5.

## 2026-11-05 — Phase 5 sliders move all five years together: shift_rates in valuation.py

Growth and operating margin are lists of five yearly numbers, so a slider per year would mean
ten sliders. Instead one slider each will shift every year by the same number of percentage
points (for example +1.0 point turns 9% growth into 10%), and a shift of 0 gives the base
case, so the page still opens at $305.60. Terminal growth is a single number and gets an
ordinary slider. The adding is done by a new function, `shift_rates` in `valuation.py`,
because it is maths and `app.py` does not compute (guard rail 5). It is its own pull
request ahead of the sliders. Its tests are worked out by hand, not copied from an Excel
cell, because the Excel model has no shift; the one Excel-linked test shows that a shift of
0 still gives $305.60. No new files.

## 2026-11-05 — Phase 5: three sliders in the sidebar, ranges in assumptions.py

`app.py` gets three sidebar sliders: a growth shift and a margin shift (each moves every
forecast year by the same amount, -5 to +5 percentage points in steps of 0.5) and terminal
growth (0% to 4% in steps of 0.25). All three start at the base case, so the page still
opens at $305.60. The ranges are named constants in `assumptions.py` with a comment
(guard rail 6), checked by four new tests in `test_assumptions.py`, including one that runs
the DCF at all eight extreme corners to prove it always returns a positive price. Terminal
growth stops at 4% because the Gordon growth formula needs it to stay well below the WACC
(10.93%) and long-run growth above the economy's is not realistic. The sliders hold plain
decimals and Streamlit's own `"percent"` display format shows them as percentages, so
`app.py` does no ×100 maths. The ranges are my proposal; they are Haavard's to change.
The multiples do not move with the sliders, on purpose: they come from peers' multiples and
Adobe's reported figures, not from the forecast. No new files. Not yet built: a WACC slider
(needs an override in `valuation.py`), the heatmap, the charts and the explanation panels.

## 2026-11-05 — run_full_dcf can take a WACC of its own

`run_full_dcf` gets one optional input, `wacc_override`. Left out, nothing changes: WACC is
worked out from the cost of equity and cost of debt as before, and the base case is still
$305.60. When given, that rate is used as the discount rate instead, and the returned
`"wacc"` is the rate actually used. Reason: the Phase 5 heatmap needs the price at other
WACCs, and a later WACC slider needs the same thing, and a WACC that is only ever calculated
cannot be moved. The change is one `if` and no new function. It is checked against all 25
cells of the workbook's sensitivity table (valuation D34:H38), which uses the rounded WACCs
9.93% to 11.93%; that is only to prove the override matches Excel. The heatmap itself will
still be centred on the exact WACC (see the decision above). No new files.

## 2026-11-05 — Phase 5: the sensitivity heatmap, and pandas becomes a listed dependency

`valuation.py` gets `sensitivity_table`, which runs the DCF at every pairing of a WACC and a
terminal growth rate and returns the grid of prices; `app.py` draws it as a 5x5 table under
the DCF, WACC down the side (the model's exact WACC plus or minus 0.5 and 1 point) and
terminal growth along the top (1.5% to 3.5%), so the middle cell is the headline $305.60.
Each cell is tinted against the market price: white at it, greener above, redder below, so
the table says something at a glance. The growth and margin sliders move the whole table;
the terminal growth slider does not, because terminal growth is one of the table's axes.
Checked against the whole workbook table by giving it the workbook's rounded WACC.
`pandas==3.1.1` is added to `requirements.txt`: Streamlit already installs it, and the
styled table needs it, so this only lists and pins what was already there (guard rail 7,
agreed with Haavard). `matplotlib` is not needed because the colours are picked by a small
function in `app.py`. The table's pandas styling cannot draw a cell outline, so the base case
is shown in bold. Done as one pull request, not two, because the function and the table are
one idea and Haavard was short on time. No new files.

## 2026-11-05 — Phase 5: a WACC slider behind a "Set the WACC myself" box

The sidebar gets a fourth control: a tick box, "Set the WACC myself", and, only when it is
ticked, a WACC slider (6% to 14% in steps of 0.25%, starting at 11%) that is passed to
`run_full_dcf` as `wacc_override`. Unticked, the model uses its own exact WACC, so the page
still opens at $305.60 and the user can always get back to the exact base case, which a
slider alone could not do (its steps never land on 10.9266%). When the slider is in use the
WACC tile is labelled "WACC (your setting)". The heatmap stays centred on the model's own
WACC whether or not the slider is used, so it always shows the same base case; only the
headline moves. The slider's bottom is 6% so it always stays above the 4% top of the terminal
growth slider. Ranges are named constants in `assumptions.py` with tests. No new files and
no change to `valuation.py`: this reuses `wacc_override` from the earlier pull request.

## 2026-11-05 — Phase 5: two charts under the headline, using Streamlit's own bar chart

A "Behind the number" section sits between the DCF tiles and the heatmap. The left chart
shows revenue and free cash flow for FY2026-30 as paired bars, and moves with the growth and
margin sliders. The right chart shows the two parts of enterprise value, the five forecast
years and the terminal value, with a caption giving the dollar amounts. It uses Streamlit's
built-in `st.bar_chart` (with the `pandas` already pinned), so there is no new dependency, and
`valuation.py` does not change: every number was already returned by `run_full_dcf`. The year
labels are a named constant, `FORECAST_YEAR_LABELS`, in `assumptions.py` with a test, so
`app.py` does no year arithmetic. Two things found while checking in a real browser: the
dollar signs in the caption must be escaped (`\$`), because Streamlit reads text between two
dollar signs as a maths formula; and the charts zoom if the mouse wheel is turned over
them, which is a Streamlit feature, not a bug. No new files.

## 2026-11-05 — Phase 5: plain-language boxes from the glossary, and test_explanations.py is added

`explanations.py` (already in CLAUDE.md's folder table for Phase 5+) holds twelve terms, each
copied word for word from Haavard's `docs/glossary.md`: its name, and its explanation. A
closed "What do these terms mean?" box under each of the four sections (DCF, Behind the
number, Sensitivity, Peer multiples) lists the terms that section uses, drawn by
`draw_explanations` in `app.py`. Only the glossary's definition sentences are used, not its
"in this model..." sentences, because those quote base-case numbers ($305.60, about 70%)
that the sliders change, and a panel that says $305.60 beside a price of $318 would mislead.
The glossary stays the source and stays Haavard's: Claude did not write or edit it. Tests for
this go in a new file, `test_explanations.py`, which is not in the folder table (one test
file per module, as before). It checks that every text is word for word in the glossary (so
the panels cannot drift from his wording), that no text contains a digit, `$` or `%`, and
that every term is used. Still to come as a follow-up pull request, once Haavard has written
the glossary entries: Upside vs market, Revenue growth, Operating margin, Peer median and
DCF vs multiples.

## 2026-11-05 — Five more terms added to the boxes: Phase 5 is complete

The five glossary entries Haavard wrote (Upside vs market, Revenue growth, Operating margin,
Peer median, DCF vs multiples) are added to `explanations.py`, word for word, bringing it to
seventeen terms. Claude checked them for accuracy first: two were sent back, because the first
version of Upside vs market described a stock's return against the stock market (it is the
DCF price against the stock's own market price), and DCF vs multiples named the two methods
without saying what the percentage means. Both were rewritten by Haavard. Placement:
Upside vs market in the DCF box; Revenue growth and Operating margin in the "Behind the
number" box, next to the forecast chart they drive; Peer median and DCF vs multiples in the
multiples box. `test_explanations.py` already checks each text against the glossary, so it
covered the new ones with no change. With this, every part of Phase 5 in CLAUDE.md is built:
sliders, sensitivity heatmap, charts, and a plain-language panel under every metric.

## 2026-11-06 — Phase 6: the README says what the app does today, and the live link goes in

The README is rewritten. It had still described Phase 0 ("No valuation or app code exists
yet") and promised "type a stock ticker or search for a company", which the app cannot do:
it values Adobe only, from a frozen snapshot. The new README says that plainly, gives the live
link (https://valuation-l3b.streamlit.app), lists what the page does, gives the steps to run
it locally on Python 3.12, and moves the ticker idea and saving under "Planned". Reason: the
front page of the project should match what exists, especially for anyone reading it as a
portfolio piece. No new files.

## 2026-11-06 — Design decision for other companies: assumptions start from the company's own last year

The forecast assumptions in `assumptions.py` (growth, margins, tax rate, D&A %, capex %,
working capital %, terminal growth) are Haavard's judgments for Adobe and would be wrong for
any other company. For a company other than Adobe the app will derive a starting point from
that company's own last reported year: hold its operating margin, tax rate, D&A % and capex %
where they were, and fade revenue growth from last year's rate towards the terminal growth
rate over the five forecast years. The sliders then adjust it, and the page will say clearly
that this is a starting point from the last reported year, not a forecast. The other options
were generic defaults for everyone (a poor fit for most companies) and making the user type
everything in (it defeats the point of choosing a ticker). Consequences, for when the live data
source is built: `data.py`'s package must grow (last year's capex, tax and prior-year revenue
at least), the default-deriving functions belong in `valuation.py` with tests, and the page
should warn that a DCF suits stable cash-generating companies and is a poor fit for banks,
loss-making and early-stage ones. Adobe keeps its hand-chosen assumptions, because those
are the Excel model's. Nothing is built yet; this only records the decision.

## 2026-11-06 — The live data source: yfinance for share price and beta, not yet switched on

`data.py` gets a second source, `live_source`, registered as `"live"` in `SOURCES`. It asks
Yahoo Finance for the current share price and beta and takes every other figure from the
snapshot, so the package stays complete and `valuation.py` and `app.py` need no change. New
dependency: `yfinance==1.8.0`, pinned, agreed with Haavard first. It is a free, unofficial
wrapper around Yahoo Finance, the same site the snapshot already cites for these two
numbers; the cost is that Yahoo does not support it, so it can break or be rate-limited
without warning. Because of that, the default source stays `"snapshot"` and the app is not
switched over in this pull request: that is a separate step, with a fallback to the snapshot
if Yahoo fails, so the page only changes after the source has been reviewed. The import of
`yfinance` sits inside the one function that touches the internet, and the tests feed in
fake Yahoo replies instead, so CI never depends on Yahoo being up. A missing,
zero or negative price, or a missing beta, stops with a plain error rather than flowing into
the DCF. No new files.

## 2026-11-06 — The app switches to the live source, with a snapshot fallback

`app.py` now asks `data.get_company_data_with_fallback`, which tries the `"live"` source
(Yahoo share price and beta) and uses the `"snapshot"` if that fails, and returns which one
it used. The fallback lives in `data.py` because it is about where figures come from, not
maths. The page remembers the answer for 15 minutes (`LIVE_DATA_CACHE_SECONDS` in `app.py`),
because Streamlit reruns the page on every slider move and each move would otherwise be a
Yahoo call; the cost is that after one Yahoo failure the page stays on the snapshot until the
memory expires. A line under the title says where the price and beta came from: a quiet grey
caption when live, a yellow warning when it fell back. Agreed with Haavard: with live figures
the page no longer shows the Excel model's $305.60 at the default sliders, because beta
changes the WACC. This is on purpose. The tests still match Excel to the cent, because they
run on the snapshot, which stays the default source in `data.py`. Only the fetching is
covered by tests; how the page looks was checked by running it. No new files.

## 2026-11-06 — The Excel "starting point" sheet: how a forecast starts from a company's last year

Haavard built a new sheet, `starting point`, in `excel/valuation-lab.xlsx` (Excel first, as in
Phase 1; the Python comes after and must match it to the cent). It uses Adobe's FY2025 as
the test case and links to `Projection` column G for last year's ratios (no new 10-K figures
are needed). The rules, from the 2026-11-06 design decision: revenue growth steps down in a
straight line from last year's rate to the terminal growth rate, reaching it in the last of
five forecast years (each year = the year before + (terminal growth - last year's growth) /
years in the forecast; for Adobe 10.53%, 8.92%, 7.32%, 5.71%, 4.11%, 2.50%); operating
margin, tax rate, D&A % and capex % stay at last year's level. Terminal growth is a link to
`valuation` C17, so it lives in one place; the number of years (5) is the one typed input
(`starting point` C13). Working capital % also stays at last year's level. That was Haavard's
call, made over the alternative of setting it to zero: he judged holding it more realistic.
The trade-off, for the record: Adobe's working capital is a cash inflow (2.55% of revenue)
because customers pay for subscriptions up front, and carrying an inflow forward is
optimistic for a company where that is a one-off; a company that uses cash keeps using it
under the same rule. The page will present the result as a starting point, not a forecast.
The workbook is replaced as a whole file: the six original sheets are identical in formulas
and values (checked), so the $305.60 result is unchanged. No new files.

## 2026-11-06 — The starting point maths in Python: three functions, one constant, nothing wired in yet

`valuation.py` gets three functions that follow the "starting point" sheet and `docs/model.md`
exactly: `last_year_ratios` (the six ratios from a company's last-year figures),
`fade_growth_rates` (equal steps from last year's growth to the terminal rate, reaching it in
the last forecast year) and `starting_point_assumptions` (the fade plus the other five ratios
held flat, returned in the shapes `run_full_dcf` already takes). The number of years is
`STARTING_POINT_YEARS = 5` in `assumptions.py`, pointing at the sheet's cell C13. Agreed with
Haavard: `last_year_ratios` stops with a plain error if revenue is zero in either year or if
the company made no profit before tax, because the tax rate and margins would mean nothing
(the page already warns that loss-making companies are a poor fit); and if last year's
growth was below the terminal rate, the same rule steps growth up, which is documented in a
test. Capex is passed in as a positive amount of spending and cash from working capital as
positive when it is an inflow, as on the `Projection` sheet. The 19 new tests use the
workbook's own cells as expected values; the one test that has no Excel value (the starting
point fed through `run_full_dcf`) only checks that the shapes fit and a price comes out. A
check that the tests can fail: changing the step to divide by years + 1 made five of them
fail. Not built yet, on purpose: getting last year's figures into `data.py` and putting any of
this on the page. No new files.

## 2026-11-06 — Last year's figures join the data package (Adobe only so far)

The package every data source must supply (`PACKAGE_FIELDS` in `data.py`) grows by five
figures, the ones `last_year_ratios` needs and the package did not yet hold:
`prior_year_revenue`, `income_tax`, `income_before_tax`, `capex` and
`cash_from_working_capital`. The snapshot fills them in for Adobe from the 10-K (pages 48 and
51), the same figures as the workbook: 21,505, 1,604, 8,734, 179 and 605. Capex is stored as a
positive amount of spending (the 10-K shows it as -179) and cash from working capital as
positive when cash comes in, as on the `Projection` sheet; working capital is the six cash
flow lines added together, because the package holds finished totals and `data.py` does not
compute (see the earlier note on debt and cash). `live_source` builds on the snapshot, so it
carries the new fields without any change. Because `check_package` insists on every field, any
future source must supply all five. Two new tests run Adobe's snapshot through
`last_year_ratios` and `starting_point_assumptions` and expect the `starting point` sheet's
cells. Not done on purpose: getting these figures for other companies from Yahoo, and
anything on the page. No new files.

## 2026-11-06 — Cost of debt for other companies: interest expense divided by debt, and no peers yet

Adobe's pre-tax cost of debt (4.16%) comes from the 10-K's debt note, which a data source
cannot supply for an arbitrary company. For other companies the model estimates it as the
yearly interest expense divided by financial debt. Haavard added it to the `starting point`
sheet first (rows 24-27: 263 / 6,210 = 4.24% for Adobe, close to the 4.16% from the notes),
and `estimate_pre_tax_cost_of_debt` in `valuation.py` matches that cell. Because `data.py`
does not calculate (guard rail 5), the package will hold the `interest_expense` and the
division happens in `valuation.py`; the package field itself comes in the next pull request.
A company with no debt gets a cost of debt of 0, which does not matter because debt then has
no weight in the WACC; a negative interest expense or debt is refused with a plain error,
because it almost always means a sign was mixed up. Also agreed with Haavard: Yahoo cannot
say who a company's peers are, so for companies other than Adobe the page will show the DCF
only, and the multiples section stays Adobe-only until there is a way to choose peers.
Housekeeping in the same pull request: `.gitignore` now ignores `~$*`, the temporary lock
file Excel creates next to a workbook while it is open, so it cannot be committed by
accident. No new files.

## 2026-11-06 — A "yahoo" data source for any company; peers and the 10-K cost of debt become optional

`data.py` gets a third source, `"yahoo"`, that builds the whole package for any ticker from
Yahoo Finance's financial statements. One function, `fetch_yahoo_statements`, touches the
internet and returns plain figures in the package's units (dollars turned into $ millions,
capex and interest expense as positive amounts); `yahoo_source` turns that into a package. To
make this possible, `interest_expense` joins the required package fields (Adobe: 263), and
the cost of debt from the 10-K notes and the four peer fields move to a new `OPTIONAL_FIELDS`,
because Yahoo cannot supply them: for other companies the cost of debt is estimated from
interest expense and the page shows the DCF only (both agreed earlier today). Agreed with
Haavard: the risk-free rate (5.29%) and equity risk premium (4.41%) are market-wide, so every
company gets the same Damodaran figures, now named constants in `data.py` dated 1 Nov 2026
(the Adobe snapshot uses the same constants, so there is one place to update); a missing core
line stops with a plain error naming it; a missing current debt line counts as 0, because
Yahoo leaves it out when there is none. One thing was decided while building, and is flagged
here: a missing long-term debt line is not guessed as 0, so a company with no debt at all
stops with an error for now. Debt is current plus long-term debt, leases left out, like
Adobe's; the addition is done by a new `valuation.financial_debt` (tested against WACC C22),
and `data.py` calls it, because the rule is that `data.py` does not calculate. The tests use
fake Yahoo replies shaped like the real ones. Checked once by hand on real data: Yahoo's
Adobe reply gives the 10-K figures and reproduces the starting point sheet's ratios and its
4.24% cost of debt; Microsoft works too, with a cost of debt estimate of 7.6% that looks high
(see status). Not done on purpose: the ticker box and anything else on the page. No new
files.

## 2026-11-06 — The ticker box: any company, as a starting point; and test_app.py is added

The page gets a "Company ticker" box at the top of the sidebar, opening on ADBE so the page
is exactly as before. For Adobe nothing changes: hand-chosen assumptions, the cost of debt
from the 10-K notes, FY2026-FY2030 labels, peer multiples, and the live-or-snapshot source.
For any other ticker the page uses the `"yahoo"` source (no snapshot fallback, because the
snapshot only has Adobe) and: the forecast assumptions from `last_year_ratios` and
`starting_point_assumptions`; the cost of debt estimated from interest expense and debt;
forecast years labelled "Year 1" to "Year 5" (other companies have other fiscal year-ends;
agreed with Haavard); no multiples section, because Yahoo cannot say who the peers are; and
a yellow warning, in wording agreed with Haavard, that this is a starting point and not a
forecast and that a DCF suits stable, cash-generating companies. The company the hand-chosen
assumptions belong to is now one named constant, `BASE_CASE_TICKER` in `assumptions.py`. If a
company cannot be valued (Yahoo knows nothing about the ticker, no pre-tax profit, or a WACC at
or below terminal growth) the page shows one plain red error naming the ticker and the footer,
instead of crashing; when Yahoo has no figures at all the message says to check the ticker,
instead of listing every missing field. One detail to know: the growth fade always ends at
the base 2.5% terminal growth, as in the Excel sheet, so moving the terminal growth slider
changes the terminal value but not the fade. The figures are remembered per ticker for 15
minutes, as before. New file `test_app.py` (not in the folder table in CLAUDE.md; one test
file per module, as before) runs the real page with Streamlit's built-in test runner and fake
Yahoo replies, so it adds no dependency and never touches the internet: it checks the Adobe
page, the fallback, another company, the warning, the missing multiples, the exact price, and
each error case, and that the footer is always there. One of its tests passed for the wrong
reason at first (the price differed from Adobe's anyway, because the cost of debt differs); it
was found by deliberately breaking the page and replaced with one that works the price out
independently. Run for real on Adobe, Microsoft and a nonsense ticker. Microsoft's result
(a DCF price 79% below the market price, because last year's capex of about 35% of revenue is
held for ever) is recorded in `docs/status.md` as a limit of the starting point, not an error.

## 2026-11-06 — Capex fades down to D&A in the starting point

Running real companies through the ticker box showed that holding capex at last year's share
of revenue for ever is too harsh for a company in a heavy-spending year: Microsoft's capex was
about 35% of revenue against D&A of about 12%, which put its DCF price 79% below the market.
In the long run a company cannot spend far more than it depreciates, because the terminal
value assumes a steady state. So capex now fades, in equal steps over the five years, from
last year's level down to last year's D&A level, the same way growth fades to the terminal rate.
Haavard built it in Excel first: row 21 of the `starting point` sheet uses
`=C21+(MIN($C$21,$C$20)-$C$21)/$C$13`, plus a worked example in rows 29-32 (capex 35%, D&A 12%,
giving 30.4%, 25.8%, 21.2%, 16.6%, 12.0%) that the Python is tested against. The fade is only
ever downwards: the target is the lower of capex % and D&A %, so a company whose capex is
already below its D&A stays flat. That matters for Adobe, whose D&A includes amortisation of
acquired intangibles; pushing its capex up to match would punish asset-light companies for no
reason. Adobe's starting point and page are unchanged (its capex row is flat, checked in the
tests; the page uses its hand-chosen assumptions anyway). In Python, `fade_capex_pcts` reuses
the same equal-steps function as the growth fade, and `starting_point_assumptions` calls it.
Result on real data on 6 Nov 2026: Microsoft's DCF price moves from 79% below its market price
to 48% below. Real companies also showed two further problems, recorded in `docs/status.md`
and not fixed here: working capital held at last year's level sinks Coca-Cola (a -15% of
revenue outflow held for ever), and Apple has no interest expense on Yahoo at all, so it cannot
be valued. No new files.
