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

## 2026-11-06 — Every figure from the yahoo source is in US dollars

Aker ASA (AKER.OL) showed Norwegian kroner with dollar signs, and checking Yahoo showed worse:
Novo Nordisk reports in DKK but its shares trade in the US in dollars, and Shell reports in
dollars but its London shares are quoted in pence, so the page mixed currencies and gave
nonsense. Decided with Haavard: convert everything to US dollars, not show each company in its
own currency. The reason is that the model's discount-rate inputs (risk-free rate 5.29%,
equity risk premium 4.41%) are US dollar figures, and discounting krone cash flows with them
would be inconsistent; converting also fixes the mixed cases. `fetch_yahoo_statements` now
returns the statement currency, the price currency and Yahoo's exchange rate to dollars for
each (a London price in "GBp" goes through pounds, a hundredth of a pound), and `yahoo_source`
multiplies every money figure by the statements' rate and the share price by the price's rate
using the new `valuation.convert_currency`. Counts (shares) and ratios (beta, growth,
margins) are not converted, and converting does not change any ratio, which a test checks. If
Yahoo has no rate, the page stops with a plain error naming the currency. The four currency
fields are optional package fields (Adobe's snapshot is in dollars and has none), and the page
shows one line saying what was converted and at what rate. Limits, recorded in status: one
rate for all of last year's statements, and ADR share ratios are not checked. While running
real companies a latent crash was found and fixed: a low WACC (a very low beta) could sit
within a point of the highest terminal growth rate in the heatmap, where the formula has no
answer, and the error was raised outside the page's error handling. The heatmap now says why it
cannot be drawn and the rest of the page stays; a test guards it. No new files.

## 2026-11-06 — Working capital now fades to zero (replacing "hold at last year's level")

Haavard's earlier choice for the starting point was to hold working capital at last year's
share of revenue, because it seemed more realistic. Real companies showed its downside: Coca-Cola's
last year was a cash outflow of 15% of revenue, probably a one-off, and holding it for ever put its
DCF price 74% below the market; Adobe's inflow of 2.5%, held for ever, flatters it. Comparing three
rules on 6 Nov 2026 (hold, fade to zero, set to zero) gave Coca-Cola $25, $69 and $72 against a
market price of $96, so fading to zero was recommended and Haavard chose it. The reasoning is
the same as for growth and capex: a number that is unusual this year drifts towards a steady
state over the forecast, because a company cannot keep gaining or losing a large share of its
revenue in working capital every year. It is symmetric: an inflow and an outflow both fade to
zero. Built Excel first: `starting point` row 22 uses `=C22-$C$22/$C$13`; `fade_working_capital_pcts`
matches D22:H22 (Adobe: 2.55%, 2.04%, 1.53%, 1.02%, 0.51%, 0%). Adobe's page still uses its
hand-chosen 1% a year, so it is unchanged. The starting point now has four moving parts (growth,
capex and working capital fade; margin, tax rate and D&A are held), all following the sheet.
Result on real data: Coca-Cola from 74% below the market to 28% below, Aker from 31% below to 2%
above. No new files.

## 2026-11-16 — A fallback cost of debt when Yahoo has no interest expense

Apple could not be valued: Yahoo has no interest expense for it, so interest expense divided by
debt could not be worked out and the page stopped with a red error. Asked what an analyst would
do, the answer was to estimate the cost of debt from the market, as the risk-free rate plus a
credit spread for the company's rating, and not to give up. Haavard agreed. Built Excel first:
`starting point` C35 (risk-free rate, linked to WACC C8), C36 (spread 1.11%, Damodaran synthetic
rating spreads, Jan 2026, Baa2/BBB, a middle-of-the-road choice) and C37 (their sum, 6.40%). A
worked example in rows 39-58 values Apple's WACC both ways: 10.010% with the BBB fallback and
10.002% with Apple's own AA spread (0.55%), a gap of 0.009 points, because debt is only 1.85% of
Apple's capital. In Python, `fallback_pre_tax_cost_of_debt` in `valuation.py` matches C37 and
D55, `CREDIT_SPREAD` in `data.py` holds the spread, and `yahoo_source` uses the fallback only
when Yahoo has no interest expense (it is no longer a required figure). The package then has
`interest_expense` set to None, the estimated `pre_tax_cost_of_debt`, and
`cost_of_debt_is_fallback` set to True, and the page shows a yellow note saying the cost of debt
is an estimate. A company that does have an interest expense is unchanged. The new field is
only for companies that use the fallback, so `test_expected_snapshot_lists_every_package_field`
now leaves it out of what Adobe's snapshot must list, as it does the currency fields. Known
limit: the fallback uses one spread for every company, so it is least accurate for heavily
indebted ones. No new files.

## 2026-11-16 — A caution when the price rests mostly on the far future

Coca-Cola's WACC is 6.14% (a low beta), only 3.6 points above terminal growth, and 88% of its
enterprise value comes from the terminal value. Asked what an analyst would do, the answer was to
sanity-check the discount rate and to look at how much of the value is terminal value (above
roughly 75% is a red flag), and not to cap the WACC. Planned as a warning for WACCs close to
terminal growth, but trying four real companies (6 Nov data) showed that a 2-point limit would
miss Coca-Cola, whose gap is 3.6 points, so Haavard chose 4 points. Terminal value share: Adobe
70%, Apple 72%, Microsoft 78%, Coca-Cola 88%. Built Excel first: `valuation` rows 30-32, C31
(`=C19/C20`, 70.0%) and C32 (`=C8-C17`, 8.4 points). In Python, `terminal_value_share` and
`wacc_minus_terminal_growth` in `valuation.py` match them, the two limits
(`TERMINAL_VALUE_SHARE_WARNING` 75%, `WACC_GAP_WARNING` 4 points) are named constants in
`assumptions.py`, and `terminal_value_cautions` in `app.py` turns them into plain sentences. The
page always says what share of enterprise value is terminal value, and shows a yellow caution when
a limit is crossed. The caution is not an error: the price is still shown. The limits are not part
of the Excel valuation, so they have no Excel cell. Adding these rows moved the workbook's
sensitivity table from `valuation` rows 34-38 to rows 37-41 (growth rates in row 36); the numbers
are the same, and the cell references in the comments of `test_valuation.py` and `assumptions.py`
were updated. An adjusted beta, the usual cure for a very low beta, is a separate pull request
later. No new files.

## 2026-11-16 — Peers: a missing multiple drops that peer from that one multiple, and 2 peers are the minimum

Haavard wants other companies to get peer multiples too, with the peers suggested automatically
and editable. The first step is the maths for peers that have no usable multiple, because Yahoo
gives all three multiples for ordinary peers but not for loss-making ones. Asked what an analyst
would do, the answer was to drop that peer from that one multiple only, take the median of the
rest, and not to show a "median" of a single number. Haavard agreed to a minimum of 2 peers.
Built Excel first: `Multiples` rows 41-49, a worked example with PepsiCo, Keurig Dr Pepper and
Mondelez where Keurig's P/E is blank on purpose (medians 2.663, 14.749 and 19.944; the P/E count
is 2; the check F49 is 0). In Python, `usable_multiples` and `median_of_usable_multiples` in
`valuation.py` match D46:F46 and F47, and `MINIMUM_PEERS = 2` is a named constant in
`assumptions.py`. `run_multiples` now takes `minimum_peers`. A multiple with too few peers gives
None for its median and its price, and the middle price is taken over the prices that exist (None
if none do). Adobe is unchanged. The page does not use the new None results yet; that comes with
the peers box. The whole peers feature is split into four pull requests: this maths, then fetching
a peer's multiples from Yahoo and suggesting peers (same industry, between a tenth and ten times
the company's size, closest five by market value), then the sidebar box and the multiples section
for other companies, then a chart of the peers. No new files.

