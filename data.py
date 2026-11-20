"""Supplies the company figures that valuation.py needs, from a data source that can be swapped.

This file only fetches and passes numbers on; it never calculates (guard rail 5). Every
source hands back the same "package" of named figures (see PACKAGE_FIELDS), so a new source
can be plugged in later without touching valuation.py or the app.

Conventions: money is in $ millions, shares are in millions, and rates are decimals
(0.05 means 5%). Every figure is in US dollars: a company that reports or trades in another
currency is converted at today's exchange rate. Turning Yahoo's dollars into millions, or its
negative capex into a positive amount, is tidying the units, not maths. Adding two reported debt lines together is
maths, so it is done by valuation.financial_debt, not here.
"""

import copy

import valuation


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
    "prior_year_revenue": "Total revenue of the full year before the latest one, $ millions",
    "income_tax": "Latest full-year income tax expense (provision for income taxes), $ millions",
    "income_before_tax": "Latest full-year income before income taxes, $ millions",
    "interest_expense": "Latest full-year interest expense, as a positive amount, $ millions; None when the source has none, in which case the package carries a fallback cost of debt",
    "capex": "Latest full-year capital spending, as a positive amount, $ millions",
    "cash_from_working_capital": "Latest full-year cash from working capital, positive when cash comes in, $ millions",
    "debt": "Financial debt: current portion plus long-term debt, leases excluded, $ millions",
    "cash_and_investments": "Cash and cash equivalents plus short-term investments, $ millions",
    "shares": "Shares outstanding, millions",
    "share_price": "Current share price, $",
    "beta": "How much the stock moves with the market (5-year monthly)",
    "risk_free_rate": "Risk-free rate, decimal",
    "equity_risk_premium": "Equity risk premium, decimal",
}

# Figures only some sources can supply. Adobe has both (typed in from the 10-K and Yahoo's
# Statistics tab); a company read from Yahoo's statements has neither, so for it the page shows
# the DCF only (see docs/decisions.md).
OPTIONAL_FIELDS = {
    "stockholders_equity": "Stockholders' equity (book value) at the end of the latest full year, $ millions; used for the return on invested capital",
    "pre_tax_cost_of_debt": "Weighted average effective interest rate on the company's debt, decimal",
    "cost_of_debt_is_fallback": "True when pre_tax_cost_of_debt is the risk-free rate plus a credit spread, because the company's interest expense was not available",
    "peer_tickers": "Tickers of the peer companies, in the same order as the three lists below",
    "peer_ev_sales": "Each peer's EV/Sales multiple",
    "peer_ev_ebitda": "Each peer's EV/EBITDA multiple",
    "peer_pe": "Each peer's P/E multiple",
    "peer_operating_margin": "Each peer's operating margin, trailing twelve months, decimal (negative for a loss); None when Yahoo has none",
    "statement_currency": "Currency the company reports in, before conversion to US dollars, for example NOK",
    "price_currency": "Currency the share trades in, before conversion to US dollars, for example NOK or GBp (pence)",
    "usd_per_statement_unit": "US dollars one unit of the statement currency was worth when the figures were fetched",
    "usd_per_price_unit": "US dollars one unit of the price currency was worth when the figures were fetched",
}


# ---------------------------------------------------------------------------
# Market-wide figures: the same for every company, typed in by hand (no simple feed)
# ---------------------------------------------------------------------------

# Dated 1 Nov 2026. These go stale: update them, MARKET_FIGURES_SOURCE and the date in their
# comments, when Damodaran publishes new ones.
MARKET_FIGURES_SOURCE = "Damodaran, 1 Nov 2026"     # what the page says these two figures come from
RISK_FREE_RATE = 0.0529             # Damodaran, US Treasury rate used in his implied ERP, 1 Nov 2026
EQUITY_RISK_PREMIUM = 0.0441        # Damodaran, implied ERP (trailing 12 months, adjusted payout), 1 Nov 2026

