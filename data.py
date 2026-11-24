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
import os
import time

import valuation


class SourceUnavailable(ValueError):
    """A data source is not answering (Yahoo limiting the server, a network failure, a daily limit used
    up), as opposed to a real problem with the company asked about (an unknown ticker, a loss with no
    tax rate). Only this kind of error makes the page try its backup source; it is a ValueError, so
    code that expects ValueError still works.
    """


class UnknownCompany(ValueError):
    """A provider answered, and it has nothing on this company (an unknown ticker, or a company its free
    plan does not cover). This is a real answer about the company, not a sign that the provider is down,
    so it is passed on as it is and never makes the page try another source.
    """


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
    "peer_tickers": "Tickers of the peer companies, in the same order as the lists below",
    "peer_ev_sales": "Each peer's EV/Sales multiple",
    "peer_ev_ebitda": "Each peer's EV/EBITDA multiple",
    "peer_pe": "Each peer's P/E multiple",
    "peer_ps": "Each peer's P/S multiple (market value over revenue)",
    "peer_forward_pe": "Each peer's forward P/E (share price over analysts' estimate of next year's earnings per share)",
    "forward_eps": "Analysts' estimate of the company's earnings per share for the next fiscal year, $ (adjusted: leaves out things like share-based pay)",
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
    # P/S: Yahoo Finance, Price/Sales (ttm), 20 Nov 2026 (the three multiples above are older; workbook:
    # Multiples G8:G11). Same order.
    "peer_ps": [6.56, 3.30, 3.38, 8.06],
    # Forward P/E: Yahoo Finance, analyst estimates for the next fiscal year, 20 Nov 2026 (workbook:
    # Multiples D70:D73). Same order.
    "peer_forward_pe": [17.22, 10.05, 11.28, 21.20],
    # Adobe's own next-year EPS, analysts' adjusted figure (GAAP EPS is far lower), Yahoo Finance,
    # 20 Nov 2026 (workbook: Multiples C77).
    "forward_eps": 27.41,
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

# When Yahoo is limiting the app's server it answers with an empty quote (no name, price or beta) while
# the statements still arrive. The code then asks once more, after this many seconds, before telling the
# reader. Chosen on 20 Nov 2026, after Yahoo refused the live app twice in three days.
YAHOO_RETRY_PAUSE_SECONDS = 2

YAHOO_BUSY_MESSAGE = (
    "Yahoo Finance isn't answering the app right now. It sometimes limits shared servers, so try again in "
    "a few minutes. Adobe still works from a frozen snapshot."
)


def _pause(seconds):
    """Wait a moment. A function of its own so the tests can skip the waiting without touching the
    clock the rest of the program uses.
    """
    time.sleep(seconds)


# After Yahoo has said it is busy, the page skips Yahoo for this many seconds and goes straight to its
# backup, instead of waiting and retrying on every click. Chosen with Haavard on 20 Nov 2026 (5 minutes), raised to
# 15 minutes on 24 Nov 2026: asking again too soon tends to make Yahoo's block last longer.
YAHOO_COOLDOWN_SECONDS = 15 * 60
_yahoo_busy_until = 0.0         # when the cool-down ends; the whole server shares it, because it is one program


def _yahoo_cooling_down():
    """Say whether Yahoo said it was busy a moment ago, so it should be skipped for now."""
    return time.time() < _yahoo_busy_until


def _start_yahoo_cooldown():
    """Note that Yahoo is busy, so it is skipped for YAHOO_COOLDOWN_SECONDS."""
    global _yahoo_busy_until
    _yahoo_busy_until = time.time() + YAHOO_COOLDOWN_SECONDS


def _quote_is_empty(info):
    """Say whether Yahoo's quote has nothing in it: none of a name, a price or a share count."""
    return not any(
        info.get(key) for key in ("longName", "shortName", "currentPrice", "regularMarketPrice", "sharesOutstanding")
    )


def _fetch_info(ticker):
    """Ask Yahoo Finance for a stock's quote, and if it comes back empty (Yahoo limiting the server),
    wait a moment and ask once more with a fresh request, because the first one keeps its empty answer.
    """
    import yfinance

    info = yfinance.Ticker(ticker).info
    if _quote_is_empty(info):
        _pause(YAHOO_RETRY_PAUSE_SECONDS)
        info = yfinance.Ticker(ticker).info
    return info


def fetch_yahoo_quote(ticker):
    """Ask Yahoo Finance for a stock's current share price and beta, asking once more if the first
    answer is empty.

    Returns a dictionary with "share_price" and "beta"; a figure Yahoo does not have comes
    back as None. This is the only function that touches the internet for a live quote.
    """
    info = _fetch_info(ticker)
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
        raise SourceUnavailable("Could not get live figures from Yahoo Finance: %s" % error) from error

    price = quote.get("share_price")
    if price is None and quote.get("beta") is None:
        _start_yahoo_cooldown()
        raise SourceUnavailable(YAHOO_BUSY_MESSAGE)        # nothing at all: Yahoo is not answering
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
    income, cash_flow, balance = stock.income_stmt, stock.cashflow, stock.balance_sheet
    info = _fetch_info(ticker)

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
        "forward_eps": info.get("forwardEps"),          # in the price currency, like the share price
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


# The figures that come from Yahoo's quote and exchange rates, not from the statements. When all of
# them are missing but the statements are there, Yahoo is limiting the server (see YAHOO_BUSY_MESSAGE).
YAHOO_QUOTE_FIELDS = [
    "company_name", "statement_currency", "price_currency", "usd_per_statement_unit", "usd_per_price_unit",
    "shares", "share_price", "beta",
]


