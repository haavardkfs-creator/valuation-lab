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
