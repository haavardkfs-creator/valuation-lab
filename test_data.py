"""Tests for data.py.

The expected snapshot numbers were copied from excel/valuation-lab.xlsx (the cell is named in
the comment). The last tests feed the data into valuation.py and expect the Excel answers.
"""

import pandas as pd
import pytest

import data
import test_valuation as base       # holds the base case assumptions, so they live in one place
import valuation as v


@pytest.fixture(autouse=True)
def fresh_provider_state(monkeypatch):
    """Start every test with Yahoo not cooling down, nothing remembered from Financial Modeling Prep,
    and no Financial Modeling Prep key (so a test never reaches the real service by accident).
    """
    monkeypatch.setattr("data._yahoo_busy_until", 0.0)
    monkeypatch.setattr("data._fmp_cache", {})
    monkeypatch.delenv("FMP_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Never really wait in a test: record the pauses the code asks for instead (see YAHOO_RETRY_PAUSE_SECONDS)."""
    pauses = []
    monkeypatch.setattr("data._pause", pauses.append)
    return pauses


# ---------------------------------------------------------------------------
# The snapshot matches the Excel model
# ---------------------------------------------------------------------------

EXPECTED_SNAPSHOT = {
    "company_name": "Adobe Inc.",
    "ticker": "ADBE",
    "revenue": 23769,                       # Inputs G11
    "ebit": 8706,                           # Multiples C18
    "depreciation_and_amortisation": 818,   # Multiples C19
    "net_income": 7130,                     # Multiples C21
    "prior_year_revenue": 21505,            # Inputs F11
    "income_tax": 1604,                     # Inputs G25
    "income_before_tax": 8734,              # Inputs G24
    "interest_expense": 263,                # starting point C25 (Inputs G21 is -263; stored as an expense)
    "capex": 179,                           # Projection G14 (Inputs G41 is -179; stored as spending)
    "cash_from_working_capital": 605,       # Projection G16 (sum of Inputs G34:G39)
    "debt": 6210,                           # WACC C22
    "cash_and_investments": 6595,           # valuation C22
    "stockholders_equity": 11623,           # history C26 (Yahoo Finance, 19 Nov 2026)
    "shares": 413,                          # WACC C20
    "share_price": 251.47,                  # WACC C19
    "beta": 1.38,                           # WACC C9
    "risk_free_rate": 0.0529,               # WACC C8
    "equity_risk_premium": 0.0441,          # WACC C10
    "pre_tax_cost_of_debt": 0.041642276422764232,   # Inputs G55 (exact, not 4.16%)
    "peer_tickers": ["ADSK", "INTU", "CRM", "SNPS"],    # Multiples C8:C11
    "peer_ev_sales": [6.71, 4.35, 4.85, 10.19],         # Multiples D8:D11
    "peer_ev_ebitda": [22.94, 13.45, 12.63, 26.18],     # Multiples E8:E11
    "peer_pe": [32.73, 20.72, 20.97, 82.62],            # Multiples F8:F11
    "peer_ps": [6.56, 3.30, 3.38, 8.06],                # Multiples G8:G11
    "peer_forward_pe": [17.22, 10.05, 11.28, 21.20],    # Multiples D70:D73
    "forward_eps": 27.41,                               # Multiples C77
}


CURRENCY_FIELDS = {"statement_currency", "price_currency", "usd_per_statement_unit", "usd_per_price_unit"}


def test_expected_snapshot_lists_every_package_field():
    # Adobe reports and trades in dollars, so its snapshot has no currency fields. It has a real
    # cost of debt from the 10-K, so it does not have the fallback flag either, and the snapshot has
    # no peer operating margins (Excel's Multiples sheet has none for Adobe's peers; the page fetches them).
    not_in_adobes_snapshot = CURRENCY_FIELDS | {"cost_of_debt_is_fallback", "peer_operating_margin"}
    assert set(EXPECTED_SNAPSHOT) == set(data.PACKAGE_FIELDS) | (set(data.OPTIONAL_FIELDS) - not_in_adobes_snapshot)


def test_required_and_optional_fields_do_not_overlap():
    assert not set(data.PACKAGE_FIELDS) & set(data.OPTIONAL_FIELDS)


def test_a_package_without_the_optional_fields_passes_the_check():
    required_only = {name: EXPECTED_SNAPSHOT[name] for name in data.PACKAGE_FIELDS}
    data.check_package(required_only)       # no cost of debt from the notes, no peer multiples


@pytest.mark.parametrize("field, expected", list(EXPECTED_SNAPSHOT.items()))
def test_snapshot_figure_matches_excel(field, expected):
    assert data.get_company_data("ADBE")[field] == expected


def test_peer_lists_have_one_entry_per_peer():
    package = data.get_company_data("ADBE")
    peers = len(package["peer_tickers"])
    assert len(package["peer_ev_sales"]) == peers
    assert len(package["peer_ev_ebitda"]) == peers
    assert len(package["peer_pe"]) == peers
    assert len(package["peer_ps"]) == peers
    assert len(package["peer_forward_pe"]) == peers


# ---------------------------------------------------------------------------
# Fetching, errors and swapping
# ---------------------------------------------------------------------------

def test_ticker_can_be_in_any_letter_case():
    assert data.get_company_data("adbe") == data.get_company_data("ADBE")


def test_unknown_ticker_is_refused_with_a_plain_error():
    with pytest.raises(ValueError, match="only has Adobe"):
        data.get_company_data("MSFT")


def test_unknown_source_is_refused_and_lists_the_real_ones():
    with pytest.raises(ValueError, match="snapshot"):
        data.get_company_data("ADBE", source="nonsense")


def test_changing_the_result_does_not_change_the_snapshot():
    package = data.get_company_data("ADBE")
    package["revenue"] = 1
    package["peer_pe"].append(999)
    fresh = data.get_company_data("ADBE")
    assert fresh["revenue"] == 23769
    assert fresh["peer_pe"] == [32.73, 20.72, 20.97, 82.62]


def test_check_package_names_the_missing_figures():
    incomplete = dict(EXPECTED_SNAPSHOT)
    del incomplete["beta"]
    del incomplete["shares"]
    with pytest.raises(ValueError) as error:
        data.check_package(incomplete)
    assert "beta" in str(error.value)       # the order of the names is not promised
    assert "shares" in str(error.value)


def test_a_new_source_can_be_plugged_in_without_changing_anything_else(monkeypatch):
    def fake_source(ticker):
        package = dict(EXPECTED_SNAPSHOT)
        package["share_price"] = 100.0
        return package

    monkeypatch.setitem(data.SOURCES, "fake", fake_source)
    assert data.get_company_data("ADBE", source="fake")["share_price"] == 100.0


def test_a_source_that_leaves_figures_out_is_caught(monkeypatch):
    monkeypatch.setitem(data.SOURCES, "broken", lambda ticker: {"ticker": ticker})
    with pytest.raises(ValueError, match="did not supply"):
        data.get_company_data("ADBE", source="broken")


# ---------------------------------------------------------------------------
# The live source (tested with fake Yahoo replies, never the internet)
# ---------------------------------------------------------------------------

def fake_quote(price=240.74, beta=1.383):
    """Return a stand-in for fetch_yahoo_quote that gives these figures."""
    return lambda ticker: {"share_price": price, "beta": beta}


class FakeYahooTicker:
    """Stands in for yfinance.Ticker: its .info looks like a real Yahoo reply."""

    def __init__(self, ticker):
        self.info = {"currentPrice": 240.74, "beta": 1.383, "shortName": "Adobe Inc."}


def test_live_source_replaces_only_the_share_price_and_beta():
    live = data.live_source("ADBE", fetch_quote=fake_quote(240.74, 1.383))
    assert live["share_price"] == 240.74
    assert live["beta"] == 1.383
    for field, expected in EXPECTED_SNAPSHOT.items():
        if field not in ("share_price", "beta"):
            assert live[field] == expected


def test_live_source_is_complete_enough_to_pass_the_package_check():
    data.check_package(data.live_source("ADBE", fetch_quote=fake_quote()))


def test_live_source_still_refuses_companies_the_snapshot_does_not_have():
    with pytest.raises(ValueError, match="only has Adobe"):
        data.live_source("MSFT", fetch_quote=fake_quote())


@pytest.mark.parametrize("bad_price", [None, 0, -5])
def test_live_source_refuses_a_missing_or_impossible_share_price(bad_price):
    with pytest.raises(ValueError, match="usable share price"):
        data.live_source("ADBE", fetch_quote=fake_quote(price=bad_price))


def test_live_source_refuses_a_missing_beta():
    with pytest.raises(ValueError, match="did not give a beta"):
        data.live_source("ADBE", fetch_quote=fake_quote(beta=None))


def test_live_source_gives_a_plain_error_when_yahoo_cannot_be_reached():
    def broken_fetch(ticker):
        raise ConnectionError("no internet")

    with pytest.raises(ValueError, match="Yahoo Finance.*no internet"):
        data.live_source("ADBE", fetch_quote=broken_fetch)


def test_fetch_yahoo_quote_picks_the_price_and_beta_out_of_yahoos_reply(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", FakeYahooTicker)
    assert data.fetch_yahoo_quote("ADBE") == {"share_price": 240.74, "beta": 1.383}


def test_fetch_yahoo_quote_gives_none_for_figures_yahoo_leaves_out(monkeypatch):
    class EmptyTicker:
        def __init__(self, ticker):
            self.info = {}

    monkeypatch.setattr("yfinance.Ticker", EmptyTicker)
    assert data.fetch_yahoo_quote("ADBE") == {"share_price": None, "beta": None}


def test_the_live_source_can_be_chosen_by_name(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", FakeYahooTicker)
    live = data.get_company_data("adbe", source="live")
    assert live["share_price"] == 240.74
    assert live["beta"] == 1.383


def test_the_default_source_is_still_the_snapshot():
    assert data.DEFAULT_SOURCE == "snapshot"


# ---------------------------------------------------------------------------
# The fallback: live first, snapshot if live fails
# ---------------------------------------------------------------------------

def test_the_preferred_and_fallback_sources_both_exist():
    assert data.PREFERRED_SOURCE in data.SOURCES
    assert data.FALLBACK_SOURCE in data.SOURCES


def test_fallback_uses_the_live_source_when_it_works(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", FakeYahooTicker)
    package, source_used = data.get_company_data_with_fallback("ADBE")
    assert source_used == "live"
    assert package["share_price"] == 240.74
    assert package["beta"] == 1.383


def test_fallback_uses_the_snapshot_when_yahoo_cannot_be_reached(monkeypatch):
    class BrokenTicker:
        def __init__(self, ticker):
            raise ConnectionError("no internet")

    monkeypatch.setattr("yfinance.Ticker", BrokenTicker)
    package, source_used = data.get_company_data_with_fallback("ADBE")
    assert source_used == "snapshot"
    assert package == EXPECTED_SNAPSHOT


def test_fallback_uses_the_snapshot_when_yahoo_gives_nothing_usable(monkeypatch):
    class EmptyTicker:
        def __init__(self, ticker):
            self.info = {}

    monkeypatch.setattr("yfinance.Ticker", EmptyTicker)
    package, source_used = data.get_company_data_with_fallback("ADBE")
    assert source_used == "snapshot"
    assert package["share_price"] == 251.47


def test_fallback_does_not_hide_a_company_neither_source_has(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", FakeYahooTicker)
    with pytest.raises(ValueError, match="only has Adobe"):
        data.get_company_data_with_fallback("MSFT")


# ---------------------------------------------------------------------------
# The whole chain: data.py -> valuation.py gives the Excel answers
# ---------------------------------------------------------------------------

def test_data_into_the_dcf_gives_305_60():
    d = data.get_company_data("ADBE")
    result = v.run_full_dcf(
        base_revenue=d["revenue"],
        growth_rates=base.GROWTH_RATES,
        operating_margins=base.OPERATING_MARGINS,
        tax_rate=base.TAX_RATE,
        da_pcts=base.DA_PCTS,
        capex_pcts=base.CAPEX_PCTS,
        wc_pcts=base.WC_PCTS,
        risk_free_rate=d["risk_free_rate"],
        beta=d["beta"],
        equity_risk_premium=d["equity_risk_premium"],
        pre_tax_cost_of_debt=d["pre_tax_cost_of_debt"],
        share_price=d["share_price"],
        shares=d["shares"],
        debt=d["debt"],
        cash_and_investments=d["cash_and_investments"],
        terminal_growth_rate=base.TERMINAL_GROWTH_RATE,
    )
    assert result["wacc"] == base.close(0.10926631869756551)
    assert result["enterprise_value"] == base.close(125828.63291039423)
    assert result["implied_share_price"] == base.close(305.60201673218938)
    assert round(result["implied_share_price"], 2) == 305.60


def test_data_into_the_multiples_gives_the_excel_prices():
    d = data.get_company_data("ADBE")
    net_debt_amount = v.net_debt(d["debt"], d["cash_and_investments"])
    prices = [
        v.price_from_ev_multiple(
            d["revenue"], v.peer_median(d["peer_ev_sales"]), net_debt_amount, d["shares"]
        ),
        v.price_from_ev_multiple(
            v.ebitda(d["ebit"], d["depreciation_and_amortisation"]),
            v.peer_median(d["peer_ev_ebitda"]),
            net_debt_amount,
            d["shares"],
        ),
        v.price_from_pe(d["net_income"], v.peer_median(d["peer_pe"]), d["shares"]),
        v.price_from_ps(d["revenue"], v.peer_median(d["peer_ps"]), d["shares"]),
        v.price_from_forward_pe(d["forward_eps"], v.peer_median(d["peer_forward_pe"])),
    ]
    assert prices == [
        base.close(333.58309927360767),     # Multiples H27
        base.close(420.51859564164647),     # H28
        base.close(463.53631961259072),     # H29
        base.close(286.03372881355932),     # H30
        base.close(390.59250000000003),     # H31
    ]


# ---------------------------------------------------------------------------
# The whole chain for another company's starting point: data.py -> valuation.py
# gives the "starting point" sheet's numbers
# ---------------------------------------------------------------------------

def test_data_into_last_year_ratios_gives_the_starting_point_sheet_ratios():
    d = data.get_company_data("ADBE")
    ratios = v.last_year_ratios(
        revenue=d["revenue"],
        prior_revenue=d["prior_year_revenue"],
        ebit=d["ebit"],
        income_tax=d["income_tax"],
        income_before_tax=d["income_before_tax"],
        depreciation_and_amortisation=d["depreciation_and_amortisation"],
        capex=d["capex"],
        cash_from_working_capital=d["cash_from_working_capital"],
    )
    for name, expected in base.STARTING_POINT_RATIOS.items():       # starting point C5:C10
        assert ratios[name] == base.close(expected)


def test_data_into_the_starting_point_gives_the_sheets_growth_fade():
    d = data.get_company_data("ADBE")
    ratios = v.last_year_ratios(
        revenue=d["revenue"],
        prior_revenue=d["prior_year_revenue"],
        ebit=d["ebit"],
        income_tax=d["income_tax"],
        income_before_tax=d["income_before_tax"],
        depreciation_and_amortisation=d["depreciation_and_amortisation"],
        capex=d["capex"],
        cash_from_working_capital=d["cash_from_working_capital"],
    )
    start = v.starting_point_assumptions(ratios, base.TERMINAL_GROWTH_RATE, 5)
    assert start["growth_rates"] == [base.close(x) for x in base.STARTING_POINT_GROWTH]     # D17:H17


# ---------------------------------------------------------------------------
# The yahoo source: any company, from Yahoo's statements (fake replies, never the internet)
# ---------------------------------------------------------------------------

def statement(rows):
    """Build a Yahoo-style statement table from {line name: (latest year, year before)}."""
    return pd.DataFrame(rows, index=["latest", "before"]).T


# Adobe's figures as Yahoo returns them, in dollars, checked once against the real reply on
# 6 Nov 2026. Yahoo leaves "Current Debt" empty for Adobe in the latest year.
ADOBE_YAHOO_INCOME = {
    "Total Revenue": (23769e6, 21505e6),
    "Operating Income": (8706e6, 7741e6),
    "Net Income": (7130e6, 5560e6),
    "Tax Provision": (1604e6, 1371e6),
    "Pretax Income": (8734e6, 6931e6),
    "Interest Expense": (263e6, 169e6),
}
ADOBE_YAHOO_CASH_FLOW = {
    "Depreciation And Amortization": (818e6, 857e6),
    "Capital Expenditure": (-179e6, -183e6),
    "Change In Working Capital": (605e6, 144e6),
}
ADOBE_YAHOO_BALANCE = {
    "Long Term Debt": (6210e6, 4129e6),
    "Current Debt": (float("nan"), 1499e6),
    "Cash Cash Equivalents And Short Term Investments": (6595e6, 7886e6),
}
ADOBE_YAHOO_INFO = {
    "longName": "Adobe Inc.",
    "financialCurrency": "USD",
    "currency": "USD",
    "sharesOutstanding": 389_200_000,
    "currentPrice": 240.74,
    "beta": 1.383,
}


def fake_statements_ticker(income=None, cash_flow=None, balance=None, info=None, fx_rates=None):
    """Return a stand-in for yfinance.Ticker that serves these statements (Adobe's by default).

    `fx_rates` maps an exchange-rate ticker such as "NOKUSD=X" to the rate Yahoo would quote.
    """
    class FakeTicker:
        def __init__(self, ticker):
            if fx_rates and ticker in fx_rates:
                self.info = {"regularMarketPrice": fx_rates[ticker]}
                return
            self.income_stmt = statement(ADOBE_YAHOO_INCOME if income is None else income)
            self.cashflow = statement(ADOBE_YAHOO_CASH_FLOW if cash_flow is None else cash_flow)
            self.balance_sheet = statement(ADOBE_YAHOO_BALANCE if balance is None else balance)
            self.info = dict(ADOBE_YAHOO_INFO if info is None else info)
    return FakeTicker


def without(rows, line):
    """Return the rows with one line left out, as if Yahoo did not have it."""
    return {name: values for name, values in rows.items() if name != line}


def test_the_yahoo_source_is_registered_and_the_default_is_still_the_snapshot():
    assert "yahoo" in data.SOURCES
    assert data.DEFAULT_SOURCE == "snapshot"


def test_fetch_yahoo_statements_turns_dollars_into_millions_and_picks_the_lines(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    got = data.fetch_yahoo_statements("ADBE")
    assert got["revenue"] == pytest.approx(23769)
    assert got["prior_year_revenue"] == pytest.approx(21505)       # the second column
    assert got["capex"] == pytest.approx(179)                      # Yahoo's -179 made positive
    assert got["interest_expense"] == pytest.approx(263)
    assert got["cash_from_working_capital"] == pytest.approx(605)
    assert got["long_term_debt"] == pytest.approx(6210)
    assert got["current_debt"] is None                             # Yahoo had no figure
    assert got["shares"] == pytest.approx(389.2)                   # millions
    assert got["share_price"] == 240.74
    assert got["company_name"] == "Adobe Inc."


def test_fetch_yahoo_statements_gives_none_for_a_missing_line_or_year(monkeypatch):
    monkeypatch.setattr(
        "yfinance.Ticker",
        fake_statements_ticker(income=without(ADOBE_YAHOO_INCOME, "Operating Income")),
    )
    assert data.fetch_yahoo_statements("ADBE")["ebit"] is None

    class OneYearTicker(fake_statements_ticker()):
        """Yahoo has only the latest year for this company."""

        def __init__(self, ticker):
            super().__init__(ticker)
            latest_only = {name: values[0] for name, values in ADOBE_YAHOO_INCOME.items()}
            self.income_stmt = pd.DataFrame({"latest": latest_only})

    monkeypatch.setattr("yfinance.Ticker", OneYearTicker)
    assert data.fetch_yahoo_statements("ADBE")["prior_year_revenue"] is None


def test_yahoo_reply_for_adobe_gives_the_same_figures_as_the_10k_snapshot(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    package = data.get_company_data("ADBE", source="yahoo")
    for field in (
        "revenue", "prior_year_revenue", "ebit", "net_income", "income_tax", "income_before_tax",
        "interest_expense", "depreciation_and_amortisation", "capex", "cash_from_working_capital",
        "debt", "cash_and_investments",
    ):
        assert package[field] == pytest.approx(EXPECTED_SNAPSHOT[field]), field


def test_the_yahoo_package_is_complete_and_has_no_adobe_only_fields(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    package = data.get_company_data("ADBE", source="yahoo")     # runs check_package
    assert set(package) == set(data.PACKAGE_FIELDS) | CURRENCY_FIELDS
    assert not {"pre_tax_cost_of_debt", "peer_tickers"} & set(package)      # Yahoo cannot supply these


def test_the_yahoo_package_uses_the_market_wide_rates_and_yahoos_quote(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    package = data.get_company_data("ADBE", source="yahoo")
    assert package["risk_free_rate"] == data.RISK_FREE_RATE == 0.0529
    assert package["equity_risk_premium"] == data.EQUITY_RISK_PREMIUM == 0.0441
    assert package["share_price"] == 240.74
    assert package["beta"] == 1.383


def test_the_yahoo_source_works_for_a_company_that_is_not_adobe(monkeypatch):
    info = dict(ADOBE_YAHOO_INFO, longName="Example Corp")
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info=info))
    package = data.get_company_data("exmp", source="yahoo")
    assert package["ticker"] == "EXMP"
    assert package["company_name"] == "Example Corp"


def test_current_debt_is_added_to_long_term_debt_when_yahoo_has_it(monkeypatch):
    balance = dict(ADOBE_YAHOO_BALANCE, **{"Current Debt": (9227e6, 2999e6), "Long Term Debt": (31067e6, 40152e6)})
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(balance=balance))
    assert data.get_company_data("EXMP", source="yahoo")["debt"] == pytest.approx(40294)


def test_a_missing_core_line_stops_with_a_plain_error_naming_it(monkeypatch):
    income = without(without(ADOBE_YAHOO_INCOME, "Operating Income"), "Tax Provision")
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(income=income))
    with pytest.raises(ValueError, match="did not supply") as error:
        data.get_company_data("ADBE", source="yahoo")
    assert "ebit" in str(error.value) and "income_tax" in str(error.value)


def test_a_ticker_yahoo_knows_nothing_about_gets_a_plain_error_without_a_list_of_fields(monkeypatch):
    nothing = fake_statements_ticker(income={}, cash_flow={}, balance={}, info={})
    monkeypatch.setattr("yfinance.Ticker", nothing)
    with pytest.raises(ValueError, match="no figures for NOPE") as error:
        data.get_company_data("nope", source="yahoo")
    assert "Check that the ticker is right" in str(error.value)
    assert "long_term_debt" not in str(error.value)


def test_a_missing_long_term_debt_line_is_not_guessed_as_zero(monkeypatch):
    balance = without(ADOBE_YAHOO_BALANCE, "Long Term Debt")
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(balance=balance))
    with pytest.raises(ValueError, match="long_term_debt"):
        data.get_company_data("ADBE", source="yahoo")


def test_a_zero_share_price_is_refused(monkeypatch):
    info = dict(ADOBE_YAHOO_INFO, currentPrice=0)
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info=info))
    with pytest.raises(ValueError, match="zero or less"):
        data.get_company_data("ADBE", source="yahoo")


def test_yahoo_being_unreachable_gives_a_plain_error(monkeypatch):
    def broken_fetch(ticker):
        raise ConnectionError("no internet")

    with pytest.raises(ValueError, match="Yahoo Finance.*no internet"):
        data.yahoo_source("ADBE", fetch_statements=broken_fetch)


def test_yahoo_package_through_the_starting_point_gives_the_sheet_numbers(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    d = data.get_company_data("ADBE", source="yahoo")
    ratios = v.last_year_ratios(
        revenue=d["revenue"],
        prior_revenue=d["prior_year_revenue"],
        ebit=d["ebit"],
        income_tax=d["income_tax"],
        income_before_tax=d["income_before_tax"],
        depreciation_and_amortisation=d["depreciation_and_amortisation"],
        capex=d["capex"],
        cash_from_working_capital=d["cash_from_working_capital"],
    )
    for name, expected in base.STARTING_POINT_RATIOS.items():       # starting point C5:C10
        assert ratios[name] == pytest.approx(expected, rel=1e-9)
    cost_of_debt = v.estimate_pre_tax_cost_of_debt(d["interest_expense"], d["debt"])
    assert cost_of_debt == pytest.approx(0.04235104669887278, rel=1e-9)     # starting point C27


# ---------------------------------------------------------------------------
# Currency: everything from the yahoo source is in US dollars
# ---------------------------------------------------------------------------

def foreign_company(statement_currency, price_currency, fx_rates):
    """A stand-in Yahoo reply with Adobe's figures, as if they were in another currency."""
    info = dict(ADOBE_YAHOO_INFO, financialCurrency=statement_currency, currency=price_currency)
    return fake_statements_ticker(info=info, fx_rates=fx_rates)


def test_a_dollar_company_is_not_changed_by_the_conversion(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    package = data.get_company_data("ADBE", source="yahoo")
    assert package["usd_per_statement_unit"] == 1.0
    assert package["usd_per_price_unit"] == 1.0
    assert package["statement_currency"] == "USD" and package["price_currency"] == "USD"
    assert package["revenue"] == pytest.approx(23769)
    assert package["share_price"] == 240.74


def test_a_krone_company_is_converted_to_dollars_at_todays_rate(monkeypatch):
    # Reports and trades in NOK, like Aker. Pretend one krone is 10 US cents.
    monkeypatch.setattr("yfinance.Ticker", foreign_company("NOK", "NOK", {"NOKUSD=X": 0.10}))
    package = data.get_company_data("AKER.OL", source="yahoo")
    assert package["revenue"] == pytest.approx(2376.9)              # 23,769 NOK million
    assert package["prior_year_revenue"] == pytest.approx(2150.5)
    assert package["debt"] == pytest.approx(621.0)                  # long-term debt converted, then added
    assert package["cash_and_investments"] == pytest.approx(659.5)
    assert package["capex"] == pytest.approx(17.9)
    assert package["share_price"] == pytest.approx(24.074)          # 240.74 NOK a share
    assert package["shares"] == pytest.approx(389.2)                # a count, not money: unchanged
    assert package["beta"] == 1.383                                 # not money either
    assert package["statement_currency"] == "NOK" and package["usd_per_statement_unit"] == 0.10
    assert package["price_currency"] == "NOK" and package["usd_per_price_unit"] == 0.10


def test_forward_eps_is_converted_like_the_share_price(monkeypatch):
    # Yahoo gives it in the currency the share trades in. Pretend one krone is 10 US cents.
    info = dict(ADOBE_YAHOO_INFO, financialCurrency="NOK", currency="NOK", forwardEps=26.25)
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info=info, fx_rates={"NOKUSD=X": 0.10}))
    assert data.get_company_data("AKER.OL", source="yahoo")["forward_eps"] == pytest.approx(2.625)


def test_forward_eps_for_statements_in_one_currency_and_shares_in_another_uses_the_price_rate(monkeypatch):
    # Like Novo Nordisk: reports in DKK, shares trade in dollars, and the estimate is in dollars too.
    info = dict(ADOBE_YAHOO_INFO, financialCurrency="DKK", currency="USD", forwardEps=3.51)
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info=info, fx_rates={"DKKUSD=X": 0.15}))
    assert data.get_company_data("NVO", source="yahoo")["forward_eps"] == pytest.approx(3.51)


