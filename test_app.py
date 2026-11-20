"""Tests for app.py.

These run the real page with Streamlit's built-in test runner and fake Yahoo replies, never
the internet. They check what the reader would see: the notes, the warnings, which sections
are drawn, and that a company that cannot be valued gets a plain error instead of a crash.
"""

from pathlib import Path

import pandas as pd
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
    ADOBE_YEAR_ENDS,
    QUARTER_ENDS,
    fake_statements_ticker,
    FMP_PROFILE,
    no_interest_expense_company,
    with_fmp,
)

APP_FILE = str(Path(__file__).parent / "app.py")


@pytest.fixture(autouse=True)
def fresh_provider_state(monkeypatch):
    """Start every test with Yahoo not cooling down, nothing remembered from Financial Modeling Prep,
    and no Financial Modeling Prep key (so a test never reaches the real service by accident).
    """
    monkeypatch.setattr("data._yahoo_busy_until", 0.0)
    monkeypatch.setattr("data._fmp_cache", {})
    # An empty key, not a missing one: the page copies a key from the real secrets file if the setting is
    # missing, and an empty one is left alone and counts as no key.
    monkeypatch.setenv("FMP_API_KEY", "")


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Never really wait in a test: the code pauses before asking Yahoo a second time (see YAHOO_RETRY_PAUSE_SECONDS)."""
    monkeypatch.setattr("data._pause", lambda seconds: None)


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


def test_another_company_gets_a_starting_point_with_a_warning_and_no_multiples_without_peers(monkeypatch):
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
    # The fake Yahoo has no industry, so no peers are suggested: the section says how to add some
    # instead of showing prices.
    assert "Peer multiples" in subheaders
    assert "EV/Sales price" not in metrics(page)
    assert any("No suitable peers were found" in caption for caption in texts(page.caption))
    assert metrics(page)["Market price"] == "$240.74"


def test_a_company_with_no_interest_expense_is_valued_with_a_note_about_the_estimate(monkeypatch):
    # Like Apple: Yahoo has no interest expense, so the cost of debt is the risk-free rate plus
    # a credit spread (starting point C37) and the page says so.
    page = run_page(monkeypatch, ticker="aapl", yahoo=no_interest_expense_company())
    assert_footer_and_no_crash(page)
    assert not page.error
    note, warning = texts(page.warning)
    assert "no interest expense" in note
    assert "6.40%" in note and "1.11%" in note
    assert warning.startswith("Starting point, not a forecast")
    assert "Discounted cash flow (DCF)" in texts(page.subheader)


def test_a_company_with_an_interest_expense_gets_no_estimate_note(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert not any("no interest expense" in warning for warning in texts(page.warning))


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
    # The page opens on Adobe first, and Yahoo giving nothing there would start the cool-down; switch it
    # off so this test is only about the typed ticker.
    monkeypatch.setattr("data._start_yahoo_cooldown", lambda: None)
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


# ---------------------------------------------------------------------------
# Currency: a company that does not report in dollars says so
# ---------------------------------------------------------------------------

def krone_company():
    """A stand-in for Yahoo's reply about a company that reports and trades in kroner."""
    info = dict(ADOBE_YAHOO_INFO, longName="Krone Corp", financialCurrency="NOK", currency="NOK")
    return fake_statements_ticker(info=info, fx_rates={"NOKUSD=X": 0.10})


def test_a_company_in_kroner_is_shown_in_dollars_with_a_conversion_note(monkeypatch):
    page = run_page(monkeypatch, ticker="krn.ol", yahoo=krone_company())
    assert_footer_and_no_crash(page)
    assert "Converted from NOK to US dollars at today's exchange rate (1 NOK = $0.1)." in texts(page.caption)
    assert metrics(page)["Market price"] == "$24.07"        # 240.74 kroner at 10 US cents each


def test_a_dollar_company_gets_no_conversion_note(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert not any(caption.startswith("Converted") for caption in texts(page.caption))


def test_the_conversion_note_names_what_was_converted():
    adobe = data.get_company_data("ADBE")
    assert app.currency_note(adobe) is None                 # the snapshot has no currency fields
    both = dict(statement_currency="NOK", price_currency="NOK", usd_per_statement_unit=0.1056, usd_per_price_unit=0.1056)
    assert app.currency_note(both) == "Converted from NOK to US dollars at today's exchange rate (1 NOK = $0.1056)."
    mixed = dict(statement_currency="DKK", price_currency="USD", usd_per_statement_unit=0.149, usd_per_price_unit=1.0)
    assert app.currency_note(mixed) == "Converted to US dollars at today's exchange rates: the statements from DKK (1 DKK = $0.149)."
    pence = dict(statement_currency="USD", price_currency="GBp", usd_per_statement_unit=1.0, usd_per_price_unit=0.01335)
    assert app.currency_note(pence) == "Converted to US dollars at today's exchange rates: the share price from GBp (1 GBp = $0.01335)."


def test_a_very_low_wacc_still_shows_the_dcf_and_explains_the_missing_heatmap(monkeypatch):
    # A negative beta pulls the WACC to about 4%: fine for the DCF, but the heatmap's lowest
    # row (a point lower) falls below its highest terminal growth rate (3.5%).
    low_beta = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, beta=-0.3))
    page = run_page(monkeypatch, ticker="lowb", yahoo=low_beta)
    assert_footer_and_no_crash(page)
    assert not page.error
    assert "DCF implied price" in metrics(page)
    assert "Sensitivity: price at different WACC and terminal growth" in texts(page.subheader)
    assert any("This table cannot be drawn" in caption for caption in texts(page.caption))
    # The WACC heatmap is missing: the tables on the page are "What the model assumes" and the margin and
    # growth table, which does not vary the WACC.
    assert [element.value.index.name for element in page.dataframe] == ["Year", "Average operating margin"]


# ---------------------------------------------------------------------------
# A price that rests mostly on the far future gets a caution
# ---------------------------------------------------------------------------

def dcf_figures(share, wacc):
    """Just the figures terminal_value_cautions reads, with the terminal value at this share of
    an enterprise value of 1,000.
    """
    return {"pv_of_terminal_value": share * 1000, "enterprise_value": 1000, "wacc": wacc}


def test_no_caution_when_both_checks_are_within_their_limits():
    # Like Adobe: 70% from the terminal value, WACC 8.4 points above terminal growth.
    assert app.terminal_value_cautions(dcf_figures(0.70, 0.1093), 0.025) == []


def test_a_high_terminal_value_share_gets_a_caution():
    [caution] = app.terminal_value_cautions(dcf_figures(0.88, 0.1093), 0.025)      # like Coca-Cola
    assert caution.startswith("88% of this company's value comes from after year 5")


def test_a_small_gap_between_wacc_and_terminal_growth_gets_a_caution():
    [caution] = app.terminal_value_cautions(dcf_figures(0.60, 0.05), 0.025)
    assert "WACC (5.00%) is only 2.5 points above terminal growth (2.50%)" in caution


def test_both_cautions_can_appear_together():
    assert len(app.terminal_value_cautions(dcf_figures(0.90, 0.05), 0.025)) == 2


def test_the_limits_themselves_do_not_trigger_a_caution():
    # Exactly 75% and exactly 4 points apart are still fine: the warning is for more / less.
    assert app.terminal_value_cautions(dcf_figures(0.75, 0.065), 0.025) == []


def test_adobes_page_says_how_much_of_its_value_is_terminal_value_and_has_no_caution(monkeypatch):
    page = run_page(monkeypatch)
    assert not page.warning
    assert any("The terminal value is 70% of the enterprise value." in caption for caption in texts(page.caption))


def test_a_low_wacc_company_gets_the_cautions_on_the_page(monkeypatch):
    low_beta = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, beta=-0.3))      # WACC about 4%
    page = run_page(monkeypatch, ticker="lowb", yahoo=low_beta)
    assert_footer_and_no_crash(page)
    warnings = texts(page.warning)
    assert any("only" in warning and "points above terminal growth" in warning for warning in warnings)
    assert any("comes from after year 5" in warning for warning in warnings)


# ---------------------------------------------------------------------------
# Peers for another company: suggested, editable, with the multiples that follow
# ---------------------------------------------------------------------------

def peer_info(market_cap_billions, ev_sales, ev_ebitda, pe, currency="USD", operating_margin=None, revenue_growth=None):
    """What Yahoo says about a made-up peer."""
    return {
        "marketCap": market_cap_billions * 1_000_000_000, "currency": currency,
        "enterpriseToRevenue": ev_sales, "enterpriseToEbitda": ev_ebitda, "trailingPE": pe,
        "operatingMargins": operating_margin, "revenueGrowth": revenue_growth,
    }


# Example Corp is worth about $94bn (price 240.74 times 389.2m shares). LOSS has no P/E, SMALL is
# far too small, FOREIGN trades in pence.
PEERS_IN_THE_INDUSTRY = {
    "AAA": peer_info(80, 2.0, 12.0, 20.0, operating_margin=0.30),
    "BBB": peer_info(120, 3.0, 16.0, 30.0, operating_margin=0.20),
    "CCC": peer_info(60, 4.0, 10.0, 25.0, operating_margin=0.10),
    "LOSS": peer_info(90, 5.0, 14.0, None, operating_margin=-0.25),
    "SMALL": peer_info(1, 1.0, 1.0, 1.0),
    "FOREIGN": peer_info(95, 9.0, 9.0, 9.0, currency="GBp"),
}


class FakeIndustry:
    """A stand-in for yfinance.Industry: Example Corp's industry holds the peers above."""
    def __init__(self, key):
        import pandas as pandas_
        self.top_companies = pandas_.DataFrame(
            {"name": ["x"] * (len(PEERS_IN_THE_INDUSTRY) + 1)}, index=["EXMP", *PEERS_IN_THE_INDUSTRY]
        )


def example_with_peers():
    """Yahoo's reply about Example Corp and its industry's peers."""
    base = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, longName="Example Corp", industryKey="widgets"))

    class Fake(base):
        def __init__(self, ticker):
            super().__init__(ticker)
            if ticker in PEERS_IN_THE_INDUSTRY:
                self.info = dict(PEERS_IN_THE_INDUSTRY[ticker])

    return Fake


def run_example_page(monkeypatch, ticker="exmp"):
    monkeypatch.setattr("yfinance.Industry", FakeIndustry)
    return run_page(monkeypatch, ticker=ticker, yahoo=example_with_peers())


def peer_box(page):
    return page.sidebar.text_input(key="peers_EXMP")


def example_prices(peer_ev_sales, peer_ev_ebitda, peer_pe):
    """Work out Example Corp's three multiples prices straight from valuation.py."""
    company = data.get_company_data("EXMP", source="yahoo")
    net_debt = valuation.net_debt(company["debt"], company["cash_and_investments"])
    return (
        valuation.price_from_ev_multiple(
            company["revenue"], valuation.median_of_usable_multiples(peer_ev_sales, 2), net_debt, company["shares"]
        ),
        valuation.price_from_ev_multiple(
            valuation.ebitda(company["ebit"], company["depreciation_and_amortisation"]),
            valuation.median_of_usable_multiples(peer_ev_ebitda, 2), net_debt, company["shares"],
        ),
        None if valuation.median_of_usable_multiples(peer_pe, 2) is None else valuation.price_from_pe(
            company["net_income"], valuation.median_of_usable_multiples(peer_pe, 2), company["shares"]
        ),
    )


def test_the_peer_box_starts_with_the_closest_dollar_peers_and_the_multiples_follow(monkeypatch):
    page = run_example_page(monkeypatch)
    assert_footer_and_no_crash(page)
    # LOSS 1.04 times smaller, AAA 1.17, BBB 1.28, CCC 1.56. SMALL is too small, FOREIGN is in pence.
    assert peer_box(page).value == "LOSS, AAA, BBB, CCC"
    sales, ebitda, pe = example_prices([5.0, 2.0, 3.0, 4.0], [14.0, 12.0, 16.0, 10.0], [None, 20.0, 30.0, 25.0])
    assert metrics(page)["EV/Sales price"] == app.dollars(sales)
    assert metrics(page)["EV/EBITDA price"] == app.dollars(ebitda)
    assert metrics(page)["P/E price"] == app.dollars(pe)      # LOSS has no P/E, so the median is of three
    assert metrics(page)["Middle of the three prices"] == app.dollars(sorted([sales, ebitda, pe])[1])
    assert any("Peers suggested from Yahoo's industry list" in caption for caption in texts(page.caption))


