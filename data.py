"""Supplies the company figures that valuation.py needs, from a data source that can be swapped.

This file only fetches and passes numbers on; it never calculates (guard rail 5). Every
source hands back the same "package" of named figures (see PACKAGE_FIELDS), so a new source
can be plugged in later without touching valuation.py or the app.

Conventions: money is in $ millions, shares are in millions, and rates are decimals
(0.05 means 5%).
"""

import copy


# ---------------------------------------------------------------------------
# The package: what every data source must provide
# ---------------------------------------------------------------------------

PACKAGE_FIELDS = {
    "company_name": "Company name",
    "ticker": "Stock ticker",
    "revenue": "Latest full-year total revenue, $ millions",
    "ebit": "Latest full-year operating income (EBIT), $ millions",
    "depreciation_and_amortisation": "Latest full-year depreciation and amortisation, $ millions",
    "net_income": "Latest full-year net income, $ millions",
    "debt": "Financial debt: current portion plus long-term debt, leases excluded, $ millions",
    "cash_and_investments": "Cash and cash equivalents plus short-term investments, $ millions",
    "shares": "Shares outstanding, millions",
    "share_price": "Current share price, $",
    "beta": "How much the stock moves with the market (5-year monthly)",
    "risk_free_rate": "Risk-free rate, decimal",
    "equity_risk_premium": "Equity risk premium, decimal",
    "pre_tax_cost_of_debt": "Weighted average effective interest rate on the company's debt, decimal",
    "peer_tickers": "Tickers of the peer companies, in the same order as the three lists below",
    "peer_ev_sales": "Each peer's EV/Sales multiple",
    "peer_ev_ebitda": "Each peer's EV/EBITDA multiple",
    "peer_pe": "Each peer's P/E multiple",
}


# ---------------------------------------------------------------------------
# Source 1: the snapshot (the numbers typed into excel/valuation-lab.xlsx)
# ---------------------------------------------------------------------------

# Frozen on 4 Nov 2026. These do not update by themselves; they are the exact figures the
# Excel model and docs/model.md use, so the Python can be checked against Excel to the cent.
ADOBE_SNAPSHOT = {
    "company_name": "Adobe Inc.",
    "ticker": "ADBE",
    # Adobe Form 10-K, FY2025 ($ millions; page numbers refer to that filing)
    "revenue": 23769,                       # Income statement, p. 48: total revenue
    "ebit": 8706,                           # Income statement, p. 48: operating income
    "depreciation_and_amortisation": 818,   # Cash flow statement, p. 51: depreciation, amortization and accretion
    "net_income": 7130,                     # Income statement, p. 48
    "debt": 6210,                           # Balance sheet, p. 47: current portion 0 + long-term debt 6,210
    "cash_and_investments": 6595,           # Balance sheet, p. 47: cash 5,431 + short-term investments 1,164
    "shares": 413,                          # FY2025 10-K cover page: year-end count after buybacks
    # Market data
    "share_price": 251.47,                  # Yahoo Finance, closing price, 2 Nov 2026
    "beta": 1.38,                           # Yahoo Finance, 5Y monthly, 2 Nov 2026
    "risk_free_rate": 0.0529,               # Damodaran, US Treasury rate used in his implied ERP, 1 Nov 2026
    "equity_risk_premium": 0.0441,          # Damodaran, implied ERP (trailing 12 months, adjusted payout), 1 Nov 2026
    # Weighted average effective rate on the senior notes, FY2025 10-K Note 17, p. 82.
    # Stored unrounded, exactly as the Excel model holds it (Inputs G55), not as 4.16%.
    "pre_tax_cost_of_debt": 0.041642276422764232,
    # Peers, trailing twelve months, Yahoo Finance Statistics tab, 4 Nov 2026.
    # Order: Autodesk, Intuit, Salesforce, Synopsys.
    "peer_tickers": ["ADSK", "INTU", "CRM", "SNPS"],
    "peer_ev_sales": [6.71, 4.35, 4.85, 10.19],
    "peer_ev_ebitda": [22.94, 13.45, 12.63, 26.18],
    "peer_pe": [32.73, 20.72, 20.97, 82.62],
}