def test_a_company_with_no_analyst_estimate_has_no_forward_eps_field(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())            # ADOBE_YAHOO_INFO has no forwardEps
    assert "forward_eps" not in data.get_company_data("ADBE", source="yahoo")


def test_converting_does_not_change_the_ratios(monkeypatch):
    # Growth, margins and the other ratios are shares of revenue, so they must not move.
    monkeypatch.setattr("yfinance.Ticker", foreign_company("NOK", "NOK", {"NOKUSD=X": 0.10}))
    d = data.get_company_data("AKER.OL", source="yahoo")
    ratios = v.last_year_ratios(
        revenue=d["revenue"],
        prior_revenue=d["prior_year_revenue"],
        ebit=d["ebit"],
        income_tax=d["income_tax"],
        income_before_tax=d["income_before_tax"],
        depreciation_and_amortisation=d["depreciation_and_amortisation"],
        capex=d["capex"],
        cash_from_working_capital=d["cash_from_working_capital"],
    )
    for name, expected in base.STARTING_POINT_RATIOS.items():       # starting point C5:C10
        assert ratios[name] == pytest.approx(expected, rel=1e-9)
    assert v.estimate_pre_tax_cost_of_debt(d["interest_expense"], d["debt"]) == pytest.approx(
        0.04235104669887278, rel=1e-9                               # starting point C27
    )


