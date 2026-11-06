"""Tests for app.py.

These run the real page with Streamlit's built-in test runner and fake Yahoo replies, never
the internet. They check what the reader would see: the notes, the warnings, which sections
are drawn, and that a company that cannot be valued gets a plain error instead of a crash.
"""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import app
import assumptions
import data
import valuation
from test_data import (
    ADOBE_YAHOO_BALANCE,
    ADOBE_YAHOO_CASH_FLOW,
    ADOBE_YAHOO_INCOME,
    ADOBE_YAHOO_INFO,
    fake_statements_ticker,
)

APP_FILE = str(Path(__file__).parent / "app.py")


@pytest.fixture(autouse=True)
def forget_remembered_figures():
    """The page remembers Yahoo's answers for 15 minutes; forget them so each test starts clean."""
    st.cache_data.clear()
    yield
    st.cache_data.clear()


def run_page(monkeypatch, ticker=None, yahoo=None):
    """Run the page with a fake Yahoo (Adobe-like figures unless told otherwise), optionally
    after typing a ticker into the box. Returns the page as the test runner sees it.
    """
    monkeypatch.setattr("yfinance.Ticker", yahoo or fake_statements_ticker())
    page = AppTest.from_file(APP_FILE, default_timeout=60).run()
    if ticker is not None:
        page.sidebar.text_input[0].set_value(ticker).run()
    return page


def texts(elements):
    """Return the text of a list of page elements."""
    return [element.value for element in elements]


def metrics(page):
    """Return the page's headline numbers as {label: value}."""
    return {metric.label: metric.value for metric in page.metric}


def assert_footer_and_no_crash(page):
    assert not page.exception
    assert app.FOOTER_TEXT in texts(page.caption)


# ---------------------------------------------------------------------------
# Adobe: the page as it has always been
# ---------------------------------------------------------------------------

def test_the_page_opens_on_adobe_with_live_figures_and_peer_multiples(monkeypatch):
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    assert page.sidebar.text_input[0].value == "ADBE"
    assert "Share price and beta are live from Yahoo Finance." in texts(page.caption)
    assert not page.warning
    assert "Peer multiples" in texts(page.subheader)
    assert "EV/Sales price" in metrics(page)


def test_adobe_falls_back_to_the_snapshot_when_yahoo_cannot_be_reached(monkeypatch):
    class BrokenTicker:
        def __init__(self, ticker):
            raise ConnectionError("no internet")

    page = run_page(monkeypatch, yahoo=BrokenTicker)
    assert_footer_and_no_crash(page)
    assert any("could not be reached" in warning for warning in texts(page.warning))
    assert metrics(page)["DCF implied price"] == "$305.60"
    assert metrics(page)["Market price"] == "$251.47"


def test_an_empty_ticker_box_means_adobe(monkeypatch):
    page = run_page(monkeypatch, ticker="   ")
    assert_footer_and_no_crash(page)
    assert "Adobe Inc. (ADBE)" in texts(page.markdown)


# ---------------------------------------------------------------------------
# Another company: a starting point, the DCF only
# ---------------------------------------------------------------------------

def other_company():
    """A stand-in for Yahoo's reply about a company that is not Adobe."""
    return fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, longName="Example Corp"))


def test_another_company_gets_a_starting_point_with_a_warning_and_no_multiples(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())      # lower case on purpose
    assert_footer_and_no_crash(page)
    assert "Example Corp (EXMP)" in texts(page.markdown)
    assert "All figures are from Yahoo Finance's latest annual statements." in texts(page.caption)
    [warning] = texts(page.warning)
    assert warning.startswith("Starting point, not a forecast")
    assert "Example Corp's own last reported year" in warning
    assert "banks, loss-making and early-stage" in warning
    subheaders = texts(page.subheader)
    assert "Discounted cash flow (DCF)" in subheaders
    assert "Behind the number" in subheaders
    assert "Peer multiples" not in subheaders
    assert "EV/Sales price" not in metrics(page)
    assert metrics(page)["Market price"] == "$240.74"