def test_the_peer_table_shows_a_dash_for_a_multiple_that_is_left_out(monkeypatch):
    page = run_example_page(monkeypatch)
    table = page.dataframe[-1].value                       # the heatmap comes first
    # The company itself comes first and the peer medians last.
    assert list(table.index) == ["EXMP (this company)", "LOSS", "AAA", "BBB", "CCC", "Peer median"]
    assert table.loc["LOSS", "P/E"] == "–" and table.loc["LOSS", "EV/Sales"] == "5.0x"
    assert table.loc["AAA", "P/E"] == "20.0x"
    assert table.loc["LOSS", "Op. margin"] == "-25.0%"            # a loss shows as a negative margin
    assert table.loc["AAA", "Op. margin"] == "30.0%"


def test_the_table_has_the_company_itself_and_the_peer_medians(monkeypatch):
    page = run_example_page(monkeypatch)
    table = page.dataframe[-1].value
    own = table.loc["EXMP (this company)"]
    assert own["Op. margin"] == "36.6%"                           # EBIT 8,706 over revenue 23,769
    # The medians of the four peers: EV/Sales of 5, 2, 3, 4 is 3.5; EV/EBITDA of 14, 12, 16, 10 is
    # 13; P/E of 20, 30, 25 (LOSS has none) is 25; margins of -25%, 30%, 20%, 10% make 15%.
    median = table.loc["Peer median"]
    assert median.tolist() == ["3.5x", "13.0x", "25.0x", "15.0%", ""]