def test_statements_and_share_price_in_different_currencies_each_use_their_own_rate(monkeypatch):
    # Like Novo Nordisk: reports in DKK, but the shares trade in the US in dollars.
    monkeypatch.setattr("yfinance.Ticker", foreign_company("DKK", "USD", {"DKKUSD=X": 0.15}))
    package = data.get_company_data("NVO", source="yahoo")
    assert package["revenue"] == pytest.approx(23769 * 0.15)        # statements converted
    assert package["share_price"] == 240.74                         # already dollars: not converted


def test_a_price_quoted_in_pence_is_converted_through_pounds(monkeypatch):
    # Like Shell in London: statements in dollars, the price in pence (hundredths of a pound).
    monkeypatch.setattr("yfinance.Ticker", foreign_company("USD", "GBp", {"GBPUSD=X": 1.30}))
    package = data.get_company_data("SHEL.L", source="yahoo")
    assert package["revenue"] == pytest.approx(23769)               # dollars: unchanged
    assert package["share_price"] == pytest.approx(240.74 * 1.30 / 100)
    assert package["usd_per_price_unit"] == pytest.approx(0.013)


def test_a_missing_exchange_rate_stops_with_a_plain_error(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", foreign_company("NOK", "NOK", {}))     # Yahoo has no NOK rate
    with pytest.raises(ValueError, match="no exchange rate for NOK"):
        data.get_company_data("AKER.OL", source="yahoo")


def test_fetch_yahoo_statements_returns_the_currencies_and_rates(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", foreign_company("DKK", "USD", {"DKKUSD=X": 0.15}))
    got = data.fetch_yahoo_statements("NVO")
    assert (got["statement_currency"], got["price_currency"]) == ("DKK", "USD")
    assert got["usd_per_statement_unit"] == 0.15
    assert got["usd_per_price_unit"] == 1.0
    assert got["revenue"] == pytest.approx(23769)                   # still in kroner here: the source converts


# ---------------------------------------------------------------------------
# A company with no interest expense on Yahoo (Apple): the cost of debt falls back
# ---------------------------------------------------------------------------

def no_interest_expense_company(**kwargs):
    """A stand-in for Yahoo's reply about a company whose income statement has no interest lines."""
    return fake_statements_ticker(income=without(ADOBE_YAHOO_INCOME, "Interest Expense"), **kwargs)


def test_a_company_with_no_interest_expense_gets_the_fallback_cost_of_debt(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", no_interest_expense_company())
    package = data.get_company_data("AAPL", source="yahoo")         # runs check_package: no error
    assert package["interest_expense"] is None
    assert package["pre_tax_cost_of_debt"] == pytest.approx(0.064)      # starting point C37
    assert package["cost_of_debt_is_fallback"] is True


def test_the_credit_spread_is_the_sheets_bbb_spread():
    assert data.CREDIT_SPREAD == 0.0111                             # starting point C36


def test_a_company_with_an_interest_expense_gets_no_fallback(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    package = data.get_company_data("ADBE", source="yahoo")
    assert "pre_tax_cost_of_debt" not in package and "cost_of_debt_is_fallback" not in package
    assert package["interest_expense"] == pytest.approx(263)


def test_the_fallback_cost_of_debt_is_the_same_in_every_currency(monkeypatch):
    # A rate is not an amount of money, so converting the statements must not touch it.
    info = dict(ADOBE_YAHOO_INFO, financialCurrency="NOK", currency="NOK")
    monkeypatch.setattr(
        "yfinance.Ticker", no_interest_expense_company(info=info, fx_rates={"NOKUSD=X": 0.09})
    )
    package = data.get_company_data("AKER.OL", source="yahoo")
    assert package["pre_tax_cost_of_debt"] == pytest.approx(0.064)


# ---------------------------------------------------------------------------
# Peers: suggested from Yahoo's industry list, with their multiples
# ---------------------------------------------------------------------------

def quote(ticker, market_cap, ev_sales=2.0, ev_ebitda=12.0, pe=20.0, currency="USD", operating_margin=0.20, revenue_growth=0.05, ps=3.0, forward_pe=15.0):
    """A peer's quote as fetch_peer_quote returns it (market value in $ millions)."""
    return {
        "ticker": ticker, "market_cap": market_cap, "currency": currency,
        "ev_sales": ev_sales, "ev_ebitda": ev_ebitda, "pe": pe, "ps": ps, "forward_pe": forward_pe, "operating_margin": operating_margin,
        "revenue_growth": revenue_growth,
    }


# The same peers as Coca-Cola's worked example on the Multiples sheet (rows 43-45), so the
# multiples are ones already checked against Excel.
COCA_COLA_PEER_QUOTES = {
    "PEP": quote("PEP", 200_000, 2.434, 12.472, 18.50692, operating_margin=0.16046),      # G43
    "KDP": quote("KDP", 49_000, 3.854, 16.631, None, operating_margin=0.18255),           # no P/E: blank on purpose (F44); G44
    "MDLZ": quote("MDLZ", 70_000, 2.663, 14.749, 21.381702, operating_margin=0.14567),    # G45
    "COKE": quote("COKE", 14_000),                              # far too small
    "SHEL": quote("SHEL", 200_000, currency="GBp"),             # not traded in US dollars
}


def fake_candidates(ticker, how_many):
    return ["PEP", "KDP", "MDLZ", "COKE", "SHEL"][:how_many]


def suggest_for_coca_cola(**kwargs):
    arguments = dict(
        ticker="KO", company_market_value=427_000, candidates_to_check=20, biggest_size_gap=10,
        how_many=5, sector_candidates_to_check=30, minimum_industry_peers=2,
        fetch_candidates=fake_candidates, fetch_sector=lambda ticker, how_many: [],
        fetch_quote=COCA_COLA_PEER_QUOTES.__getitem__,       # no quote for KO itself: ranked by size, as before
    )
    arguments.update(kwargs)
    return data.suggest_peers(**arguments)


def test_suggested_peers_are_the_closest_in_size_that_trade_in_dollars():
    got = suggest_for_coca_cola()
    # PEP is 2.1 times smaller, MDLZ 6.1, KDP 8.7. COKE is too small, SHEL is in pence.
    assert got["peer_tickers"] == ["PEP", "MDLZ", "KDP"]


def test_suggested_peers_come_with_their_multiples_in_the_same_order():
    got = suggest_for_coca_cola()
    assert got["peer_ev_sales"] == [2.434, 2.663, 3.854]
    assert got["peer_ev_ebitda"] == [12.472, 14.749, 16.631]
    assert got["peer_pe"] == [18.50692, 21.381702, None]        # Keurig's blank P/E stays None


def test_suggested_peers_give_the_medians_checked_against_the_multiples_sheet():
    got = suggest_for_coca_cola()
    assert v.median_of_usable_multiples(got["peer_ev_sales"], 2) == pytest.approx(2.663)      # D46
    assert v.median_of_usable_multiples(got["peer_ev_ebitda"], 2) == pytest.approx(14.749)    # E46
    assert v.median_of_usable_multiples(got["peer_pe"], 2) == pytest.approx(19.944311)        # F46


def test_suggested_peers_are_capped_at_how_many_are_asked_for():
    assert suggest_for_coca_cola(how_many=2)["peer_tickers"] == ["PEP", "MDLZ"]


def test_only_the_first_candidates_to_check_are_looked_at():
    # With 2 candidates checked, only PEP and KDP are looked up.
    assert suggest_for_coca_cola(candidates_to_check=2)["peer_tickers"] == ["PEP", "KDP"]


def test_a_company_with_no_suitable_peers_gets_empty_lists_not_an_error():
    got = suggest_for_coca_cola(company_market_value=5_000_000)      # like Apple: nothing close in size
    assert got == {
        "peer_tickers": [], "peer_ev_sales": [], "peer_ev_ebitda": [], "peer_pe": [], "peer_ps": [],
        "peer_forward_pe": [], "peer_operating_margin": [], "peer_source": None,
    }


def test_a_company_whose_industry_yahoo_does_not_know_gets_empty_lists():
    got = suggest_for_coca_cola(fetch_candidates=lambda ticker, how_many: [])
    assert got["peer_tickers"] == []


def test_one_peer_yahoo_cannot_read_is_skipped():
    def flaky(symbol):
        if symbol == "MDLZ":
            raise ConnectionError("no answer")
        return COCA_COLA_PEER_QUOTES[symbol]

    assert suggest_for_coca_cola(fetch_quote=flaky)["peer_tickers"] == ["PEP", "KDP"]


def test_when_yahoo_cannot_be_reached_at_all_suggesting_peers_stops_with_a_plain_error():
    def down(symbol):
        raise ConnectionError("no internet")

    with pytest.raises(ValueError, match="none of the 5 candidates could be read"):
        suggest_for_coca_cola(fetch_quote=down)

    def no_industry_lookup(ticker, how_many):
        raise ConnectionError("no internet")

    with pytest.raises(ValueError, match="Could not get peers from Yahoo Finance: no internet"):
        suggest_for_coca_cola(fetch_candidates=no_industry_lookup)


def test_peer_multiples_for_tickers_the_reader_chose_keep_their_order():
    got = data.peer_multiples(["MDLZ", "PEP"], fetch_quote=COCA_COLA_PEER_QUOTES.__getitem__)
    assert got["peer_tickers"] == ["MDLZ", "PEP"]
    assert got["peer_ev_sales"] == [2.663, 2.434]


def test_a_ticker_yahoo_knows_nothing_about_has_no_multiples_and_no_error():
    unknown = quote("ZZZZ", None, None, None, None, currency=None, operating_margin=None)
    got = data.peer_multiples(["ZZZZ"], fetch_quote=lambda ticker: unknown)
    assert got["peer_pe"] == [None]
    assert v.median_of_usable_multiples(got["peer_pe"], 2) is None


def test_peer_multiples_stops_with_a_plain_error_when_yahoo_fails():
    def down(ticker):
        raise ConnectionError("no internet")

    with pytest.raises(ValueError, match="Could not get peer figures from Yahoo Finance: no internet"):
        data.peer_multiples(["PEP"], fetch_quote=down)


# The two functions that really talk to Yahoo, with yfinance faked.

class FakeInfoTicker:
    """A stand-in for yfinance.Ticker that serves one prepared info dictionary per ticker."""
    infos = {}

    def __init__(self, ticker):
        self.info = dict(self.infos.get(ticker, {}))


class FakeIndex:
    """A stand-in for yfinance.Industry, whose top_companies is a table indexed by ticker."""
    def __init__(self, key):
        self.top_companies = None if key == "nothing" else pd.DataFrame(
            {"name": ["Coca-Cola", "PepsiCo", "Monster"]}, index=["KO", "PEP", "MNST"]
        )


def test_fetch_peer_quote_turns_the_market_value_into_millions_and_picks_the_multiples(monkeypatch):
    FakeInfoTicker.infos = {"PEP": {
        "marketCap": 200_363_819_008, "currency": "USD", "enterpriseToRevenue": 2.434,
        "enterpriseToEbitda": 12.472, "trailingPE": 18.50692, "priceToSalesTrailing12Months": 2.2,
        "forwardPE": 16.5, "operatingMargins": 0.16046, "revenueGrowth": 0.04,
    }}
    monkeypatch.setattr("yfinance.Ticker", FakeInfoTicker)
    got = data.fetch_peer_quote("PEP")
    assert got == {
        "ticker": "PEP", "market_cap": pytest.approx(200_363.819008), "currency": "USD",
        "ev_sales": 2.434, "ev_ebitda": 12.472, "pe": 18.50692, "ps": 2.2, "forward_pe": 16.5, "operating_margin": 0.16046,
        "revenue_growth": 0.04,
    }


def test_fetch_peer_quote_gives_none_for_a_figure_yahoo_does_not_have(monkeypatch):
    FakeInfoTicker.infos = {"LOSS": {"marketCap": 5_000_000_000, "currency": "USD"}}
    monkeypatch.setattr("yfinance.Ticker", FakeInfoTicker)
    got = data.fetch_peer_quote("LOSS")
    assert got["pe"] is None and got["ev_ebitda"] is None and got["ev_sales"] is None and got["ps"] is None
    assert got["forward_pe"] is None
    assert got["operating_margin"] is None and got["revenue_growth"] is None
    assert data.fetch_peer_quote("UNKNOWN")["market_cap"] is None


def test_fetch_peer_candidates_lists_the_industry_without_the_company_itself(monkeypatch):
    FakeInfoTicker.infos = {"KO": {"industryKey": "beverages-non-alcoholic"}}
    monkeypatch.setattr("yfinance.Ticker", FakeInfoTicker)
    monkeypatch.setattr("yfinance.Industry", FakeIndex)
    assert data.fetch_peer_candidates("KO", 20) == ["PEP", "MNST"]
    assert data.fetch_peer_candidates("KO", 1) == ["PEP"]


def test_fetch_peer_candidates_gives_nothing_when_yahoo_has_no_industry(monkeypatch):
    FakeInfoTicker.infos = {"ODD": {}, "NOTHING": {"industryKey": "nothing"}}
    monkeypatch.setattr("yfinance.Ticker", FakeInfoTicker)
    monkeypatch.setattr("yfinance.Industry", FakeIndex)
    assert data.fetch_peer_candidates("ODD", 20) == []              # no industry key at all
    assert data.fetch_peer_candidates("NOTHING", 20) == []          # industry with no companies listed


def test_suggested_peers_come_with_their_operating_margins_in_the_same_order():
    got = suggest_for_coca_cola()
    assert got["peer_tickers"] == ["PEP", "MDLZ", "KDP"]
    assert got["peer_operating_margin"] == [0.16046, 0.14567, 0.18255]      # Multiples G43, G45, G44


def test_suggested_peers_give_the_operating_margin_median_checked_against_the_multiples_sheet():
    got = suggest_for_coca_cola()
    assert v.median_of_available(got["peer_operating_margin"], 2) == pytest.approx(0.16046)    # G46


def test_a_peer_with_a_negative_operating_margin_keeps_it():
    losing = quote("LOSS", 90_000, operating_margin=-0.22427)
    got = data.peer_multiples(["LOSS"], fetch_quote=lambda ticker: losing)
    assert got["peer_operating_margin"] == [-0.22427]


# ---------------------------------------------------------------------------
# History: the last few years of the main figures
# ---------------------------------------------------------------------------

ADOBE_YEAR_ENDS = [pd.Timestamp(f"{year}-11-30") for year in (2025, 2024, 2023, 2022)]      # newest first, as Yahoo gives them


def history_ticker(income=None, cash_flow=None):
    """A stand-in for yfinance.Ticker with Adobe's four years (the `history` sheet), as Yahoo
    returns them: dollars, newest year first. Free cash flow has a fifth year Yahoo's income
    statement lacks, as for the real Adobe.
    """
    income_rows = income if income is not None else {
        "Total Revenue": [23769e6, 21505e6, 19409e6, 17606e6],
        "Operating Income": [8706e6, 7741e6, 6650e6, 6098e6],
        "Net Income": [7130e6, 5560e6, 5428e6, 4756e6],
        "Diluted Average Shares": [427e6, 450e6, 459e6, 471e6],
    }
    cash_rows = cash_flow if cash_flow is not None else {
        "Free Cash Flow": [9852e6, 7873e6, 6942e6, 7396e6],
    }

    class FakeHistoryTicker:
        def __init__(self, ticker):
            width = len(next(iter(income_rows.values())))
            self.income_stmt = pd.DataFrame(income_rows, index=ADOBE_YEAR_ENDS[:width]).T
            cash_width = len(next(iter(cash_rows.values())))
            self.cashflow = pd.DataFrame(cash_rows, index=ADOBE_YEAR_ENDS[:cash_width]).T
    return FakeHistoryTicker


def test_the_history_has_the_years_oldest_first_in_millions(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", history_ticker())
    got = data.fetch_yahoo_history("ADBE")
    assert got["years"] == ["FY2022", "FY2023", "FY2024", "FY2025"]
    assert got["revenue"] == [17606, 19409, 21505, 23769]                   # history C8:F8
    assert got["operating_income"] == [6098, 6650, 7741, 8706]              # C9:F9
    assert got["net_income"] == [4756, 5428, 5560, 7130]                    # C10:F10
    assert got["free_cash_flow"] == [7396, 6942, 7873, 9852]                # C11:F11
    assert got["diluted_shares"] == [471, 459, 450, 427]                    # C12:F12


def test_the_history_ratios_match_the_history_sheet_end_to_end(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", history_ticker())
    got = data.get_history("ADBE")
    assert v.ratios_by_year(got["operating_income"], got["revenue"])[-1] == pytest.approx(0.36627540073204595)    # F16
    assert v.yearly_growth(got["revenue"])[-1] == pytest.approx(0.10527784236224136)                              # F15
    assert v.yearly_growth(got["diluted_shares"])[-1] == pytest.approx(-0.051111111111111107)                     # F18


def test_a_year_without_revenue_is_left_out(monkeypatch):
    income = {
        "Total Revenue": [23769e6, float("nan"), 19409e6],
        "Operating Income": [8706e6, 7741e6, 6650e6],
    }
    monkeypatch.setattr("yfinance.Ticker", history_ticker(income=income, cash_flow={"Free Cash Flow": [9852e6, 7873e6, 6942e6]}))
    got = data.fetch_yahoo_history("ADBE")
    assert got["years"] == ["FY2023", "FY2025"]
    assert got["revenue"] == [19409, 23769]


def test_a_figure_yahoo_does_not_have_is_none(monkeypatch):
    income = {"Total Revenue": [23769e6, 21505e6]}                         # no operating income, net income or shares
    monkeypatch.setattr("yfinance.Ticker", history_ticker(income=income, cash_flow={"Free Cash Flow": [9852e6]}))
    got = data.fetch_yahoo_history("ADBE")
    assert got["operating_income"] == [None, None] and got["diluted_shares"] == [None, None]
    assert got["free_cash_flow"] == [None, 9852]                           # only the latest year has one


def test_free_cash_flow_is_matched_to_its_year_not_to_its_position(monkeypatch):
    # Yahoo's cash flow has a year the income statement lacks, so the columns do not line up by position.
    class OffsetTicker:
        def __init__(self, ticker):
            self.income_stmt = pd.DataFrame({"Total Revenue": [200e6, 100e6]}, index=ADOBE_YEAR_ENDS[1:3]).T
            self.cashflow = pd.DataFrame({"Free Cash Flow": [9e6, 8e6, 7e6]}, index=ADOBE_YEAR_ENDS[0:3]).T

    monkeypatch.setattr("yfinance.Ticker", OffsetTicker)
    got = data.fetch_yahoo_history("ADBE")
    assert got["years"] == ["FY2023", "FY2024"]
    assert got["free_cash_flow"] == [7, 8]                                 # not 9 and 8


def test_columns_that_are_not_dates_still_get_a_label(monkeypatch):
    # The page tests fake Yahoo with columns named "latest" and "before".
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    got = data.fetch_yahoo_history("ADBE")
    assert got["years"] == ["before", "latest"] and got["revenue"] == [21505, 23769]


def test_the_money_in_a_history_is_converted_to_dollars_and_the_shares_are_not():
    history = {
        "years": ["FY2024", "FY2025"], "revenue": [1000.0, 2000.0], "operating_income": [None, 500.0],
        "net_income": [100.0, 200.0], "free_cash_flow": [50.0, None], "diluted_shares": [10.0, 9.0],
    }
    got = data.history_in_dollars(history, 0.10)
    assert got["revenue"] == pytest.approx([100.0, 200.0])
    assert got["operating_income"] == [None, pytest.approx(50.0)]
    assert got["free_cash_flow"] == [pytest.approx(5.0), None]
    assert got["diluted_shares"] == [10.0, 9.0] and got["years"] == ["FY2024", "FY2025"]


def test_get_history_converts_with_the_rate_it_is_given(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", history_ticker())
    got = data.get_history("AKER.OL", usd_per_unit=0.1)
    assert got["revenue"][-1] == pytest.approx(2376.9)


def test_get_history_stops_with_a_plain_error_when_yahoo_fails_or_has_nothing():
    def down(ticker):
        raise ConnectionError("no internet")

    with pytest.raises(ValueError, match="Could not get the history from Yahoo Finance: no internet"):
        data.get_history("ADBE", fetch_history=down)
    with pytest.raises(ValueError, match="Yahoo Finance has no yearly figures for ZZZZ"):
        data.get_history("ZZZZ", fetch_history=lambda ticker: {"years": []})


# ---------------------------------------------------------------------------
# Trailing twelve months: the latest four quarters (workbook: `ttm` sheet, Adobe)
# ---------------------------------------------------------------------------

QUARTER_ENDS = [pd.Timestamp(day) for day in ("2026-08-31", "2026-05-31", "2026-02-28", "2025-11-30", "2025-08-31", "2025-05-31")]


def quarterly_ticker(income=None, cash_flow=None, balance=None, income_quarters=QUARTER_ENDS):
    """A stand-in for yfinance.Ticker with Adobe's quarters (the `ttm` sheet), newest first.
    The two older quarters are there to prove they are not counted.
    """
    income_rows = income if income is not None else {
        "Total Revenue": [6760e6, 6618e6, 6398e6, 6194e6, 5900e6, 5800e6],
        "Operating Income": [2354e6, 2238e6, 2418e6, 2261e6, 2000e6, 1900e6],
        "Net Income": [1827e6, 1712e6, 1889e6, 1856e6, 1500e6, 1400e6],
    }
    cash_rows = cash_flow if cash_flow is not None else {
        "Depreciation And Amortization": [215e6, 193e6, 174e6, 184e6, 170e6, 160e6],
    }
    balance_rows = balance if balance is not None else {
        "Long Term Debt": [4766e6, 4766e6],
        "Current Debt": [1597e6, 1500e6],
        "Total Debt": [6363e6, 6266e6],
        "Cash Cash Equivalents And Short Term Investments": [5639e6, 5000e6],
    }

    class FakeQuarterlyTicker:
        def __init__(self, ticker):
            self.quarterly_income_stmt = pd.DataFrame(income_rows, index=income_quarters[:len(next(iter(income_rows.values())))]).T
            self.quarterly_cashflow = pd.DataFrame(cash_rows, index=income_quarters[:len(next(iter(cash_rows.values())))]).T
            self.quarterly_balance_sheet = pd.DataFrame(balance_rows, index=income_quarters[:len(next(iter(balance_rows.values())))]).T
    return FakeQuarterlyTicker


def test_the_last_twelve_months_match_the_ttm_sheet(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", quarterly_ticker())
    got = data.fetch_yahoo_ttm("ADBE")
    assert got["period_end"] == "31 Aug 2026"
    assert got["revenue"] == 25970                             # ttm G6
    assert got["operating_income"] == 9271                     # G7
    assert got["net_income"] == 7284                           # G8
    assert got["depreciation_and_amortisation"] == 766         # G9
    assert got["debt"] == 6363                                 # C14: long-term 4,766 + current 1,597
    assert got["cash_and_investments"] == 5639                 # C15


def test_the_ttm_multiples_match_the_ttm_sheet_end_to_end(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", quarterly_ticker())
    ttm = data.get_ttm("ADBE")
    got = v.ttm_overview(
        share_price=251.47, shares=413, debt=ttm["debt"], cash_and_investments=ttm["cash_and_investments"],
        revenue=ttm["revenue"], operating_income=ttm["operating_income"],
        depreciation_and_amortisation=ttm["depreciation_and_amortisation"], net_income=ttm["net_income"],
    )
    assert got["ev_sales"] == pytest.approx(4.0269969195225261)        # C22
    assert got["ev_ebitda"] == pytest.approx(10.419558633057687)       # C23
    assert got["pe"] == pytest.approx(14.258252333882481)              # C24
    assert got["operating_margin"] == pytest.approx(0.3569888332691567)    # C25


def test_a_quarter_that_has_just_ended_but_is_not_reported_yet_is_skipped(monkeypatch):
    # Like Nvidia's newest column on 19 Nov 2026: the quarter is in the table, with no figures yet.
    income = {
        "Total Revenue": [float("nan"), 6760e6, 6618e6, 6398e6, 6194e6],
        "Operating Income": [float("nan"), 2354e6, 2238e6, 2418e6, 2261e6],
        "Net Income": [float("nan"), 1827e6, 1712e6, 1889e6, 1856e6],
    }
    cash = {"Depreciation And Amortization": [float("nan"), 215e6, 193e6, 174e6, 184e6]}
    monkeypatch.setattr("yfinance.Ticker", quarterly_ticker(income=income, cash_flow=cash))
    got = data.fetch_yahoo_ttm("NVDA")
    assert got["period_end"] == "31 May 2026"                  # the second column: the first has no revenue
    assert got["revenue"] == 6760 + 6618 + 6398 + 6194         # the four reported quarters, not counting the empty one
    assert got["depreciation_and_amortisation"] == 215 + 193 + 174 + 184


def test_fewer_than_four_reported_quarters_leaves_that_figure_out(monkeypatch):
    income = {"Total Revenue": [6760e6, 6618e6, 6398e6], "Operating Income": [2354e6, 2238e6, 2418e6], "Net Income": [1827e6, 1712e6, 1889e6]}
    monkeypatch.setattr("yfinance.Ticker", quarterly_ticker(income=income))
    got = data.fetch_yahoo_ttm("NEW")
    assert got["revenue"] is None and got["operating_income"] is None and got["net_income"] is None


def test_a_missing_long_term_debt_line_is_zero_when_total_debt_is_there(monkeypatch):
    # Like First Solar: total debt of 325 less leases of 217 is its current debt of 108.
    balance = {
        "Current Debt": [108e6], "Total Debt": [325e6], "Cash Cash Equivalents And Short Term Investments": [1624e6],
    }
    monkeypatch.setattr("yfinance.Ticker", quarterly_ticker(balance=balance))
    got = data.fetch_yahoo_ttm("FSLR")
    assert got["debt"] == 108


def test_a_missing_long_term_debt_line_with_no_total_debt_is_not_believed(monkeypatch):
    balance = {"Current Debt": [108e6], "Cash Cash Equivalents And Short Term Investments": [1624e6]}
    monkeypatch.setattr("yfinance.Ticker", quarterly_ticker(balance=balance))
    assert data.fetch_yahoo_ttm("ODD")["debt"] is None
    with pytest.raises(ValueError, match="missing: debt"):
        data.get_ttm("ODD")


def test_missing_current_debt_counts_as_zero(monkeypatch):
    balance = {"Long Term Debt": [4766e6], "Cash Cash Equivalents And Short Term Investments": [5639e6]}
    monkeypatch.setattr("yfinance.Ticker", quarterly_ticker(balance=balance))
    assert data.fetch_yahoo_ttm("ADBE")["debt"] == 4766


def test_missing_da_does_not_stop_the_ttm_but_leaves_the_ev_ebitda_out(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", quarterly_ticker(cash_flow={"Capital Expenditure": [-50e6, -40e6, -30e6, -20e6]}))
    ttm = data.get_ttm("ADBE")
    assert ttm["depreciation_and_amortisation"] is None
    got = v.ttm_overview(
        share_price=251.47, shares=413, debt=ttm["debt"], cash_and_investments=ttm["cash_and_investments"],
        revenue=ttm["revenue"], operating_income=ttm["operating_income"],
        depreciation_and_amortisation=None, net_income=ttm["net_income"],
    )
    assert got["ev_ebitda"] is None and got["ebitda"] is None
    assert got["ev_sales"] == pytest.approx(4.0269969195225261)        # the rest still works


def test_a_cash_flow_quarter_is_matched_to_its_date_not_to_its_position(monkeypatch):
    # The cash flow table lacks the newest quarter, so its columns are shifted by one position.
    # Matching by position would add four wrong quarters; matching by date finds one is missing.
    class Shifted(quarterly_ticker()):
        def __init__(self, ticker):
            super().__init__(ticker)
            self.quarterly_cashflow = pd.DataFrame(
                {"Depreciation And Amortization": [193e6, 174e6, 184e6, 170e6]}, index=QUARTER_ENDS[1:5]
            ).T

    monkeypatch.setattr("yfinance.Ticker", Shifted)
    assert data.fetch_yahoo_ttm("ADBE")["depreciation_and_amortisation"] is None      # the newest quarter has no D&A


def test_the_ttm_money_is_converted_to_dollars_and_the_date_is_left_alone():
    ttm = {
        "period_end": "30 Sep 2026", "revenue": 1000.0, "operating_income": 300.0, "net_income": None,
        "depreciation_and_amortisation": 50.0, "debt": 200.0, "cash_and_investments": 100.0,
    }
    got = data.ttm_in_dollars(ttm, 0.10)
    assert got["revenue"] == pytest.approx(100.0) and got["debt"] == pytest.approx(20.0) and got["net_income"] is None
    assert got["period_end"] == "30 Sep 2026"


def test_get_ttm_stops_with_a_plain_error_when_yahoo_fails():
    def down(ticker):
        raise ConnectionError("no internet")

    with pytest.raises(ValueError, match="Could not get the last twelve months from Yahoo Finance: no internet"):
        data.get_ttm("ADBE", fetch_ttm=down)


def test_get_ttm_names_what_is_missing():
    incomplete = {
        "period_end": "31 Aug 2026", "revenue": 1000.0, "operating_income": None, "net_income": 100.0,
        "depreciation_and_amortisation": 10.0, "debt": 50.0, "cash_and_investments": None,
    }
    with pytest.raises(ValueError, match=r"missing: operating_income, cash_and_investments"):
        data.get_ttm("ODD", fetch_ttm=lambda ticker: incomplete)


def test_columns_that_are_not_dates_give_no_period_date(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())    # the page tests' fake has no quarterly statements at all
    with pytest.raises(ValueError, match="Could not get the last twelve months"):
        data.get_ttm("ADBE")


# ---------------------------------------------------------------------------
# Peers by profile (margin and growth), and a top-up from the wider sector
# ---------------------------------------------------------------------------

# Adobe-like: worth about 94,000, a margin of 36% and growth of 13%. Market values in $ millions.
PROFILE_QUOTES = {
    "ME": quote("ME", 94_000, operating_margin=0.36, revenue_growth=0.13),
    "INTU": quote("INTU", 93_000, operating_margin=0.29, revenue_growth=0.14),
    "SNOW": quote("SNOW", 99_000, operating_margin=-0.22, revenue_growth=0.35),
    "CDNS": quote("CDNS", 85_000, operating_margin=0.30, revenue_growth=0.22),
    "ADSK": quote("ADSK", 60_000, operating_margin=0.28, revenue_growth=0.16),
    "PAYX": quote("PAYX", 40_000, operating_margin=0.40, revenue_growth=0.05),
    "TINY": quote("TINY", 1_000, operating_margin=0.36, revenue_growth=0.13),             # a perfect profile but far too small
    "SEC1": quote("SEC1", 100_000, operating_margin=0.35, revenue_growth=0.12),           # sector: a near-perfect profile
    "SEC2": quote("SEC2", 80_000, operating_margin=0.30, revenue_growth=0.10),
    "SEC3": quote("SEC3", 120_000, operating_margin=0.20, revenue_growth=0.30),
    "SECP": quote("SECP", 90_000, currency="GBp", operating_margin=0.36, revenue_growth=0.13),        # not in dollars
}


def suggest_by_profile(industry, sector=(), **kwargs):
    arguments = dict(
        ticker="ME", company_market_value=94_000, candidates_to_check=20, biggest_size_gap=10, how_many=5,
        sector_candidates_to_check=30, minimum_industry_peers=2,
        fetch_candidates=lambda ticker, how_many: list(industry)[:how_many],
        fetch_sector=lambda ticker, how_many: list(sector)[:how_many],
        fetch_quote=PROFILE_QUOTES.__getitem__,
    )
    arguments.update(kwargs)
    return data.suggest_peers(**arguments)


def test_suggested_peers_are_ranked_by_how_much_they_look_like_the_company():
    got = suggest_by_profile(["SNOW", "CDNS", "INTU", "PAYX", "ADSK", "TINY"])
    # Against 36% and 13%: INTU 0.08, ADSK 0.11, PAYX 0.12, CDNS 0.15, SNOW 0.80. TINY is too small.
    assert got["peer_tickers"] == ["INTU", "ADSK", "PAYX", "CDNS", "SNOW"]
    assert got["peer_source"] == "industry"


def test_without_the_companys_own_profile_the_peers_are_ranked_by_size():
    def no_own_quote(symbol):
        if symbol == "ME":
            raise ConnectionError("no answer")
        return PROFILE_QUOTES[symbol]

    got = suggest_by_profile(["SNOW", "CDNS", "INTU", "PAYX", "ADSK"], fetch_quote=no_own_quote)
    assert got["peer_tickers"] == ["INTU", "SNOW", "CDNS", "ADSK", "PAYX"]            # 93k, 99k, 85k, 60k, 40k around 94k


def test_a_company_with_too_few_industry_peers_is_topped_up_from_its_sector():
    # Only INTU is in the industry list; the sector has three more suitable companies and one in pence.
    got = suggest_by_profile(["INTU"], sector=["SEC3", "SEC1", "SECP", "SEC2", "INTU"])
    assert got["peer_tickers"] == ["INTU", "SEC1", "SEC2", "SEC3"]                      # INTU first, then the sector's by profile
    assert got["peer_source"] == "sector"
    assert "SECP" not in got["peer_tickers"]                                           # not in dollars
    assert got["peer_tickers"].count("INTU") == 1                                      # not listed twice


def test_the_top_up_never_makes_the_list_longer_than_asked_for():
    got = suggest_by_profile(["INTU"], sector=["SEC1", "SEC2", "SEC3"], how_many=3)
    assert got["peer_tickers"] == ["INTU", "SEC1", "SEC2"]


def test_a_company_whose_industry_gives_enough_peers_is_not_topped_up():
    def never(ticker, how_many):
        raise AssertionError("the sector must not be looked up")

    got = suggest_by_profile(["INTU", "ADSK"], fetch_sector=never)                      # two suitable peers is enough
    assert got["peer_tickers"] == ["INTU", "ADSK"] and got["peer_source"] == "industry"


def test_a_company_with_no_industry_peers_gets_the_sectors():
    got = suggest_by_profile([], sector=["SEC2", "SEC1"])
    assert got["peer_tickers"] == ["SEC1", "SEC2"] and got["peer_source"] == "sector"


def test_without_any_suitable_peers_even_in_the_sector_the_lists_are_empty():
    got = suggest_by_profile(["TINY"], sector=["TINY", "SECP"])
    assert got["peer_tickers"] == [] and got["peer_source"] is None


def test_a_sector_list_that_cannot_be_had_just_means_no_top_up():
    def down(ticker, how_many):
        raise ConnectionError("no internet")

    got = suggest_by_profile(["INTU"], fetch_sector=down)
    assert got["peer_tickers"] == ["INTU"] and got["peer_source"] == "industry"


def test_sector_companies_that_cannot_be_read_just_mean_no_top_up():
    def sector_unreadable(symbol):
        if symbol.startswith("SEC"):
            raise ConnectionError("no answer")
        return PROFILE_QUOTES[symbol]

    got = suggest_by_profile(["INTU"], sector=["SEC1", "SEC2"], fetch_quote=sector_unreadable)
    assert got["peer_tickers"] == ["INTU"] and got["peer_source"] == "industry"


def test_the_top_up_applies_the_same_size_filter():
    got = suggest_by_profile(["INTU"], sector=["TINY"])                                # a perfect profile, but 94 times too small
    assert got["peer_tickers"] == ["INTU"]


# The sector lookup that really talks to Yahoo, with yfinance faked.

class FakeSector:
    """A stand-in for yfinance.Sector: the sector holds the company and two others."""
    def __init__(self, key):
        self.top_companies = None if key == "nothing" else pd.DataFrame(
            {"name": ["a", "b", "c"]}, index=["ME", "AAA", "BBB"]
        )


def test_fetch_sector_candidates_lists_the_sector_without_the_company_itself(monkeypatch):
    FakeInfoTicker.infos = {"ME": {"sectorKey": "technology"}}
    monkeypatch.setattr("yfinance.Ticker", FakeInfoTicker)
    monkeypatch.setattr("yfinance.Sector", FakeSector)
    assert data.fetch_sector_candidates("ME", 30) == ["AAA", "BBB"]
    assert data.fetch_sector_candidates("ME", 1) == ["AAA"]


def test_fetch_sector_candidates_gives_nothing_when_yahoo_has_no_sector(monkeypatch):
    FakeInfoTicker.infos = {"ODD": {}, "NOTHING": {"sectorKey": "nothing"}}
    monkeypatch.setattr("yfinance.Ticker", FakeInfoTicker)
    monkeypatch.setattr("yfinance.Sector", FakeSector)
    assert data.fetch_sector_candidates("ODD", 30) == []
    assert data.fetch_sector_candidates("NOTHING", 30) == []


# ---------------------------------------------------------------------------
# Stockholders' equity in the data package (for the return on invested capital)
# ---------------------------------------------------------------------------

def balance_with_equity(**lines):
    """Adobe's fake balance sheet with equity lines added: each is {line name: (latest, year before)}."""
    return dict(ADOBE_YAHOO_BALANCE, **lines)


def test_adobes_snapshot_carries_the_equity_from_the_history_sheet():
    assert data.get_company_data("ADBE", source="snapshot")["stockholders_equity"] == 11623      # history C26


def test_the_yahoo_package_has_the_equity_when_yahoo_has_it(monkeypatch):
    balance = balance_with_equity(**{"Stockholders Equity": (11623e6, 11213e6)})
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(balance=balance))
    assert data.get_company_data("ADBE", source="yahoo")["stockholders_equity"] == pytest.approx(11623)


def test_the_yahoo_package_falls_back_to_common_stock_equity(monkeypatch):
    balance = balance_with_equity(**{"Common Stock Equity": (9000e6, 8000e6)})
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(balance=balance))
    assert data.get_company_data("ADBE", source="yahoo")["stockholders_equity"] == pytest.approx(9000)


def test_the_yahoo_package_simply_lacks_the_equity_when_yahoo_does_not_have_it(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())               # the fake balance sheet has no equity line
    package = data.get_company_data("ADBE", source="yahoo")
    assert "stockholders_equity" not in package                                    # optional: the page says "Not meaningful"


def test_the_equity_of_a_company_in_another_currency_is_converted_to_dollars(monkeypatch):
    balance = balance_with_equity(**{"Stockholders Equity": (10_000e6, 9_000e6)})
    info = dict(ADOBE_YAHOO_INFO, financialCurrency="NOK", currency="NOK")
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(balance=balance, info=info, fx_rates={"NOKUSD=X": 0.10}))
    assert data.get_company_data("AKER.OL", source="yahoo")["stockholders_equity"] == pytest.approx(1000)


# ---------------------------------------------------------------------------
# When Yahoo limits the server: one retry, and a plain message
# ---------------------------------------------------------------------------

def test_a_quote_with_nothing_in_it_is_called_empty():
    assert data._quote_is_empty({})
    assert data._quote_is_empty({"beta": 1.3, "trailingPE": 20})                    # no name, price or share count
    assert not data._quote_is_empty({"longName": "Adobe Inc."})
    assert not data._quote_is_empty({"currentPrice": 240.74})
    assert not data._quote_is_empty({"sharesOutstanding": 389_200_000})


def ticker_that_is_empty_at_first(empty_answers):
    """A stand-in for yfinance.Ticker whose first `empty_answers` requests get an empty quote, then Adobe's."""
    requests = []

    class Flaky(fake_statements_ticker()):
        def __init__(self, ticker):
            super().__init__(ticker)
            requests.append(ticker)
            if len(requests) <= empty_answers:
                self.info = {}

    return Flaky, requests


def test_an_empty_quote_is_asked_for_again_once_after_a_pause(monkeypatch, no_waiting):
    flaky, requests = ticker_that_is_empty_at_first(empty_answers=2)        # the statements request, then the first info request
    monkeypatch.setattr("yfinance.Ticker", flaky)
    got = data.fetch_yahoo_statements("ADBE")
    assert got["company_name"] == "Adobe Inc." and got["share_price"] == 240.74    # the retry got the quote
    assert no_waiting == [data.YAHOO_RETRY_PAUSE_SECONDS]                          # it waited once
    assert len(requests) == 3                                                      # statements, quote, quote again


def test_a_good_quote_is_not_asked_for_twice_and_nothing_is_waited_for(monkeypatch, no_waiting):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    data.fetch_yahoo_statements("ADBE")
    assert no_waiting == []


def test_a_live_quote_is_also_asked_for_again_when_empty(monkeypatch, no_waiting):
    flaky, requests = ticker_that_is_empty_at_first(empty_answers=1)
    monkeypatch.setattr("yfinance.Ticker", flaky)
    assert data.fetch_yahoo_quote("ADBE") == {"share_price": 240.74, "beta": 1.383}
    assert no_waiting == [data.YAHOO_RETRY_PAUSE_SECONDS] and len(requests) == 2


def test_the_pause_is_two_seconds():
    assert data.YAHOO_RETRY_PAUSE_SECONDS == 2


def test_when_yahoo_stays_empty_the_reader_gets_a_plain_message_not_a_list_of_fields(monkeypatch):
    # The statements arrive but Yahoo's quote is empty twice, as on the live app on 18 and 20 Nov 2026.
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info={}))
    with pytest.raises(ValueError) as error:
        data.get_company_data("NVDA", source="yahoo")
    assert str(error.value) == data.YAHOO_BUSY_MESSAGE
    assert "company_name" not in str(error.value) and "try again in a few minutes" in str(error.value)


def test_the_plain_message_says_adobe_still_works():
    assert "Adobe still works from a frozen snapshot" in data.YAHOO_BUSY_MESSAGE


def test_when_yahoo_has_nothing_at_all_the_old_message_about_the_ticker_stays(monkeypatch):
    # No quote and no statements: more likely a ticker Yahoo does not know than Yahoo being busy.
    empty = {"Total Revenue": (float("nan"), float("nan"))}
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(income=empty, cash_flow={"X": (1.0, 1.0)}, balance={"Y": (1.0, 1.0)}, info={}))
    with pytest.raises(ValueError, match="has no figures for ZZZZ. Check that the ticker is right"):
        data.get_company_data("ZZZZ", source="yahoo")


def test_a_quote_with_only_some_figures_missing_still_names_them(monkeypatch):
    info = {key: value for key, value in ADOBE_YAHOO_INFO.items() if key != "beta"}      # only the beta is missing
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info=info))
    with pytest.raises(ValueError, match="did not supply, for ADBE: beta"):
        data.get_company_data("ADBE", source="yahoo")


def test_a_live_quote_with_neither_price_nor_beta_gets_the_plain_message():
    with pytest.raises(ValueError) as error:
        data.live_source("ADBE", fetch_quote=lambda ticker: {"share_price": None, "beta": None})
    assert str(error.value) == data.YAHOO_BUSY_MESSAGE


def test_a_live_quote_missing_only_one_figure_keeps_its_own_message():
    with pytest.raises(ValueError, match="did not give a beta"):
        data.live_source("ADBE", fetch_quote=lambda ticker: {"share_price": 240.74, "beta": None})
    with pytest.raises(ValueError, match="did not give a usable share price"):
        data.live_source("ADBE", fetch_quote=lambda ticker: {"share_price": None, "beta": 1.38})


def test_adobe_falls_back_to_the_snapshot_when_yahoo_gives_nothing(monkeypatch):
    # What the live app does when Yahoo limits it: Adobe keeps working from the frozen snapshot.
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info={}))
    package, source = data.get_company_data_with_fallback("ADBE")
    assert source == data.FALLBACK_SOURCE == "snapshot"
    assert package["share_price"] == 251.47                                          # the snapshot's price, not a live one


