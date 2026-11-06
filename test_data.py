"""Tests for data.py.

The expected snapshot numbers were copied from excel/valuation-lab.xlsx (the cell is named in
the comment). The last tests feed the data into valuation.py and expect the Excel answers.
"""

import pandas as pd
import pytest

import data
import test_valuation as base       # holds the base case assumptions, so they live in one place
import valuation as v


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
}


def test_expected_snapshot_lists_every_package_field():
    assert set(EXPECTED_SNAPSHOT) == set(data.PACKAGE_FIELDS) | set(data.OPTIONAL_FIELDS)


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
    ]
    assert prices == [
        base.close(333.58309927360767),     # Multiples H27
        base.close(420.51859564164647),     # H28
        base.close(463.53631961259072),     # H29
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
    "sharesOutstanding": 389_200_000,
    "currentPrice": 240.74,
    "beta": 1.383,
}


def fake_statements_ticker(income=None, cash_flow=None, balance=None, info=None):
    """Return a stand-in for yfinance.Ticker that serves these statements (Adobe's by default)."""
    class FakeTicker:
        def __init__(self, ticker):
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


def test_the_yahoo_package_is_complete_and_has_no_optional_fields(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker())
    package = data.get_company_data("ADBE", source="yahoo")     # runs check_package
    assert set(package) == set(data.PACKAGE_FIELDS)
    assert not set(package) & set(data.OPTIONAL_FIELDS)


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