def snapshot_source(ticker):
    """Return Adobe's figures from the frozen snapshot of the Excel model's numbers.

    Stops with a plain error for any other company, because the snapshot only holds Adobe.
    """
    if ticker != ADOBE_SNAPSHOT["ticker"]:
        raise ValueError(
            "The snapshot source only has Adobe (ADBE), so it cannot supply '%s'." % ticker
        )
    return copy.deepcopy(ADOBE_SNAPSHOT)


# ---------------------------------------------------------------------------
# Source 2: live (current share price and beta from Yahoo Finance)
# ---------------------------------------------------------------------------

def fetch_yahoo_quote(ticker):
    """Ask Yahoo Finance for a stock's current share price and beta.

    Returns a dictionary with "share_price" and "beta"; a figure Yahoo does not have comes
    back as None. This is the only function that touches the internet.
    """
    # Imported here, not at the top, so the snapshot source works even without yfinance.
    import yfinance

    info = yfinance.Ticker(ticker).info
    return {"share_price": info.get("currentPrice"), "beta": info.get("beta")}


def live_source(ticker, fetch_quote=fetch_yahoo_quote):
    """Return Adobe's figures with today's share price and beta from Yahoo Finance.

    Everything else (the 10-K figures, risk-free rate, equity risk premium, peers) still
    comes from the snapshot. Stops with a plain error if Yahoo cannot be reached or does not
    give a usable price or beta. `fetch_quote` can be swapped, which is how the tests run
    without the internet.
    """
    package = snapshot_source(ticker)
    try:
        quote = fetch_quote(ticker)
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise ValueError("Could not get live figures from Yahoo Finance: %s" % error) from error

    price = quote.get("share_price")
    if price is None or price <= 0:
        raise ValueError("Yahoo Finance did not give a usable share price for %s." % ticker)
    beta = quote.get("beta")
    if beta is None:
        raise ValueError("Yahoo Finance did not give a beta for %s." % ticker)

    package["share_price"] = price
    package["beta"] = beta
    return package


# ---------------------------------------------------------------------------
# Choosing a source and fetching
# ---------------------------------------------------------------------------

# To add a new source later, write a function that takes a ticker and returns a package,
# then add it here under a name. Nothing else needs to change.
SOURCES = {
    "snapshot": snapshot_source,
    "live": live_source,
}

DEFAULT_SOURCE = "snapshot"


def check_package(package):
    """Make sure a data source supplied every figure in PACKAGE_FIELDS, so a half-empty
    package is caught here and not deep inside a calculation.
    """
    missing = [name for name in PACKAGE_FIELDS if name not in package]
    if missing:
        raise ValueError("The data source did not supply: " + ", ".join(missing))


def get_company_data(ticker, source=DEFAULT_SOURCE):
    """Fetch the package of figures for a company from the chosen data source.

    Returns a dictionary of named figures, checked to be complete. The ticker can be in any
    letter case.
    """
    if source not in SOURCES:
        raise ValueError(
            "Unknown data source '%s'. Available sources: %s." % (source, ", ".join(SOURCES))
        )
    package = SOURCES[source](ticker.upper())
    check_package(package)
    return package


# The page tries the preferred source first and falls back to the other if it fails.
PREFERRED_SOURCE = "live"
FALLBACK_SOURCE = "snapshot"


def get_company_data_with_fallback(ticker):
    """Fetch a company's figures from the live source, or from the snapshot if the live
    source fails.

    Returns two things: the package of figures, and the name of the source that supplied it,
    so the page can tell the reader where the numbers came from.
    """
    try:
        return get_company_data(ticker, source=PREFERRED_SOURCE), PREFERRED_SOURCE
    except ValueError:      # live_source turns every Yahoo failure into a ValueError
        return get_company_data(ticker, source=FALLBACK_SOURCE), FALLBACK_SOURCE