## 2026-11-16 — Suggesting peers from Yahoo's industry list, by size

Haavard wanted the app to find similar companies itself. Yahoo's industry lists were tried on three
companies: good for Coca-Cola (PepsiCo, Monster, Keurig Dr Pepper), loose for Adobe (Uber, Shopify
and ADP mixed in with Salesforce and Intuit), useless for Apple (only tiny companies). Asked what
an analyst would do, the answer was to screen by industry, then narrow by size, so the design is
suggest-then-edit: the app suggests up to 5 peers and the reader can change them (the box comes in
the next pull request). Rule: the first 20 companies in the industry list, US-dollar listings only,
within 10 times the company's market value, the 5 closest in size. 20 candidates keep the first
load to about 4 seconds (about 0.2 seconds per company), and the same Yahoo call gives a peer's
market value and its three multiples. No Excel example, by Haavard's choice: it is a screening
rule, so it lives in `docs/model.md` ("Suggesting peers"). In Python, `size_gap` and `closest_peers`
in `valuation.py` do the picking; `fetch_peer_candidates`, `fetch_peer_quote`, `peer_multiples` and
`suggest_peers` in `data.py` do the fetching, and can be swapped for the tests; the three numbers
(20, 10, 5) are `PEER_CANDIDATES_TO_CHECK`, `PEER_BIGGEST_SIZE_GAP` and `SUGGESTED_PEERS` in
`assumptions.py`. One peer Yahoo cannot read is skipped; if none can be read, there is a plain
error. A company with no suitable peers gets empty lists, not an error. Nothing is on the page yet.
Known limits: a company with fewer than 2 suitable peers (Apple, Microsoft) gets no multiples until
the reader types peers; non-US-dollar peers are not suggested; "closest in size" is not the same as
"most similar business". No new files.

## 2026-11-16 — The peer box: suggested, editable, and the multiples section for every company

The last piece of the peers feature that Haavard asked for: other companies now get peer multiples
on the page. Agreed with Haavard: Adobe is unchanged (its four hand-chosen peers, no box); any
other company gets a "Peer tickers" sidebar box, filled in the first time with the suggestions
from the previous pull request and editable; a small table of the peers' multiples under the prices;
and a cap of 8 typed peers. The box has its own state per company (key `peers_<ticker>`), so
switching companies does not carry the peers over. Suggestions and peer multiples are remembered
for 15 minutes like the company's own figures. Where a multiple has fewer than 2 usable peers its
price says "Not enough peers" and "DCF vs multiples" says "Not available". With no peers at all
(Apple) the section stays, with a note on how to add some; this replaces the old behaviour of
hiding the section for other companies, so `test_app.py`'s test of that case now expects the
section and the note, and still expects no prices. The label "Middle of the three" became "Middle
of the prices", because it can be the middle of two. If Yahoo's industry lookup fails the page
shows a yellow warning and an empty box; if the typed peers cannot be fetched it warns too; a
ticker Yahoo knows nothing about is named in a note and left out. No Excel change: the maths
(`run_multiples`, the usable-peer median) was already matched to the Multiples sheet. On real data
(16 Nov 2026): Coca-Cola gets PEP, MNST, KDP and prices $36.05 / $54.80 / $99.38 against a market
price of $99.18; Apple gets an empty box; Pfizer gets five peers, with Gilead's missing P/E left
out. No new files.

## 2026-11-18 — An overview of eight numbers, and the peers' operating margins