# Used only when Yahoo has no interest expense for a company (Apple, for one), so its cost of
# debt cannot be estimated from its own figures. It is a middle-of-the-road spread: the extra a
# BBB-rated (Baa2) company pays over the risk-free rate.
CREDIT_SPREAD = 0.0111              # Damodaran synthetic rating spreads, Jan 2026 (Baa2/BBB); starting point C36


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
    "prior_year_revenue": 21505,            # Income statement, p. 48: FY2024 total revenue (Inputs F11)
    "income_tax": 1604,                     # Income statement, p. 48: provision for income taxes
    "income_before_tax": 8734,              # Income statement, p. 48: income before income taxes
    "interest_expense": 263,                # Income statement, p. 48: interest expense (shown as -263 there)
    "capex": 179,                          # Cash flow statement, p. 51: purchases of property and equipment (shown as -179 there)
    # Cash flow statement, p. 51: the six working capital lines added together (receivables,
    # prepaid expenses, payables, accrued expenses, income taxes payable, deferred revenue).
    "cash_from_working_capital": 605,
    "debt": 6210,                           # Balance sheet, p. 47: current portion 0 + long-term debt 6,210
    "cash_and_investments": 6595,           # Balance sheet, p. 47: cash 5,431 + short-term investments 1,164
    "stockholders_equity": 11623,           # Yahoo Finance, FY2025 stockholders' equity, 19 Nov 2026 (workbook: history C26)
    "shares": 413,                          # FY2025 10-K cover page: year-end count after buybacks
    # Market data
    "share_price": 251.47,                  # Yahoo Finance, closing price, 2 Nov 2026
    "beta": 1.38,                           # Yahoo Finance, 5Y monthly, 2 Nov 2026
    "risk_free_rate": RISK_FREE_RATE,
    "equity_risk_premium": EQUITY_RISK_PREMIUM,
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
# Source 3: yahoo (any company, from Yahoo Finance's financial statements)
# ---------------------------------------------------------------------------

MILLION = 1_000_000     # Yahoo reports money in dollars; the package is in $ millions


def _statement_line(frame, names, column):
    """Read one figure from a Yahoo statement table: the first of `names` that Yahoo has,
    for the year in `column` (0 is the latest year, 1 the year before).

    Returns None if Yahoo has no figure for it.
    """
    if column >= len(frame.columns):
        return None
    for name in names:
        if name in frame.index:
            value = frame.loc[name].iloc[column]
            if value == value:      # a "not a number" means Yahoo has no figure for that year
                return float(value)
    return None


def _fetch_usd_per_unit(currency):
    """Ask Yahoo how many US dollars one unit of a currency is worth.

    Returns 1 for dollars and None if Yahoo has no rate. Yahoo quotes London shares in pence
    ("GBp"), a hundredth of a pound.
    """
    import yfinance

    if currency == "USD":
        return 1.0
    if currency == "GBp":
        pounds = _fetch_usd_per_unit("GBP")
        return None if pounds is None else pounds / 100
    quote = yfinance.Ticker(currency + "USD=X").info
    return quote.get("regularMarketPrice") or quote.get("previousClose")