# The company's money figures, which Yahoo gives in the currency the company reports in.
YAHOO_MONEY_FIELDS = [
    "revenue", "prior_year_revenue", "ebit", "net_income", "income_tax", "income_before_tax",
    "interest_expense", "depreciation_and_amortisation", "capex", "cash_from_working_capital",
    "cash_and_investments", "stockholders_equity",
]


def yahoo_source(ticker, fetch_statements=fetch_yahoo_statements):
    """Return a company's figures from Yahoo Finance's financial statements (see statements_source).
    When Yahoo says it is busy, it is skipped for the next few minutes (YAHOO_COOLDOWN_SECONDS).
    """
    try:
        return statements_source(ticker, fetch_statements, "Yahoo Finance", YAHOO_BUSY_MESSAGE)
    except SourceUnavailable as error:
        if str(error) == YAHOO_BUSY_MESSAGE:
            _start_yahoo_cooldown()
        raise


def statements_source(ticker, fetch_statements, provider, busy_message):
    """Return a company's figures from a provider's financial statements, for any company the
    provider covers, all in US dollars.

    A company that reports or trades in another currency (kroner, pence, ...) is converted at
    the exchange rate Yahoo gives today: the statement figures at the statement currency's
    rate, and the share price at the price currency's rate. The risk-free rate and equity risk
    premium are the market-wide figures typed in above. The package has no cost of debt from
    the debt notes and no peer multiples, because Yahoo cannot supply them. When Yahoo has no
    interest expense either (Apple), the package carries a fallback cost of debt, the risk-free
    rate plus a credit spread, and says so. Stops with a plain error naming any other figure
    the provider did not supply, or a SourceUnavailable error if the provider cannot be reached or
    (when busy_message is given) sends the statements without a quote, which means it is limiting us.
    `fetch_statements` can be swapped, which is how the tests run without the internet.
    """
    try:
        statements = fetch_statements(ticker)
    except (SourceUnavailable, UnknownCompany):
        raise
    except Exception as error:      # a provider can fail in many ways; the reader needs one clear message
        raise SourceUnavailable("Could not get figures from %s: %s" % (provider, error)) from error

    missing = [name for name in YAHOO_REQUIRED if statements.get(name) is None]
    if len(missing) == len(YAHOO_REQUIRED):
        raise ValueError(
            "%s has no figures for %s. Check that the ticker is right; "
            "US-listed companies work best." % (provider, ticker)
        )
    if busy_message and all(statements.get(name) is None for name in YAHOO_QUOTE_FIELDS):
        raise SourceUnavailable(busy_message)        # the statements came but no quote at all: the provider is limiting us
    for currency_name, rate_name in (
        ("statement_currency", "usd_per_statement_unit"),
        ("price_currency", "usd_per_price_unit"),
    ):
        if statements.get(currency_name) is not None and statements.get(rate_name) is None:
            raise ValueError(
                "%s has no exchange rate for %s, so the figures for %s cannot be "
                "converted to US dollars." % (provider, statements[currency_name], ticker)
            )
    if missing:
        raise ValueError("%s did not supply, for %s: %s." % (provider, ticker, ", ".join(missing)))
    if statements["share_price"] <= 0 or statements["shares"] <= 0:
        raise ValueError("%s gave a share price or share count of zero or less for %s." % (provider, ticker))

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
    if statements.get("forward_eps") is not None:
        # Yahoo gives it in the currency the share trades in, so it converts like the share price.
        package["forward_eps"] = to_usd(statements["forward_eps"], statements["usd_per_price_unit"])
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
    except SourceUnavailable:
        raise
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise SourceUnavailable("Could not get the history from Yahoo Finance: %s" % error) from error
    if not history["years"]:
        raise ValueError("Yahoo Finance has no yearly figures for %s." % ticker)
    return history_in_dollars(history, usd_per_unit)


# ---------------------------------------------------------------------------
# News and management: recent headlines and the top officers, from Yahoo (roadmap #11, first part)
# ---------------------------------------------------------------------------

def safe_link(address):
    """Return a web address only if it is a plain https link, otherwise None. Headlines come from
    outside, so a link that is not https (or is missing) is shown as plain text, never as a link.
    """
    if isinstance(address, str) and address.startswith("https://") and " " not in address:
        return address
    return None


def tidy_text(text):
    """Squeeze the stray double spaces Yahoo leaves inside names ("Mr. Shantanu  Narayen") and trim the ends.
    Anything that is not text comes back as an empty string.
    """
    return " ".join(text.split()) if isinstance(text, str) else ""


def fetch_yahoo_news(ticker):
    """Ask Yahoo Finance for a company's recent headlines, newest first. Each is a dictionary with its
    "title", "publisher", "published" (the date, such as 2026-11-20, or None) and "url" (an https link, or
    None). An item without a title is dropped. This and fetch_yahoo_officers are the only functions in this
    part that touch the internet.
    """
    import yfinance

    headlines = []
    for item in yfinance.Ticker(ticker).news or []:
        content = item.get("content") or {}
        title = tidy_text(content.get("title"))
        if not title:
            continue
        link = (content.get("canonicalUrl") or {}).get("url") or (content.get("clickThroughUrl") or {}).get("url")
        published = content.get("pubDate")
        headlines.append({
            "title": title,
            "publisher": tidy_text((content.get("provider") or {}).get("displayName")) or None,
            "published": published[:10] if isinstance(published, str) and len(published) >= 10 else None,
            "url": safe_link(link),
        })
    return headlines


