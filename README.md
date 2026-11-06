# Valuation Lab

A learning project: an interactive valuation of Adobe, built to learn finance and Python
at the same time. It runs a discounted cash flow (DCF) valuation and a peer multiples
comparison, lets you change the assumptions and watch the price move, and explains every
metric in plain language.

**Live app: https://valuation-l3b.streamlit.app**

This is a learning project, not investment advice.

## What it does today

The app opens on **Adobe (ADBE)**, and a **Company ticker** box in the sidebar lets you value
any other company on Yahoo Finance. Adobe's forecast is hand-chosen and checked against the Excel
model. For any other company, every figure comes from Yahoo Finance's latest annual statements
converted to US dollars at today's exchange rate if the company reports or trades in another currency, and the forecast is only a **starting point, not a forecast**: revenue growth fades in equal
steps to the terminal growth rate, capex fades down to the D&A level if it was above it, and
margins, tax rate, D&A and working capital stay at last year's level. Other companies get the DCF only (no peer multiples), and a DCF
suits stable, cash-generating companies, not banks, loss-making or early-stage ones.

For Adobe, the share price and beta are live from Yahoo Finance
(remembered for 15 minutes); if Yahoo cannot be reached, the page says so and uses a frozen
snapshot instead. Every other figure comes from the snapshot of the Excel model (dated
4 Nov 2026; sources are in `data.py` and `docs/model.md`). With the snapshot's price and beta
the base-case DCF gives an implied share price of $305.60, against a market price of $251.47;
with live figures the result moves a little with Yahoo's beta.

- **Sliders** change revenue growth, operating margin and terminal growth, and an optional
  "Set the WACC myself" control replaces the model's own WACC.
- A **sensitivity heatmap** shows the price at different WACCs and terminal growth rates.
- **Two charts** show the five-year forecast and what the company is worth today.
- A **peer multiples comparison** (EV/Sales, EV/EBITDA, P/E) sits beside the DCF.
- A **"What do these terms mean?" box** under each section explains the terms in plain
  language, using the wording in `docs/glossary.md`.

## Running it locally

You need Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

To run the tests:

```bash
pytest
```

The tests check the Python against the numbers in the Excel model (`excel/valuation-lab.xlsx`),
so they fail if the two ever drift apart.

## Planned

- A way to choose peer companies, so other companies can get a multiples comparison too.
- Optionally, saving a user's assumptions.

## How it is built

All valuation maths lives in `valuation.py`. `data.py` supplies the company figures,
`assumptions.py` holds the forecast assumptions, `explanations.py` holds the plain-language
text and `app.py` only draws the page. See [CLAUDE.md](CLAUDE.md) for the full folder
structure and the rules the project follows, [docs/model.md](docs/model.md) for every
formula, and [docs/status.md](docs/status.md) for what is done and what is next.