def fetch_yahoo_statements(ticker):
    """Ask Yahoo Finance for a company's latest two annual statements and its quote.

    Returns a dictionary of figures in the company's own currency, in millions (shares in
    millions); a figure Yahoo does not have comes back as None. Capex and interest expense
    come back as positive amounts. Debt comes back as two separate lines. The currencies the
    statements and the share price are in come back too, with the exchange rate to US dollars
    for each. This is the only function in this source that touches the internet.
    """
    # Imported here, not at the top, so the other sources work even without yfinance.
    import yfinance

    stock = yfinance.Ticker(ticker)
    income, cash_flow, balance, info = stock.income_stmt, stock.cashflow, stock.balance_sheet, stock.info

    def millions(frame, names, column=0, positive=False):
        value = _statement_line(frame, names, column)
        if value is None:
            return None
        value = value / MILLION
        return abs(value) if positive else value

    shares = info.get("sharesOutstanding")
    statement_currency = info.get("financialCurrency")
    price_currency = info.get("currency")
    return {
        "company_name": info.get("longName") or info.get("shortName"),
        "statement_currency": statement_currency,
        "price_currency": price_currency,
        "usd_per_statement_unit": None if statement_currency is None else _fetch_usd_per_unit(statement_currency),
        "usd_per_price_unit": None if price_currency is None else _fetch_usd_per_unit(price_currency),
        "revenue": millions(income, ["Total Revenue"]),
        "prior_year_revenue": millions(income, ["Total Revenue"], column=1),
        "ebit": millions(income, ["Operating Income"]),
        "net_income": millions(income, ["Net Income"]),
        "income_tax": millions(income, ["Tax Provision"]),
        "income_before_tax": millions(income, ["Pretax Income"]),
        "interest_expense": millions(income, ["Interest Expense"], positive=True),
        "depreciation_and_amortisation": millions(
            cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion"]
        ),
        "capex": millions(cash_flow, ["Capital Expenditure"], positive=True),
        "cash_from_working_capital": millions(cash_flow, ["Change In Working Capital"]),
        "long_term_debt": millions(balance, ["Long Term Debt"]),
        "current_debt": millions(balance, ["Current Debt"]),
        "cash_and_investments": millions(balance, ["Cash Cash Equivalents And Short Term Investments"]),
        "stockholders_equity": millions(balance, ["Stockholders Equity", "Common Stock Equity"]),
        "shares": None if shares is None else shares / MILLION,
        "share_price": info.get("currentPrice"),
        "beta": info.get("beta"),
    }


# Figures Yahoo must supply for a company to be valued. Current debt is one exception: Yahoo
# leaves it out when a company has none, so a missing one counts as 0. Interest expense is the
# other: when Yahoo has none (Apple), the cost of debt falls back to the risk-free rate plus a
# credit spread.
YAHOO_REQUIRED = [
    "company_name", "statement_currency", "price_currency", "usd_per_statement_unit",
    "usd_per_price_unit", "revenue", "prior_year_revenue", "ebit", "net_income", "income_tax",
    "income_before_tax", "depreciation_and_amortisation", "capex",
    "cash_from_working_capital", "long_term_debt", "cash_and_investments", "shares",
    "share_price", "beta",
]


# The company's money figures, which Yahoo gives in the currency the company reports in.
YAHOO_MONEY_FIELDS = [
    "revenue", "prior_year_revenue", "ebit", "net_income", "income_tax", "income_before_tax",
    "interest_expense", "depreciation_and_amortisation", "capex", "cash_from_working_capital",
    "cash_and_investments", "stockholders_equity",
]


