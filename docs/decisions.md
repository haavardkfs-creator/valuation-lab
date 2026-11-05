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