def test_the_reader_can_change_the_peers(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("aaa  ccc").run()             # lower case and spaces on purpose
    assert not page.exception
    sales, ebitda, pe = example_prices([2.0, 4.0], [12.0, 10.0], [20.0, 25.0])
    assert metrics(page)["EV/Sales price"] == app.dollars(sales)
    assert metrics(page)["P/E price"] == app.dollars(pe)
    assert list(page.dataframe[-1].value.index) == ["EXMP (this company)", "AAA", "CCC", "Peer median"]


def test_with_one_peer_the_prices_say_there_are_not_enough_peers(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("AAA").run()
    assert not page.exception
    for label in ("EV/Sales price", "EV/EBITDA price", "P/E price", "Middle of the prices"):
        assert metrics(page)[label] == "Not enough peers"
    assert metrics(page)["DCF vs multiples"] == "Not available"


def test_a_multiple_with_too_few_peers_is_skipped_and_the_others_still_count(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("LOSS, AAA").run()            # LOSS has no P/E: only AAA's is usable
    assert metrics(page)["P/E price"] == "Not enough peers"
    sales, ebitda, _ = example_prices([5.0, 2.0], [14.0, 12.0], [None, 20.0])
    assert metrics(page)["EV/Sales price"] == app.dollars(sales)
    assert metrics(page)["Average of two prices"] == app.dollars((sales + ebitda) / 2)      # two prices: an average


def test_an_empty_peer_box_shows_how_to_add_peers_instead_of_prices(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("").run()
    assert not page.exception
    assert "EV/Sales price" not in metrics(page)
    assert any("Type at least 2 peer tickers" in caption for caption in texts(page.caption))
    assert app.FOOTER_TEXT in texts(page.caption)


def test_a_ticker_yahoo_knows_nothing_about_is_named_and_left_out(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("AAA, BBB, ZZZZ").run()
    assert not page.exception
    assert any("Yahoo Finance has no multiples for ZZZZ" in caption for caption in texts(page.caption))
    assert metrics(page)["EV/Sales price"] != "Not enough peers"       # AAA and BBB are enough


def test_only_the_first_eight_peers_are_used(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("AAA, BBB, CCC, LOSS, P5, P6, P7, P8, P9").run()
    assert not page.exception
    assert any("Only the first 8 peers are used." in caption for caption in texts(page.caption))
    assert len(page.dataframe[-1].value) == 8 + 2                 # the 8 peers, the company and the median


def test_when_yahoos_industry_lookup_fails_the_page_warns_and_the_box_starts_empty(monkeypatch):
    class BrokenIndustry:
        def __init__(self, key):
            raise ConnectionError("no internet")

    monkeypatch.setattr("yfinance.Industry", BrokenIndustry)
    page = run_page(monkeypatch, ticker="exmp", yahoo=example_with_peers())
    assert_footer_and_no_crash(page)
    assert any("Could not get peers from Yahoo Finance" in warning for warning in texts(page.warning))
    assert peer_box(page).value == ""
    assert "DCF implied price" in metrics(page)               # the DCF is still shown


def test_adobe_has_no_peer_box_and_keeps_its_four_peers(monkeypatch):
    page = run_page(monkeypatch)
    assert len(page.sidebar.text_input) == 1                   # only the company ticker
    assert list(page.dataframe[-1].value.index) == [
        "ADBE (this company)", "ADSK", "INTU", "CRM", "SNPS", "Peer median"
    ]
    assert metrics(page)["EV/Sales price"] == "$333.58"
    assert not any("Peers suggested" in caption for caption in texts(page.caption))


def test_each_company_gets_its_own_peer_box(monkeypatch):
    page = run_example_page(monkeypatch)
    assert page.sidebar.text_input(key="peers_EXMP").value == "LOSS, AAA, BBB, CCC"


# The small helpers.

def test_parse_peer_tickers_handles_commas_spaces_capitals_repeats_and_the_companys_own_ticker():
    got, cut = app.parse_peer_tickers(" pep, kdp  MDLZ,PEP ,ko", "KO", 8)
    assert got == ["PEP", "KDP", "MDLZ"] and cut is False


def test_parse_peer_tickers_cuts_off_after_the_limit_and_says_so():
    got, cut = app.parse_peer_tickers("A B C D", "KO", 3)
    assert got == ["A", "B", "C"] and cut is True
    assert app.parse_peer_tickers("A B C", "KO", 3) == (["A", "B", "C"], False)     # exactly the limit
    assert app.parse_peer_tickers("", "KO", 3) == ([], False)


def test_the_peer_table_shows_dashes_for_missing_zero_and_negative_multiples():
    peers = {
        "peer_tickers": ["A", "B"], "peer_ev_sales": [2.0, None],
        "peer_ev_ebitda": [-5.0, 12.34], "peer_pe": [0, float("nan")],
    }
    peers["peer_operating_margin"] = [-0.1, None]
    overview = {"ev_sales": 4.0, "ev_ebitda": None, "pe": 20.0, "operating_margin": 0.3}
    medians = {"median_ev_sales": None, "median_ev_ebitda": None, "median_pe": None}
    table = app.peer_table(peers, "ME (this company)", overview, medians)
    assert table.loc["A"].tolist() == ["2.0x", "–", "–", "-10.0%", "⚠ Low margin"]       # a loss: depressed earnings
    assert table.loc["B"].tolist() == ["–", "12.3x", "–", "–", ""]
    assert table.loc["ME (this company)"].tolist() == ["4.0x", "–", "20.0x", "30.0%", ""]
    assert table.loc["Peer median"].tolist() == ["–", "–", "–", "–", ""]         # one margin is not enough


def test_a_price_that_could_not_be_worked_out_says_so():
    assert app.price_or_note(None) == "Not enough peers"
    assert app.price_or_note(305.6) == "$305.60"


# ---------------------------------------------------------------------------
# The overview: eight numbers for a quick picture of the company
# ---------------------------------------------------------------------------

def test_company_overview_for_adobe_matches_the_multiples_sheet():
    # The snapshot has the 10-K figures and the 251.47 share price the workbook uses.
    got = app.company_overview(data.get_company_data("ADBE", source="snapshot"))
    assert got["market_value"] == pytest.approx(103857.11)                   # Multiples C54
    assert got["ev_sales"] == pytest.approx(4.3532378307880011)              # C56
    assert got["ev_ebitda"] == pytest.approx(10.864354262914741)             # C57
    assert got["pe"] == pytest.approx(14.56621458625526)                     # C58
    assert got["operating_margin"] == pytest.approx(0.36627540073204595)     # C59
    assert got["revenue_growth"] == pytest.approx(0.10527784236224136)       # C60
    assert got["free_cash_flow_yield"] == pytest.approx(0.080409922853478935)    # C62
    assert got["net_debt_to_ebitda"] == pytest.approx(-0.040424191516169675)     # C63


def test_the_overview_is_on_the_page_with_all_eight_numbers(monkeypatch):
    page = run_page(monkeypatch)
    assert "Overview" in texts(page.subheader)
    shown = metrics(page)
    assert shown["Revenue growth"] == "10.5%"
    assert shown["Operating margin"] == "36.6%"
    assert shown["Net debt ÷ EBITDA"] == "-0.04x"                  # net cash
    for label in ("Free cash flow yield", "EV/Sales", "EV/EBITDA", "P/E"):
        assert shown[label] != app.NOT_MEANINGFUL, label


def test_another_company_gets_the_overview_too(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert_footer_and_no_crash(page)
    assert metrics(page)["Operating margin"] == "36.6%"
    assert metrics(page)["Revenue growth"] == "10.5%"


def test_a_company_that_lost_money_says_not_meaningful_instead_of_a_wrong_number(monkeypatch):
    losing_income = dict(ADOBE_YAHOO_INCOME, **{"Net Income": (-500e6, 1e9), "Pretax Income": (-600e6, 1e9)})
    yahoo = fake_statements_ticker(income=losing_income, info=dict(ADOBE_YAHOO_INFO, longName="Loss Corp"))
    monkeypatch.setattr("yfinance.Ticker", yahoo)
    # With no pre-tax profit the starting point cannot be worked out, so the page explains that
    # instead (tested above); this checks that the overview itself still copes.
    company = data.get_company_data("LOSSY", source="yahoo")
    got = app.company_overview(company)
    assert got["pe"] is None and got["free_cash_flow_yield"] is None
    assert got["operating_margin"] == pytest.approx(8706 / 23769)         # EBIT is still positive here
    assert app.percent_or_note(None) == app.NOT_MEANINGFUL and app.multiple_or_note(None) == app.NOT_MEANINGFUL
    assert app.multiple_or_note(14.566, 1) == "14.6x" and app.multiple_or_note(-0.0404, 2) == "-0.04x"


# ---------------------------------------------------------------------------
# What the model assumes: the actual numbers, and sliders that are clearly a change
# ---------------------------------------------------------------------------

def assumptions_on(page):
    """The 'What the model assumes' table of a page: it is the first table, before the heatmap."""
    return page.dataframe[0].value


def test_the_page_shows_what_the_model_assumes_for_adobe_year_by_year(monkeypatch):
    page = run_page(monkeypatch)
    assert "What the model assumes" in texts(page.subheader)
    table = assumptions_on(page)
    assert list(table.index) == assumptions.FORECAST_YEAR_LABELS
    assert list(table.columns) == [
        "Revenue growth", "Operating margin", "Tax rate", "D&A % of revenue",
        "Capex % of revenue", "Working capital % of revenue",
    ]
    # Adobe's hand-chosen assumptions (Projection H6:L17), shown as the model uses them.
    assert table["Revenue growth"].tolist() == ["9.00%", "9.00%", "8.00%", "7.50%", "7.00%"]
    assert table["Operating margin"].tolist() == ["36.80%", "36.95%", "37.50%", "38.00%", "39.00%"]
    assert table["Tax rate"].tolist() == ["18.00%"] * 5
    assert table["D&A % of revenue"].tolist() == ["3.30%", "3.20%", "3.10%", "3.00%", "2.90%"]
    assert table["Capex % of revenue"].tolist() == ["0.90%", "1.00%", "1.00%", "1.10%", "1.20%"]
    assert table["Working capital % of revenue"].tolist() == ["1.00%"] * 5


def test_the_assumptions_line_says_where_they_come_from_and_what_the_sliders_do(monkeypatch):
    page = run_page(monkeypatch)
    [line] = [caption for caption in texts(page.caption) if caption.startswith("Adobe's assumptions")]
    assert "hand-chosen" in line and "2.50%" in line
    assert "growth by +0.0 points" in line and "operating margin by +0.0 points" in line


def test_moving_a_slider_changes_the_table_by_that_many_points(monkeypatch):
    page = run_page(monkeypatch)
    page.sidebar.slider[0].set_value(1.5).run()                  # growth: +1.5 points
    page.sidebar.slider[1].set_value(-2.0).run()                 # margin: -2.0 points
    assert not page.exception
    table = assumptions_on(page)
    assert table["Revenue growth"].tolist() == ["10.50%", "10.50%", "9.50%", "9.00%", "8.50%"]
    assert table["Operating margin"].tolist() == ["34.80%", "34.95%", "35.50%", "36.00%", "37.00%"]
    assert table["Tax rate"].tolist() == ["18.00%"] * 5          # the sliders leave everything else alone
    line = [caption for caption in texts(page.caption) if caption.startswith("Adobe's assumptions")][0]
    assert "growth by +1.5 points" in line and "operating margin by -2.0 points" in line


def test_the_shift_sliders_are_in_points_and_start_at_zero(monkeypatch):
    page = run_page(monkeypatch)
    growth, margin = page.sidebar.slider[0], page.sidebar.slider[1]
    assert growth.label == "Revenue growth: change every year by" and growth.value == 0.0
    assert margin.label == "Operating margin: change every year by" and margin.value == 0.0
    assert (growth.min, growth.max, growth.step) == (-5.0, 5.0, 0.5)


def test_another_company_gets_the_table_with_numbered_years_and_the_faded_path(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    table = assumptions_on(page)
    assert list(table.index) == assumptions.GENERIC_YEAR_LABELS
    assert table["Revenue growth"].tolist()[-1] == "2.50%"       # the fade ends at the terminal growth rate
    assert table["Working capital % of revenue"].tolist()[-1] == "0.00%"      # working capital fades to zero
    assert any("starting point worked out from the company's own last reported year" in caption
               for caption in texts(page.caption))


def test_the_line_says_whose_wacc_it_is(monkeypatch):
    page = run_page(monkeypatch)
    assert any("the model's own WACC" in caption for caption in texts(page.caption))
    page.sidebar.checkbox[0].check().run()
    assert any("the WACC you set" in caption for caption in texts(page.caption))


# The "-0 %" problem: a zero must be written as a plain zero.

def test_a_rate_too_small_to_show_is_never_written_as_negative_zero():
    assert app.percent(-0.00004) == "0.0%" and app.percent(0.0) == "0.0%"
    assert app.precise_percent(-0.000001) == "0.00%"
    assert app.percent(-0.123) == "-12.3%" and app.precise_percent(-0.0001) == "-0.01%"      # real values are kept


def test_shift_from_points_turns_points_into_a_decimal_and_a_zero_stays_zero():
    import math
    assert app.shift_from_points(1.5) == 0.015
    assert app.shift_from_points(-5.0) == -0.05
    assert math.copysign(1, app.shift_from_points(-0.0)) == 1       # not a negative zero


def test_points_text_writes_a_sign_and_never_negative_zero():
    assert app.points_text(0.015) == "+1.5 points"
    assert app.points_text(-0.02) == "-2.0 points"
    assert app.points_text(0.0) == "+0.0 points" and app.points_text(-0.0) == "+0.0 points"


# ---------------------------------------------------------------------------
# How the WACC is built: every step, and where each input comes from
# ---------------------------------------------------------------------------

def adobe_snapshot_wacc_table():
    """The WACC table for Adobe's snapshot: the 10-K figures and the $251.47 price the workbook uses."""
    company = data.get_company_data("ADBE", source="snapshot")
    return app.wacc_table(company, app.build_dcf_inputs(company, 0, 0), "snapshot")


def test_the_wacc_table_matches_every_step_of_the_wacc_sheet():
    table, _ = adobe_snapshot_wacc_table()
    assert list(table.index) == [
        "Risk-free rate", "Beta", "Equity risk premium", "Cost of equity", "Pre-tax cost of debt",
        "Tax rate", "Cost of debt after tax", "Market value of equity", "Debt", "Weight of equity",
        "Weight of debt", "WACC",
    ]
    values = table["Value"].to_dict()
    assert values == {
        "Risk-free rate": "5.29%",                    # WACC C8
        "Beta": "1.38",                               # C9
        "Equity risk premium": "4.41%",               # C10
        "Cost of equity": "11.38%",                   # C11
        "Pre-tax cost of debt": "4.16%",              # C14
        "Tax rate": "18.00%",                         # C15
        "Cost of debt after tax": "3.41%",            # C16
        "Market value of equity": "$103,857m",        # C21
        "Debt": "$6,210m",                            # C22
        "Weight of equity": "94.36%",                 # C24
        "Weight of debt": "5.64%",                    # C25
        "WACC": "10.93%",                             # C29
    }


def test_the_wacc_table_says_where_adobes_inputs_come_from():
    table, _ = adobe_snapshot_wacc_table()
    where = table["Where it comes from"].to_dict()
    assert where["Risk-free rate"] == "Damodaran, 1 Nov 2026 (typed in by hand)"
    assert where["Equity risk premium"] == "Damodaran, 1 Nov 2026 (typed in by hand)"
    assert where["Beta"].startswith("Frozen snapshot of the Excel model")
    assert where["Pre-tax cost of debt"] == "The weighted average interest rate in the 10-K's debt notes"
    assert where["Tax rate"] == "The forecast tax rate (the Projection sheet)"
    assert where["Debt"] == "The 10-K: current plus long-term debt"


def test_the_wacc_table_is_on_the_page_and_its_wacc_is_the_one_the_dcf_uses(monkeypatch):
    page = run_page(monkeypatch)
    assert "How the WACC is built" in texts(page.subheader)
    table = wacc_table_of(page)
    assert table.loc["Beta", "Where it comes from"] == "Yahoo Finance, 5-year monthly"      # live, not the snapshot
    assert table.loc["WACC", "Value"].startswith(metrics(page)["WACC"][:-2])               # 10.9x% and 10.9%


def test_another_companys_inputs_are_labelled_as_estimates_from_its_own_figures(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    where = wacc_table_of(page)["Where it comes from"]
    assert where["Pre-tax cost of debt"] == "Estimate: last year's interest expense divided by debt"
    assert where["Tax rate"] == "Last year's rate: income tax divided by pre-tax income"
    assert where["Debt"] == "Yahoo Finance: current plus long-term debt"


def test_a_company_using_the_fallback_cost_of_debt_says_so_in_the_wacc_table(monkeypatch):
    page = run_page(monkeypatch, ticker="aapl", yahoo=no_interest_expense_company())
    table = wacc_table_of(page)
    assert table.loc["Pre-tax cost of debt", "Value"] == "6.40%"                           # the risk-free rate plus 1.11%
    assert table.loc["Pre-tax cost of debt", "Where it comes from"].startswith("Estimate: the risk-free rate plus")


def test_the_wacc_sentence_says_why_the_number_is_what_it_is():
    _, build = adobe_snapshot_wacc_table()
    assert app.wacc_explanation(build, build["wacc"], False) == (
        "94% of the funding is equity, costing 11.38%; 6% is debt, costing 3.41% after tax. "
        "Blended, that is 10.93%."
    )


def test_a_company_with_no_debt_is_explained_as_all_equity():
    build = {"weight_of_debt": 0.0, "weight_of_equity": 1.0, "cost_of_equity": 0.09,
             "after_tax_cost_of_debt": 0.0, "wacc": 0.09}
    assert app.wacc_explanation(build, 0.09, False) == (
        "The company has no debt, so the WACC is just its cost of equity, 9.00%."
    )


def test_when_the_reader_sets_a_wacc_the_page_still_shows_the_models_own_build(monkeypatch):
    page = run_page(monkeypatch)
    own = wacc_table_of(page).loc["WACC", "Value"]
    page.sidebar.checkbox[0].check().run()                                                 # "Set the WACC myself"
    assert not page.exception
    assert wacc_table_of(page).loc["WACC", "Value"] == own                                 # the build is unchanged
    [line] = [c for c in texts(page.caption) if "You have set the WACC to 11.00%" in c]    # the slider's start
    assert "instead of the model's own" in line


def test_a_very_low_wacc_company_still_gets_its_wacc_table(monkeypatch):
    low_beta = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, beta=-0.3))
    page = run_page(monkeypatch, ticker="lowb", yahoo=low_beta)
    assert not page.exception
    assert wacc_table_of(page).loc["Beta", "Value"] == "-0.30"


# ---------------------------------------------------------------------------
# Warnings about the peers: a margin far from theirs, distorted peers, and an honest middle
# ---------------------------------------------------------------------------

def run_page_with_industry(monkeypatch, peers_in_industry):
    """Run Example Corp's page with a made-up industry of the given peers (ticker -> Yahoo info)."""
    import pandas as pandas_

    class Industry:
        def __init__(self, key):
            self.top_companies = pandas_.DataFrame(
                {"name": ["x"] * (len(peers_in_industry) + 1)}, index=["EXMP", *peers_in_industry]
            )

    base = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, longName="Example Corp", industryKey="widgets"))

    class Fake(base):
        def __init__(self, ticker):
            super().__init__(ticker)
            if ticker in peers_in_industry:
                self.info = dict(peers_in_industry[ticker])

    monkeypatch.setattr("yfinance.Industry", Industry)
    return run_page(monkeypatch, ticker="exmp", yahoo=Fake)


# Three peers like First Solar's, as Yahoo showed them on 18 Nov 2026: a healthy one, one with a
# margin of 0.6% (Enphase) and one with a one-off P/E of 3.9 (Sunrun).
SOLAR_LIKE_PEERS = {
    "AAA": peer_info(30, 2.8, 14.3, 19.8, operating_margin=0.186),
    "BBB": peer_info(25, 2.2, 31.9, 34.3, operating_margin=0.006),
    "CCC": peer_info(20, 4.7, 18.0, 3.9, operating_margin=0.063),
}


def test_the_middle_price_is_named_for_how_many_prices_it_is_the_middle_of():
    def with_prices(sales, ebitda, pe):
        return {"price_ev_sales": sales, "price_ev_ebitda": ebitda, "price_pe": pe}

    assert app.middle_price_label(with_prices(1, 2, 3)) == "Middle of the three prices"
    assert app.middle_price_label(with_prices(1, None, 3)) == "Average of two prices"
    assert app.middle_price_label(with_prices(None, None, 3)) == "The only price"
    assert app.middle_price_label(with_prices(None, None, None)) == "Middle of the prices"


def test_two_prices_get_a_warning_that_they_have_no_middle(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("LOSS, AAA").run()                 # LOSS has no P/E: two prices only
    assert any("their average, not a middle" in warning for warning in texts(page.warning))


def test_three_prices_get_no_such_warning(monkeypatch):
    page = run_example_page(monkeypatch)
    assert not any("their average, not a middle" in warning for warning in texts(page.warning))


def test_the_margin_warning_says_how_far_above_or_below_the_peers_the_company_is():
    peers = {"peer_operating_margin": [0.186, 0.006, 0.063]}               # a middle of 6.3%
    warning = app.margin_gap_warning("First Solar", 0.306, peers)
    assert warning.startswith("First Solar's operating margin (30.6%) is 24.3 points above its peers' middle (6.3%).")
    assert "lean more on EV/EBITDA and P/E" in warning
    peers_like_pfizers = {"peer_operating_margin": [0.38, 0.32, 0.34, 0.35, 0.37]}      # a middle of 35.0%
    assert app.margin_gap_warning("Pfizer", 0.278, peers_like_pfizers) is None          # 7.2 points below: within the limit
    below = app.margin_gap_warning("Pfizer", 0.20, peers_like_pfizers)
    assert "is 15.0 points below its peers' middle (35.0%)" in below


def test_no_margin_warning_within_the_limit_or_without_margins_to_compare():
    peers = {"peer_operating_margin": [0.20, 0.20, 0.20]}
    assert app.margin_gap_warning("A", 0.299, peers) is None               # 9.9 points: within the limit
    assert app.margin_gap_warning("A", 0.301, peers) is not None           # 10.1 points
    assert app.margin_gap_warning("A", 0.101, peers) is None               # 9.9 points below: within the limit
    assert app.margin_gap_warning("A", 0.099, peers) is not None           # 10.1 points below
    assert app.margin_gap_warning("A", None, peers) is None
    assert app.margin_gap_warning("A", 0.3, {"peer_operating_margin": [0.2, None, None]}) is None


def test_the_page_warns_when_the_companys_margin_is_far_from_its_peers(monkeypatch):
    page = run_example_page(monkeypatch)
    # Example Corp earns 36.6%; its peers' margins of -25%, 30%, 20% and 10% have a middle of 15.0%.
    [warning] = [w for w in texts(page.warning) if "operating margin" in w]
    assert warning.startswith("Example Corp's operating margin (36.6%) is 21.6 points above its peers' middle (15.0%).")


def test_no_margin_warning_on_the_page_with_too_few_peer_margins(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("AAA").run()
    assert not any("operating margin" in w for w in texts(page.warning))


def test_the_flag_text_names_every_reason():
    assert app.flag_text([]) == ""
    assert app.flag_text(["low_margin"]) == "⚠ Low margin"
    assert app.flag_text(["low_margin", "ev_ebitda", "pe"]) == "⚠ Low margin, EV/EBITDA outlier, P/E outlier"


def test_flagged_peers_are_marked_in_the_table_and_explained_under_it(monkeypatch):
    page = run_page_with_industry(monkeypatch, SOLAR_LIKE_PEERS)
    table = page.dataframe[-1].value
    assert table.loc["AAA", "Flag"] == ""
    assert table.loc["BBB", "Flag"] == "⚠ Low margin"                       # margin of 0.6%
    assert table.loc["CCC", "Flag"] == "⚠ P/E outlier"                      # 3.9 against the peers' middle, 19.8
    assert table.loc["EXMP (this company)", "Flag"] == "" and table.loc["Peer median", "Flag"] == ""
    captions = texts(page.caption)
    assert any(c.startswith("⚠ BBB: its operating margin (0.6%) is below 5%") for c in captions)
    import statistics
    middle = f"{statistics.median([19.8, 34.3, 3.9]):.1f}x"                 # all three peers' P/Es
    assert any(c.startswith(f"⚠ CCC: its P/E of 3.9x is far from the peers' middle ({middle})") for c in captions)
    assert any("Flagged peers still count in the medians" in c for c in captions)


def test_a_flagged_peer_still_counts_in_the_median(monkeypatch):
    page = run_page_with_industry(monkeypatch, SOLAR_LIKE_PEERS)
    # Flag only: the P/E median is still over all three peers (19.8, 34.3, 3.9), which is 19.8.
    assert page.dataframe[-1].value.loc["Peer median", "P/E"] == "19.8x"


def test_a_solar_like_company_gets_the_margin_warning_too(monkeypatch):
    page = run_page_with_industry(monkeypatch, SOLAR_LIKE_PEERS)
    [warning] = [w for w in texts(page.warning) if "operating margin" in w]
    assert "points above its peers' middle (6.3%)" in warning                # 36.6% against 6.3%


def test_no_flag_text_or_explanations_when_no_peer_is_distorted(monkeypatch):
    healthy = {
        "AAA": peer_info(80, 2.0, 12.0, 20.0, operating_margin=0.30),
        "BBB": peer_info(120, 3.0, 16.0, 30.0, operating_margin=0.20),
        "CCC": peer_info(60, 4.0, 10.0, 25.0, operating_margin=0.10),
    }
    page = run_page_with_industry(monkeypatch, healthy)
    assert set(page.dataframe[-1].value["Flag"]) == {""}
    assert not any(c.startswith("⚠") for c in texts(page.caption))
    assert not any("Flagged peers still count" in c for c in texts(page.caption))


def test_adobes_page_flags_synopsys_for_its_pe(monkeypatch):
    page = run_page(monkeypatch)
    table = page.dataframe[-1].value
    assert table.loc["SNPS", "Flag"] == "⚠ P/E outlier"                      # 82.6x is 3.1 times the peers' middle
    assert table.loc["ADSK", "Flag"] == ""
    import statistics
    middle = f"{statistics.median([32.73, 20.72, 20.97, 82.62]):.1f}x"       # all four peers' P/Es
    assert any(c.startswith(f"⚠ SNPS: its P/E of 82.6x is far from the peers' middle ({middle})") for c in texts(page.caption))
    assert "Middle of the three prices" in metrics(page)                     # Adobe has all three prices


def wacc_table_of(page):
    """The 'How the WACC is built' table of a page: the one with a 'Where it comes from' column."""
    [table] = [element.value for element in page.table if "Where it comes from" in element.value.columns]
    return table


# ---------------------------------------------------------------------------
# History: the last few years, a table and two charts
# ---------------------------------------------------------------------------

def adobe_with_four_years(operating_income=None):
    """Yahoo's reply for Adobe with four years of statements, as the real one has: the latest two
    years are the ones the page's other tests use, so the valuation does not change.
    """
    base = fake_statements_ticker()
    income = pd.DataFrame(
        {
            "Total Revenue": [23769e6, 21505e6, 19409e6, 17606e6],
            "Operating Income": operating_income or [8706e6, 7741e6, 6650e6, 6098e6],
            "Net Income": [7130e6, 5560e6, 5428e6, 4756e6],
            "Tax Provision": [1604e6, 1371e6, 1000e6, 900e6],
            "Pretax Income": [8734e6, 6931e6, 6400e6, 5600e6],
            "Interest Expense": [263e6, 169e6, 150e6, 120e6],
            "Diluted Average Shares": [427e6, 450e6, 459e6, 471e6],
        },
        index=ADOBE_YEAR_ENDS,
    ).T
    cash_flow = pd.DataFrame(
        {
            "Depreciation And Amortization": [818e6, 857e6, 800e6, 750e6],
            "Capital Expenditure": [-179e6, -183e6, -150e6, -140e6],
            "Change In Working Capital": [605e6, 144e6, 100e6, 90e6],
            "Free Cash Flow": [9852e6, 7873e6, 6942e6, 7396e6],
        },
        index=ADOBE_YEAR_ENDS,
    ).T

    class Fake(base):
        def __init__(self, ticker):
            super().__init__(ticker)
            if not hasattr(self, "info") or "marketCap" in self.info:
                return
            self.income_stmt, self.cashflow = income, cash_flow

    return Fake


def history_table_of(page):
    """The history table of a page: the one whose first row is Revenue and whose columns are years."""
    [table] = [element.value for element in page.table if "Revenue growth" in element.value.index]
    return table


def test_the_history_table_matches_the_history_sheet(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    assert "History" in texts(page.subheader)
    table = history_table_of(page)
    assert list(table.columns) == ["FY2022", "FY2023", "FY2024", "FY2025"]
    assert table.loc["Revenue"].tolist() == ["$17,606m", "$19,409m", "$21,505m", "$23,769m"]
    assert table.loc["Revenue growth"].tolist() == ["–", "10.2%", "10.8%", "10.5%"]                 # history D15:F15
    assert table.loc["Operating income"].tolist() == ["$6,098m", "$6,650m", "$7,741m", "$8,706m"]
    assert table.loc["Operating margin"].tolist() == ["34.6%", "34.3%", "36.0%", "36.6%"]           # C16:F16
    assert table.loc["Net income"].tolist() == ["$4,756m", "$5,428m", "$5,560m", "$7,130m"]
    assert table.loc["Free cash flow (reported)"].tolist() == ["$7,396m", "$6,942m", "$7,873m", "$9,852m"]
    assert table.loc["Free cash flow margin"].tolist() == ["42.0%", "35.8%", "36.6%", "41.4%"]      # C17:F17
    assert table.loc["Diluted average shares"].tolist() == ["471m", "459m", "450m", "427m"]
    assert table.loc["Yearly change in shares"].tolist() == ["–", "-2.5%", "-2.0%", "-5.1%"]        # D18:F18


def test_the_note_quotes_reported_free_cash_flow_against_the_models(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    [note] = [c for c in texts(page.caption) if c.startswith("Free cash flow here is as the company reports it")]
    assert "$9,852m reported against $8,351m in the model" in note.replace("\\", "")      # without the escaping backslashes
    assert any(c.startswith("Yahoo Finance gives 4 years of figures") and "diluted average" in c for c in texts(page.caption))


def test_the_history_works_with_the_two_years_of_the_simple_fake(monkeypatch):
    page = run_page(monkeypatch)                      # columns named "before" and "latest", no shares or cash flow line
    assert not page.exception
    table = history_table_of(page)
    assert list(table.columns) == ["before", "latest"]
    assert table.loc["Revenue growth"].tolist() == ["–", "10.5%"]
    assert table.loc["Diluted average shares"].tolist() == ["–", "–"]
    assert table.loc["Free cash flow (reported)"].tolist() == ["–", "–"]


def test_the_history_of_a_company_in_kroner_is_shown_in_dollars(monkeypatch):
    page = run_page(monkeypatch, ticker="krn.ol", yahoo=krone_company())
    assert history_table_of(page).loc["Revenue", "latest"] == "$2,377m"            # 23,769 kroner millions at 10 US cents


def test_if_the_history_cannot_be_fetched_the_page_says_so_and_carries_on(monkeypatch):
    def down(ticker, usd_per_unit=1.0):
        raise ValueError("Could not get the history from Yahoo Finance: no internet")

    monkeypatch.setattr("data.get_history", down)
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    assert "History" in texts(page.subheader)
    assert any(c.startswith("The history is not available right now. Could not get the history") for c in texts(page.caption))
    assert "DCF implied price" in metrics(page)                                    # the rest of the page is fine


def test_a_loss_shows_as_a_negative_amount_and_margin_in_the_table():
    # First Solar's FY2022 and FY2023, as Yahoo showed them on 18 Nov 2026.
    history = {
        "years": ["FY2022", "FY2023"], "revenue": [2619.0, 3319.0], "operating_income": [-281.0, 886.0],
        "net_income": [-44.0, 831.0], "free_cash_flow": [-30.0, -785.0], "diluted_shares": [107.0, 107.0],
    }
    table = app.history_table(history)
    assert table.loc["Operating income"].tolist() == ["-$281m", "$886m"]
    assert table.loc["Operating margin"].tolist() == ["-10.7%", "26.7%"]
    assert table.loc["Free cash flow (reported)"].tolist() == ["-$30m", "-$785m"]


def test_the_chart_data_has_amounts_in_millions_and_margins_in_percent():
    history = {
        "years": ["FY2024", "FY2025"], "revenue": [21505.0, 23769.0], "operating_income": [7741.0, 8706.0],
        "net_income": [5560.0, 7130.0], "free_cash_flow": [7873.0, None], "diluted_shares": [450.0, 427.0],
    }
    amounts, margins = app.history_chart_data(history)
    assert list(amounts.index) == ["FY2024", "FY2025"]
    assert amounts["Revenue"].tolist() == [21505.0, 23769.0]
    assert amounts["Free cash flow (reported)"].iloc[0] == 7873.0 and amounts["Free cash flow (reported)"].isna().iloc[1]
    assert margins["Operating margin"].round(1).tolist() == [36.0, 36.6]
    assert margins["FCF margin"].iloc[0] == pytest.approx(7873 / 21505 * 100) and margins["FCF margin"].isna().iloc[1]


def test_the_helpers_write_amounts_with_signs_and_dashes():
    assert app.millions_text(23769.0) == "$23,769m" and app.millions_text(-281.4) == "-$281m"
    assert app.millions_text(None) == "–" and app.rate_text(None) == "–" and app.rate_text(0.105) == "10.5%"


def test_the_note_still_makes_sense_when_the_models_free_cash_flow_is_not_known():
    history = {"free_cash_flow": [None, 9852.0]}
    assert app.free_cash_flow_note(history, {"free_cash_flow": None}, "Loss Corp").endswith("so the two differ.")


def test_the_dollar_signs_in_the_history_note_are_escaped_so_they_are_not_read_as_maths(monkeypatch):
    # Without the backslashes Streamlit shows the text between two dollar signs as a formula.
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    [note] = [c for c in texts(page.caption) if c.startswith("Free cash flow here is as the company reports it")]
    assert "\\$9,852m reported against \\$8,351m in the model" in note
    assert "$9,852m" not in note.replace("\\$", "")                # every dollar sign has its backslash


# ---------------------------------------------------------------------------
# Is the latest year typical? Warnings from the history (workbook: `history` C20:C22)
# ---------------------------------------------------------------------------

def history_with_margins(*margins):
    """A history with revenue of 100 every year and these operating margins (oldest first)."""
    return {
        "years": [f"FY{2022 + number}" for number in range(len(margins))], "revenue": [100.0] * len(margins),
        "operating_income": [None if margin is None else margin * 100 for margin in margins],
        "net_income": [None] * len(margins), "free_cash_flow": [None] * len(margins), "diluted_shares": [None] * len(margins),
    }


def test_a_margin_far_above_its_history_is_called_a_possible_peak_and_a_wide_swing_is_noted():
    # First Solar's margins on 18 Nov 2026: -10.7%, 26.7%, 33.1% and 30.6%.
    peak, swing = app.margin_history_warnings(history_with_margins(-0.107, 0.267, 0.331, 0.306), "First Solar")
    assert peak == (
        "First Solar's latest operating margin (30.6%) is 14.2 points above the average of the earlier years "
        "(16.4%). This year may be a peak, so a forecast that holds it flat could be too optimistic."
    )
    assert swing == (
        "The operating margin has swung by 43.8 points between its best (33.1%) and worst (-10.7%) year. "
        "One year is a poor guide for a margin like that, so look at the whole history."
    )


def test_a_margin_far_below_its_history_is_called_a_possible_bottom():
    # Ford's margins: 4.0%, 3.1%, 2.8% and then a loss of 4.9%.
    [bottom] = app.margin_history_warnings(history_with_margins(0.040, 0.031, 0.028, -0.049), "Ford")
    assert "is 8.2 points below the average of the earlier years (3.3%)" in bottom
    assert "may be a bottom" in bottom and "too pessimistic" in bottom


def test_a_steady_margin_gets_no_warning():
    # Adobe's margins (history C16:F16): within 1.7 points of the earlier average, a swing of 2.4.
    assert app.margin_history_warnings(history_with_margins(0.34636, 0.34262, 0.35996, 0.36628), "Adobe") == []


def test_a_swinging_margin_whose_latest_year_is_near_the_average_only_gets_the_swing_note():
    # Pfizer's margins: 37.7%, 7.4%, 23.5%, 27.8%. The latest is 4.96 points above the earlier average,
    # just inside the 5-point limit, but the swing is 30.3 points.
    [swing] = app.margin_history_warnings(history_with_margins(0.377, 0.074, 0.235, 0.278), "Pfizer")
    assert swing.startswith("The operating margin has swung by 30.3 points")


def test_too_few_years_gives_no_warning():
    assert app.margin_history_warnings(history_with_margins(0.1, 0.4), "Two Years") == []
    assert app.margin_history_warnings(history_with_margins(None, None, 0.3), "One Margin") == []


def test_the_page_warns_when_the_latest_margin_may_be_a_peak(monkeypatch):
    # Older years' operating income gives margins of -10%, 10% and 15% before the latest 36.6%.
    page = run_page(monkeypatch, yahoo=adobe_with_four_years(operating_income=[8706e6, 3226e6, 1941e6, -1761e6]))
    peak = [w for w in texts(page.warning) if "may be a peak" in w]
    assert len(peak) == 1 and peak[0].startswith("Adobe Inc.'s latest operating margin (36.6%) is 31.6 points above")
    assert any("swung by 46.6 points" in w for w in texts(page.warning))


def test_the_page_warns_when_the_latest_margin_may_be_a_bottom(monkeypatch):
    # Older years at 50%, 55% and 60% before the latest 36.6%.
    page = run_page(monkeypatch, yahoo=adobe_with_four_years(operating_income=[8706e6, 12903e6, 10675e6, 8803e6]))
    assert any("may be a bottom" in w and "points below the average" in w for w in texts(page.warning))


def test_adobes_four_years_give_no_history_warning_on_the_page(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    assert not any("earlier years" in w or "swung by" in w for w in texts(page.warning))


def test_the_two_year_simple_fake_gives_no_history_warning(monkeypatch):
    page = run_page(monkeypatch)
    assert not page.warning


# ---------------------------------------------------------------------------
# What the market price implies: the reverse DCF on the page
# ---------------------------------------------------------------------------

ANSWER = {"shift": -0.0747, "model_average": 0.3766, "implied_average": 0.3019}


def test_the_margin_sentence_gives_the_implied_margin_against_the_models():
    sentence = app.implied_margin_sentence(251.47, ANSWER, None)
    assert sentence == (
        "To justify the market price of $251.47, the market is pricing in an average operating margin of "
        "30.2% over the five forecast years, against 37.7% in the model, with revenue growth as modelled."
    )


def test_the_growth_sentence_gives_the_implied_growth_against_the_models():
    answer = {"shift": -0.0475, "model_average": 0.081, "implied_average": 0.0335}
    assert app.implied_growth_sentence(251.47, answer, None) == (
        "Or, holding the margin as modelled, an average revenue growth of 3.4% a year, against 8.1% in the model."
    )


def test_each_sentence_says_plainly_when_no_answer_exists():
    assert app.implied_margin_sentence(1e9, None, None) == (
        "No operating margin within 50 points of the model's makes the DCF equal the market price of $1,000,000,000.00."
    )
    assert app.implied_growth_sentence(1e9, None, None).startswith("No revenue growth within 50 points of the model's")


def test_the_history_clause_says_whether_the_implied_figure_is_above_below_or_within_the_range():
    history = history_with_margins(0.343, 0.343, 0.360, 0.366)                    # Adobe's range: 34.3% to 36.6%
    below = app.implied_margin_sentence(251.47, ANSWER, history)
    assert "In its history the operating margin ranged from 34.3% to 36.6%, so the implied figure is below its worst year." in below
    within = app.implied_margin_sentence(251.47, dict(ANSWER, implied_average=0.35), history)
    assert within.endswith("so the implied figure is within that range.")
    above = app.implied_margin_sentence(251.47, dict(ANSWER, implied_average=0.45), history)
    assert above.endswith("so the implied figure is above its best year.")


def test_the_growth_clause_uses_the_years_of_revenue_growth_in_the_history():
    history = history_with_margins(0.1, 0.1, 0.1, 0.1)
    history["revenue"] = [100.0, 110.0, 126.5, 132.825]                           # growth of 10%, 15% and 5%
    sentence = app.implied_growth_sentence(100, {"shift": 0.0, "model_average": 0.08, "implied_average": 0.12}, history)
    assert "In its history revenue growth ranged from 5.0% to 15.0%, so the implied figure is within that range." in sentence


def test_no_history_clause_when_the_history_has_no_figure_to_compare_with():
    history = history_with_margins(None, None, None)
    assert "In its history" not in app.implied_margin_sentence(251.47, ANSWER, history)
    assert app.history_range_clause("the operating margin", 0.3, []) == ""


def test_the_page_has_the_market_price_implies_section_under_the_dcf_numbers(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    subheaders = texts(page.subheader)
    assert subheaders.index("Discounted cash flow (DCF)") < subheaders.index("What the market price implies") < subheaders.index("Overview")
    shown = metrics(page)
    assert shown["Operating margin it implies"].endswith("%") and shown["Revenue growth it implies"].endswith("%")


def test_the_pages_implied_figures_match_the_solver_for_the_pages_price(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    company = data.get_company_data_with_fallback("ADBE")[0]
    answers = valuation.reverse_dcf(
        app.build_dcf_inputs(company, 0, 0), company["share_price"], assumptions.TERMINAL_GROWTH_RATE, None,
        assumptions.REVERSE_DCF_SEARCH_RANGE, assumptions.REVERSE_DCF_TOLERANCE,
    )
    assert metrics(page)["Operating margin it implies"] == app.percent(answers["margin"]["implied_average"])
    assert metrics(page)["Revenue growth it implies"] == app.percent(answers["growth"]["implied_average"])
    captions = [caption.replace("\\", "") for caption in texts(page.caption)]           # without the escaping backslashes
    assert any(c.startswith(f"To justify the market price of {app.dollars(company['share_price'])}") for c in captions)
    assert any("In its history the operating margin ranged from 34.3% to 36.6%" in c for c in captions)       # Adobe's four years
    assert any(c.startswith("Or, holding the margin as modelled, an average revenue growth of") for c in captions)


def test_the_implied_figures_move_with_the_sliders_and_the_wacc(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    before = metrics(page)["Operating margin it implies"]
    page.sidebar.slider[1].set_value(-2.0).run()                     # a margin 2 points lower in the model
    assert not page.exception
    # The implied margin is an absolute figure: a lower modelled margin does not change what the price needs...
    assert metrics(page)["Operating margin it implies"] == before
    # ...but the WACC does: a higher discount rate needs a higher margin to justify the same price.
    page.sidebar.checkbox[0].check().run()
    page.sidebar.slider[3].set_value(0.13).run()
    after = float(metrics(page)["Operating margin it implies"].rstrip("%"))
    assert after > float(before.rstrip("%"))


def test_the_dollar_signs_in_the_implied_sentences_are_escaped(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    [sentence] = [c for c in texts(page.caption) if c.startswith("To justify the market price of")]
    assert "of \\$" in sentence                                       # the backslash is there


def test_the_implied_section_still_appears_when_the_history_is_missing(monkeypatch):
    def down(ticker, usd_per_unit=1.0):
        raise ValueError("Could not get the history from Yahoo Finance: no internet")

    monkeypatch.setattr("data.get_history", down)
    page = run_page(monkeypatch)
    assert not page.exception
    assert "What the market price implies" in texts(page.subheader)
    sentence = [c for c in texts(page.caption) if c.startswith("To justify the market price of")][0]
    assert "In its history" not in sentence


# ---------------------------------------------------------------------------
# The second sensitivity table: price at different margins and growth
# ---------------------------------------------------------------------------

def margin_growth_table_of(page):
    """The margin and growth table of a page: the one whose rows are average operating margins."""
    [table] = [element.value for element in page.dataframe if element.value.index.name == "Average operating margin"]
    return table


def test_the_shift_labels_show_the_average_and_the_shift_or_base():
    assert app.shift_label(0.3765, 0.0) == "37.65% (base)"                      # two decimals, like the assumptions table
    assert app.shift_label(0.2765, -0.10) == "27.65% (-10 pts)"
    assert app.shift_label(0.1010, 0.02) == "10.10% (+2 pts)"
    assert app.shift_label(0.4265, 0.05) == "42.65% (+5 pts)"


def test_the_page_has_the_margin_and_growth_table_under_the_wacc_heatmap(monkeypatch):
    page = run_page(monkeypatch)
    subheaders = texts(page.subheader)
    wacc_table = subheaders.index("Sensitivity: price at different WACC and terminal growth")
    assert subheaders.index("Sensitivity: price at different margins and growth") == wacc_table + 1


def test_the_tables_rows_and_columns_are_the_average_margins_and_growth_with_their_shifts(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    table = margin_growth_table_of(page)
    assert table.index.tolist() == [
        "27.65% (-10 pts)", "32.65% (-5 pts)", "37.65% (base)", "42.65% (+5 pts)", "47.65% (+10 pts)",
    ]
    assert table.columns.tolist() == [
        "4.10% (-4 pts)", "6.10% (-2 pts)", "8.10% (base)", "10.10% (+2 pts)", "12.10% (+4 pts)",
    ]
    assert table.columns.name == "Average revenue growth"


def test_the_middle_cell_is_the_dcf_price_shown_above(monkeypatch):
    page = run_page(monkeypatch)
    table = margin_growth_table_of(page)
    assert app.dollars(table.iloc[2, 2]) == metrics(page)["DCF implied price"]


def test_the_tables_prices_are_the_models_for_each_pair_of_shifts(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    table = margin_growth_table_of(page)
    company = data.get_company_data_with_fallback("ADBE")[0]
    expected = valuation.margin_growth_table(
        app.build_dcf_inputs(company, 0, 0), assumptions.TERMINAL_GROWTH_RATE, None,
        assumptions.MARGIN_GROWTH_TABLE_MARGIN_SHIFTS, assumptions.MARGIN_GROWTH_TABLE_GROWTH_SHIFTS,
    )
    assert table.to_numpy().flatten().tolist() == pytest.approx([price for row in expected["prices"] for price in row])
    assert table.iloc[0, 0] < table.iloc[2, 2] < table.iloc[4, 4]                  # worst corner < base < best corner


def test_the_growth_slider_moves_the_table_and_its_labels(monkeypatch):
    page = run_page(monkeypatch)
    before = margin_growth_table_of(page).iloc[2, 2]
    page.sidebar.slider[0].set_value(1.0).run()                                    # growth +1 point
    assert not page.exception
    table = margin_growth_table_of(page)
    assert table.iloc[2, 2] > before                                               # the middle moves with the sliders
    assert app.dollars(table.iloc[2, 2]) == metrics(page)["DCF implied price"]
    assert table.columns[2] == "9.10% (base)"                                      # the average growth is now 9.10%


def test_the_table_uses_the_wacc_the_reader_set(monkeypatch):
    page = run_page(monkeypatch)
    page.sidebar.checkbox[0].check().run()
    page.sidebar.slider[3].set_value(0.13).run()
    table = margin_growth_table_of(page)
    assert app.dollars(table.iloc[2, 2]) == metrics(page)["DCF implied price"]     # the DCF price at the reader's WACC


def test_the_caption_gives_the_market_price_and_the_dcf_price_with_escaped_dollar_signs(monkeypatch):
    page = run_page(monkeypatch)
    [caption] = [c for c in texts(page.caption) if c.startswith("Each cell moves the operating margin")]
    assert "market price of \\$" in caption and "The bold price, \\$" in caption
    assert "$" not in caption.replace("\\$", "")                                  # every dollar sign has its backslash


def test_another_company_gets_the_margin_and_growth_table_too(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert not page.exception
    table = margin_growth_table_of(page)
    assert app.dollars(table.iloc[2, 2]) == metrics(page)["DCF implied price"]


# ---------------------------------------------------------------------------
# The last twelve months: the company on the same footing as its peers
# ---------------------------------------------------------------------------

def adobe_with_quarters():
    """Yahoo's reply for Adobe with its last four quarters (the `ttm` sheet) and the latest balance
    sheet, on top of the fiscal-year statements the page's other tests use.
    """
    base = adobe_with_four_years()
    income = pd.DataFrame(
        {
            "Total Revenue": [6760e6, 6618e6, 6398e6, 6194e6, 5900e6],
            "Operating Income": [2354e6, 2238e6, 2418e6, 2261e6, 2000e6],
            "Net Income": [1827e6, 1712e6, 1889e6, 1856e6, 1500e6],
        },
        index=QUARTER_ENDS[:5],
    ).T
    cash_flow = pd.DataFrame({"Depreciation And Amortization": [215e6, 193e6, 174e6, 184e6, 170e6]}, index=QUARTER_ENDS[:5]).T
    balance = pd.DataFrame(
        {
            "Long Term Debt": [4766e6], "Current Debt": [1597e6], "Total Debt": [6363e6],
            "Cash Cash Equivalents And Short Term Investments": [5639e6],
        },
        index=QUARTER_ENDS[:1],
    ).T

    class Fake(base):
        def __init__(self, ticker):
            super().__init__(ticker)
            self.quarterly_income_stmt, self.quarterly_cashflow, self.quarterly_balance_sheet = income, cash_flow, balance

    return Fake


def expected_ttm_overview(share_price):
    """The TTM numbers for the page's price, worked out straight from valuation.py (the snapshot's 413 shares)."""
    return valuation.ttm_overview(
        share_price=share_price, shares=413, debt=6363, cash_and_investments=5639, revenue=25970,
        operating_income=9271, depreciation_and_amortisation=766, net_income=7284,
    )


def test_the_overview_puts_the_peer_comparable_numbers_on_the_last_twelve_months(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_quarters())
    expected = expected_ttm_overview(240.74)                     # the page's price from the fake Yahoo
    shown = metrics(page)
    assert shown["EV/Sales"] == app.multiple_or_note(expected["ev_sales"])
    assert shown["EV/EBITDA"] == app.multiple_or_note(expected["ev_ebitda"])
    assert shown["P/E"] == app.multiple_or_note(expected["pe"])
    assert shown["Operating margin"] == app.percent(expected["operating_margin"]) == "35.7%"     # ttm C25
    assert any("the four quarters to 31 Aug 2026" in caption for caption in texts(page.caption))


def test_the_other_overview_numbers_stay_on_the_last_fiscal_year(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_quarters())
    fiscal = run_page(monkeypatch, yahoo=adobe_with_four_years())
    for label in ("Revenue growth", "Free cash flow yield", "Net debt ÷ EBITDA"):
        assert metrics(page)[label] == metrics(fiscal)[label], label
    assert metrics(page)["Revenue growth"] == "10.5%"             # last fiscal year, history F15


def test_the_dcf_itself_does_not_move_with_the_last_twelve_months(monkeypatch):
    with_ttm = run_page(monkeypatch, yahoo=adobe_with_quarters())
    without = run_page(monkeypatch, yahoo=adobe_with_four_years())
    assert metrics(with_ttm)["DCF implied price"] == metrics(without)["DCF implied price"]
    assert metrics(with_ttm)["WACC"] == metrics(without)["WACC"]


def test_the_peers_tables_own_row_uses_the_last_twelve_months_like_the_peers(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_quarters())
    expected = expected_ttm_overview(240.74)
    own = page.dataframe[-1].value.loc["ADBE (this company)"]
    assert own["EV/Sales"] == f"{expected['ev_sales']:.1f}x"
    assert own["Op. margin"] == "35.7%"
    assert any(c.startswith("Each multiple needs at least") and "last twelve months (to 31 Aug 2026)" in c for c in texts(page.caption))


def test_without_the_quarters_everything_stays_on_the_fiscal_year_and_says_so(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    assert metrics(page)["Operating margin"] == "36.6%"           # the fiscal year's margin
    [note] = [c for c in texts(page.caption) if c.startswith("Worked out from the last fiscal year and today's share price: the last twelve months")]
    assert "not available" in note
    assert any("last fiscal year and today's price" in c for c in texts(page.caption))      # the peers caption's fallback


def test_apply_ttm_replaces_only_the_four_peer_comparable_numbers():
    overview = {
        "ev_sales": 4.0, "ev_ebitda": 10.0, "pe": 14.0, "operating_margin": 0.366, "revenue_growth": 0.105,
        "free_cash_flow_yield": 0.08, "net_debt_to_ebitda": -0.04, "free_cash_flow": 8351.0,
    }
    company = {"share_price": 251.47, "shares": 413}
    ttm = {
        "period_end": "31 Aug 2026", "revenue": 25970.0, "operating_income": 9271.0, "net_income": 7284.0,
        "depreciation_and_amortisation": 766.0, "debt": 6363.0, "cash_and_investments": 5639.0,
    }
    got = app.apply_ttm(overview, company, ttm)
    assert got["ev_sales"] == pytest.approx(4.0269969195225261)            # ttm C22
    assert got["ev_ebitda"] == pytest.approx(10.419558633057687)           # C23
    assert got["pe"] == pytest.approx(14.258252333882481)                  # C24
    assert got["operating_margin"] == pytest.approx(0.3569888332691567)    # C25
    for unchanged in ("revenue_growth", "free_cash_flow_yield", "net_debt_to_ebitda", "free_cash_flow"):
        assert got[unchanged] == overview[unchanged]
    assert got["ttm_period_end"] == "31 Aug 2026" and got["ttm_error"] is None
    assert overview["ev_sales"] == 4.0                                      # the original is not changed


def test_apply_ttm_without_the_quarters_changes_nothing_and_records_why():
    overview = {"ev_sales": 4.0, "pe": 14.0, "operating_margin": 0.366}
    got = app.apply_ttm(overview, {"share_price": 1, "shares": 1}, None, "no internet")
    assert (got["ev_sales"], got["pe"], got["operating_margin"]) == (4.0, 14.0, 0.366)
    assert got["ttm_period_end"] is None and got["ttm_error"] == "no internet"


def test_a_missing_da_leaves_only_the_ev_ebitda_out():
    ttm = {
        "period_end": "31 Aug 2026", "revenue": 25970.0, "operating_income": 9271.0, "net_income": 7284.0,
        "depreciation_and_amortisation": None, "debt": 6363.0, "cash_and_investments": 5639.0,
    }
    got = app.apply_ttm({"ev_sales": 1, "ev_ebitda": 1, "pe": 1, "operating_margin": 1}, {"share_price": 251.47, "shares": 413}, ttm)
    assert got["ev_ebitda"] is None and got["ev_sales"] is not None and got["pe"] is not None


def test_the_margin_warning_uses_the_last_twelve_months_margin():
    ttm = {
        "period_end": "30 Sep 2026", "revenue": 5014.0, "operating_income": 1890.0, "net_income": 1861.0,
        "depreciation_and_amortisation": 584.0, "debt": 108.0, "cash_and_investments": 1624.0,
    }
    overview = app.apply_ttm({"operating_margin": 0.306, "ev_sales": 1, "ev_ebitda": 1, "pe": 1}, {"share_price": 150.98, "shares": 107}, ttm)
    warning = app.margin_gap_warning("First Solar", overview["operating_margin"], {"peer_operating_margin": [0.186, 0.006, 0.063]})
    assert "(37.7%) is 31.4 points above" in warning              # First Solar's TTM margin, not its fiscal-year 30.6%


# ---------------------------------------------------------------------------
# Peers by profile in the peer box, and the note when they come from the wider sector
# ---------------------------------------------------------------------------

def run_profile_page(monkeypatch, industry_peers, sector_peers=None):
    """Run Example Corp's page (margin 36.6%, growth 10.5%, worth about $94bn) with made-up peers in its
    industry and, if given, in its wider sector. Both are dictionaries of ticker -> Yahoo info.
    """
    import pandas as pandas_

    sector_peers = sector_peers or {}
    everyone = {**industry_peers, **sector_peers}

    class Industry:
        def __init__(self, key):
            self.top_companies = pandas_.DataFrame({"name": ["x"] * (len(industry_peers) + 1)}, index=["EXMP", *industry_peers])

    class Sector:
        def __init__(self, key):
            self.top_companies = pandas_.DataFrame({"name": ["x"] * (len(sector_peers) + 1)}, index=["EXMP", *sector_peers])

    base = fake_statements_ticker(info=dict(
        ADOBE_YAHOO_INFO, longName="Example Corp", industryKey="widgets", sectorKey="gadgets",
        operatingMargins=0.366, revenueGrowth=0.105,
    ))

    class Fake(base):
        def __init__(self, ticker):
            super().__init__(ticker)
            if ticker in everyone:
                self.info = dict(everyone[ticker])

    monkeypatch.setattr("yfinance.Industry", Industry)
    monkeypatch.setattr("yfinance.Sector", Sector)
    return run_page(monkeypatch, ticker="exmp", yahoo=Fake)


# By size AAA (90bn) would come first, then BBB (80bn), then CCC (60bn). By profile against 36.6% and
# 10.5%: CCC (35%, 10%) is closest, then AAA (30%, 12%), then BBB (5%, 40%).
PROFILE_PEERS = {
    "AAA": peer_info(90, 2.0, 12.0, 20.0, operating_margin=0.30, revenue_growth=0.12),
    "BBB": peer_info(80, 3.0, 16.0, 30.0, operating_margin=0.05, revenue_growth=0.40),
    "CCC": peer_info(60, 4.0, 10.0, 25.0, operating_margin=0.35, revenue_growth=0.10),
}


def test_the_peer_box_is_filled_in_with_the_peers_that_look_most_like_the_company(monkeypatch):
    page = run_profile_page(monkeypatch, PROFILE_PEERS)
    assert page.sidebar.text_input(key="peers_EXMP").value == "CCC, AAA, BBB"      # not AAA, BBB, CCC, which is by size


def test_the_suggested_peers_caption_says_they_are_chosen_by_margin_and_growth(monkeypatch):
    page = run_profile_page(monkeypatch, PROFILE_PEERS)
    [caption] = [c for c in texts(page.caption) if c.startswith("Peers suggested from Yahoo's industry list")]
    assert "operating margin and revenue growth are closest to the company's" in caption
    assert "within a tenth to ten times its size" in caption
    assert "closest in size" not in caption


def test_no_sector_note_when_the_industry_gives_enough_peers(monkeypatch):
    page = run_profile_page(monkeypatch, PROFILE_PEERS)
    assert not any("wider sector" in c for c in texts(page.caption))


SECTOR_PEERS = {
    "SEC1": peer_info(100, 2.5, 13.0, 22.0, operating_margin=0.35, revenue_growth=0.11),
    "SEC2": peer_info(70, 3.5, 15.0, 28.0, operating_margin=0.25, revenue_growth=0.08),
}


def test_a_company_with_one_industry_peer_is_topped_up_from_its_sector_with_a_note(monkeypatch):
    page = run_profile_page(monkeypatch, {"AAA": PROFILE_PEERS["AAA"]}, SECTOR_PEERS)
    assert page.sidebar.text_input(key="peers_EXMP").value == "AAA, SEC1, SEC2"
    [note] = [c for c in texts(page.caption) if "wider sector" in c]
    assert note.startswith("This company's industry had too few suitable peers, so some or all of these come from its wider sector.")
    assert "check that they fit" in note
    assert page.dataframe[-1].value.index.tolist()[1:-1] == ["AAA", "SEC1", "SEC2"]      # the table shows all three


def test_the_sector_note_goes_away_when_the_reader_changes_the_peers(monkeypatch):
    page = run_profile_page(monkeypatch, {"AAA": PROFILE_PEERS["AAA"]}, SECTOR_PEERS)
    page.sidebar.text_input(key="peers_EXMP").set_value("AAA, SEC1").run()
    assert not page.exception
    assert not any("wider sector" in c for c in texts(page.caption))


def test_a_company_with_no_peers_anywhere_still_gets_the_empty_box_and_its_note(monkeypatch):
    page = run_profile_page(monkeypatch, {}, {})
    assert not page.exception
    assert page.sidebar.text_input(key="peers_EXMP").value == ""
    assert any("No suitable peers were found" in c for c in texts(page.caption))


# ---------------------------------------------------------------------------
# Quality: return on invested capital, cash conversion, interest cover, share count change
# ---------------------------------------------------------------------------

def test_the_quality_row_matches_the_history_sheets_quality_block(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    shown = metrics(page)
    assert shown["ROIC"] == "63.2%"                                             # history C32
    assert shown["Cash conversion"] == "1.38x"                                  # F25
    assert shown["Interest cover"] == "33.1x"                                   # C34
    assert shown["Share count change"] == "-9.3%"                               # C35, with "over 3 years" beneath it
    [share_metric] = [metric for metric in page.metric if metric.label == "Share count change"]
    assert share_metric.delta == "over 3 years"


def test_the_history_table_has_cash_conversion_for_each_year(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    table = history_table_of(page)
    assert table.loc["Cash conversion (FCF ÷ net income)"].tolist() == ["1.56x", "1.28x", "1.42x", "1.38x"]     # history C25:F25


def test_the_page_says_what_the_quality_row_is_for(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    [caption] = [c for c in texts(page.caption) if c.startswith("The last row, about quality")]
    assert "last fiscal year" in caption and "tax benefit as no tax" in caption and "buybacks" in caption


def test_without_a_history_the_quality_row_still_shows_what_it_can(monkeypatch):
    page = run_page(monkeypatch)                                                # two years, no shares or cash flow line
    shown = metrics(page)
    assert shown["ROIC"] == "63.2%"                                             # the snapshot's equity and the 10-K figures
    assert shown["Share count change"] == "Not available"
    assert shown["Cash conversion"] == "Not meaningful"                         # no reported free cash flow


def company_for_quality(**changes):
    """A company's figures as the data package holds them, for the quality numbers."""
    company = {
        "ebit": 8706, "income_tax": 1604, "income_before_tax": 8734, "debt": 6210, "cash_and_investments": 6595,
        "net_income": 7130, "stockholders_equity": 11623, "interest_expense": 263,
    }
    company.update(changes)
    return company


HISTORY_FOR_QUALITY = {"free_cash_flow": [7396.0, 9852.0], "diluted_shares": [471.0, 427.0]}


def test_apply_quality_adds_the_four_numbers_and_keeps_the_rest():
    got = app.apply_quality({"ev_sales": 4.0}, company_for_quality(), HISTORY_FOR_QUALITY)
    assert got["ev_sales"] == 4.0
    assert got["roic"] == pytest.approx(0.63242055551568566)                    # history C32
    assert got["cash_conversion"] == pytest.approx(1.3817671809256662)          # F25
    assert got["interest_cover"] == pytest.approx(33.102661596958178)           # C34
    assert got["share_count_change"] == pytest.approx(427 / 471 - 1) and got["share_count_years"] == 1


def test_a_company_without_an_equity_figure_has_no_roic():
    company = company_for_quality()
    del company["stockholders_equity"]
    assert app.apply_quality({}, company, HISTORY_FOR_QUALITY)["roic"] is None


def test_negative_equity_after_buybacks_gives_no_roic():
    got = app.apply_quality({}, company_for_quality(stockholders_equity=-20000), HISTORY_FOR_QUALITY)
    assert got["roic"] is None                                                  # invested capital is below zero


def test_a_tax_benefit_does_not_inflate_roic():
    # Pfizer-like: income tax of -35 on a pre-tax profit of 1,000 is a rate of -3.5%.
    got = app.apply_quality({}, company_for_quality(ebit=1000, income_tax=-35, income_before_tax=1000, debt=0, cash_and_investments=0, stockholders_equity=5000), HISTORY_FOR_QUALITY)
    assert got["roic"] == pytest.approx(0.20)                                   # 1,000 / 5,000, not 1,035 / 5,000


def test_without_a_history_there_is_no_cash_conversion_or_share_change_but_roic_remains():
    got = app.apply_quality({}, company_for_quality(), None)
    assert got["cash_conversion"] is None and got["share_count_change"] is None and got["roic"] is not None


def test_the_interest_cover_text_tells_no_interest_from_not_known():
    assert app.interest_cover_text({"interest_expense": 263, "interest_cover": 33.102661596958178}) == "33.1x"
    assert app.interest_cover_text({"interest_expense": 0, "interest_cover": None}) == "No interest"
    assert app.interest_cover_text({"interest_expense": None, "interest_cover": None}) == "Not available"      # like Apple on Yahoo
    assert app.interest_cover_text({"interest_expense": 10, "interest_cover": -9.0}) == "-9.0x"                # a loss does not cover it


def test_the_share_count_text_gives_the_years_it_covers():
    assert app.share_count_text({"share_count_change": -0.0934, "share_count_years": 3}) == ("-9.3%", "over 3 years")
    assert app.share_count_text({"share_count_change": 0.05, "share_count_years": 1}) == ("5.0%", "over 1 year")
    assert app.share_count_text({"share_count_change": None, "share_count_years": None}) == ("Not available", None)
    assert app.share_count_text({}) == ("Not available", None)


def test_the_multiple_with_two_decimals_or_a_dash():
    assert app.multiple_or_dash(1.3817671809256662) == "1.38x" and app.multiple_or_dash(None) == "–"


# ---------------------------------------------------------------------------
# Fewer requests to Yahoo: slow-changing data is remembered for hours
# ---------------------------------------------------------------------------

def test_slow_data_is_remembered_for_six_hours_and_the_market_for_fifteen_minutes():
    assert app.SLOW_DATA_CACHE_SECONDS == 6 * 60 * 60
    assert app.LIVE_DATA_CACHE_SECONDS == 15 * 60


def test_peer_suggestions_are_looked_up_once_however_often_the_page_is_drawn(monkeypatch):
    calls = []

    def fake_suggest(*arguments):
        calls.append(arguments)
        return {"peer_tickers": ["AAA"], "peer_ev_sales": [2.0], "peer_ev_ebitda": [12.0], "peer_pe": [20.0],
                "peer_operating_margin": [0.3], "peer_source": "industry"}

    monkeypatch.setattr("data.suggest_peers", fake_suggest)
    first = app.load_suggested_peers("EXMP", 94_000)
    second = app.load_suggested_peers("EXMP", 94_000)
    assert first == second and len(calls) == 1
    app.load_suggested_peers("OTHER", 94_000)                                       # another company is a new lookup
    assert len(calls) == 2


def test_the_history_and_the_last_twelve_months_are_each_looked_up_once(monkeypatch):
    history_calls, ttm_calls = [], []
    monkeypatch.setattr("data.get_history", lambda ticker, rate: history_calls.append(ticker) or {"years": ["FY2025"]})
    monkeypatch.setattr("data.get_ttm", lambda ticker, rate: ttm_calls.append(ticker) or {"period_end": "31 Aug 2026"})
    for _ in range(3):
        app.load_history("EXMP", 1.0)
        app.load_ttm("EXMP", 1.0)
    assert history_calls == ["EXMP"] and ttm_calls == ["EXMP"]


def test_the_peers_multiples_and_the_company_are_still_remembered_for_the_shorter_time(monkeypatch):
    # They move with the market, so they keep the 15 minutes: the page uses the shorter constant for them.
    import inspect
    source = inspect.getsource(app)
    assert "@st.cache_data(ttl=LIVE_DATA_CACHE_SECONDS, show_spinner=False)\ndef load_company(" in source
    assert "@st.cache_data(ttl=LIVE_DATA_CACHE_SECONDS, show_spinner=False)\ndef load_peer_multiples(" in source
    for slow in ("load_suggested_peers", "load_history", "load_ttm"):
        assert f"@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)\ndef {slow}(" in source


def test_the_page_shows_the_plain_message_when_yahoo_is_limiting_the_server(monkeypatch):
    page = run_page(monkeypatch, ticker="nvda", yahoo=fake_statements_ticker(info={}))
    assert not page.exception
    [error] = page.error
    assert "Could not value NVDA." in error.value
    assert "Yahoo Finance isn't answering the app right now" in error.value
    assert "company_name" not in error.value                                         # no list of field names any more
    assert app.FOOTER_TEXT in texts(page.caption)                                    # and the footer is still there


def test_adobe_still_works_from_the_snapshot_with_a_warning_when_yahoo_is_limiting_the_server(monkeypatch):
    page = run_page(monkeypatch, yahoo=fake_statements_ticker(info={}))
    assert_footer_and_no_crash(page)
    assert any("could not be reached" in warning for warning in texts(page.warning))
    assert metrics(page)["Market price"] == "$251.47"                                # the frozen snapshot's price


# ---------------------------------------------------------------------------
# Financial Modeling Prep: the backup when Yahoo is limiting the server
# ---------------------------------------------------------------------------

def run_page_with_yahoo_down(monkeypatch, ticker=None, **fmp_replacements):
    """Run the page with Yahoo giving nothing (as when it limits the server) and a working fake of
    Financial Modeling Prep, whose answers can be replaced.
    """
    with_fmp(monkeypatch, **fmp_replacements)
    return run_page(monkeypatch, ticker=ticker, yahoo=fake_statements_ticker(info={}))


def test_adobe_takes_its_live_price_from_fmp_when_yahoo_is_not_answering(monkeypatch):
    page = run_page_with_yahoo_down(monkeypatch)
    assert_footer_and_no_crash(page)
    assert (
        "Share price and beta are live from Financial Modeling Prep, because Yahoo Finance could not be reached."
        in texts(page.caption)
    )
    assert not page.warning
    assert metrics(page)["Market price"] == "$250.00"                                # FMP's price, not the snapshot's


def test_adobe_warns_that_neither_provider_answered_when_it_falls_to_the_snapshot(monkeypatch):
    page = run_page_with_yahoo_down(monkeypatch, profile=[dict(FMP_PROFILE[0], price=None)])
    assert_footer_and_no_crash(page)
    assert any("Neither Yahoo Finance nor Financial Modeling Prep could be reached" in w for w in texts(page.warning))
    assert metrics(page)["Market price"] == "$251.47"


def test_another_company_is_valued_from_fmp_when_yahoo_is_not_answering(monkeypatch):
    page = run_page_with_yahoo_down(monkeypatch, ticker="exmp")
    assert_footer_and_no_crash(page)
    assert not page.error
    assert "All figures are from Financial Modeling Prep's latest annual statements." in texts(page.caption)
    assert "Share price and beta are live from Yahoo Finance." not in texts(page.caption)


def test_the_wacc_table_and_history_name_fmp_when_it_supplied_them(monkeypatch):
    page = run_page_with_yahoo_down(monkeypatch, ticker="exmp")
    [wacc_table] = [table.value for table in page.table if "Beta" in table.value.index]
    assert wacc_table.loc["Beta", "Value"] == "1.50"
    assert wacc_table.loc["Beta", "Where it comes from"] == "Financial Modeling Prep, 5-year monthly"
    assert any(text.startswith("Financial Modeling Prep gives 3 years of figures") for text in texts(page.caption))


def test_the_peers_come_from_fmps_peer_list_and_the_page_says_so(monkeypatch):
    peers = [
        {"symbol": "EXMP", "mktCap": 100_000_000_000},         # the company itself: left out
        {"symbol": "AAA", "mktCap": 90_000_000_000},
        {"symbol": "BBB", "mktCap": 120_000_000_000},
        {"symbol": "HUGE", "mktCap": 3_000_000_000_000},       # thirty times the size: too big
    ]
    page = run_page_with_yahoo_down(monkeypatch, ticker="exmp", **{"stock-peers": peers})
    assert page.sidebar.text_input(key="peers_EXMP").value == "AAA, BBB"
    assert any("Peers suggested from Financial Modeling Prep's peer list" in text for text in texts(page.caption))
    assert any("peers' figures from Financial Modeling Prep" in text for text in texts(page.caption))
    assert metrics(page)["EV/Sales price"] != "Not available"


def test_a_company_fmp_does_not_know_gets_a_plain_error_naming_fmp(monkeypatch):
    page = run_page_with_yahoo_down(monkeypatch, ticker="nope", profile=[])
    [error] = texts(page.error)
    assert error.startswith("Could not value NOPE.")
    assert "Financial Modeling Prep has no figures for NOPE" in error


def test_when_both_providers_are_down_the_error_says_so_plainly(monkeypatch):
    def refuse(path, **parameters):
        raise data.SourceUnavailable("Financial Modeling Prep's free daily limit of 250 requests has been used up.")

    with_fmp(monkeypatch)
    monkeypatch.setattr("data._fmp_get", refuse)
    page = run_page(monkeypatch, ticker="nvda", yahoo=fake_statements_ticker(info={}))
    [error] = texts(page.error)
    assert "Yahoo Finance isn't answering the app right now" in error
    assert "daily limit of 250 requests" in error


def test_the_key_is_copied_from_streamlits_private_settings_into_the_environment(monkeypatch):
    import os

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setattr(st, "secrets", {"FMP_API_KEY": "from-secrets"})
    app.bridge_fmp_key()
    assert os.environ["FMP_API_KEY"] == "from-secrets"
    assert data.fmp_available()


def test_with_no_secrets_at_all_the_page_starts_without_the_backup(monkeypatch):
    class NoSecrets:
        def __getitem__(self, name):
            raise FileNotFoundError("no secrets file")

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setattr(st, "secrets", NoSecrets())
    app.bridge_fmp_key()
    assert not data.fmp_available()


def test_the_provider_is_named_from_the_source_used():
    assert app.provider_name("yahoo") == app.provider_name("live") == "Yahoo Finance"
    assert app.provider_name("fmp") == app.provider_name("live_fmp") == "Financial Modeling Prep"
    assert app.provider_name("snapshot") == "Yahoo Finance"      # the snapshot's figures were copied from Yahoo


# ---------------------------------------------------------------------------
# One-off adjustment to operating income
# ---------------------------------------------------------------------------

def oneoff_box(page):
    return page.sidebar.number_input(key="oneoff_EXMP")


def run_exmp_with_quarters(monkeypatch, adjustment=None):
    """Run a company that is not Adobe (it has Adobe's figures, four years and four quarters), optionally
    after typing a one-off adjustment into the box.
    """
    page = run_page(monkeypatch, ticker="exmp", yahoo=adobe_with_quarters())
    if adjustment is not None:
        oneoff_box(page).set_value(adjustment).run()
    return page


def test_the_adjustment_box_is_in_the_sidebar_for_other_companies_and_starts_at_zero(monkeypatch):
    page = run_exmp_with_quarters(monkeypatch)
    box = oneoff_box(page)
    assert box.label == "Adjust operating income by ($ millions a year)" and box.value == 0.0
    assert "One-off items" in [header.value for header in page.sidebar.header]


def test_adobe_has_no_adjustment_box(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_quarters())
    assert len(page.sidebar.number_input) == 0
    assert "One-off items" not in [header.value for header in page.sidebar.header]


def test_with_no_adjustment_there_is_no_note_and_nothing_changes(monkeypatch):
    plain = run_exmp_with_quarters(monkeypatch)
    zero = run_exmp_with_quarters(monkeypatch, 0)
    assert not any("You have adjusted operating income" in w for w in texts(zero.warning))
    assert metrics(zero) == metrics(plain)


def test_the_adjustment_lowers_the_dcf_price_by_what_the_model_says(monkeypatch):
    page = run_exmp_with_quarters(monkeypatch, -1000)
    assert not page.exception
    company = app.apply_adjustment(data.get_company_data("EXMP", source="yahoo"), -1000)
    inputs = app.build_dcf_inputs(company, 0, 0)
    expected, _ = app.run_valuation(company, inputs, assumptions.TERMINAL_GROWTH_RATE)
    assert metrics(page)["DCF implied price"] == app.dollars(expected["implied_share_price"])
    assert metrics(page)["DCF implied price"] != metrics(run_exmp_with_quarters(monkeypatch))["DCF implied price"]


def test_the_starting_points_margin_is_the_adjusted_one(monkeypatch):
    page = run_exmp_with_quarters(monkeypatch, -1000)
    table = assumptions_on(page)
    assert table["Operating margin"].iloc[0] == "32.42%"                          # starting point C65: (8,706 - 1,000) / 23,769


def test_the_twelve_month_margin_and_ev_ebitda_use_the_adjustment_too(monkeypatch):
    plain = run_exmp_with_quarters(monkeypatch)
    adjusted = run_exmp_with_quarters(monkeypatch, -1000)
    assert metrics(plain)["Operating margin"] == "35.7%"                          # ttm C25
    assert metrics(adjusted)["Operating margin"] == "31.8%"                       # ttm C30: (9,271 - 1,000) / 25,970
    assert float(metrics(adjusted)["EV/EBITDA"].rstrip("x")) > float(metrics(plain)["EV/EBITDA"].rstrip("x"))


def test_the_fiscal_year_numbers_worked_from_ebit_use_the_adjustment(monkeypatch):
    plain = run_exmp_with_quarters(monkeypatch)
    adjusted = run_exmp_with_quarters(monkeypatch, -1000)
    assert metrics(plain)["Interest cover"] == "33.1x" and metrics(adjusted)["Interest cover"] == "29.3x"   # (8,706 - 1,000) / 263
    assert metrics(adjusted)["Net debt ÷ EBITDA"] != metrics(plain)["Net debt ÷ EBITDA"]
    assert metrics(adjusted)["Free cash flow yield"] != metrics(plain)["Free cash flow yield"]


def test_what_is_reported_stays_as_reported(monkeypatch):
    plain = run_exmp_with_quarters(monkeypatch)
    adjusted = run_exmp_with_quarters(monkeypatch, -1000)
    for label in ("P/E", "Cash conversion", "Revenue growth", "EV/Sales", "Market price", "WACC"):
        assert metrics(adjusted)[label] == metrics(plain)[label], label
    assert history_table_of(adjusted).equals(history_table_of(plain))             # the History is as the company reported


def test_the_yellow_note_says_what_changed_and_what_did_not(monkeypatch):
    page = run_exmp_with_quarters(monkeypatch, -1000)
    [note] = [w for w in texts(page.warning) if w.startswith("You have adjusted operating income by")]
    assert "by -$1,000m a year" in note
    assert "The DCF, the margins, EV/EBITDA" in note
    assert "The History, the P/E, cash conversion and revenue growth are as reported" in note


def test_a_positive_amount_adds_back_a_one_off_cost(monkeypatch):
    plain = run_exmp_with_quarters(monkeypatch)
    page = run_exmp_with_quarters(monkeypatch, 500)
    assert "by $500m a year" in [w for w in texts(page.warning) if "You have adjusted" in w][0]
    assert float(metrics(page)["Operating margin"].rstrip("%")) > float(metrics(plain)["Operating margin"].rstrip("%"))


def test_the_reverse_dcf_and_the_tables_follow_the_adjusted_model(monkeypatch):
    plain = run_exmp_with_quarters(monkeypatch)
    adjusted = run_exmp_with_quarters(monkeypatch, -1000)
    # What the price needs does not depend on the model's margin, so the implied margin is unchanged...
    assert metrics(adjusted)["Operating margin it implies"] == metrics(plain)["Operating margin it implies"]
    # ...but the model's own margin in the sentence is the adjusted one (32.42% held flat), and the growth
    # the price implies, which holds the margin as modelled, moves.
    sentence = [c for c in texts(adjusted.caption) if c.startswith("To justify the market price of")][0]
    assert "against 32.4% in the model" in sentence
    assert metrics(adjusted)["Revenue growth it implies"] != metrics(plain)["Revenue growth it implies"]
    assert app.dollars(margin_growth_table_of(adjusted).iloc[2, 2]) == metrics(adjusted)["DCF implied price"]    # the middle is still the DCF price


def test_each_company_has_its_own_adjustment_box(monkeypatch):
    page = run_exmp_with_quarters(monkeypatch)
    assert page.sidebar.number_input(key="oneoff_EXMP") is not None


def test_apply_adjustment_changes_only_ebit_and_leaves_the_original_alone():
    company = {"ebit": 8706.0, "net_income": 7130.0, "income_tax": 1604.0, "income_before_tax": 8734.0}
    adjusted = app.apply_adjustment(company, -1000)
    assert adjusted == {"ebit": 7706.0, "net_income": 7130.0, "income_tax": 1604.0, "income_before_tax": 8734.0}
    assert company["ebit"] == 8706.0


def test_apply_adjustment_to_ttm_changes_only_operating_income_and_copes_without_the_quarters():
    ttm = {"period_end": "31 Aug 2026", "revenue": 25970.0, "operating_income": 9271.0, "net_income": 7284.0}
    adjusted = app.apply_adjustment_to_ttm(ttm, -1000)
    assert adjusted["operating_income"] == 8271.0 and adjusted["revenue"] == 25970.0 and adjusted["net_income"] == 7284.0
    assert ttm["operating_income"] == 9271.0
    assert app.apply_adjustment_to_ttm(None, -1000) is None


def test_the_note_is_none_without_an_adjustment_and_names_the_amount_with_one():
    assert app.adjustment_note(0) is None and app.adjustment_note(0.0) is None
    assert "by -$1,000m a year" in app.adjustment_note(-1000)
    assert "by $250m a year" in app.adjustment_note(250)
