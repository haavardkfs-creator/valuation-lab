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
steps to the terminal growth rate, capex fades down to the D&A level if it was above it, working capital fades to zero, and
margins, tax rate and D&A stay at last year's level. Other companies get the DCF only (no peer multiples), and a DCF
suits stable, cash-generating companies, not banks, loss-making or early-stage ones.

For Adobe, the share price and beta are live from Yahoo Finance
(remembered for 15 minutes); if Yahoo cannot be reached, the page says so and uses a frozen
snapshot instead. Every other figure comes from the snapshot of the Excel model (dated
4 Nov 2026; sources are in `data.py` and `docs/model.md`). With the snapshot's price and beta
the base-case DCF gives an implied share price of $305.60, against a market price of $251.47;
with live figures the result moves a little with Yahoo's beta.

Yahoo sometimes refuses the shared server the live app runs on, so there is a second source:
**Financial Modeling Prep** (free plan: US companies only, 250 requests a day). The page asks Yahoo
first and switches to Financial Modeling Prep, with a note saying so, when Yahoo is not answering.
It needs a key, kept out of the code: on this computer in `.streamlit/secrets.toml` (git-ignored) as
`FMP_API_KEY = "..."`, and on Streamlit Cloud in the app's Secrets. Without a key the page works as
before, on Yahoo alone.

- Six **tabs** under the header: Overview (the football field, the overview numbers grouped by what they say,
  the history, news and management), DCF, Multiples, Sensitivity, Compare and Explanations (the glossary).
- An **analyst view** on the Overview tab: Yahoo Finance's consensus rating and price targets (and a bar for them on
  the football field), as a comparison for the model.
- **Search by company name**: type part of a name in the sidebar and click the company you mean; a ticker that is not found
  also offers likely matches.
- An **"answer first" header** at the top: the company's name, a verdict badge (undervalued, fairly valued or
  overvalued, from the DCF against the market price), four headline cards and a 12-month price chart.
- **Sliders** change revenue growth, operating margin and terminal growth, and an optional
  "Set the WACC myself" control replaces the model's own WACC.
- A **sensitivity heatmap** shows the price at different WACCs and terminal growth rates.
- **Two charts** show the five-year forecast and what the company is worth today.
- A **peer multiples comparison** (EV/Sales, EV/EBITDA, P/E, P/S and forward P/E) sits beside the DCF.
- **News and management** at the end of the page: the five most recent headlines (as links) and the top
  officers, from Yahoo Finance. It is context only; nothing in the valuation depends on it.
- A **Compare tab**: type a second ticker and see the two companies side by side, in a table and in a chart of how far
  each way of valuing them is from their own market price. Both get the same sliders and the same typed-in WACC.
- A **shareable link**: the page's address holds the company, the sliders, the typed-in WACC, the one-off amount and the peers,
  so copying the address from the browser sends exactly your view.
- A **macro backdrop** under the news: the 10-year Treasury yield, the Fed funds rate and US inflation, from FRED. Background
  only; it needs a free `FRED_API_KEY` (the same two places as the Financial Modeling Prep key) and says so when it has none.
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