# ---------------------------------------------------------------------------
# Financial Modeling Prep (FMP): the backup when Yahoo is limiting the server
# ---------------------------------------------------------------------------
# The rows below are trimmed to the lines the code reads, with the line names and the dollar (not
# million) units Financial Modeling Prep's "stable" interface used when Haavard and Claude tried
# Adobe on 20 Nov 2026. The values are round made-up numbers in Adobe's size, so the sums are easy
# to check by hand.

FMP_PROFILE = [{
    "symbol": "ADBE", "companyName": "Adobe Inc.", "price": 250.0, "marketCap": 100_000_000_000,
    "beta": 1.5, "currency": "USD",
}]
FMP_ANNUAL_INCOME = [      # the latest year first, as FMP sends them
    {"date": "2025-11-28", "fiscalYear": "2025", "reportedCurrency": "USD", "revenue": 24_000_000_000,
     "operatingIncome": 9_000_000_000, "netIncome": 7_000_000_000, "incomeTaxExpense": 1_500_000_000,
     "incomeBeforeTax": 8_500_000_000, "interestExpense": 250_000_000, "weightedAverageShsOutDil": 400_000_000},
    {"date": "2024-11-29", "fiscalYear": "2024", "reportedCurrency": "USD", "revenue": 21_500_000_000,
     "operatingIncome": 7_800_000_000, "netIncome": 5_600_000_000, "incomeTaxExpense": 1_200_000_000,
     "incomeBeforeTax": 6_800_000_000, "interestExpense": 200_000_000, "weightedAverageShsOutDil": 430_000_000},
    {"date": "2023-12-01", "fiscalYear": "2023", "reportedCurrency": "USD", "revenue": 19_000_000_000,
     "operatingIncome": 7_000_000_000, "netIncome": 5_400_000_000, "incomeTaxExpense": 1_000_000_000,
     "incomeBeforeTax": 6_400_000_000, "interestExpense": 150_000_000, "weightedAverageShsOutDil": 460_000_000},
]
FMP_ANNUAL_CASH = [
    {"date": "2025-11-28", "depreciationAndAmortization": 800_000_000, "capitalExpenditure": -180_000_000,
     "changeInWorkingCapital": 600_000_000, "freeCashFlow": 9_000_000_000},
    {"date": "2024-11-29", "depreciationAndAmortization": 700_000_000, "capitalExpenditure": -150_000_000,
     "changeInWorkingCapital": 500_000_000, "freeCashFlow": 7_500_000_000},
    {"date": "2023-12-01", "depreciationAndAmortization": 600_000_000, "capitalExpenditure": -120_000_000,
     "changeInWorkingCapital": 400_000_000, "freeCashFlow": 6_900_000_000},
]
FMP_ANNUAL_BALANCE = [{
    "date": "2025-11-28", "longTermDebt": 6_000_000_000, "shortTermDebt": 500_000_000,
    "cashAndShortTermInvestments": 6_500_000_000, "totalStockholdersEquity": 11_000_000_000,
}]
FMP_QUARTER_INCOME = [      # five quarters, the latest first; only the latest four are summed
    {"date": "2026-08-28", "revenue": 6_000_000_000, "operatingIncome": 2_400_000_000, "netIncome": 1_800_000_000},
    {"date": "2026-05-29", "revenue": 5_900_000_000, "operatingIncome": 2_300_000_000, "netIncome": 1_700_000_000},
    {"date": "2026-02-27", "revenue": 5_800_000_000, "operatingIncome": 2_200_000_000, "netIncome": 1_600_000_000},
    {"date": "2025-11-28", "revenue": 5_700_000_000, "operatingIncome": 2_100_000_000, "netIncome": 1_500_000_000},
    {"date": "2025-08-29", "revenue": 5_000_000_000, "operatingIncome": 1_000_000_000, "netIncome": 1_000_000_000},
]
FMP_QUARTER_CASH = [
    {"date": row["date"], "depreciationAndAmortization": 200_000_000} for row in FMP_QUARTER_INCOME
]
FMP_QUARTER_BALANCE = [{
    "date": "2026-08-28", "longTermDebt": 6_000_000_000, "shortTermDebt": 400_000_000,
    "cashAndShortTermInvestments": 7_000_000_000,
}]