def test_another_companys_price_is_the_starting_point_dcf(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    # Work out the same price independently, straight from valuation.py: the starting point
    # from the company's own last year, the estimated cost of debt, no hand-chosen assumptions.
    company = data.get_company_data("EXMP", source="yahoo")
    ratios = valuation.last_year_ratios(
        revenue=company["revenue"],
        prior_revenue=company["prior_year_revenue"],
        ebit=company["ebit"],
        income_tax=company["income_tax"],
        income_before_tax=company["income_before_tax"],
        depreciation_and_amortisation=company["depreciation_and_amortisation"],
        capex=company["capex"],
        cash_from_working_capital=company["cash_from_working_capital"],
    )
    start = valuation.starting_point_assumptions(
        ratios, assumptions.TERMINAL_GROWTH_RATE, assumptions.STARTING_POINT_YEARS
    )
    expected = valuation.run_full_dcf(
        base_revenue=company["revenue"],
        **start,
        risk_free_rate=company["risk_free_rate"],
        beta=company["beta"],
        equity_risk_premium=company["equity_risk_premium"],
        pre_tax_cost_of_debt=valuation.estimate_pre_tax_cost_of_debt(
            company["interest_expense"], company["debt"]
        ),
        share_price=company["share_price"],
        shares=company["shares"],
        debt=company["debt"],
        cash_and_investments=company["cash_and_investments"],
        terminal_growth_rate=assumptions.TERMINAL_GROWTH_RATE,
    )
    assert metrics(page)["DCF implied price"] == app.dollars(expected["implied_share_price"])
    # ... and it is not the price Adobe's hand-chosen assumptions would give.
    hand_chosen = valuation.run_full_dcf(
        **app.build_dcf_inputs(data.get_company_data("ADBE"), 0.0, 0.0),
        terminal_growth_rate=assumptions.TERMINAL_GROWTH_RATE,
    )
    assert app.dollars(hand_chosen["implied_share_price"]) != metrics(page)["DCF implied price"]


# ---------------------------------------------------------------------------
# A company that cannot be valued gets a plain error, and the footer
# ---------------------------------------------------------------------------

def test_a_ticker_yahoo_knows_nothing_about_shows_a_plain_error(monkeypatch):
    nothing = fake_statements_ticker(income={}, cash_flow={}, balance={}, info={})
    page = run_page(monkeypatch, ticker="nope", yahoo=nothing)
    assert_footer_and_no_crash(page)
    [error] = texts(page.error)
    assert error.startswith("Could not value NOPE.")
    assert "Yahoo Finance has no figures for NOPE" in error
    assert "Check that the ticker is right" in error
    assert not page.metric


def test_a_company_with_no_pre_tax_profit_shows_a_plain_error(monkeypatch):
    loss = dict(ADOBE_YAHOO_INCOME, **{"Pretax Income": (-100e6, 50e6)})
    page = run_page(monkeypatch, ticker="loss", yahoo=fake_statements_ticker(income=loss))
    assert_footer_and_no_crash(page)
    assert "no pre-tax profit" in texts(page.error)[0]
    assert not page.metric


def test_a_wacc_at_or_below_terminal_growth_shows_a_plain_error(monkeypatch):
    odd = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, beta=-10))     # pulls the WACC far below 2.5%
    page = run_page(monkeypatch, ticker="odd", yahoo=odd)
    assert_footer_and_no_crash(page)
    assert "must be lower than the discount rate" in texts(page.error)[0]


def test_yahoo_being_down_for_another_company_shows_a_plain_error(monkeypatch):
    class BrokenTicker:
        def __init__(self, ticker):
            raise ConnectionError("no internet")

    page = run_page(monkeypatch, ticker="exmp", yahoo=BrokenTicker)
    assert_footer_and_no_crash(page)
    assert "no internet" in texts(page.error)[0]


# ---------------------------------------------------------------------------
# The helpers that choose between Adobe and another company
# ---------------------------------------------------------------------------

def test_adobe_is_the_default_and_the_only_base_case():
    assert app.DEFAULT_TICKER == assumptions.BASE_CASE_TICKER == data.ADOBE_SNAPSHOT["ticker"]
    assert app.is_base_case(data.get_company_data("ADBE"))


def test_adobe_keeps_its_hand_chosen_assumptions():
    chosen = app.forecast_assumptions(data.get_company_data("ADBE"))
    assert chosen["growth_rates"] == assumptions.GROWTH_RATES
    assert chosen["tax_rate"] == assumptions.TAX_RATE


def test_adobe_keeps_its_cost_of_debt_from_the_notes():
    assert app.cost_of_debt(data.get_company_data("ADBE")) == pytest.approx(0.041642276422764232)


def test_another_company_gets_the_starting_point_and_the_estimated_cost_of_debt(monkeypatch):
    monkeypatch.setattr("yfinance.Ticker", other_company())
    company = data.get_company_data("EXMP", source="yahoo")
    start = app.forecast_assumptions(company)
    assert start["growth_rates"][-1] == pytest.approx(assumptions.TERMINAL_GROWTH_RATE)    # the fade
    assert start["tax_rate"] == pytest.approx(1604 / 8734)                                  # last year's rate
    assert app.cost_of_debt(company) == pytest.approx(263 / 6210)                           # starting point C27


def test_the_year_labels_for_other_companies_are_numbered_and_as_long_as_the_forecast():
    assert assumptions.GENERIC_YEAR_LABELS == ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5"]
    assert len(assumptions.GENERIC_YEAR_LABELS) == assumptions.STARTING_POINT_YEARS
    assert len(assumptions.GENERIC_YEAR_LABELS) == len(assumptions.FORECAST_YEAR_LABELS)