def fetch_yahoo_officers(ticker):
    """Ask Yahoo Finance for a company's top officers, in Yahoo's order (chairman, CEO and CFO first).
    Each is a dictionary with a "name" and a "title" (None if Yahoo has none). An officer without a name
    is dropped.
    """
    officers = []
    for officer in _fetch_info(ticker).get("companyOfficers") or []:
        name = tidy_text(officer.get("name"))
        if name:
            officers.append({"name": name, "title": tidy_text(officer.get("title")) or None})
    return officers


def get_company_context(ticker, fetch_news=fetch_yahoo_news, fetch_officers=fetch_yahoo_officers):
    """Get a company's recent headlines and top officers from Yahoo, as {"news": [...], "officers": [...]}.
    A part Yahoo could not give (it failed, as opposed to having none) comes back as None, so the page can
    say which part is missing and show the other. Stops with a SourceUnavailable error when Yahoo said it was
    busy a moment ago (it is then left alone) or when neither part could be had. `fetch_news` and
    `fetch_officers` can be swapped, which is how the tests run without the internet.
    """
    if _yahoo_cooling_down():
        raise SourceUnavailable(YAHOO_BUSY_MESSAGE)

    def attempt(fetch):
        try:
            return fetch(ticker)
        except Exception:       # Yahoo can fail in many ways; this part is optional, so it is just left out
            return None

    context = {"news": attempt(fetch_news), "officers": attempt(fetch_officers)}
    if context["news"] is None and context["officers"] is None:
        raise SourceUnavailable("Could not get the news or the officers from Yahoo Finance.")
    return context


# ---------------------------------------------------------------------------
# The macro backdrop: three US interest-rate and inflation numbers from FRED (the Federal Reserve Bank of St. Louis)
# ---------------------------------------------------------------------------

FRED_NAME = "FRED"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_TIMEOUT_SECONDS = 10
# How many of the newest readings are asked for. FRED marks a day with no reading (a bank holiday) with a ".", so
# a few are asked for and the newest real one is used.
FRED_READINGS_ASKED = 10

# The three numbers shown: (key, label, FRED's series name, FRED's "units" setting, whether it is one reading a month).
# DGS10 is the 10-year US Treasury yield and DFF the Fed funds rate, both in percent a day. CPIAUCSL is the consumer price
# index, which FRED turns into "percent change from a year ago" when asked for units "pc1": US inflation over 12 months.
MACRO_SERIES = (
    ("treasury_yield", "10-year Treasury yield", "DGS10", None, False),
    ("fed_funds", "Fed funds rate", "DFF", None, False),
    ("inflation", "US inflation, last 12 months", "CPIAUCSL", "pc1", True),
)


def fred_api_key():
    """Return the FRED key from the environment (the page puts it there from Streamlit's private settings), or None if
    there is none. The key is never written anywhere.
    """
    return os.environ.get("FRED_API_KEY") or None


def fetch_fred_latest(series_id, units=None):
    """Ask FRED for the newest real reading of one series and return {"value": a percent, "date": "YYYY-MM-DD"}. Stops
    with a SourceUnavailable error, whose message never holds the key, if there is no key, FRED cannot be reached or
    refuses the key, or it has no recent reading. This is the only function that talks to FRED.
    """
    key = fred_api_key()
    if key is None:
        raise SourceUnavailable("No FRED key is set.")
    import requests         # already installed as part of yfinance; it carries the security certificates

    parameters = {
        "series_id": series_id, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": FRED_READINGS_ASKED,
    }
    if units:
        parameters["units"] = units
    try:
        response = requests.get(FRED_URL, params=parameters, timeout=FRED_TIMEOUT_SECONDS)
        status = response.status_code
        readings = response.json().get("observations", []) if status == 200 else []
    except Exception as error:      # the address, which holds the key, is never put in a message
        raise SourceUnavailable("Could not reach %s: %s" % (FRED_NAME, type(error).__name__)) from None
    if status in (400, 401, 403):
        raise SourceUnavailable("%s did not accept the key." % FRED_NAME)
    if status == 429:
        raise SourceUnavailable("%s says too many requests have been made; try again later." % FRED_NAME)
    if status != 200:
        raise SourceUnavailable("%s answered with an error (HTTP %d)." % (FRED_NAME, status))
    for reading in readings:
        try:
            return {"value": float(reading["value"]), "date": reading["date"]}
        except (KeyError, TypeError, ValueError):       # a "." for a day with no reading: try the one before
            continue
    raise SourceUnavailable("%s has no recent reading for %s." % (FRED_NAME, series_id))


def get_macro_backdrop(fetch=fetch_fred_latest):
    """Get the three macro numbers as a list with one {"key", "label", "value", "date", "monthly"} per number, in the order
    of MACRO_SERIES. A number FRED could not give comes back with a value and date of None, so the page can show the others.
    Stops with a SourceUnavailable error if none could be had. `fetch` can be swapped, which is how the tests run
    without the internet.
    """
    rows, first_problem = [], None
    for key, label, series_id, units, monthly in MACRO_SERIES:
        try:
            latest = fetch(series_id, units)
        except Exception as error:      # one number failing must not hide the others
            latest = None
            first_problem = first_problem or error
        rows.append({
            "key": key, "label": label, "monthly": monthly,
            "value": latest["value"] if latest else None, "date": latest["date"] if latest else None,
        })
    if all(row["value"] is None for row in rows):
        raise SourceUnavailable(
            str(first_problem) if isinstance(first_problem, SourceUnavailable) else "Could not get the macro numbers from FRED."
        )
    return rows


def risk_free_from_macro(rows):
    """Pick today's 10-year US Treasury yield out of the macro numbers (see get_macro_backdrop) as a decimal rate, ready to
    use as the risk-free rate: {"rate": 0.0412, "date": "2026-11-19"}. FRED gives percent, so this only moves the decimal point.
    Stops with a SourceUnavailable error if the yield is not among them.
    """
    for row in rows:
        if row["key"] == "treasury_yield" and row["value"] is not None:
            return {"rate": row["value"] / 100, "date": row["date"]}
    raise SourceUnavailable("FRED has no 10-year Treasury yield right now.")