def fake_fmp(**replacements):
    """Return a stand-in for data._fmp_get that serves Adobe-like rows, and records the questions.

    `replacements` swaps the answer for one request, by the name "path" or "path_quarter".
    """
    answers = {
        "profile": FMP_PROFILE,
        "income-statement": FMP_ANNUAL_INCOME,
        "income-statement_quarter": FMP_QUARTER_INCOME,
        "cash-flow-statement": FMP_ANNUAL_CASH,
        "cash-flow-statement_quarter": FMP_QUARTER_CASH,
        "balance-sheet-statement": FMP_ANNUAL_BALANCE,
        "balance-sheet-statement_quarter": FMP_QUARTER_BALANCE,
        "stock-peers": [
            {"symbol": "ADBE", "mktCap": 100_000_000_000},         # the company itself: left out
            {"symbol": "AAA", "mktCap": 90_000_000_000},
            {"symbol": "BBB", "mktCap": 120_000_000_000},
            {"symbol": "HUGE", "mktCap": 3_000_000_000_000},       # thirty times bigger: too big
        ],
        "key-metrics-ttm": [{"evToSalesTTM": 6.0, "evToEBITDATTM": 15.0}],
        "ratios-ttm": [{"priceToEarningsRatioTTM": 25.0, "priceToSalesRatioTTM": 7.5, "operatingProfitMarginTTM": 0.3}],
    }
    answers.update(replacements)
    asked = []

    def get(path, **parameters):
        asked.append((path, parameters))
        name = path + ("_quarter" if parameters.get("period") == "quarter" else "")
        return answers[name]

    get.asked = asked
    return get