Haavard asked for the company's operating margin and its own multiples on the page, "an important
factor to look at for investing", and then for the other numbers an analyst would look at for an
overview. Asked what an analyst checks, the answer was five questions: is it growing, does it earn
on its sales, does profit become cash, is the debt a risk, and is the price fair. Eight numbers
answer them, all from figures the page already has: revenue growth, operating margin, free cash
flow yield, net debt over EBITDA, EV/Sales, EV/EBITDA and P/E (plus the market value and enterprise
value behind them). Left for later, with reasons: ROIC and ROE (need new balance sheet figures),
dividend yield and the 52-week range (say less about value), interest cover (Yahoo has no interest
expense for some companies, such as Apple) and analyst forecasts (outside what the app does).
Built Excel first: `Multiples` rows 52-64, every figure linked, with a check cell (C64) that ties
the last-year free cash flow to `Projection` G18. The page shows them in an "Overview" section
under the DCF section; the peers table gets the company itself as its first row, a "Peer median"
row last, and a column of peers' operating margins, fetched with the same Yahoo call as their
multiples (`operatingMargins`, trailing twelve months). For Adobe, whose peers come from the
snapshot of the Excel model, the margins are fetched live and the column is blank if Yahoo cannot
be reached. Margins differ from multiples in one rule: a negative margin counts in the peer
median, because a loss is real information, while a negative multiple is left out. A number that
would mean nothing shows "Not meaningful". The company's own row uses its last full year and
today's price, and the peers use Yahoo's trailing twelve months, so the page says small
differences are expected. In Python, `stock_overview` and the small functions behind it, and
`median_of_available`, are in `valuation.py`, matched to the cells; `peer_operating_margin` joined
the peer figures in `data.py`. The page's tooltips are short plain definitions; the glossary
entries for the new terms are Haavard's to write. Existing tests of the peers table now expect the
extra rows and column. No new files.

## 2026-11-18 — The website roadmap and the order of work

Haavard shared a list of 11 improvements to make the site a good tool, most important first:
history, a reverse DCF, a margin-and-growth sensitivity, visible assumptions, more robust peer
multiples, scenarios, quality metrics, adjustments for one-off items, a transparent WACC, forward
multiples, and a thesis field with export. It is recorded in full in `docs/status.md` under "Next".
Before ordering it, Yahoo was checked for what it can supply: 4-5 years of annual statements (not
10), 7 quarters (enough for a trailing-twelve-month view) and analyst estimates. So history starts
with 4-5 years, and 10 would need a second data source later. The order of work follows dependency
and size, not only importance: transparency first (visible assumptions and a transparent WACC, both
small), because the reverse DCF, scenarios and one-off adjustments all depend on seeing exactly which
path the model uses; then the quick peer warnings; then history; then the reverse DCF and the second
sensitivity table; then the larger peer changes; then quality metrics, adjustments and scenarios;
then forward multiples and the thesis export. Haavard agreed to this order and can change it. Two
items need decisions when their turn comes: how to choose peers by business type (Yahoo only has
industry), and a new dependency for PDF export. This is a plan, not a build: nothing in the code
changes in this pull request, and no new files.

## 2026-11-18 — Visible assumptions, and sliders that are clearly a change (roadmap #4)

The first item built from the roadmap. The sliders said "0 %", which could mean the actual growth or
an adjustment, and sometimes "-0 %". The cause of "-0 %" was found: stepping from -5% in steps of
0.005 comes to -5.2e-18, not 0, and the browser shows that as "-0 %"; the page's own `percent()`
also wrote tiny negative rates as "-0.0%". Decided with Haavard: the growth and margin sliders now
work in percentage points ("+0.0 pts", half-point steps, the same ±5 range), which lands exactly
on zero and says plainly that the slider is a change from the base case; and a new section, "What
the model assumes", shows the actual growth, margin, tax rate, D&A, capex and working capital for
each forecast year after the sliders, with the terminal growth rate, the WACC and the slider
changes in a line below. `percent()` and `precise_percent()` never write a negative zero. In
`assumptions.py` the points constants are the single source, and the old decimal ones are derived
from them (divided by 100), so the model and its tests are unchanged. No Excel step: nothing new is
calculated, the table shows numbers the model already uses. Verified in the running app by stepping
a slider up from its minimum to zero. One existing test changed: the very-low-WACC page test said
"no table" when the heatmap is missing; it now says the only table is the assumptions table. The
tooltips on the sliders point to the new table. No new files.

## 2026-11-18 — A transparent WACC (roadmap #9)