# ---------------------------------------------------------------------------
# What other analysts say: Yahoo Finance's consensus rating and price targets (opinions, not this app's advice)
# ---------------------------------------------------------------------------

# Yahoo's own words for the consensus, written the way the page shows them.
ANALYST_RATING_NAMES = {
    "strong_buy": "Strong buy", "buy": "Buy", "hold": "Hold", "underperform": "Underperform", "sell": "Sell",
}

# The columns of Yahoo's table of how many analysts give each rating, and the key each is kept under.
ANALYST_COUNT_COLUMNS = {
    "strongBuy": "strong_buy", "buy": "buy", "hold": "hold", "sell": "sell", "strongSell": "strong_sell",
}


def fetch_yahoo_analysts(ticker):
    """Ask Yahoo Finance what analysts say about a share. Gives {"info": ..., "targets": ..., "counts": ...}: the
    consensus rating, rating mean and number of analysts from the quote, the price targets (low, mean, median, high) in
    the currency the share trades in, and the table of how many analysts give each rating. A part Yahoo could not give
    is an Exception stored instead of the value, so the caller can tell "no coverage" (empty) from "could not ask"
    (an error). This is the only function in this part that touches the internet.
    """
    import yfinance

    stock = yfinance.Ticker(ticker)
    parts = {}
    for name, ask in (
        ("info", lambda: stock.info),
        ("targets", lambda: stock.analyst_price_targets),
        ("counts", lambda: stock.recommendations_summary),
    ):
        try:
            parts[name] = ask()
        except Exception as error:      # kept, not raised: one missing part must not hide the others
            parts[name] = error
    return parts


def get_analyst_view(ticker, usd_per_unit=1.0, fetch_analysts=fetch_yahoo_analysts):
    """Get the analyst consensus for a share as {"rating", "rating_mean", "analysts", "counts", "targets"}: the rating's
    name (None when Yahoo has no consensus), Yahoo's rating mean (1 is strong buy, 5 is sell), how many analysts, how many give
    each rating (None without a table) and the price targets in US dollars (None unless Yahoo gives a low, a mean and a
    high). `usd_per_unit` converts the targets from the currency the share trades in, the rate the page's share price
    was converted with. A company with no coverage gives all None, which is an answer, not an error. Leaves Yahoo alone
    while it is cooling down, and stops with a plain error if Yahoo could not be asked at all. `fetch_analysts` can be
    swapped, which is how the tests run without the internet.
    """
    if _yahoo_cooling_down():
        raise SourceUnavailable(YAHOO_BUSY_MESSAGE)
    try:
        parts = fetch_analysts(ticker)
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise SourceUnavailable("Could not get the analysts' view from Yahoo Finance: %s" % error) from error
    if all(isinstance(part, Exception) for part in parts.values()):
        raise SourceUnavailable("Could not get the analysts' view from Yahoo Finance.")

    info = parts["info"] if isinstance(parts["info"], dict) else {}
    analysts = info.get("numberOfAnalystOpinions")
    view = {
        "rating": ANALYST_RATING_NAMES.get(info.get("recommendationKey")),
        "rating_mean": info.get("recommendationMean"),
        "analysts": int(analysts) if isinstance(analysts, (int, float)) and analysts == analysts and analysts > 0 else None,
        "counts": None,
        "targets": None,
    }
    table = parts["counts"]
    if hasattr(table, "iloc") and len(table):
        rows = table[table["period"] == "0m"] if "period" in table else table
        row = (rows if len(rows) else table).iloc[0]
        counts = {key: int(row[column]) for column, key in ANALYST_COUNT_COLUMNS.items() if column in row}
        if len(counts) == len(ANALYST_COUNT_COLUMNS) and sum(counts.values()) > 0:
            view["counts"] = counts
    targets = parts["targets"]
    if isinstance(targets, dict) and all(isinstance(targets.get(key), (int, float)) and targets[key] > 0 for key in ("low", "mean", "high")):
        view["targets"] = {
            key: valuation.convert_currency(targets[key], usd_per_unit)
            for key in ("low", "mean", "median", "high")
            if isinstance(targets.get(key), (int, float)) and targets[key] > 0
        }
    return view


def has_analyst_coverage(view):
    """Say whether Yahoo has anything from analysts for a share: a consensus rating, price targets or a table of ratings."""
    return any(view[key] for key in ("rating", "targets", "counts"))


# ---------------------------------------------------------------------------
# Searching for a company by name (Yahoo Finance's free search), so a reader can find a ticker
# ---------------------------------------------------------------------------

def fetch_yahoo_search(query, how_many):
    """Ask Yahoo Finance's search what matches a name or part of one. Gives Yahoo's own list, most relevant first: each
    a dictionary with a "symbol", names, an exchange and a "quoteType" (a share, a fund, a future and so on). This is the
    only function in this part that touches the internet.
    """
    import yfinance

    return yfinance.Search(query, max_results=how_many, news_count=0).quotes


