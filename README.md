# Valuation Lab

A learning project. Type a stock ticker or search for a company, and this app fetches its
financials, runs a discounted cash flow valuation and a multiples comparison, and lets you
explore how changing revenue growth, operating margin, WACC and terminal growth changes the
result. Every metric is explained in plain language.

This is a learning project, not investment advice.

## Status
finished with phase 5. The app values ADBE only, from a frozen snapshot of the figures from the excel model. 
It runs a DCF (implied price $305.60 against a market price of $251.47) and a peer multiples comparison (EV/Sales, EV/EBITDA and P/E prices, with a middle value of $420.52).
You can change the assumptions with sliders (revenue growth, operating margin and terminal growth) and with an optional “Set the WACC myself” control.
It shows a sensitivity heatmap (price by WACC and terminal growth), two charts (the forecast, and what the company is worth today) and “What do these terms mean?” boxes that come from your glossary.
It has a footer saying it’s a learning project, not investment advice.
## Running it locally

Nothing to run yet. Once `app.py` exists (Phase 4 onward):

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Live app

Not deployed yet. This section will hold the Streamlit Community Cloud link once Phase 6
ships.

## Project layout

See [CLAUDE.md](CLAUDE.md) for the full folder structure and what each file is for.