Haavard asked for the inputs behind the WACC to be visible so a reader can see why it is, for
example, 12.7%. The `WACC` sheet already had every step (rows 8-29), so there was no Excel step.
A new section, "How the WACC is built", under "What the model assumes", shows each step as a row
(risk-free rate, beta, equity risk premium, cost of equity, pre-tax cost of debt, tax rate, cost of
debt after tax, market value of equity, debt, the two weights, the WACC), a "where it comes from"
column, and one sentence that says why the number is what it is. Agreed with Haavard: that place,
and the source column. In Python, `capital_weights` (the sheet's C24 and C25) is new, `wacc()` now
uses it so the table and the DCF cannot disagree, and `wacc_breakdown` returns every step; all are
tested against the sheet's cells. `MARKET_FIGURES_SOURCE` in `data.py` holds the source and date of
the two typed-in market figures, so the page and the constants cannot drift apart. The section uses
a static table (`st.table`), so it does not count among the page's interactive tables. If the reader
sets a WACC of their own, the table keeps showing the model's build. Seeing the inputs for real
companies exposed a problem, recorded under "Open" in `docs/status.md`: Pfizer's last-year tax rate is
negative (-3.54%, a tax benefit), and the starting point holds it flat, which flatters its cash flows.
Together with its low beta (0.30, a cost of equity of 6.60%) this explains its odd DCF price. Not
fixed here: one idea per pull request. No new files.

## 2026-11-18 — Warnings about the peers (roadmap #5a)

The first part of the peer-robustness item. Real peer groups were tried before choosing the rules:
First Solar's own margin of 30.6% against its peers' 6.3%, Enphase with a margin of 0.6% and an
EV/EBITDA of 31.9x, Sunrun with a P/E of 3.9x, Merck with 139x. Haavard chose to flag and not
exclude (the median already resists one outlier, excluding hides information, and he can still
remove a peer from the box), and agreed the limits: a margin gap over 10 points, a margin under 5%,
and a multiple over 3 times or under a third of the peers' middle. A "Flag" column marks the peers,
a line explains each, a yellow warning says when the margins are far apart, and the "middle" price
is named honestly: "Middle of the three prices", "Average of two prices" (with a warning) or "The
only price". In `valuation.py`: `margin_gap`, `is_outlier` and `flag_peers`; the limits are named
constants in `assumptions.py`. One change after the agreement, found while checking on live data:
the multiple was first compared with the middle of the OTHER peers, which gave a false alarm for
Pfizer's Bristol-Myers (a normal P/E of 13.2 looked far from 49.1, because Merck's 139.2 had dragged
the others' middle up). It is now compared with the middle of ALL the peers, the same middle the
price uses; Merck is flagged, Bristol-Myers is not, and Sunrun, Enphase and Synopsys still are. This
makes the rule simpler to explain and consistent with the page, and is easy to revert. Known limit:
Adobe's page now shows the margin warning too (11.8 points), and a flag on Synopsys, which the
Excel notes already call an outlier. Rules of thumb, so no Excel step; the rules are written up in
`docs/model.md` ("Warnings about the peers") for Haavard to check. No new files.

## 2026-11-18 — The history section (roadmap #1, first slice)

The biggest item on the roadmap: everything on the page rested on one year, which can be a peak or a
bottom. Yahoo was checked first: 4 or 5 years of annual statements for six companies, not 10 (10
years would need a second data source, later), with Adobe's income statement at 4 years and its cash
flow at 5. The item is built in two slices, agreed with Haavard: this one, the history itself, and the
next one, a check of the latest year against the history (a peak or a bottom). Built Excel first:
sheet `history` with Adobe's four years typed in from Yahoo and the ratios as formulas (C8:F18). The
page has a "History" section under the Overview: a table with a column per year, two charts, and
notes. Two definitions matter and were decided with Haavard: free cash flow is shown as the company
REPORTS it (cash from operations minus capital spending), clearly labelled, with a note quoting how
it differs from the model's own free cash flow (Adobe: $9,852m against $8,351m); and the share count is
the diluted AVERAGE over each year, not the shares outstanding (427m against 413m). In `data.py`,
`fetch_yahoo_history` reads the years oldest first and matches free cash flow to its year by date, not
by position (Yahoo's two statements do not always have the same years), `history_in_dollars` converts
the money, and `get_history` wraps both with plain errors. In `valuation.py`, `yearly_growth` and
`ratios_by_year` match the sheet's cells. The page fetches the history on its own, remembers it for 15
minutes, and if Yahoo fails says so in one line and carries on. Two things found while checking it in
the running app: a note with two dollar signs was shown as a maths formula (so its dollar signs are
escaped, as in the earlier charts section), and a chart legend was cut off (its series is called "FCF
margin"). Adding a second static table meant the WACC tests now find their table by its content, not
its position. No Excel change beyond the new sheet; no new files in the repository.

## 2026-11-18 — Is the latest year typical? (roadmap #1b)

The second slice of the history item, agreed with Haavard: use the history to say whether the latest year
may be a peak or a bottom, which is the First Solar question. Eight real companies were tried first
(latest operating margin against the average of the earlier years, and the swing between the best and
worst year). Haavard agreed the limits: 5 points from the earlier average and 15 points of swing. The
two numbers separate the cases cleanly: First Solar +14.2 and 43.9, Nvidia +14.6 and 41.7, Ford -8.2,
Pfizer 5.0 (just under) but a swing of 30.3, against Adobe, Coca-Cola and Apple within 2.3 points and
a swing under 4. A third rule had to be named: at least 3 years of margins are needed
(`MINIMUM_HISTORY_YEARS`), because an average of one earlier year is not a history; I added it and said so.
Built Excel first: `history` C20 (the earlier average), C21 (the gap in points) and C22 (the swing in
points). In Python, `history_check` in `valuation.py` matches all three; the limits are named constants in
`assumptions.py`; `margin_history_warnings` in `app.py` writes the sentences ("may be a peak", "may be a
bottom", "swung by"), shown as yellow warnings at the top of the History section. The warnings change
nothing in the valuation: using an average margin in the starting point would be a model change, for
later. Found while checking on live data and recorded under "Open" in `docs/status.md`: for a company that
lost money last year (Ford) the page shows only the "no pre-tax profit" error, so the overview and the
history never appear, exactly when a history would help most. Not fixed here. No new files.

## 2026-11-18 — The reverse DCF: what does the market price imply? (roadmap #2)

Haavard asked for the tool to work out, from the market price, the margin or growth it implies, for
example "the market is pricing in a 20% margin", the most useful insight from his First Solar analysis.
Agreed with Haavard: solve for the margin and for the growth separately, each holding the other as
modelled; report the average over the five forecast years; and put it in a section right under the DCF
numbers, set against the company's history as a reading aid. Tried first on real numbers: First Solar
20.3%, Adobe 30.2%, Coca-Cola 42.6%, Nvidia 94.7%. Built Excel first: sheet `reverse dcf`, a copy of the
DCF with a margin shift and a growth shift (check cell C37 is 0 at zero shifts) and the two Goal Seek
results typed in (C41:D42). In Python, `solve_for_target` finds, by repeatedly halving a range, where a
steadily rising or falling function reaches a target, and `reverse_dcf` uses it with `run_full_dcf`; they
match the Goal Seek results to within 0.00001 points (Excel stops at its own tolerance). The search range
(50 points either way) and the tolerance (1e-9) are named constants in `assumptions.py`; an answer outside
the range is reported as "No answer". The answers use the page's WACC (the model's, or the reader's),
terminal growth and sliders, so they move with them. The implied margin is an absolute figure: moving the
margin slider changes the model's margin but not what the price needs. The history comparison needed the
history before the section is drawn, so the page now loads it earlier. No new files in the repository.

## 2026-11-19 — A second sensitivity table: margin and growth (roadmap #3)

WACC and terminal growth are not the biggest risks, so a second table varies the operating margin and the
revenue growth. Tried first on Adobe and First Solar: a 10-point cut in margin costs Adobe $73 a share, a
4-point cut in growth $47. Agreed with Haavard: margin -10, -5, 0, +5, +10 points and growth -4, -2, 0, +2,
+4 points; labels showing the actual averages, not only the shifts; and a place under the WACC table.
The Excel step was to be an Excel Data Table on the `reverse dcf` sheet, but the table never filled (the
saved file had headers and no results, and no Data Table formula), so the check became six readings of
the price at chosen shifts (C55:E60): the base case, the four corners and (+5, +2). Python matches all six
to within 0.000001, and the corners to 12 digits. In `valuation.py`, `margin_growth_table` returns the
prices and the averages; the steps are named constants in `assumptions.py`. Unlike the WACC table, which
varies the WACC itself and so ignores the WACC slider, this one uses the WACC the DCF uses, so its middle
cell is always the DCF price above; the sliders move it. Labels use two decimals because an average of
37.65% is stored just below the halfway point and one decimal showed 37.6% or 37.7% arbitrarily. Two
existing tests changed: the low-WACC page test now says the WACC heatmap is missing (it used to say the
only table was the assumptions table). The empty Data Table grid is still on the `reverse dcf` sheet
(rows 44-51); Haavard can delete it. No new files in the repository.

## 2026-11-19 — The company on trailing twelve months, like its peers (roadmap #5b)

Yahoo's peer multiples and margins are trailing twelve months, while the company's own numbers used its last
fiscal year, so the comparison was not like for like. Tried first on real companies: First Solar's operating
margin is 30.6% for the fiscal year and 37.7% over the last twelve months (against peers at 6.3%), and
summing the last four quarters reproduces Yahoo's own trailing revenue exactly. Agreed with Haavard: only
what the peers table compares goes on TTM (EV/Sales, EV/EBITDA, P/E and the operating margin, in the
Overview and in the peers table's own row), with debt and cash from the latest quarter; free cash flow
yield, net debt over EBITDA, revenue growth, the History and the DCF stay on the last fiscal year and the
page says which is which; the DCF's own base stays on the fiscal year for now. Built Excel first: sheet
`ttm` with Adobe's four quarters typed in from Yahoo and the multiples as formulas (G6:G9, C14:C25). In
Python, `trailing_total` and `ttm_overview` in `valuation.py` match the sheet's cells; `fetch_yahoo_ttm`,
`ttm_in_dollars` and `get_ttm` in `data.py` read the quarters; `apply_ttm` in `app.py` puts them in the
Overview. Two real-world gaps found on live data and handled: a quarter that has just ended can be a column
with no figures yet (Nvidia), so the latest four quarters with revenue are used; and Yahoo leaves
"Long Term Debt" out when it is zero (First Solar), which is believed only when a total debt figure is
there. If the quarters cannot be had, the page keeps the fiscal year and says so. The margin warning
against peers now uses the TTM margin, which makes it like for like (First Solar's gap is 31.4 points, not
24.3). No new files.

## 2026-11-19 — Suggest peers by profile, and top up from the sector (roadmap #5c)

The hard part of the peer-robustness item: choosing peers by business type, not size. Yahoo only has an
industry and a sector, so there is no real business description to match on. Three ideas were tried on real
companies and Haavard agreed to the first two together: rank the industry's candidates by how close their
operating margin and revenue growth are to the company's (equal weights, size kept only as a filter of a
tenth to ten times), and top up from the wider sector when the industry gives fewer than 2 suitable peers,
labelled so the reader checks them. The third idea, doing nothing more, remained as the editable box. It is
a screening rule, so no Excel step; it is written up in `docs/model.md` ("Suggesting peers"). Results: Adobe's
size ranking had brought in Snowflake (a loss-maker); by profile Intuit, Autodesk and Cadence come first;
Pfizer gains Johnson & Johnson; Apple and Microsoft get large technology companies with the sector note;
First Solar is not topped up, which is right because its sector top-up would be Seagate, ADP and Accenture.
In `valuation.py`, `profile_distance` is new and `closest_peers` ranks by it (candidates without a margin or
growth, or a company without its own, fall back to size, so the old behaviour is kept when profile data is
missing). In `data.py`, the quotes now carry revenue growth, `fetch_sector_candidates` is new, and
`suggest_peers` ranks, tops up and says where the peers came from (`peer_source`); a sector that cannot be
had only means no top-up. `PEER_SECTOR_CANDIDATES_TO_CHECK` (30) is a named constant. The page's caption,
the peer box's tooltip and a note for sector-sourced peers say what was done; the note disappears when the
reader edits the box. A first load that needs the sector is slower (about 11 to 12 seconds on live data, 5
to 8 otherwise). Known limits: growth is the latest quarter against a year earlier, so it is noisy; "closest
in margin and growth" is not "most similar business". No new files.

## 2026-11-20 — Quality numbers (roadmap #7)

To help separate a good business from a cheap one, four numbers were added: return on invested capital, cash
conversion, interest cover and the change in the share count. Tried first on seven real companies. Two
decisions with Haavard. First, invested capital is debt + equity - cash, matching the net debt used everywhere
else, and not Yahoo's own figure, which does not subtract cash (Adobe's ROIC is 63% against 40% on Yahoo's);
buybacks that shrink equity push the ROIC up (Apple 97%, Nvidia 107%) and negative equity makes it "not
meaningful". Second, the tax rate in ROIC is floored at zero, because Pfizer's -3.5% (a benefit) would inflate it;
this is only for this number and does not settle the open question about the forecast's negative tax rate. Built
Excel first: the `history` sheet, rows 24-35 (cash conversion by year, equity, invested capital, NOPAT, ROIC,
interest cover, share count change). In Python, `cash_conversion`, `invested_capital`,
`return_on_invested_capital`, `interest_cover`, `share_count_change` and `quality_numbers` in `valuation.py`
match the sheet's cells. The data package gains the optional `stockholders_equity` (from Yahoo's balance sheet,
converted like the other money figures; typed into Adobe's snapshot from the sheet). Cash conversion uses the
reported free cash flow from the History, because that is the figure people compare. The page shows the four
numbers as the last row of the Overview and cash conversion as a row of the History table; it says "Not
available" where Yahoo has no figure, "No interest" for a company with no interest expense, and "Not
meaningful" where the number would mean nothing. Checked in the running app, which showed two labels cut off
("Return on invested capital", "-9.3% over 3 years"): the label is now "ROIC" with the full name in its tooltip,
and the years sit in the small line under the share count change. In my plan I wrote FY2022's cash conversion as
1.55x; the sheet says 1.56x (7,396 / 4,756 = 1.555). No new files.

## 2026-11-20 — Hardening against Yahoo limiting the live app

On 18 and 20 Nov 2026 the live app showed "Yahoo Finance did not supply ... company_name, ... share_price,
beta" for companies other than Adobe, and a yellow "could not be reached" warning for Adobe. From the
developer's machine Yahoo answered normally, so it was not the code: Yahoo was limiting the Streamlit server,
which shares its internet address with many other apps. `yfinance` is an unofficial tool, so this can happen
without warning, and a reboot does not help. Agreed with Haavard to fix this before the next roadmap item.
Three changes, with no Excel step because nothing new is calculated. (1) A plain message: when the statements
arrive but none of the quote figures (name, currencies, exchange rates, shares, price, beta) do, the reader
sees "Yahoo Finance isn't answering the app right now. It sometimes limits shared servers, so try again in a
few minutes. Adobe still works from a frozen snapshot." instead of a list of field names; if neither the
statements nor the quote arrive, the old "check the ticker" message stays, and if only some figures are
missing they are still named. (2) One retry: an empty quote (no name, price or share count) is asked for again
once, after `YAHOO_RETRY_PAUSE_SECONDS` (2 seconds), with a fresh request because the first one keeps its
empty answer; the live Adobe quote does the same. (3) Fewer requests: the history, the last twelve months and
the suggested peers (the most expensive part of a first load: up to 50 lookups) are remembered for 6 hours
(`SLOW_DATA_CACHE_SECONDS`) instead of 15 minutes, because they change only when a company reports or hardly
ever; the share price, the company's own figures and the peers' multiples keep the 15 minutes because they
move with the market. The 6 hours were agreed with Haavard. In the tests the pause is a function of its own
(`data._pause`) that they replace; replacing `time.sleep` for the whole program made Streamlit's own test
harness busy-loop and slowed the suite from 16 to 75 seconds. A second data source that does not depend on
Yahoo is the real fix and is still open. No new files.

## 2026-11-20 — A field to adjust operating income for one-off items (roadmap #8)

Without it a margin can look better or worse than it really is: First Solar's 45X tax credits sit inside its
operating income. Tried first on First Solar with assumed amounts: -$500m takes the DCF from $221 to $156 (the
market price is $152), -$1,000m to $91. Three decisions with Haavard. (1) One yearly amount, applied to both the
last fiscal year and the last twelve months, so the DCF, the margins, EV/EBITDA and the peer comparison agree; a
recurring distortion such as a tax credit is in both. (2) Net income and the P/E stay as reported, with a note, and a
one-time gain in net income is a different adjustment, not built. (3) A sidebar box for companies other than
Adobe, whose DCF uses hand-chosen assumptions. Built Excel first: `starting point` rows 60-66 (adjusted EBIT 7,706,
adjusted margin 32.42%) and `ttm` rows 27-33 (adjusted TTM margin 31.85%, adjusted EV/EBITDA 11.57x); the existing
`last_year_ratios` and `ttm_overview` already reproduce those cells exactly, so no new maths was needed.
`apply_adjustment` and `apply_adjustment_to_ttm` in `app.py` add the amount to EBIT and to TTM operating income
before anything else is worked out, so every number worked from them follows, and `adjustment_note` writes the yellow
note saying what changed and what is as reported. The box has its own state per company. Two things found while
testing: the implied margin in the reverse DCF does not change with the adjustment (what the price needs is
absolute; it is the model's own margin in the sentence and the implied growth that move), and the tax rate is left
as reported (income tax over pre-tax income) rather than recomputed. Known limit: the same amount is applied to both
periods, which suits a recurring item but only approximates a one-off in a single period. No new files.

## 2026-11-20 — A second data source: Financial Modeling Prep, behind Yahoo

Yahoo kept refusing the Streamlit server, so every company but Adobe showed an error. Haavard asked for a backup so
the app does not depend on one provider; Claude declined to log in to his Nordnet account (a password is not
something Claude handles, and Nordnet is not a data feed), so the backup is Financial Modeling Prep (FMP), a data
provider with a keyed interface. Decisions made with Haavard. (1) Yahoo first, FMP second, the frozen Adobe snapshot
last: `_yahoo_then_fmp` in `data.py` tries Yahoo, and only a `SourceUnavailable` error (Yahoo not answering, the
network, a daily limit) makes it try FMP; a real answer about the company (unknown ticker, no pre-tax profit, a company
FMP's free plan does not cover) is passed on as it is (`UnknownCompany`), because asking another provider would only
repeat it. (2) A five-minute cool-down (`YAHOO_COOLDOWN_SECONDS`): once Yahoo has refused, the page does not ask it
again for five minutes, so each page load does not spend ten seconds waiting on a provider that is refusing us.
(3) One pull request for the whole backup, because it is one idea; Adobe's chain is live Yahoo, then live FMP
(`live_fmp`), then the snapshot. (4) FMP's free plan allows 250 requests a day and five rows per request, so every
answer is remembered for six hours (`FMP_CACHE_SECONDS`), one company costs about 12 requests, and peers cost two
requests each. To save requests FMP's suggested peers are the ones from its own peer list closest in size, without the
margin-and-growth ranking or the sector top-up Yahoo's get, and the peers' revenue growth is left out. The page says
which list was used. (5) The key lives only in Streamlit's private settings (`.streamlit/secrets.toml`, git-ignored, or
the Secrets box on Streamlit Cloud); `app.py` copies it into the environment, `data.py` reads it there, and it is never
printed, put in a message or committed. Without a key the backup is simply off. (6) One new dependency,
`requests==2.34.2`: it was already installed because `yfinance` needs it, and it is now pinned because `data.py` uses it
directly. Known limits: US companies only on the free plan; FMP's share count is market value over price, so it is only
as good as those two; its beta may be measured differently from Yahoo's; the 250 requests a day would run out after
roughly twenty fresh companies. No new files.

## 2026-11-20 — Scenarios: bear, base, bull and a probability-weighted price (roadmap #6)

A DCF gives one number from one set of assumptions, which looks more certain than it is. Four decisions with
Haavard. (1) Levers: a scenario shifts every year's operating margin and revenue growth, the same two levers as the
sliders and the margin-and-growth table; terminal growth and WACC stay as they are, because they are not what
the company's own results decide. (2) Sizes: bear -5 margin points and -2 growth points, bull +5 and +2, chosen after trying
Adobe, Coca-Cola and First Solar (Adobe's bear price is about the market's, Coca-Cola's bull price is still below it);
editable in a closed "Scenarios" box in the sidebar, limited to 20 points either way and to the right side of no change,
so a bear case cannot be better than the base and a bull case cannot be worse. The base case is always no shift, so it is the DCF
itself and a test checks that. (3) Probabilities: 25%, 50% and 25%, editable, and anything that does not add up to
100% gets a plain warning instead of prices, with a tolerance only for rounding noise in decimal arithmetic. (4) Placement: a
"Scenarios" section directly under "What the market price implies", because both ask what the market price is
assuming. Built Excel first: the `scenarios` sheet (inputs C6:E8, results C19:E22, one block per case below)
and `run_scenarios` in `valuation.py` reproduces its prices and weighted price exactly. Scenarios work on top of the
slider settings, so moving a slider moves all three prices. The weights are a judgment, not a fact, and the page says
so. No new files.

## 2026-11-20 — A normal tax rate for negative rates and an adjusted beta (one pull request)

Two inputs made low-beta companies' DCF prices look odd (Pfizer: DCF $96 against a market price of $28), and they are
one idea, making a company's inputs more realistic, so they went in one pull request, each built in Excel first
(`starting point` rows 68-73 and 75-84). Decisions with Haavard, after trying six real companies. (1) Tax: when last
year's rate is negative, the forecast uses 21% (the US federal rate), not zero (too kind) and not left alone. On its own the
change is small (flooring at zero moved Pfizer by $2); it matters because it also keeps the after-tax cost of debt
below the pre-tax cost. (2) Beta: two-thirds observed plus one-third of 1, for every company except Adobe, so Adobe's
hand-built $305.60 base case, the `scenarios` sheet and their tests are not disturbed; the price is that Adobe and the others are
treated a little differently, and the page says so by showing both betas for the others. (3) Display: the WACC table shows
"0.53 (observed 0.30)" and says where the number comes from. Result on live data: Pfizer's DCF goes from $96 to $65,
still well above its $28 market price, so these two changes are honest but do not explain the whole gap; the rest of
it comes from the starting point (one year's margin held flat) and is not solved. Tests that expected the observed beta
for other companies were updated, and the very-low-WACC tests now use an observed beta of -0.95, which the adjustment
turns into the -0.30 they need. `NORMAL_TAX_RATE`, `BETA_WEIGHT_ON_OBSERVED` and `MARKET_BETA` are in `assumptions.py`
with their Excel cells. No new files.

## 2026-11-20 — A cash flow check: warn when the model's cash flow is far above the reported one

Looking into why Pfizer's DCF price ($65) was more than twice its market price ($28) found no bug: the model starts from
operating profit, and about $7bn of costs sit between Pfizer's operating profit and its pre-tax income. The page already
quoted the model's and the reported free cash flow side by side but did not warn. Decisions with Haavard, after trying nine
real companies. (1) Compare the figures the page already has (the model's free cash flow for the last year against the
reported one), not the forecast's first year, which adds growth and a working capital fade to the comparison. (2) Warn only when
the model is above the reported figure, by more than 25% (`FREE_CASH_FLOW_RATIO_WARNING = 1.25`): below is normal because
reported free cash flow adds back share-based pay. Only Pfizer (1.83) warns today; Merck (1.13) does not. (3) Reported
free cash flow is not adjusted for interest, which it pays and the model does not; that is part of every ratio but too small
to matter for a 25% limit, and keeps the Excel check to one division. (4) The warning says what to do (check the annual report, or
use the one-off adjustment box) and is placed in the History section next to the numbers, above the table. Built Excel first
(`history` rows 37-49); `free_cash_flow_check` in `valuation.py` reproduces its ratio and its Warn/OK result. When the reader
adjusts operating income, the model's figure changes and the warning can go away, which is the point. No new files.


## 2026-11-20 — A company that cannot be valued still gets its overview and history

Ford lost money last year (operating profit -9.2bn, pre-tax profit -11.8bn), and the page showed only "A tax rate can't be worked out because the company made no pre-tax profit", with nothing below it, although a loss-maker is exactly where a history helps most. The reason is that `draw_page` had one `try` around loading the company, building the DCF and working out the overview, so any `ValueError` ended the page. Decisions with Haavard. (1) Split the `try`: loading the company (unknown ticker, no data, Yahoo down) still ends in the plain error page, because there is nothing to show; building the DCF is a second `try`, and when it fails the page draws the reason, then the Overview and History, then the footer. (2) Everything that needs a DCF is skipped, including the peer multiples table (it is built from the DCF run); drawing it for these companies would be more work and is left out on purpose. (3) The same path catches the other way a DCF can fail, a discount rate at or below terminal growth, which is better for the reader than an error alone. (4) A DCF is not forced on a loss-maker by swapping in a normal tax rate: Ford's operating margin is negative too, so any forecast that holds margins flat would be negative every year and mean nothing. No new maths, so no Excel step. `draw_dcf_unavailable` in `app.py` writes the message. No new files.

## 2026-11-20 — Price to sales (P/S) added to the multiples, and counted in the middle price

Haavard asked for forward P/E and P/S in the multiples and for both to count in the middle price. Done one at a time, P/S first, because forward P/E needs a new data field. Decisions. (1) P/S counts in the middle price (the median of four prices instead of three): Adobe's middle price goes from $420.52 to $377.05 and its gap to the DCF from -27.3% to -18.9%; Adobe's DCF ($305.60) is untouched. The alternative, showing P/S on its own beside an unchanged middle, was offered and not taken. (2) P/S has no net debt step: market value over sales is already an equity value, like P/E, so the price is revenue × peer median P/S ÷ shares. (3) Data: Yahoo's `priceToSalesTrailing12Months` (which equals market value ÷ revenue) and, for the backup, FMP's `priceToSalesRatioTTM`, checked live on Apple against Yahoo (10.396 on both). (4) Adobe's peers are frozen in the snapshot, so the four P/S figures are Yahoo's of 20 Nov 2026 while the other three columns are from April; the workbook says so in `Multiples` I7. Mixed dates are a small inconsistency, accepted rather than retyping all three columns. (5) A peer can also be flagged "P/S outlier" by the same 3-times rule, which is a Python screening rule with no cell in the workbook, like the other flags. (6) The company's own P/S (workbook C66) is in the peer table only, not an overview box. (7) No glossary text was written: that is Haavard's, noted under "open". Built Excel first; `Multiples` G7:G13, row 30, C35:C37 and C66. No new files.

## 2026-11-20 — Forward P/E added to the multiples, and counted in the middle price

The second half of Haavard's request (P/S was first). Decisions. (1) Forward P/E counts in the middle price, now the median of five prices (the middle one): Adobe's middle price goes from $377.05 to $390.59 and its gap to the DCF from -18.9% to -21.8%. (2) The price is next year's analyst EPS times the peers' median forward P/E, which is already per share: no net debt step, no division by shares. (3) Data: Yahoo gives both the peers' `forwardPE` and the company's `forwardEps` in the same lookup the page already makes, so it costs no Financial Modeling Prep requests. The forward EPS is in the currency the share trades in (checked on Novo Nordisk, price in dollars and reporting in kroner, and on Aker), so it converts at the share price's rate. (4) With Yahoo down the FMP backup gives no forward P/E: a third request per peer and one for the company would use up the free 250 a day quickly; the page then says "No estimate". (5) The estimate is the analysts' adjusted EPS (Adobe 27.41 against 17.91 GAAP), consistent only because the peers' forward P/E is on the same basis; the page says so under the table, and the model never compares forward with ordinary P/E. (6) A peer can be flagged "Forward P/E outlier" by the same 3-times rule (a Python screening rule, like the others). (7) Adobe's snapshot holds the peers' forward P/E and Adobe's EPS of 20 Nov 2026, as typed in the workbook; the live page keeps the snapshot EPS while using the live price, so over time they drift apart. (8) A company with no estimate, or one not above zero, shows "No estimate" and the middle uses the other prices. No glossary text written (Haavard's). Built Excel first: `Multiples` rows 68-77, row 31, C35:C37. No new files.

## 2026-11-20 — News and management on the page (roadmap #11, part 1 of 3)

Haavard wants a thesis page that also carries news about the company, management and the macro backdrop (all three, plus his own reasons boxes and a Markdown download, nothing saved on the server). Built as three pull requests, one idea each: this one, then macro, then the thesis page that gathers everything. Decisions. (1) Source: Yahoo Finance only, because its news feed and officer list come free in calls the page already knows how to make; there is no Financial Modeling Prep fallback, which would cost requests of the free daily limit for something optional. (2) Placement: at the end of the page, above the footer, since nothing in the valuation depends on it and it should not push the assumptions and charts down; it also shows for a company whose DCF cannot be built, where news matters most. (3) Size: 5 headlines and 5 officers (`NEWS_ITEMS_SHOWN`, `OFFICERS_SHOWN` in `assumptions.py`), remembered together for 15 minutes (`LIVE_DATA_CACHE_SECONDS`): one lookup rather than two caches. (4) Honest limits: Yahoo gives today's officers only, so "management changes" would need old lists stored, which we do not do; and it sometimes mixes general market stories into a company's news (Ford), so the page says so. (5) Safety: headlines and names are untrusted text from outside. Every character markdown could read as formatting (a dollar sign starts a maths formula in Streamlit, brackets and asterisks make links and bold) gets a backslash; only plain `https://` links are kept; a bracket inside an address is encoded. (6) Failure: each part may fail on its own and the other still shows; if neither can be had, or Yahoo said it was busy a moment ago (then it is left alone), the section says it is not available right now and the rest of the page is untouched. No maths, so no Excel step. No new files.