def yahoo_source(ticker, fetch_statements=fetch_yahoo_statements):
    """Return a company's figures from Yahoo Finance's financial statements, for any company,
    all in US dollars.

    A company that reports or trades in another currency (kroner, pence, ...) is converted at
    the exchange rate Yahoo gives today: the statement figures at the statement currency's
    rate, and the share price at the price currency's rate. The risk-free rate and equity risk
    premium are the market-wide figures typed in above. The package has no cost of debt from
    the debt notes and no peer multiples, because Yahoo cannot supply them. When Yahoo has no
    interest expense either (Apple), the package carries a fallback cost of debt, the risk-free
    rate plus a credit spread, and says so. Stops with a plain error naming any other figure
    Yahoo did not supply, or if Yahoo cannot be reached.
    `fetch_statements` can be swapped, which is how the tests run without the internet.
    """
    try:
        statements = fetch_statements(ticker)
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise ValueError("Could not get figures from Yahoo Finance: %s" % error) from error

    missing = [name for name in YAHOO_REQUIRED if statements.get(name) is None]
    if len(missing) == len(YAHOO_REQUIRED):
        raise ValueError(
            "Yahoo Finance has no figures for %s. Check that the ticker is right; "
            "US-listed companies work best." % ticker
        )
    for currency_name, rate_name in (
        ("statement_currency", "usd_per_statement_unit"),
        ("price_currency", "usd_per_price_unit"),
    ):
        if statements.get(currency_name) is not None and statements.get(rate_name) is None:
            raise ValueError(
                "Yahoo Finance has no exchange rate for %s, so the figures for %s cannot be "
                "converted to US dollars." % (statements[currency_name], ticker)
            )
    if missing:
        raise ValueError("Yahoo Finance did not supply, for %s: %s." % (ticker, ", ".join(missing)))
    if statements["share_price"] <= 0 or statements["shares"] <= 0:
        raise ValueError("Yahoo Finance gave a share price or share count of zero or less for %s." % ticker)

    to_usd = valuation.convert_currency
    statement_rate = statements["usd_per_statement_unit"]
    current_debt = statements.get("current_debt")
    if current_debt is None:
        current_debt = 0

    package = {
        name: to_usd(statements[name], statement_rate)
        for name in YAHOO_MONEY_FIELDS
        if statements.get(name) is not None
    }
    if statements.get("interest_expense") is None:
        # No interest expense to divide by debt, so estimate the cost of debt from the market.
        package["interest_expense"] = None
        package["pre_tax_cost_of_debt"] = valuation.fallback_pre_tax_cost_of_debt(
            RISK_FREE_RATE, CREDIT_SPREAD
        )
        package["cost_of_debt_is_fallback"] = True
    package.update(
        company_name=statements["company_name"],
        ticker=ticker,
        debt=valuation.financial_debt(
            to_usd(current_debt, statement_rate), to_usd(statements["long_term_debt"], statement_rate)
        ),
        shares=statements["shares"],
        share_price=to_usd(statements["share_price"], statements["usd_per_price_unit"]),
        beta=statements["beta"],
        risk_free_rate=RISK_FREE_RATE,
        equity_risk_premium=EQUITY_RISK_PREMIUM,
        statement_currency=statements["statement_currency"],
        price_currency=statements["price_currency"],
        usd_per_statement_unit=statement_rate,
        usd_per_price_unit=statements["usd_per_price_unit"],
    )
    return package


# ---------------------------------------------------------------------------
# History: the last few years of the main figures
# ---------------------------------------------------------------------------

# The money figures in a history, which Yahoo gives in the currency the company reports in.
HISTORY_MONEY_FIELDS = ["revenue", "operating_income", "net_income", "free_cash_flow"]


def fetch_yahoo_history(ticker):
    """Ask Yahoo Finance for a company's yearly figures, as many years as it has (4 or 5),
    oldest first, in the company's own currency and in millions: revenue, operating income, net
    income, free cash flow as the company reports it (cash from operations minus capital
    spending) and the diluted average number of shares over the year. A year is kept only if
    Yahoo has its revenue; any other figure Yahoo does not have for a year is None.
    This is the only function that looks up a history on the internet.
    """
    import yfinance

    stock = yfinance.Ticker(ticker)
    income, cash_flow = stock.income_stmt, stock.cashflow

    def millions(frame, names, column):
        value = _statement_line(frame, names, column)
        return None if value is None else value / 1_000_000

    history = {"years": []}
    for field in HISTORY_MONEY_FIELDS + ["diluted_shares"]:
        history[field] = []
    for column, date in enumerate(income.columns):                  # the latest year first
        revenue = millions(income, ["Total Revenue"], column)
        if revenue is None:
            continue
        cash_column = list(cash_flow.columns).index(date) if date in cash_flow.columns else None
        history["years"].append(f"FY{date.year}" if hasattr(date, "year") else str(date))
        history["revenue"].append(revenue)
        history["operating_income"].append(millions(income, ["Operating Income"], column))
        history["net_income"].append(millions(income, ["Net Income"], column))
        history["free_cash_flow"].append(
            None if cash_column is None else millions(cash_flow, ["Free Cash Flow"], cash_column)
        )
        history["diluted_shares"].append(
            millions(income, ["Diluted Average Shares", "Basic Average Shares"], column)
        )
    for field in history:
        history[field].reverse()                                    # oldest first, as a reader expects
    return history


def history_in_dollars(history, usd_per_unit):
    """Turn a history's money figures into US dollars at the given exchange rate (the shares
    and the year labels are left alone). A figure that is None stays None.
    """
    converted = dict(history)
    for field in HISTORY_MONEY_FIELDS:
        converted[field] = [
            None if amount is None else valuation.convert_currency(amount, usd_per_unit)
            for amount in history[field]
        ]
    return converted


