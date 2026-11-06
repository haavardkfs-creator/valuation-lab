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
