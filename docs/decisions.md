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