def get_history(ticker, usd_per_unit=1.0, fetch_history=fetch_yahoo_history):
    """Get a company's yearly history in US dollars, oldest year first. `usd_per_unit` is what one
    unit of the company's reporting currency is worth in dollars (1 for a dollar company).
    Stops with a plain error if Yahoo cannot be reached or has no yearly figures.
    `fetch_history` can be swapped, which is how the tests run without the internet.
    """
    try:
        history = fetch_history(ticker)
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise ValueError("Could not get the history from Yahoo Finance: %s" % error) from error
    if not history["years"]:
        raise ValueError("Yahoo Finance has no yearly figures for %s." % ticker)
    return history_in_dollars(history, usd_per_unit)


# ---------------------------------------------------------------------------
# Trailing twelve months: the latest four quarters, to compare with the peers
# ---------------------------------------------------------------------------

# The money figures in a trailing-twelve-month set, which Yahoo gives in the currency the company
# reports in.
TTM_MONEY_FIELDS = [
    "revenue", "operating_income", "net_income", "depreciation_and_amortisation", "debt", "cash_and_investments",
]


def fetch_yahoo_ttm(ticker):
    """Ask Yahoo Finance for a company's last twelve months: the sum of its latest four quarters of
    revenue, operating income, net income and depreciation and amortisation, and its debt and cash
    from the latest quarter's balance sheet, in the company's own currency and in millions.
    Quarters that have no revenue yet are skipped. Also returns the date the latest quarter ended. A flow figure Yahoo does not have for all four
    quarters is None. This is the only function that looks up the quarters on the internet.
    """
    import yfinance

    stock = yfinance.Ticker(ticker)
    income, cash_flow, balance = stock.quarterly_income_stmt, stock.quarterly_cashflow, stock.quarterly_balance_sheet
    # The latest four quarters that have revenue, newest first: a quarter that has just ended can be a
    # column in the table that has no figures yet, because the company has not reported it.
    dates = [
        date for position, date in enumerate(income.columns)
        if _statement_line(income, ["Total Revenue"], position) is not None
    ][:4]

    def four_quarters(frame, names):
        """The figure for each of the four quarters (None where Yahoo has none), matched by date."""
        values = []
        for date in dates:
            value = None
            if date in frame.columns:
                value = _statement_line(frame, names, list(frame.columns).index(date))
            values.append(None if value is None else value / 1_000_000)
        return values

    def latest_balance(names):
        value = _statement_line(balance, names, 0)
        return None if value is None else value / 1_000_000

    current_debt = latest_balance(["Current Debt"])
    long_term_debt = latest_balance(["Long Term Debt"])
    if long_term_debt is None and latest_balance(["Total Debt"]) is not None:
        # Yahoo leaves the line out when it is zero (First Solar: total debt less leases is its
        # current debt), but only believe that when the balance sheet is filled in.
        long_term_debt = 0.0
    return {
        "period_end": dates[0].strftime("%-d %b %Y") if dates and hasattr(dates[0], "strftime") else None,
        "revenue": valuation.trailing_total(four_quarters(income, ["Total Revenue"])),
        "operating_income": valuation.trailing_total(four_quarters(income, ["Operating Income"])),
        "net_income": valuation.trailing_total(four_quarters(income, ["Net Income"])),
        "depreciation_and_amortisation": valuation.trailing_total(
            four_quarters(cash_flow, ["Depreciation And Amortization", "Depreciation Amortization Depletion"])
        ),
        "debt": (
            None if long_term_debt is None
            else valuation.financial_debt(0 if current_debt is None else current_debt, long_term_debt)
        ),
        "cash_and_investments": latest_balance(["Cash Cash Equivalents And Short Term Investments"]),
    }


def ttm_in_dollars(ttm, usd_per_unit):
    """Turn a trailing-twelve-month set's money figures into US dollars at the given exchange rate
    (the date is left alone). A figure that is None stays None.
    """
    converted = dict(ttm)
    for field in TTM_MONEY_FIELDS:
        converted[field] = None if ttm[field] is None else valuation.convert_currency(ttm[field], usd_per_unit)
    return converted