def search_companies(query, how_many, minimum_characters, matches_asked, fetch_matches=fetch_yahoo_search):
    """Find the companies that match a name (or part of one) the reader typed, as a list of {"ticker", "name",
    "exchange"}, most relevant first, at most `how_many`. Yahoo is asked for `matches_asked` (more than are shown,
    because many are dropped): only company shares are kept, futures, funds and the like are dropped, and a ticker
    appears once. Fewer than `minimum_characters` typed gives an empty list without asking anyone. Leaves Yahoo alone
    while it is cooling down, and stops with a plain error if Yahoo cannot be reached. `fetch_matches` can be swapped,
    which is how the tests run without the internet.
    """
    query = tidy_text(query)
    if len(query) < minimum_characters:
        return []
    if _yahoo_cooling_down():
        raise SourceUnavailable(YAHOO_BUSY_MESSAGE)
    try:
        found = fetch_matches(query, matches_asked)
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise SourceUnavailable("Could not search Yahoo Finance: %s" % error) from error
    matches, seen = [], set()
    for item in found or []:
        ticker = tidy_text(item.get("symbol"))
        if item.get("quoteType") != "EQUITY" or not ticker or ticker in seen:
            continue
        seen.add(ticker)
        matches.append({
            "ticker": ticker,
            "name": tidy_text(item.get("shortname")) or tidy_text(item.get("longname")) or ticker,
            "exchange": tidy_text(item.get("exchDisp") or item.get("exchange")) or None,
        })
        if len(matches) == how_many:
            break
    return matches


# ---------------------------------------------------------------------------
# The share price over the last twelve months (for the sparkline in the page header)
# ---------------------------------------------------------------------------

def fetch_yahoo_price_history(ticker):
    """Ask Yahoo Finance for a share's daily closing prices over the last year, oldest first, as a list of
    {"date": "2026-11-20", "close": 217.71} in the currency the share trades in. A day without a price is
    left out. This is the only function in this part that touches the internet.
    """
    import yfinance

    closes = yfinance.Ticker(ticker).history(period="1y")["Close"].dropna()
    return [{"date": day.strftime("%Y-%m-%d"), "close": float(close)} for day, close in closes.items()]


def get_price_history(ticker, usd_per_unit=1.0, fetch_prices=fetch_yahoo_price_history):
    """Get a share's closing prices over the last year in US dollars, oldest first. `usd_per_unit` is what one
    unit of the currency the share trades in is worth in dollars (1 for a dollar share), the same rate the page's
    share price was converted with. Leaves Yahoo alone while it is cooling down, and stops with a plain error if
    Yahoo cannot be reached or has no prices. `fetch_prices` can be swapped, which is how the tests run without
    the internet.
    """
    if _yahoo_cooling_down():
        raise SourceUnavailable(YAHOO_BUSY_MESSAGE)
    try:
        prices = fetch_prices(ticker)
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise SourceUnavailable("Could not get the price history from Yahoo Finance: %s" % error) from error
    if not prices:
        raise ValueError("Yahoo Finance has no price history for %s." % ticker)
    return [{"date": price["date"], "close": valuation.convert_currency(price["close"], usd_per_unit)} for price in prices]


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
    except SourceUnavailable:
        raise
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise SourceUnavailable("Could not get the last twelve months from Yahoo Finance: %s" % error) from error
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
    its five multiples (EV/Sales, EV/EBITDA, P/E, P/S and forward P/E), its operating margin and its revenue growth
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
        "ps": info.get("priceToSalesTrailing12Months"),
        "forward_pe": info.get("forwardPE"),
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
        "peer_ps": [quote["ps"] for quote in quotes],
        "peer_forward_pe": [quote["forward_pe"] for quote in quotes],
        "peer_operating_margin": [quote["operating_margin"] for quote in quotes],
    }