def with_fmp(monkeypatch, **replacements):
    """Switch on the backup for a test: a key in the environment and the fake answers."""
    monkeypatch.setenv("FMP_API_KEY", "test-key-not-real")
    fake = fake_fmp(**replacements)
    monkeypatch.setattr("data._fmp_get", fake)
    return fake


class FakeResponse:
    """A stand-in for what the requests library hands back."""

    def __init__(self, status_code=200, body=None):
        self.status_code, self._body = status_code, body if body is not None else [{"ok": True}]

    def json(self):
        return self._body


def test_the_fmp_sources_are_registered():
    assert "fmp" in data.SOURCES and "live_fmp" in data.SOURCES


def test_there_is_no_key_unless_one_is_set(monkeypatch):
    assert not data.fmp_available()
    monkeypatch.setenv("FMP_API_KEY", "abc")
    assert data.fmp_available()
    monkeypatch.setenv("FMP_API_KEY", "")
    assert not data.fmp_available()


def test_asking_fmp_without_a_key_stops_with_a_plain_error():
    with pytest.raises(data.SourceUnavailable, match="No Financial Modeling Prep key"):
        data._fmp_get("profile", symbol="ADBE")


def test_fmp_get_sends_the_key_and_the_question_and_returns_the_rows(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret-123")
    sent = {}

    def fake_get(url, params, timeout):
        sent.update(url=url, params=params, timeout=timeout)
        return FakeResponse(200, [{"symbol": "ADBE"}])

    monkeypatch.setattr("requests.get", fake_get)
    assert data._fmp_get("profile", symbol="ADBE") == [{"symbol": "ADBE"}]
    assert sent["url"] == "https://financialmodelingprep.com/stable/profile"
    assert sent["params"] == {"symbol": "ADBE", "apikey": "secret-123"}
    assert sent["timeout"] == data.FMP_TIMEOUT_SECONDS


def test_fmp_get_remembers_an_answer_so_the_daily_limit_is_not_wasted(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "k")
    calls = []
    monkeypatch.setattr("requests.get", lambda url, params, timeout: calls.append(url) or FakeResponse())
    data._fmp_get("profile", symbol="ADBE")
    data._fmp_get("profile", symbol="ADBE")
    data._fmp_get("profile", symbol="AAPL")             # a different question is asked again
    assert len(calls) == 2


def test_fmp_get_asks_again_once_the_remembered_answer_is_old(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "k")
    calls = []
    monkeypatch.setattr("requests.get", lambda url, params, timeout: calls.append(url) or FakeResponse())
    clock = [1000.0]
    monkeypatch.setattr("data.time.time", lambda: clock[0])
    data._fmp_get("profile", symbol="ADBE")
    clock[0] += data.FMP_CACHE_SECONDS + 1
    data._fmp_get("profile", symbol="ADBE")
    assert len(calls) == 2


@pytest.mark.parametrize("status, message", [
    (429, "250 requests"),
    (401, "did not accept the key"),
    (403, "did not accept the key"),
    (500, "HTTP 500"),
])
def test_fmp_get_turns_each_kind_of_refusal_into_a_source_unavailable_error(monkeypatch, status, message):
    monkeypatch.setenv("FMP_API_KEY", "secret-123")
    monkeypatch.setattr("requests.get", lambda url, params, timeout: FakeResponse(status))
    with pytest.raises(data.SourceUnavailable, match=message) as error:
        data._fmp_get("profile", symbol="ADBE")
    assert "secret-123" not in str(error.value)


def test_a_company_the_free_plan_does_not_cover_is_a_plain_error_not_a_reason_to_switch(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "k")
    monkeypatch.setattr("requests.get", lambda url, params, timeout: FakeResponse(402))
    with pytest.raises(data.UnknownCompany, match="free plan does not cover NOVO"):
        data._fmp_get("profile", symbol="NOVO")


def test_an_unreachable_fmp_never_puts_the_key_in_the_message(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "secret-123")

    def broken(url, params, timeout):
        raise ConnectionError("failed for https://x/?apikey=secret-123")

    monkeypatch.setattr("requests.get", broken)
    with pytest.raises(data.SourceUnavailable) as error:
        data._fmp_get("profile", symbol="ADBE")
    assert "secret-123" not in str(error.value)
    assert "ConnectionError" in str(error.value)


def test_fetch_fmp_statements_turns_dollars_into_millions_and_picks_the_lines(monkeypatch):
    with_fmp(monkeypatch)
    got = data.fetch_fmp_statements("ADBE")
    assert got["company_name"] == "Adobe Inc."
    assert got["revenue"] == pytest.approx(24000)
    assert got["prior_year_revenue"] == pytest.approx(21500)       # the second row
    assert got["ebit"] == pytest.approx(9000)
    assert got["capex"] == pytest.approx(180)                      # FMP's -180 made positive
    assert got["interest_expense"] == pytest.approx(250)
    assert got["cash_from_working_capital"] == pytest.approx(600)
    assert got["long_term_debt"] == pytest.approx(6000)
    assert got["current_debt"] == pytest.approx(500)
    assert got["cash_and_investments"] == pytest.approx(6500)
    assert got["stockholders_equity"] == pytest.approx(11000)
    assert got["shares"] == pytest.approx(400)                     # market value 100,000 / price 250
    assert got["share_price"] == 250.0
    assert got["beta"] == 1.5
    assert got["usd_per_statement_unit"] == 1.0 and got["usd_per_price_unit"] == 1.0


def test_fetch_fmp_statements_leaves_out_what_fmp_did_not_send(monkeypatch):
    thin_cash = [{key: value for key, value in FMP_ANNUAL_CASH[0].items() if key != "capitalExpenditure"}]
    with_fmp(monkeypatch, **{"cash-flow-statement": thin_cash})
    assert data.fetch_fmp_statements("ADBE")["capex"] is None


def test_a_company_reporting_in_another_currency_comes_back_without_a_rate(monkeypatch):
    krone = [dict(FMP_ANNUAL_INCOME[0], reportedCurrency="NOK")] + FMP_ANNUAL_INCOME[1:]
    with_fmp(monkeypatch, **{"income-statement": krone})
    got = data.fetch_fmp_statements("XYZ")
    assert got["statement_currency"] == "NOK" and got["usd_per_statement_unit"] is None


def test_the_fmp_source_builds_the_same_package_as_the_yahoo_source(monkeypatch):
    with_fmp(monkeypatch)
    package = data.get_company_data("adbe", source="fmp")
    assert package["ticker"] == "ADBE"
    assert package["revenue"] == pytest.approx(24000)
    assert package["debt"] == pytest.approx(6500)                  # 6,000 long term + 500 current
    assert package["interest_expense"] == pytest.approx(250)
    assert "cost_of_debt_is_fallback" not in package


def test_the_fmp_package_has_the_same_fields_as_the_yahoo_package(monkeypatch):
    with_fmp(monkeypatch)
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    fmp, yahoo = set(data.get_company_data("ADBE", source="fmp")), set(data.get_company_data("ADBE", source="yahoo"))
    assert yahoo <= fmp                                  # everything the page reads from Yahoo's package is there
    assert fmp - yahoo <= {"stockholders_equity"}        # Yahoo's fake has no equity line; FMP always sends one


def test_the_fmp_source_estimates_the_cost_of_debt_when_there_is_no_interest_expense(monkeypatch):
    no_interest = [dict(FMP_ANNUAL_INCOME[0], interestExpense=None)] + FMP_ANNUAL_INCOME[1:]
    with_fmp(monkeypatch, **{"income-statement": no_interest})
    package = data.get_company_data("ADBE", source="fmp")
    assert package["cost_of_debt_is_fallback"] is True


def test_an_unknown_ticker_at_fmp_is_a_plain_error_that_names_fmp(monkeypatch):
    with_fmp(monkeypatch, profile=[])
    with pytest.raises(data.UnknownCompany, match="Financial Modeling Prep has no figures for NOPE"):
        data.get_company_data("NOPE", source="fmp")


def test_fmp_share_count_is_market_value_over_price(monkeypatch):
    with_fmp(monkeypatch, profile=[dict(FMP_PROFILE[0], price=None)])
    assert data.fetch_fmp_statements("ADBE")["shares"] is None


def test_fetch_fmp_quote_gives_price_and_beta(monkeypatch):
    with_fmp(monkeypatch)
    assert data.fetch_fmp_quote("ADBE") == {"share_price": 250.0, "beta": 1.5}


def test_live_fmp_source_is_the_snapshot_with_fmps_price_and_beta(monkeypatch):
    with_fmp(monkeypatch)
    package = data.get_company_data("ADBE", source="live_fmp")
    assert package["share_price"] == 250.0 and package["beta"] == 1.5
    assert package["revenue"] == EXPECTED_SNAPSHOT["revenue"]


def test_live_fmp_source_refuses_a_quote_without_a_price(monkeypatch):
    with_fmp(monkeypatch, profile=[dict(FMP_PROFILE[0], price=None)])
    with pytest.raises(data.SourceUnavailable):
        data.get_company_data("ADBE", source="live_fmp")


def test_fmp_history_is_oldest_first_in_millions_with_cash_flow_matched_by_date(monkeypatch):
    with_fmp(monkeypatch)
    history = data.fetch_fmp_history("ADBE")
    assert history["years"] == ["FY2023", "FY2024", "FY2025"]
    assert history["revenue"] == pytest.approx([19000, 21500, 24000])
    assert history["operating_income"] == pytest.approx([7000, 7800, 9000])
    assert history["net_income"] == pytest.approx([5400, 5600, 7000])
    assert history["free_cash_flow"] == pytest.approx([6900, 7500, 9000])
    assert history["diluted_shares"] == pytest.approx([460, 430, 400])


def test_fmp_history_leaves_a_year_without_cash_flow_blank_not_wrong(monkeypatch):
    with_fmp(monkeypatch, **{"cash-flow-statement": FMP_ANNUAL_CASH[:1]})        # only the latest year
    history = data.fetch_fmp_history("ADBE")
    assert history["free_cash_flow"] == [None, None, pytest.approx(9000)]


def test_get_history_any_switches_to_fmp_when_yahoo_is_not_answering(monkeypatch):
    with_fmp(monkeypatch)
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)           # Yahoo is cooling down
    history = data.get_history_any("ADBE")
    assert history["source"] == "fmp"
    assert history["years"] == ["FY2023", "FY2024", "FY2025"]
    assert history["revenue"] == pytest.approx([19000, 21500, 24000])