def get_ttm(ticker, usd_per_unit=1.0, fetch_ttm=fetch_yahoo_ttm):
    """Get a company's last twelve months in US dollars. `usd_per_unit` is what one unit of the
    company's reporting currency is worth in dollars (1 for a dollar company). Stops with a plain
    error if Yahoo cannot be reached, or does not have four quarters of revenue, operating income
    and net income, or the latest debt and cash, which the multiples need. D&A may be missing: the
    EV/EBITDA is then left out. `fetch_ttm` can be swapped, which is how the tests run without the
    internet.
    """
    try:
        ttm = fetch_ttm(ticker)
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise ValueError("Could not get the last twelve months from Yahoo Finance: %s" % error) from error
    needed = ["revenue", "operating_income", "net_income", "debt", "cash_and_investments"]
    missing = [name for name in needed if ttm[name] is None]
    if missing:
        raise ValueError(
            "Yahoo Finance does not have four quarters of figures for %s (missing: %s)." % (ticker, ", ".join(missing))
        )
    return ttm_in_dollars(ttm, usd_per_unit)


# ---------------------------------------------------------------------------
# Peers: suggested from Yahoo's industry list, with their multiples
# ---------------------------------------------------------------------------

def fetch_peer_candidates(ticker, how_many):
    """Ask Yahoo Finance which companies are in the same industry as this one, and return the
    tickers of the first how_many (Yahoo lists the most important first), leaving out the
    company itself. Returns an empty list if Yahoo does not know the company's industry.
    This is the only function that looks up an industry on the internet.
    """
    import yfinance

    industry_key = yfinance.Ticker(ticker).info.get("industryKey")
    if not industry_key:
        return []
    top_companies = yfinance.Industry(industry_key).top_companies
    if top_companies is None:
        return []
    return [symbol for symbol in top_companies.index if symbol != ticker][:how_many]


def fetch_sector_candidates(ticker, how_many):
    """Ask Yahoo Finance which companies are in the same sector as this one (a wider group than its
    industry: technology, not software), and return the tickers of the first how_many (Yahoo lists
    the most important first), leaving out the company itself. Returns an empty list if Yahoo does
    not know the company's sector. This is the only function that looks up a sector on the internet.
    """
    import yfinance

    sector_key = yfinance.Ticker(ticker).info.get("sectorKey")
    if not sector_key:
        return []
    top_companies = yfinance.Sector(sector_key).top_companies
    if top_companies is None:
        return []
    return [symbol for symbol in top_companies.index if symbol != ticker][:how_many]


