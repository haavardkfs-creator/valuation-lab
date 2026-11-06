# Valuation Lab

A learning project: an interactive valuation of Adobe, built to learn finance and Python
at the same time. It runs a discounted cash flow (DCF) valuation and a peer multiples
comparison, lets you change the assumptions and watch the price move, and explains every
metric in plain language.

**Live app: https://valuation-l3b.streamlit.app**

This is a learning project, not investment advice.

## What it does today

The app values **Adobe (ADBE)** from a frozen snapshot of the figures in the Excel model
(dated 4 Nov 2026; sources are in `data.py` and `docs/model.md`). In the base case the DCF
gives an implied share price of $305.60, against a market price of $251.47.

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

- A live data source, starting with share price and beta, so you could type a ticker and
  value companies other than Adobe. Today the app only knows Adobe. For other companies the
  forecast would start from the company's own last reported year and be shown clearly as a
  starting point, not a forecast.
- Optionally, saving a user's assumptions.

## How it is built

All valuation maths lives in `valuation.py`. `data.py` supplies the company figures,
`assumptions.py` holds the forecast assumptions, `explanations.py` holds the plain-language
text and `app.py` only draws the page. See [CLAUDE.md](CLAUDE.md) for the full folder
structure and the rules the project follows, [docs/model.md](docs/model.md) for every
formula, and [docs/status.md](docs/status.md) for what is done and what is next.