def test_get_history_any_says_yahoo_when_yahoo_answered(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    with_fmp(monkeypatch)
    monkeypatch.setattr("data.fetch_fmp_history", lambda ticker: pytest.fail("asked FMP"))
    assert data.get_history_any("ADBE")["source"] == "yahoo"


def test_fmp_ttm_adds_the_latest_four_quarters_and_reads_the_latest_balance_sheet(monkeypatch):
    with_fmp(monkeypatch)
    ttm = data.fetch_fmp_ttm("ADBE")
    assert ttm["period_end"] == "28 Aug 2026"
    assert ttm["revenue"] == pytest.approx(23400)                  # 6,000 + 5,900 + 5,800 + 5,700
    assert ttm["operating_income"] == pytest.approx(9000)
    assert ttm["net_income"] == pytest.approx(6600)
    assert ttm["depreciation_and_amortisation"] == pytest.approx(800)
    assert ttm["debt"] == pytest.approx(6400)
    assert ttm["cash_and_investments"] == pytest.approx(7000)


def test_fmp_ttm_without_d_and_a_leaves_it_blank_so_ev_ebitda_is_left_out(monkeypatch):
    with_fmp(monkeypatch, **{"cash-flow-statement_quarter": [{"date": "2026-08-28"}]})
    assert data.fetch_fmp_ttm("ADBE")["depreciation_and_amortisation"] is None


def test_fmp_ttm_asks_for_no_more_rows_than_the_free_plan_allows(monkeypatch):
    fake = with_fmp(monkeypatch)
    data.fetch_fmp_ttm("ADBE")
    assert all(parameters.get("limit", 1) <= data.FMP_ROWS for _, parameters in fake.asked)


def test_get_ttm_any_tags_the_provider(monkeypatch):
    with_fmp(monkeypatch)
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)           # Yahoo is cooling down
    got = data.get_ttm_any("ADBE")
    assert got["source"] == "fmp" and got["revenue"] == pytest.approx(23400)


def test_the_fmp_peer_list_leaves_out_the_company_itself(monkeypatch):
    with_fmp(monkeypatch)
    peers = data.fetch_fmp_peer_list("ADBE")
    assert [peer["ticker"] for peer in peers] == ["AAA", "BBB", "HUGE"]
    assert peers[0]["market_cap"] == pytest.approx(90000)


def test_an_fmp_peer_quote_gives_the_multiples_and_margin(monkeypatch):
    with_fmp(monkeypatch)
    quote = data.fetch_fmp_peer_quote("AAA")
    assert (quote["ev_sales"], quote["ev_ebitda"], quote["pe"], quote["operating_margin"]) == (6.0, 15.0, 25.0, 0.3)
    assert quote["ps"] == 7.5                                       # FMP's "priceToSalesRatioTTM"
    assert quote["forward_pe"] is None                              # left out: it would cost another request


def test_fmp_peer_suggestions_keep_the_ones_close_in_size_and_fetch_their_multiples(monkeypatch):
    with_fmp(monkeypatch)
    figures = data.suggest_peers_fmp("ADBE", 100000, 10, 5)
    assert figures["peer_tickers"] == ["AAA", "BBB"]               # HUGE is thirty times the size
    assert figures["peer_ev_sales"] == [6.0, 6.0]
    assert figures["peer_ps"] == [7.5, 7.5]
    assert figures["peer_forward_pe"] == [None, None]
    assert figures["peer_operating_margin"] == [0.3, 0.3]
    assert figures["peer_source"] == "industry"


def test_fmp_peer_suggestions_with_nobody_in_range_say_so(monkeypatch):
    with_fmp(monkeypatch, **{"stock-peers": []})
    figures = data.suggest_peers_fmp("ADBE", 100000, 10, 5)
    assert figures["peer_tickers"] == [] and figures["peer_source"] is None


def test_fmp_peer_suggestions_take_no_more_than_asked_for(monkeypatch):
    with_fmp(monkeypatch)
    assert len(data.suggest_peers_fmp("ADBE", 100000, 10, 1)["peer_tickers"]) == 1