def fetch_peer_quote(ticker):
    """Ask Yahoo Finance for one peer's market value (in $ millions), the currency it trades in
    its three multiples (EV/Sales, EV/EBITDA and P/E), its operating margin and its revenue growth
    (the latest quarter against a year earlier), all as Yahoo gives them. A figure Yahoo does not
    have comes back as None. This is the only function that looks up a peer on
    the internet.
    """
    import yfinance

    info = yfinance.Ticker(ticker).info
    market_cap = info.get("marketCap")
    return {
        "ticker": ticker,
        "market_cap": None if market_cap is None else market_cap / 1_000_000,
        "currency": info.get("currency"),
        "ev_sales": info.get("enterpriseToRevenue"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "pe": info.get("trailingPE"),
        "operating_margin": info.get("operatingMargins"),
        "revenue_growth": info.get("revenueGrowth"),
    }


def peer_figures(quotes):
    """Lay peers' quotes out the way a data package holds peers: their tickers, and one list
    for each multiple and for the operating margin, in the same order. A figure Yahoo did not
    have stays None.
    """
    return {
        "peer_tickers": [quote["ticker"] for quote in quotes],
        "peer_ev_sales": [quote["ev_sales"] for quote in quotes],
        "peer_ev_ebitda": [quote["ev_ebitda"] for quote in quotes],
        "peer_pe": [quote["pe"] for quote in quotes],
        "peer_operating_margin": [quote["operating_margin"] for quote in quotes],
    }


def peer_multiples(tickers, fetch_quote=fetch_peer_quote):
    """Get the multiples of peers the reader chose, in the order given. A ticker Yahoo knows
    nothing about comes back with every multiple None, so it is simply left out of the medians.
    `fetch_quote` can be swapped, which is how the tests run without the internet.
    """
    try:
        return peer_figures([fetch_quote(ticker) for ticker in tickers])
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise ValueError("Could not get peer figures from Yahoo Finance: %s" % error) from error


def read_quotes(symbols, fetch_quote):
    """Look up each peer, skipping one Yahoo cannot read. Stops with a plain error if there were
    candidates and none could be read, which means Yahoo cannot be reached.
    """
    quotes = []
    for symbol in symbols:
        try:
            quotes.append(fetch_quote(symbol))
        except Exception:           # one unreadable peer should not hide the others
            continue
    if symbols and not quotes:
        raise ValueError(
            "Could not get peers from Yahoo Finance: none of the %d candidates could be read." % len(symbols)
        )
    return quotes


def suggest_peers(
    ticker,
    company_market_value,
    candidates_to_check,
    biggest_size_gap,
    how_many,
    sector_candidates_to_check,
    minimum_industry_peers,
    fetch_candidates=fetch_peer_candidates,
    fetch_sector=fetch_sector_candidates,
    fetch_quote=fetch_peer_quote,
):
    """Suggest peers for a company: look at the first candidates_to_check companies in its Yahoo
    industry, keep those that trade in US dollars and are within biggest_size_gap times of the
    company's market value ($ millions), and return the how_many that look most like it, meaning
    the closest operating margin and revenue growth (see valuation.closest_peers; if the company's
    own margin or growth is unknown they are ranked by size), with their multiples (see peer_figures).

    If the industry gives fewer than minimum_industry_peers suitable peers (Apple, Microsoft), the
    list is topped up from the first sector_candidates_to_check companies in the company's wider
    sector, chosen the same way. The answer also has "peer_source": "industry", "sector" (some or
    all came from the wider sector, so the reader should check them), or None when nothing was found.
    Returns empty lists when nothing suitable is found.

    One peer Yahoo cannot look up is skipped. Stops with a plain error if Yahoo cannot be reached at
    all; a sector list that cannot be had only means no top-up. The fetch functions can be swapped,
    which is how the tests run without the internet.
    """
    try:
        symbols = fetch_candidates(ticker, candidates_to_check)
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise ValueError("Could not get peers from Yahoo Finance: %s" % error) from error
    quotes = read_quotes(symbols, fetch_quote)

    try:
        own = fetch_quote(ticker)
        own_margin, own_growth = own["operating_margin"], own["revenue_growth"]
    except Exception:               # without its own profile the ranking falls back to size
        own_margin = own_growth = None

    def best(candidate_quotes, limit):
        in_dollars = [quote for quote in candidate_quotes if quote["currency"] == "USD"]
        return valuation.closest_peers(
            company_market_value, in_dollars, biggest_size_gap, limit, own_margin, own_growth
        )

    chosen, source = best(quotes, how_many), "industry"
    if len(chosen) < minimum_industry_peers:
        try:
            sector_symbols = [
                symbol for symbol in fetch_sector(ticker, sector_candidates_to_check) if symbol not in symbols
            ]
            extra = best(read_quotes(sector_symbols, fetch_quote), how_many - len(chosen))
        except Exception:           # no sector list, or none could be read: keep what the industry gave
            extra = []
        if extra:
            chosen, source = chosen + extra, "sector"
    figures = peer_figures(chosen)
    figures["peer_source"] = source if chosen else None
    return figures


# ---------------------------------------------------------------------------
# Choosing a source and fetching
# ---------------------------------------------------------------------------

# To add a new source later, write a function that takes a ticker and returns a package,
# then add it here under a name. Nothing else needs to change.
SOURCES = {
    "snapshot": snapshot_source,
    "live": live_source,
    "yahoo": yahoo_source,
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
