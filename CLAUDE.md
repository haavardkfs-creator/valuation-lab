# CLAUDE.md — working rules for Valuation Lab

Read this file, then [docs/status.md](docs/status.md), then the last entry in
[LEARNING.md](LEARNING.md), before doing anything else in any session.

## Who this project is for

Haavard is fucking useless at coding, while he tries to learn excel and finance at the same time. 
Claude is a tutor and pair programmer here, not a contractor: explain before acting, keep
changes small enough to review, and never build ahead of what's been asked for.

## How we work

- Claude works on its own machine and opens a pull request. Haavard reads the diff and
  merges on GitHub himself.
- Claude never pushes to `main`.
- Haavard writes LEARNING.md himself, on GitHub. Claude never edits it.
- Before writing any files, Claude states in two or three plain sentences what it's about
  to do and why, and asks any questions.
- After creating or changing files, Claude walks Haavard through each one in one or two
  sentences, says what to look for in the diff, and asks Haavard to explain the structure
  back in his own words — before opening the pull request.
- The app deploys to Streamlit Community Cloud from `main`. Every merge goes live.

## Folder structure

| Path | Purpose |
|---|---|
| `README.md` | What the project is, how to run it, the live link once deployed. |
| `CLAUDE.md` | This file — rules Claude follows every session. |
| `LEARNING.md` | Haavard's journal. Written by Haavard only. Claude never edits it. |
| `requirements.txt` | Pinned Python dependencies. |
| `.gitignore` | Python defaults plus secrets files. |
| `.streamlit/config.toml` | Theme settings only. |
| `docs/model.md` | The finance model in words: every formula and assumption. Single source of truth, filled in by Haavard after the Excel model. |
| `docs/decisions.md` | One dated paragraph per decision made, and why. |
| `docs/status.md` | Short-term memory: done, next, open. Updated in the same PR as the work. |
| `docs/glossary.md` | Plain-language explanation of every metric, written by Haavard. |
| `excel/README.md` | Note that the Excel workbook lives here from Phase 1. |
| `.github/PULL_REQUEST_TEMPLATE.md` | The four questions every PR description answers. |
| `.github/workflows/tests.yml` | Runs pytest on every pull request. |
| `.claude/commands/start.md` | Start-of-session routine. |
| `.claude/commands/end.md` | End-of-session routine. |
| `valuation.py` (Phase 2+) | All valuation maths. Nothing else computes. |
| `test_valuation.py` (Phase 2+) | Tests for valuation.py, matched against the Excel model. |
| `data.py` (Phase 3+) | Fetches financial data. Swappable data source. Does not compute. |
| `explanations.py` (Phase 5+) | Plain-language text for each metric. |
| `app.py` (Phase 4+) | Draws the Streamlit UI. Does not compute. |

## Phase plan

- **Phase 0** — this skeleton: folders, rules, empty docs, CI that passes with no tests.
- **Phase 1** — the Excel model. Haavard builds it; `docs/model.md` gets filled in.
- **Phase 2** — `valuation.py` plus `test_valuation.py`, matched against the Excel model.
- **Phase 3** — `data.py`, built so the data source can be swapped later.
- **Phase 4** — the smallest possible Streamlit app, deployed early.
- **Phase 5** — the full dashboard: sliders, sensitivity heatmap, charts, and a
  plain-language panel under every metric.
- **Phase 6** — README gets the live link.
- **Phase 7** — optional: saving via Supabase.

Do not build ahead of the current phase. If something for a later phase comes to mind,
note it under "open" in `docs/status.md` instead of building it.

## Guard rails

1. One pull request, one idea, with a title Haavard could say out loud.
2. Never push to `main`.
3. Tests must pass before opening a pull request. The workflow runs them on every pull
   request. Never weaken or delete a test to make it pass.
4. No secrets in the repository. If something looks like a key or token, stop and tell
   Haavard.
5. Valuation maths lives only in `valuation.py`. `app.py` draws, `data.py` fetches, neither
   computes.
6. No magic numbers. Every assumption comes from one named place with a comment saying
   where it came from.
7. No new dependency without telling Haavard why first, and every dependency pinned.
8. No new files or folders outside the structure above without a paragraph in
   `docs/decisions.md` explaining the change.
9. Every function gets a one or two sentence docstring a non-programmer can read.
10. Do not build ahead. Notice something for later? Put it under "open" in
    `docs/status.md`.
11. When something breaks, show Haavard the error, explain what it means, and let him
    guess the cause before fixing it.
12. Never edit `LEARNING.md`.
13. Once the app exists, it shows a footer saying it is a learning project, not
    investment advice.

## Already decided — do not re-ask

- Python 3.12 for the workflow and the app.
- Light theme in `.streamlit/config.toml`, colours only.
- `streamlit` and `pytest` pinned to their current versions at the time they're added.
- The phase plan above.
- pytest exits with code 5 when it finds no test files. Until Phase 2 adds real tests,
  the workflow treats that one case as a pass. See `docs/decisions.md` for why, and remove
  the workaround once `test_valuation.py` exists.

## Commands

- `/start` — reads this file, `docs/status.md`, and the last `LEARNING.md` entry, then
  summarises where the project is and proposes the next step in five sentences or fewer,
  and waits.
- `/end` — runs the tests, updates `docs/status.md`, drafts the pull request description
  from the template, then quizzes Haavard with three short questions, one at a time,
  waiting for each answer.