def test_peer_multiples_any_switches_to_fmp_and_says_so(monkeypatch):
    with_fmp(monkeypatch)
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)
    figures = data.peer_multiples_any(["AAA", "BBB"])
    assert figures["peer_data_source"] == "fmp" and figures["peer_pe"] == [25.0, 25.0]


def test_suggest_peers_any_says_which_provider_gave_the_peers(monkeypatch):
    with_fmp(monkeypatch)
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)
    assert data.suggest_peers_any("ADBE", 100000, 20, 10, 5, 30, 2)["peer_data_source"] == "fmp"


# --- Yahoo first, FMP second ---

def test_yahoo_answers_first_and_fmp_is_not_asked(monkeypatch):
    with_fmp(monkeypatch)
    got = data._yahoo_then_fmp(lambda: "from yahoo", lambda: pytest.fail("asked FMP"))
    assert got == ("from yahoo", "yahoo")


def test_fmp_answers_when_yahoo_is_not_answering(monkeypatch):
    with_fmp(monkeypatch)

    def yahoo():
        raise data.SourceUnavailable("Yahoo is down.")

    assert data._yahoo_then_fmp(yahoo, lambda: "from fmp") == ("from fmp", "fmp")


def test_without_a_key_yahoos_own_error_comes_through(monkeypatch):
    def yahoo():
        raise data.SourceUnavailable("Yahoo is down.")

    with pytest.raises(data.SourceUnavailable, match="Yahoo is down"):
        data._yahoo_then_fmp(yahoo, lambda: pytest.fail("asked FMP without a key"))


def test_a_real_company_problem_at_yahoo_is_not_sent_to_fmp(monkeypatch):
    with_fmp(monkeypatch)

    def yahoo():
        raise ValueError("Yahoo Finance has no figures for NOPE.")

    with pytest.raises(ValueError, match="no figures for NOPE") as error:
        data._yahoo_then_fmp(yahoo, lambda: pytest.fail("asked FMP"))
    assert not isinstance(error.value, data.SourceUnavailable)


def test_when_both_are_down_the_error_names_both(monkeypatch):
    with_fmp(monkeypatch)

    def yahoo():
        raise data.SourceUnavailable("Yahoo is down.")

    def fmp():
        raise data.SourceUnavailable("FMP is down.")

    with pytest.raises(data.SourceUnavailable) as error:
        data._yahoo_then_fmp(yahoo, fmp)
    assert "Yahoo is down." in str(error.value) and "FMP is down." in str(error.value)


def test_while_yahoo_is_cooling_down_it_is_not_asked_at_all(monkeypatch):
    with_fmp(monkeypatch)
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)
    assert data._yahoo_then_fmp(lambda: pytest.fail("asked Yahoo"), lambda: "from fmp") == ("from fmp", "fmp")


def test_get_other_company_data_uses_yahoo_when_it_works(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    with_fmp(monkeypatch)
    package, source = data.get_other_company_data("ADBE")
    assert source == "yahoo" and package["share_price"] == 240.74


def test_get_other_company_data_falls_back_to_fmp_when_yahoo_gives_nothing(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info={}))
    with_fmp(monkeypatch)
    package, source = data.get_other_company_data("ADBE")
    assert source == "fmp" and package["share_price"] == 250.0


def test_a_yahoo_that_gave_nothing_starts_the_cool_down(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info={}))
    with_fmp(monkeypatch)
    data.get_other_company_data("ADBE")
    assert data._yahoo_cooling_down()


# --- Adobe: live, then live from FMP, then the snapshot ---

def test_adobe_uses_fmps_quote_when_yahoo_is_not_answering(monkeypatch):
    class EmptyTicker:
        def __init__(self, ticker):
            self.info = {}

    monkeypatch.setattr("yfinance.Ticker", EmptyTicker)
    with_fmp(monkeypatch)
    package, source_used = data.get_company_data_with_fallback("ADBE")
    assert source_used == "live_fmp"
    assert package["share_price"] == 250.0


def test_adobe_uses_the_snapshot_when_neither_provider_answers(monkeypatch):
    class EmptyTicker:
        def __init__(self, ticker):
            self.info = {}

    monkeypatch.setattr("yfinance.Ticker", EmptyTicker)
    with_fmp(monkeypatch, profile=[dict(FMP_PROFILE[0], price=None)])
    package, source_used = data.get_company_data_with_fallback("ADBE")
    assert source_used == "snapshot" and package == EXPECTED_SNAPSHOT


def test_adobe_skips_yahoo_while_it_is_cooling_down(monkeypatch):
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)
    monkeypatch.setattr("yfinance.Ticker", lambda ticker: pytest.fail("asked Yahoo"))
    with_fmp(monkeypatch)
    assert data.get_company_data_with_fallback("ADBE")[1] == "live_fmp"


# ---------------------------------------------------------------------------
# News and management: headlines and top officers from Yahoo (not Excel: text, no maths)
# ---------------------------------------------------------------------------

def news_item(title="Adobe launches something", provider="Zacks", published="2026-11-20T20:13:24Z",
              link="https://finance.yahoo.com/news/a.html"):
    """One headline as yfinance gives it: everything of interest sits under "content"."""
    return {"id": "x", "content": {
        "title": title, "pubDate": published, "provider": {"displayName": provider},
        "canonicalUrl": {"url": link}, "clickThroughUrl": {"url": link},
    }}


class FakeNewsTicker:
    """A stand-in for yfinance.Ticker that has news and officers (in .info, as Yahoo has them)."""
    news_items = []
    officers = []

    def __init__(self, ticker):
        self.news = list(self.news_items)
        self.info = {"companyOfficers": list(self.officers), "currentPrice": 10.0, "beta": 1.0}


@pytest.mark.parametrize("address, expected", [
    ("https://finance.yahoo.com/news/a.html", "https://finance.yahoo.com/news/a.html"),
    ("http://example.com/plain", None),                      # not https
    ("javascript:alert(1)", None),
    ("https://example.com/has a space", None),
    ("", None), (None, None), (42, None),
])
def test_only_plain_https_links_are_kept(address, expected):
    assert data.safe_link(address) == expected


def test_tidy_text_squeezes_stray_spaces_and_ignores_anything_that_is_not_text():
    assert data.tidy_text("  Mr. Shantanu   Narayen ") == "Mr. Shantanu Narayen"
    assert data.tidy_text(None) == "" and data.tidy_text(5) == ""


def test_headlines_come_back_tidy_in_yahoos_order(monkeypatch):
    FakeNewsTicker.news_items = [
        news_item("First   headline", "Zacks", "2026-11-20T20:13:24Z"),
        news_item("Second headline", "Simply Wall St.", "2026-11-19T08:00:00Z"),
    ]
    monkeypatch.setattr("yfinance.Ticker", FakeNewsTicker)
    got = data.fetch_yahoo_news("ADBE")
    assert got == [
        {"title": "First headline", "publisher": "Zacks", "published": "2026-11-20",
         "url": "https://finance.yahoo.com/news/a.html"},
        {"title": "Second headline", "publisher": "Simply Wall St.", "published": "2026-11-19",
         "url": "https://finance.yahoo.com/news/a.html"},
    ]


def test_a_headline_with_an_unsafe_link_keeps_its_text_but_loses_the_link(monkeypatch):
    FakeNewsTicker.news_items = [news_item(link="javascript:alert(1)")]
    monkeypatch.setattr("yfinance.Ticker", FakeNewsTicker)
    [item] = data.fetch_yahoo_news("ADBE")
    assert item["title"] == "Adobe launches something" and item["url"] is None


def test_a_headline_falls_back_to_the_click_through_link_and_copes_with_missing_parts(monkeypatch):
    bare = {"content": {"title": "No extras", "clickThroughUrl": {"url": "https://example.com/x"}}}
    FakeNewsTicker.news_items = [bare, {"content": {"title": ""}}, {"content": None}, {}]
    monkeypatch.setattr("yfinance.Ticker", FakeNewsTicker)
    got = data.fetch_yahoo_news("ADBE")
    assert got == [{"title": "No extras", "publisher": None, "published": None, "url": "https://example.com/x"}]


def test_no_news_gives_an_empty_list_not_an_error(monkeypatch):
    FakeNewsTicker.news_items = []
    monkeypatch.setattr("yfinance.Ticker", FakeNewsTicker)
    assert data.fetch_yahoo_news("ADBE") == []


def test_officers_come_back_with_tidy_names_and_titles(monkeypatch):
    FakeNewsTicker.officers = [
        {"name": "Mr. Shantanu  Narayen", "title": "Chairman & CEO", "age": 61, "totalPay": 5797825},
        {"name": "Ms. Jane Doe", "title": None},
        {"name": "", "title": "Nameless"},                     # no name: left out
    ]
    monkeypatch.setattr("yfinance.Ticker", FakeNewsTicker)
    assert data.fetch_yahoo_officers("ADBE") == [
        {"name": "Mr. Shantanu Narayen", "title": "Chairman & CEO"},
        {"name": "Ms. Jane Doe", "title": None},
    ]


def test_a_company_without_an_officer_list_gives_an_empty_list(monkeypatch):
    FakeNewsTicker.officers = []
    monkeypatch.setattr("yfinance.Ticker", FakeNewsTicker)
    assert data.fetch_yahoo_officers("ADBE") == []


def test_the_context_has_both_parts():
    got = data.get_company_context(
        "ADBE", fetch_news=lambda ticker: [{"title": "x"}], fetch_officers=lambda ticker: [{"name": "y"}]
    )
    assert got == {"news": [{"title": "x"}], "officers": [{"name": "y"}]}


def test_a_part_that_fails_is_none_and_the_other_part_is_still_given():
    def broken(ticker):
        raise ConnectionError("no internet")

    got = data.get_company_context("ADBE", fetch_news=broken, fetch_officers=lambda ticker: [])
    assert got == {"news": None, "officers": []}                # None: could not be fetched; []: there are none
    got = data.get_company_context("ADBE", fetch_news=lambda ticker: [], fetch_officers=broken)
    assert got == {"news": [], "officers": None}


def test_when_neither_part_can_be_had_the_context_stops_with_a_plain_error():
    def broken(ticker):
        raise ConnectionError("no internet")

    with pytest.raises(data.SourceUnavailable, match="news or the officers"):
        data.get_company_context("ADBE", fetch_news=broken, fetch_officers=broken)


def test_the_context_leaves_yahoo_alone_while_it_is_cooling_down(monkeypatch):
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)

    def must_not_be_called(ticker):
        pytest.fail("asked Yahoo")

    with pytest.raises(data.SourceUnavailable, match="isn't answering"):
        data.get_company_context("ADBE", fetch_news=must_not_be_called, fetch_officers=must_not_be_called)


# ---------------------------------------------------------------------------
# The share price over the last twelve months (for the sparkline; not Excel: just Yahoo's closing prices)
# ---------------------------------------------------------------------------

class FakeHistoryTicker:
    """A stand-in for yfinance.Ticker whose history() gives a small table of closing prices, one gap included."""
    closes = {"2026-11-18": 100.0, "2026-11-19": float("nan"), "2026-11-20": 104.5}

    def __init__(self, ticker):
        pass

    def history(self, period):
        assert period == "1y"
        return pd.DataFrame({"Close": list(self.closes.values())}, index=pd.to_datetime(list(self.closes)))


def test_the_price_history_is_a_list_of_dates_and_closes_without_the_days_that_have_no_price(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", FakeHistoryTicker)
    assert data.fetch_yahoo_price_history("ADBE") == [
        {"date": "2026-11-18", "close": 100.0},
        {"date": "2026-11-20", "close": 104.5},
    ]


def test_prices_are_converted_to_dollars_at_the_given_rate():
    prices = data.get_price_history(
        "AKER.OL", usd_per_unit=0.10, fetch_prices=lambda ticker: [{"date": "2026-11-20", "close": 1034.0}]
    )
    assert prices == [{"date": "2026-11-20", "close": pytest.approx(103.4)}]


def test_a_dollar_share_keeps_its_prices():
    prices = data.get_price_history("ADBE", fetch_prices=lambda ticker: [{"date": "2026-11-20", "close": 217.71}])
    assert prices == [{"date": "2026-11-20", "close": 217.71}]


def test_a_price_in_pence_is_converted_through_pounds():
    # Like Shell in London: 9,358 pence is $121.65 at $1.30 a pound.
    prices = data.get_price_history(
        "SHEL.L", usd_per_unit=0.013, fetch_prices=lambda ticker: [{"date": "2026-11-20", "close": 9358.0}]
    )
    assert prices[0]["close"] == pytest.approx(121.654)


def test_no_prices_stops_with_a_plain_error():
    with pytest.raises(ValueError, match="no price history for ZZZ"):
        data.get_price_history("ZZZ", fetch_prices=lambda ticker: [])


def test_yahoo_failing_stops_with_a_plain_error():
    def broken(ticker):
        raise ConnectionError("no internet")

    with pytest.raises(data.SourceUnavailable, match="Could not get the price history from Yahoo Finance: no internet"):
        data.get_price_history("ADBE", fetch_prices=broken)


def test_the_price_history_leaves_yahoo_alone_while_it_is_cooling_down(monkeypatch):
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)

    def must_not_be_called(ticker):
        pytest.fail("asked Yahoo")

    with pytest.raises(data.SourceUnavailable, match="isn't answering"):
        data.get_price_history("ADBE", fetch_prices=must_not_be_called)
