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
    no_interest_expense_company,
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
    assert not page.dataframe


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

def peer_info(market_cap_billions, ev_sales, ev_ebitda, pe, currency="USD"):
    """What Yahoo says about a made-up peer."""
    return {
        "marketCap": market_cap_billions * 1_000_000_000, "currency": currency,
        "enterpriseToRevenue": ev_sales, "enterpriseToEbitda": ev_ebitda, "trailingPE": pe,
    }


# Example Corp is worth about $94bn (price 240.74 times 389.2m shares). LOSS has no P/E, SMALL is
# far too small, FOREIGN trades in pence.
PEERS_IN_THE_INDUSTRY = {
    "AAA": peer_info(80, 2.0, 12.0, 20.0),
    "BBB": peer_info(120, 3.0, 16.0, 30.0),
    "CCC": peer_info(60, 4.0, 10.0, 25.0),
    "LOSS": peer_info(90, 5.0, 14.0, None),
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
    assert metrics(page)["Middle of the prices"] == app.dollars(sorted([sales, ebitda, pe])[1])
    assert any("Peers suggested from Yahoo's industry list" in caption for caption in texts(page.caption))


def test_the_peer_table_shows_a_dash_for_a_multiple_that_is_left_out(monkeypatch):
    page = run_example_page(monkeypatch)
    table = page.dataframe[-1].value                       # the heatmap comes first
    assert list(table.index) == ["LOSS", "AAA", "BBB", "CCC"]
    assert table.loc["LOSS", "P/E"] == "–" and table.loc["LOSS", "EV/Sales"] == "5.0x"
    assert table.loc["AAA", "P/E"] == "20.0x"


def test_the_reader_can_change_the_peers(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("aaa  ccc").run()             # lower case and spaces on purpose
    assert not page.exception
    sales, ebitda, pe = example_prices([2.0, 4.0], [12.0, 10.0], [20.0, 25.0])
    assert metrics(page)["EV/Sales price"] == app.dollars(sales)
    assert metrics(page)["P/E price"] == app.dollars(pe)
    assert list(page.dataframe[-1].value.index) == ["AAA", "CCC"]


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
    assert metrics(page)["Middle of the prices"] == app.dollars((sales + ebitda) / 2)


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
    assert len(page.dataframe[-1].value) == 8


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
    assert list(page.dataframe[-1].value.index) == ["ADSK", "INTU", "CRM", "SNPS"]
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
    table = app.peer_table(peers)
    assert table.loc["A"].tolist() == ["2.0x", "–", "–"]
    assert table.loc["B"].tolist() == ["–", "12.3x", "–"]


def test_a_price_that_could_not_be_worked_out_says_so():
    assert app.price_or_note(None) == "Not enough peers"
    assert app.price_or_note(305.6) == "$305.60"