def peer_multiples(tickers, fetch_quote=fetch_peer_quote):
    """Get the multiples of peers the reader chose, in the order given. A ticker Yahoo knows
    nothing about comes back with every multiple None, so it is simply left out of the medians.
    `fetch_quote` can be swapped, which is how the tests run without the internet.
    """
    try:
        return peer_figures([fetch_quote(ticker) for ticker in tickers])
    except SourceUnavailable:
        raise
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise SourceUnavailable("Could not get peer figures from Yahoo Finance: %s" % error) from error


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
        raise SourceUnavailable(
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
    except SourceUnavailable:
        raise
    except Exception as error:      # Yahoo can fail in many ways; the reader needs one clear message
        raise SourceUnavailable("Could not get peers from Yahoo Finance: %s" % error) from error
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
# Source 4: Financial Modeling Prep (FMP), a keyed backup for when Yahoo is limiting the server
# ---------------------------------------------------------------------------

FMP_NAME = "Financial Modeling Prep"
FMP_BASE_URL = "https://financialmodelingprep.com/stable/"
FMP_TIMEOUT_SECONDS = 20
FMP_ROWS = 5                 # the free plan returns at most 5 rows (years or quarters) per request
# The free plan allows 250 requests a day, so an answer is remembered in the running program for this
# long: the same statements serve the company, its history and its peers. Chosen with Haavard on 20 Nov 2026.
FMP_CACHE_SECONDS = 6 * 60 * 60
FMP_LIMIT_MESSAGE = (
    "Financial Modeling Prep's free daily limit of 250 requests has been used up; it starts again within a day."
)
_fmp_cache = {}              # (path, parameters) -> (when it was asked, the answer)


def fmp_api_key():
    """Return the Financial Modeling Prep key from the environment (the page puts it there from
    Streamlit's private settings), or None if there is none. The key is never written anywhere.
    """
    return os.environ.get("FMP_API_KEY") or None


def fmp_available():
    """Say whether a Financial Modeling Prep key is set, so the backup can be tried at all."""
    return fmp_api_key() is not None


def _fmp_get(path, **parameters):
    """Ask Financial Modeling Prep for one thing and return its answer (a list of rows). The answer
    is remembered for FMP_CACHE_SECONDS so the free daily limit is not wasted on repeats. Stops with a
    SourceUnavailable error if it cannot be reached, the key is refused or the daily limit is used up,
    and with an UnknownCompany error if the free plan does not cover the company (non-US companies).
    This is the only function that talks to Financial Modeling Prep.
    """
    key = fmp_api_key()
    if key is None:
        raise SourceUnavailable("No Financial Modeling Prep key is set.")
    cache_key = (path, tuple(sorted(parameters.items())))
    cached = _fmp_cache.get(cache_key)
    if cached is not None and time.time() - cached[0] < FMP_CACHE_SECONDS:
        return cached[1]
    import requests         # already installed as part of yfinance; it carries the security certificates

    try:
        response = requests.get(
            FMP_BASE_URL + path, params=dict(parameters, apikey=key), timeout=FMP_TIMEOUT_SECONDS
        )
    except Exception as error:      # the address, which holds the key, is never put in a message
        raise SourceUnavailable(
            "Could not reach %s: %s" % (FMP_NAME, type(error).__name__)
        ) from None
    if response.status_code == 429:
        raise SourceUnavailable(FMP_LIMIT_MESSAGE)
    if response.status_code in (401, 403):
        raise SourceUnavailable("%s did not accept the key." % FMP_NAME)
    if response.status_code == 402:
        raise UnknownCompany(
            "%s's free plan does not cover %s: it works for US-listed companies."
            % (FMP_NAME, parameters.get("symbol", path))
        )
    if response.status_code != 200:
        raise SourceUnavailable("%s answered with an error (HTTP %d)." % (FMP_NAME, response.status_code))
    answer = response.json()
    _fmp_cache[cache_key] = (time.time(), answer)
    return answer


def _fmp_rows(path, ticker, **parameters):
    """Ask for rows (years, quarters, one profile) and stop with a plain error if there are none,
    which is what Financial Modeling Prep sends for a ticker it does not know.
    """
    rows = _fmp_get(path, symbol=ticker, **parameters)
    if not isinstance(rows, list) or not rows:
        raise UnknownCompany(
            "%s has no figures for %s. Check that the ticker is right; US-listed companies work best."
            % (FMP_NAME, ticker)
        )
    return rows


def _fmp_millions(value):
    """Turn Financial Modeling Prep's dollars into millions, keeping a missing figure missing."""
    return None if value is None else value / 1_000_000


def fetch_fmp_statements(ticker):
    """Get a company's latest annual figures from Financial Modeling Prep, in the same shape as
    fetch_yahoo_statements: money in millions, capex and interest as positive amounts, shares worked
    out as market value over price (FMP has no share count). Its free plan covers US companies, so the
    currencies are US dollars, and a company reporting in another currency comes back without a rate.
    """
    profile = _fmp_rows("profile", ticker)[0]
    income = _fmp_rows("income-statement", ticker, limit=FMP_ROWS)
    balance = _fmp_rows("balance-sheet-statement", ticker, limit=FMP_ROWS)
    cash_flow = _fmp_rows("cash-flow-statement", ticker, limit=FMP_ROWS)
    latest_income, latest_balance, latest_cash = income[0], balance[0], cash_flow[0]
    price, market_cap = profile.get("price"), profile.get("marketCap")
    reported, traded = latest_income.get("reportedCurrency"), profile.get("currency")
    capex = latest_cash.get("capitalExpenditure")
    return {
        "company_name": profile.get("companyName"),
        "statement_currency": reported,
        "price_currency": traded,
        "usd_per_statement_unit": 1.0 if reported == "USD" else None,
        "usd_per_price_unit": 1.0 if traded == "USD" else None,
        "revenue": _fmp_millions(latest_income.get("revenue")),
        "prior_year_revenue": _fmp_millions(income[1].get("revenue")) if len(income) > 1 else None,
        "ebit": _fmp_millions(latest_income.get("operatingIncome")),
        "net_income": _fmp_millions(latest_income.get("netIncome")),
        "income_tax": _fmp_millions(latest_income.get("incomeTaxExpense")),
        "income_before_tax": _fmp_millions(latest_income.get("incomeBeforeTax")),
        "interest_expense": _fmp_millions(latest_income.get("interestExpense")),
        "depreciation_and_amortisation": _fmp_millions(latest_cash.get("depreciationAndAmortization")),
        "capex": None if capex is None else _fmp_millions(abs(capex)),
        "cash_from_working_capital": _fmp_millions(latest_cash.get("changeInWorkingCapital")),
        "long_term_debt": _fmp_millions(latest_balance.get("longTermDebt")),
        "current_debt": _fmp_millions(latest_balance.get("shortTermDebt")),
        "cash_and_investments": _fmp_millions(latest_balance.get("cashAndShortTermInvestments")),
        "stockholders_equity": _fmp_millions(latest_balance.get("totalStockholdersEquity")),
        "shares": (
            None if not price or not market_cap
            else valuation.shares_from_market_value(_fmp_millions(market_cap), price)
        ),
        "share_price": price,
        "beta": profile.get("beta"),
    }


def fmp_source(ticker, fetch_statements=fetch_fmp_statements):
    """Return a company's figures from Financial Modeling Prep, in the same package as the Yahoo
    source (see statements_source): all in US dollars, with the same cost-of-debt fallback.
    """
    return statements_source(ticker, fetch_statements, FMP_NAME, None)


def fetch_fmp_quote(ticker):
    """Get a stock's current share price and beta from Financial Modeling Prep, in the same shape as
    fetch_yahoo_quote.
    """
    profile = _fmp_rows("profile", ticker)[0]
    return {"share_price": profile.get("price"), "beta": profile.get("beta")}


def live_fmp_source(ticker, fetch_quote=fetch_fmp_quote):
    """Return Adobe's figures with today's share price and beta from Financial Modeling Prep, and
    everything else from the snapshot (the same as live_source, with the other provider).
    """
    package = snapshot_source(ticker)
    quote = fetch_quote(ticker)
    if not quote.get("share_price") or quote["share_price"] <= 0 or quote.get("beta") is None:
        raise SourceUnavailable("%s did not give a usable share price and beta for %s." % (FMP_NAME, ticker))
    package["share_price"], package["beta"] = quote["share_price"], quote["beta"]
    return package


def fetch_fmp_history(ticker):
    """Get a company's yearly history from Financial Modeling Prep (up to 5 years), in the same shape
    as fetch_yahoo_history: oldest first, millions, the diluted average share count, and free cash
    flow as the company reports it. The cash flow is matched to its year by date.
    """
    income = _fmp_rows("income-statement", ticker, limit=FMP_ROWS)
    cash_flow = {row.get("date"): row for row in _fmp_rows("cash-flow-statement", ticker, limit=FMP_ROWS)}
    history = {"years": []}
    for field in HISTORY_MONEY_FIELDS + ["diluted_shares"]:
        history[field] = []
    for row in income:                                              # the latest year first
        if row.get("revenue") is None:
            continue
        cash = cash_flow.get(row.get("date"), {})
        history["years"].append("FY%s" % row.get("fiscalYear", str(row.get("date", ""))[:4]))
        history["revenue"].append(_fmp_millions(row.get("revenue")))
        history["operating_income"].append(_fmp_millions(row.get("operatingIncome")))
        history["net_income"].append(_fmp_millions(row.get("netIncome")))
        history["free_cash_flow"].append(_fmp_millions(cash.get("freeCashFlow")))
        history["diluted_shares"].append(_fmp_millions(row.get("weightedAverageShsOutDil")))
    for field in history:
        history[field].reverse()                                    # oldest first, as a reader expects
    return history


def fetch_fmp_ttm(ticker):
    """Get a company's last twelve months from Financial Modeling Prep, in the same shape as
    fetch_yahoo_ttm: the sum of the latest four quarters of revenue, operating income, net income and
    D&A (matched by date), and debt and cash from the latest quarter's balance sheet.
    """
    income = _fmp_rows("income-statement", ticker, period="quarter", limit=FMP_ROWS)
    cash_flow = {row.get("date"): row for row in _fmp_rows("cash-flow-statement", ticker, period="quarter", limit=FMP_ROWS)}
    balance = _fmp_rows("balance-sheet-statement", ticker, period="quarter", limit=FMP_ROWS)[0]
    quarters = [row for row in income if row.get("revenue") is not None][:4]       # the latest four, newest first

    def four(name, rows_by_date=None):
        return [
            _fmp_millions((row if rows_by_date is None else rows_by_date.get(row.get("date"), {})).get(name))
            for row in quarters
        ]

    long_term_debt = _fmp_millions(balance.get("longTermDebt"))
    if long_term_debt is None and balance.get("totalDebt") is not None:
        long_term_debt = 0.0                                        # the line is left out when it is zero
    current_debt = _fmp_millions(balance.get("shortTermDebt"))
    return {
        "period_end": (
            valuation_date_label(quarters[0].get("date")) if quarters else None
        ),
        "revenue": valuation.trailing_total(four("revenue")),
        "operating_income": valuation.trailing_total(four("operatingIncome")),
        "net_income": valuation.trailing_total(four("netIncome")),
        "depreciation_and_amortisation": valuation.trailing_total(four("depreciationAndAmortization", cash_flow)),
        "debt": (
            None if long_term_debt is None
            else valuation.financial_debt(0 if current_debt is None else current_debt, long_term_debt)
        ),
        "cash_and_investments": _fmp_millions(balance.get("cashAndShortTermInvestments")),
    }


def valuation_date_label(iso_date):
    """Write a date such as 2026-08-28 as 28 Aug 2026, or None if it cannot be read."""
    import datetime

    try:
        return datetime.date.fromisoformat(str(iso_date)).strftime("%-d %b %Y")
    except ValueError:
        return None


def fetch_fmp_peer_list(ticker):
    """Get the peers Financial Modeling Prep lists for a company, each with its market value in
    millions, in the shape closest_peers takes. The free plan covers US companies, so the currency is
    US dollars. The company itself is left out.
    """
    return [
        {"ticker": row["symbol"], "market_cap": _fmp_millions(row.get("mktCap")), "currency": "USD"}
        for row in _fmp_get("stock-peers", symbol=ticker)
        if row.get("symbol") and row["symbol"] != ticker
    ]


def fetch_fmp_peer_quote(symbol):
    """Get one peer's multiples and operating margin from Financial Modeling Prep (two requests), in
    the same shape as fetch_peer_quote. Its market value comes from the peer list, and the revenue
    growth and the forward P/E, which would each cost a third request, are left out (None).
    """
    metrics = _fmp_rows("key-metrics-ttm", symbol)[0]
    ratios = _fmp_rows("ratios-ttm", symbol)[0]
    return {
        "ticker": symbol,
        "market_cap": None,
        "currency": "USD",
        "ev_sales": metrics.get("evToSalesTTM"),
        "ev_ebitda": metrics.get("evToEBITDATTM"),
        "pe": ratios.get("priceToEarningsRatioTTM"),
        "ps": ratios.get("priceToSalesRatioTTM"),
        "forward_pe": None,                 # needs another request for analyst estimates; left out to save the daily limit
        "operating_margin": ratios.get("operatingProfitMarginTTM"),
        "revenue_growth": None,
    }


def suggest_peers_fmp(
    ticker,
    company_market_value,
    biggest_size_gap,
    how_many,
    fetch_peer_list=fetch_fmp_peer_list,
    fetch_quote=fetch_fmp_peer_quote,
):
    """Suggest peers from Financial Modeling Prep's own peer list: keep those within biggest_size_gap
    times of the company's market value ($ millions), take the how_many closest in size, and fetch their
    multiples. To save the free daily limit it does not rank by margin and growth, and there is no
    sector top-up. Returns the same lists as suggest_peers, with "peer_source" "industry" (or None).
    """
    candidates = fetch_peer_list(ticker)
    chosen = valuation.closest_peers(company_market_value, candidates, biggest_size_gap, how_many)
    figures = peer_figures(read_quotes([candidate["ticker"] for candidate in chosen], fetch_quote))
    figures["peer_source"] = "industry" if chosen else None
    return figures


# ---------------------------------------------------------------------------
# Yahoo first, Financial Modeling Prep second
# ---------------------------------------------------------------------------

def _yahoo_then_fmp(yahoo_call, fmp_call):
    """Try Yahoo; if it is not answering (or has said it is busy a moment ago), try Financial Modeling
    Prep if a key is set. Returns the answer and which provider gave it ("yahoo" or "fmp"). A real
    problem with the company (an unknown ticker, no pre-tax profit) is not retried with the backup.
    Stops with a SourceUnavailable error naming both if neither answers.
    """
    if _yahoo_cooling_down():
        yahoo_error = SourceUnavailable(YAHOO_BUSY_MESSAGE)
    else:
        try:
            return yahoo_call(), "yahoo"
        except SourceUnavailable as error:
            yahoo_error = error
    if not fmp_available():
        raise yahoo_error
    try:
        return fmp_call(), "fmp"
    except SourceUnavailable as fmp_error:
        raise SourceUnavailable("%s %s" % (yahoo_error, fmp_error)) from fmp_error


def get_other_company_data(ticker):
    """Get a company's package of figures for any company but Adobe: from Yahoo, or from Financial
    Modeling Prep when Yahoo is not answering. Returns the package and the provider's name.
    """
    return _yahoo_then_fmp(
        lambda: get_company_data(ticker, source="yahoo"),
        lambda: get_company_data(ticker, source="fmp"),
    )


def get_history_any(ticker, usd_per_unit=1.0):
    """Get a company's yearly history from Yahoo, or from Financial Modeling Prep when Yahoo is not
    answering. The history says which provider gave it, under "source".
    """
    history, source = _yahoo_then_fmp(
        lambda: get_history(ticker, usd_per_unit),
        lambda: get_history(ticker, usd_per_unit, fetch_history=fetch_fmp_history),
    )
    return dict(history, source=source)


def get_ttm_any(ticker, usd_per_unit=1.0):
    """Get a company's last twelve months from Yahoo, or from Financial Modeling Prep when Yahoo is
    not answering. The set says which provider gave it, under "source".
    """
    ttm, source = _yahoo_then_fmp(
        lambda: get_ttm(ticker, usd_per_unit),
        lambda: get_ttm(ticker, usd_per_unit, fetch_ttm=fetch_fmp_ttm),
    )
    return dict(ttm, source=source)


def suggest_peers_any(
    ticker, company_market_value, candidates_to_check, biggest_size_gap, how_many,
    sector_candidates_to_check, minimum_industry_peers,
):
    """Suggest peers from Yahoo (by margin and growth, with a sector top-up), or from Financial
    Modeling Prep's peer list (by size) when Yahoo is not answering. The figures say which
    provider gave them, under "peer_data_source".
    """
    figures, source = _yahoo_then_fmp(
        lambda: suggest_peers(
            ticker, company_market_value, candidates_to_check, biggest_size_gap, how_many,
            sector_candidates_to_check, minimum_industry_peers,
        ),
        lambda: suggest_peers_fmp(ticker, company_market_value, biggest_size_gap, how_many),
    )
    return dict(figures, peer_data_source=source)


def peer_multiples_any(tickers):
    """Get the multiples of peers the reader chose, from Yahoo, or from Financial Modeling Prep when
    Yahoo is not answering. The figures say which provider gave them, under "peer_data_source".
    """
    figures, source = _yahoo_then_fmp(
        lambda: peer_multiples(tickers),
        lambda: peer_multiples(tickers, fetch_quote=fetch_fmp_peer_quote),
    )
    return dict(figures, peer_data_source=source)


# ---------------------------------------------------------------------------
# Choosing a source and fetching
# ---------------------------------------------------------------------------

# To add a new source later, write a function that takes a ticker and returns a package,
# then add it here under a name. Nothing else needs to change.
SOURCES = {
    "snapshot": snapshot_source,
    "live": live_source,
    "yahoo": yahoo_source,
    "fmp": lambda ticker: fmp_source(ticker),
    "live_fmp": lambda ticker: live_fmp_source(ticker),
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
    """Fetch Adobe's figures with a live share price and beta from Yahoo, or from Financial Modeling
    Prep if Yahoo is not answering, or from the frozen snapshot if neither is.

    Returns two things: the package of figures, and the name of the source that supplied it
    ("live", "live_fmp" or "snapshot"), so the page can tell the reader where the numbers came from.
    """
    if not _yahoo_cooling_down():
        try:
            return get_company_data(ticker, source=PREFERRED_SOURCE), PREFERRED_SOURCE
        except SourceUnavailable:       # live_source turns every Yahoo failure into this error
            pass
    if fmp_available():
        try:
            return get_company_data(ticker, source="live_fmp"), "live_fmp"
        except SourceUnavailable:
            pass
    return get_company_data(ticker, source=FALLBACK_SOURCE), FALLBACK_SOURCE
