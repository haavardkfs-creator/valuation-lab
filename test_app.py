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
import theme
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


def header_of(page):
    """The page's "answer first" header: the HTML the page writes at the top (company name, ticker badge, verdict
    badge and the four headline cards). The first HTML block is the card styling, the second is the header.
    """
    blocks = [element.value for element in page.get("html")]
    [header] = [block for block in blocks if 'class="vl-header"' in block]
    return header


def peer_table_of(page):
    """The peer table of a page: the table whose columns are the multiples and a Flag column. Found by its columns,
    not by its position, so moving sections between tabs does not break the tests that read it.
    """
    [table] = [
        element.value for element in page.dataframe if {"EV/Sales", "Forward P/E", "Flag"} <= set(element.value.columns)
    ]
    return table


def market_price_of(page):
    """The market price a page shows, read from the "Current price" card of its header."""
    return card_values(header_of(page))["Current price"]


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
    assert market_price_of(page) == "$251.47"


def test_an_empty_ticker_box_means_adobe(monkeypatch):
    page = run_page(monkeypatch, ticker="   ")
    assert_footer_and_no_crash(page)
    header = header_of(page)
    assert "<h1>Adobe Inc.</h1>" in header and ">ADBE</span>" in header          # the name and its ticker badge


# ---------------------------------------------------------------------------
# Another company: a starting point, the DCF only
# ---------------------------------------------------------------------------

def other_company():
    """A stand-in for Yahoo's reply about a company that is not Adobe."""
    return fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, longName="Example Corp"))


def test_another_company_gets_a_starting_point_with_a_warning_and_no_multiples_without_peers(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())      # lower case on purpose
    assert_footer_and_no_crash(page)
    header = header_of(page)
    assert "<h1>Example Corp</h1>" in header and ">EXMP</span>" in header
    assert "All figures are from Yahoo Finance's latest annual statements." in texts(page.caption)
    assert not page.warning                                                  # the starting-point caveat is a calm note now
    [note] = texts(page.info)
    assert note.startswith("Starting point, not a forecast")
    assert "Example Corp's last reported margins flat" in note
    assert "banks, loss-makers or early-stage ones" in note
    subheaders = texts(page.subheader)
    assert "Discounted cash flow (DCF)" in subheaders
    assert "Behind the number" in subheaders
    # The fake Yahoo has no industry, so no peers are suggested: the section says how to add some
    # instead of showing prices.
    assert "Peer multiples" in subheaders
    assert "EV/Sales price" not in metrics(page)
    assert any("No suitable peers were found" in caption for caption in texts(page.caption))
    assert market_price_of(page) == "$240.74"


def test_a_company_with_no_interest_expense_is_valued_with_a_note_about_the_estimate(monkeypatch):
    # Like Apple: Yahoo has no interest expense, so the cost of debt is the risk-free rate plus
    # a credit spread (starting point C37) and the page says so.
    page = run_page(monkeypatch, ticker="aapl", yahoo=no_interest_expense_company())
    assert_footer_and_no_crash(page)
    assert not page.error
    [note] = texts(page.warning)
    assert "no interest expense" in note
    assert "6.40%" in note and "1.11%" in note
    [starting_point] = texts(page.info)
    assert starting_point.startswith("Starting point, not a forecast")
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
        ratios, assumptions.TERMINAL_GROWTH_RATE, assumptions.STARTING_POINT_YEARS,
        normal_tax_rate=assumptions.NORMAL_TAX_RATE,
    )
    expected = valuation.run_full_dcf(
        base_revenue=company["revenue"],
        **start,
        risk_free_rate=company["risk_free_rate"],
        beta=valuation.adjusted_beta(company["beta"], assumptions.BETA_WEIGHT_ON_OBSERVED, assumptions.MARKET_BETA),
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


def test_a_company_with_no_pre_tax_profit_gets_the_reason_but_still_its_overview_and_history(monkeypatch):
    loss = dict(ADOBE_YAHOO_INCOME, **{"Pretax Income": (-100e6, 50e6)})
    page = run_page(monkeypatch, ticker="loss", yahoo=fake_statements_ticker(income=loss))
    assert_footer_and_no_crash(page)
    [error] = texts(page.error)
    assert error.startswith("Could not value LOSS.") and "no pre-tax profit" in error
    assert "still shown" in error
    subheaders = texts(page.subheader)
    assert "Overview" in subheaders and "History" in subheaders
    assert "EV/Sales" in metrics(page) and "Operating margin" in metrics(page)
    # Nothing that needs a DCF is drawn: no DCF section, no implied price, no heatmap, no peer multiples.
    assert "DCF implied price" not in metrics(page)
    for section in ("Discounted cash flow (DCF)", "What the market price implies", "Peer multiples"):
        assert section not in subheaders
    assert not page.dataframe


def test_a_loss_maker_with_a_negative_operating_margin_shows_its_overview_numbers_as_they_are(monkeypatch):
    # Ford's shape: operating profit and pre-tax profit both negative, so no tax rate and no free cash flow.
    loss = dict(ADOBE_YAHOO_INCOME, **{
        "Pretax Income": (-600e6, 1e9), "Operating Income": (-400e6, 1e9), "Net Income": (-500e6, 1e9),
    })
    page = run_page(monkeypatch, ticker="loss", yahoo=fake_statements_ticker(income=loss))
    assert_footer_and_no_crash(page)
    assert "Could not value LOSS." in texts(page.error)[0]
    shown = metrics(page)
    assert shown["Operating margin"] == "-1.7%"                  # -400 / 23,769, shown as it is
    assert shown["P/E"] == app.NOT_MEANINGFUL                    # no P/E for a company that lost money


def test_a_discount_rate_that_is_too_low_also_keeps_the_overview_and_history(monkeypatch):
    odd = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, beta=-10))
    page = run_page(monkeypatch, ticker="odd", yahoo=odd)
    assert_footer_and_no_crash(page)
    assert "must be lower than the discount rate" in texts(page.error)[0]
    assert "Overview" in texts(page.subheader) and "History" in texts(page.subheader)


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
    assert market_price_of(page) == "$24.07"        # 240.74 kroner at 10 US cents each


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


def test_a_very_low_wacc_still_draws_the_heatmap_with_the_impossible_cells_left_blank(monkeypatch):
    # A negative beta pulls the WACC to about 4%: fine for the DCF, but the heatmap's lower rows (down to 3 points
    # lower) have a WACC at or below some of its terminal growth rates (up to 3.5%), where the formula has no
    # answer. Those cells stay blank and the rest of the table is drawn. The page adjusts the beta towards 1
    # (two-thirds observed plus one-third of 1), so -0.95 observed is -0.30 in the model.
    low_beta = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, beta=-0.95))
    page = run_page(monkeypatch, ticker="lowb", yahoo=low_beta)
    assert_footer_and_no_crash(page)
    assert not page.error
    assert "DCF implied price" in metrics(page)
    assert "Sensitivity: price at different WACC and terminal growth" in texts(page.subheader)
    captions = texts(page.caption)
    assert not any("This table cannot be drawn" in caption for caption in captions)
    assert any("A blank cell has no answer" in caption for caption in captions)
    # The numbers table under the heatmap has dashes where there is no answer and a price at the base case.
    wacc_table = next(element.value for element in page.dataframe if element.value.index.name == "WACC")
    assert wacc_table.iloc[0].isna().all()                                  # the lowest WACC is below every growth rate
    base_row, base_column = assumptions.HEATMAP_WACC_OFFSETS.index(0.0), assumptions.HEATMAP_TERMINAL_GROWTH_RATES.index(
        assumptions.TERMINAL_GROWTH_RATE
    )
    assert wacc_table.iloc[base_row, base_column] > 0
    assert wacc_table.iloc[-1].notna().all()                                # three points higher: every cell has an answer


def test_when_no_combination_has_an_answer_the_table_says_it_cannot_be_drawn(monkeypatch):
    def impossible(*args, **kwargs):
        raise ValueError("No pairing has an answer.")

    monkeypatch.setattr("valuation.sensitivity_table", impossible)
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    assert any("This table cannot be drawn" in caption for caption in texts(page.caption))
    # The football field still has the five multiples bars, and says its DCF bar could not be drawn.
    assert "Where the price sits" in texts(page.subheader)
    assert any(caption.startswith("The DCF bar is left out") for caption in texts(page.caption))


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

def peer_info(market_cap_billions, ev_sales, ev_ebitda, pe, currency="USD", operating_margin=None, revenue_growth=None, ps=None, forward_pe=None):
    """What Yahoo says about a made-up peer."""
    return {
        "marketCap": market_cap_billions * 1_000_000_000, "currency": currency,
        "enterpriseToRevenue": ev_sales, "enterpriseToEbitda": ev_ebitda, "trailingPE": pe,
        "priceToSalesTrailing12Months": ps, "forwardPE": forward_pe,
        "operatingMargins": operating_margin, "revenueGrowth": revenue_growth,
    }


# Example Corp is worth about $94bn (price 240.74 times 389.2m shares). LOSS has no P/E and, in this
# made-up case, no P/S or forward P/E either, SMALL is far too small, FOREIGN trades in pence.
PEERS_IN_THE_INDUSTRY = {
    "AAA": peer_info(80, 2.0, 12.0, 20.0, operating_margin=0.30, ps=3.0, forward_pe=12.0),
    "BBB": peer_info(120, 3.0, 16.0, 30.0, operating_margin=0.20, ps=4.0, forward_pe=15.0),
    "CCC": peer_info(60, 4.0, 10.0, 25.0, operating_margin=0.10, ps=5.0, forward_pe=18.0),
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


def example_with_peers(forward_eps=10.0):
    """Yahoo's reply about Example Corp and its industry's peers. Analysts expect it to earn `forward_eps`
    a share next year (None: no estimate)."""
    info = dict(ADOBE_YAHOO_INFO, longName="Example Corp", industryKey="widgets")
    if forward_eps is not None:
        info["forwardEps"] = forward_eps
    base = fake_statements_ticker(info=info)

    class Fake(base):
        def __init__(self, ticker):
            super().__init__(ticker)
            if ticker in PEERS_IN_THE_INDUSTRY:
                self.info = dict(PEERS_IN_THE_INDUSTRY[ticker])

    return Fake


def run_example_page(monkeypatch, ticker="exmp", forward_eps=10.0):
    monkeypatch.setattr("yfinance.Industry", FakeIndustry)
    return run_page(monkeypatch, ticker=ticker, yahoo=example_with_peers(forward_eps))


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


def example_ps_price(peer_ps):
    """Work out Example Corp's P/S price straight from valuation.py: revenue times the peers' middle P/S, over shares."""
    company = data.get_company_data("EXMP", source="yahoo")
    return valuation.price_from_ps(
        company["revenue"], valuation.median_of_usable_multiples(peer_ps, 2), company["shares"]
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
    ps = example_ps_price([None, 3.0, 4.0, 5.0])
    assert metrics(page)["P/S price"] == app.dollars(ps)      # LOSS has no P/S, so the median of 3, 4, 5 is 4
    forward_pe = 10.0 * 15.0                                  # next year's EPS of 10 times the peers' middle, 15
    assert metrics(page)["Forward P/E price"] == app.dollars(forward_pe)
    import statistics
    assert metrics(page)["Middle of the five prices"] == app.dollars(
        statistics.median([sales, ebitda, pe, ps, forward_pe])
    )
    assert any("Peers suggested from Yahoo's industry list" in caption for caption in texts(page.caption))


def test_the_peer_table_shows_a_dash_for_a_multiple_that_is_left_out(monkeypatch):
    page = run_example_page(monkeypatch)
    table = peer_table_of(page)                       # the heatmap comes first
    # The company itself comes first and the peer medians last.
    assert list(table.index) == ["EXMP (this company)", "LOSS", "AAA", "BBB", "CCC", "Peer median"]
    assert table.loc["LOSS", "P/E"] == "–" and table.loc["LOSS", "EV/Sales"] == "5.0x"
    assert table.loc["AAA", "P/E"] == "20.0x"
    assert table.loc["LOSS", "Op. margin"] == "-25.0%"            # a loss shows as a negative margin
    assert table.loc["AAA", "Op. margin"] == "30.0%"


def test_the_table_has_the_company_itself_and_the_peer_medians(monkeypatch):
    page = run_example_page(monkeypatch)
    table = peer_table_of(page)
    own = table.loc["EXMP (this company)"]
    assert own["Op. margin"] == "36.6%"                           # EBIT 8,706 over revenue 23,769
    # The medians of the four peers: EV/Sales of 5, 2, 3, 4 is 3.5; EV/EBITDA of 14, 12, 16, 10 is
    # 13; P/E of 20, 30, 25 (LOSS has none) is 25; P/S of 3, 4, 5 (LOSS has none) is 4; margins of
    # -25%, 30%, 20%, 10% make 15%. Forward P/E of 12, 15, 18 (LOSS has none) is 15.
    median = table.loc["Peer median"]
    assert median.tolist() == ["3.5x", "13.0x", "25.0x", "4.0x", "15.0x", "15.0%", ""]
    assert table.loc["AAA", "P/S"] == "3.0x" and table.loc["LOSS", "P/S"] == "–"
    assert table.loc["BBB", "Forward P/E"] == "15.0x" and table.loc["LOSS", "Forward P/E"] == "–"
    assert own["Forward P/E"] == "24.1x"                          # price 240.74 over next year's EPS of 10


def test_the_reader_can_change_the_peers(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("aaa  ccc").run()             # lower case and spaces on purpose
    assert not page.exception
    sales, ebitda, pe = example_prices([2.0, 4.0], [12.0, 10.0], [20.0, 25.0])
    assert metrics(page)["EV/Sales price"] == app.dollars(sales)
    assert metrics(page)["P/E price"] == app.dollars(pe)
    assert list(peer_table_of(page).index) == ["EXMP (this company)", "AAA", "CCC", "Peer median"]


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
    assert len(peer_table_of(page)) == 8 + 2                 # the 8 peers, the company and the median


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
    assert list(peer_table_of(page).index) == [
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
        "peer_ev_ebitda": [-5.0, 12.34], "peer_pe": [0, float("nan")], "peer_ps": [-1.0, 2.5],
        "peer_forward_pe": [None, 9.87],
    }
    peers["peer_operating_margin"] = [-0.1, None]
    overview = {"ev_sales": 4.0, "ev_ebitda": None, "pe": 20.0, "ps": 1.5, "forward_pe": 8.0, "operating_margin": 0.3}
    medians = {
        "median_ev_sales": None, "median_ev_ebitda": None, "median_pe": None, "median_ps": None,
        "median_forward_pe": None,
    }
    table = app.peer_table(peers, "ME (this company)", overview, medians)
    assert table.loc["A"].tolist() == ["2.0x", "–", "–", "–", "–", "-10.0%", "⚠ Low margin"]       # a loss: depressed earnings
    assert table.loc["B"].tolist() == ["–", "12.3x", "–", "2.5x", "9.9x", "–", ""]
    assert table.loc["ME (this company)"].tolist() == ["4.0x", "–", "20.0x", "1.5x", "8.0x", "30.0%", ""]
    assert table.loc["Peer median"].tolist() == ["–", "–", "–", "–", "–", "–", ""]         # one margin is not enough


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
    low_beta = fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, beta=-0.95))
    page = run_page(monkeypatch, ticker="lowb", yahoo=low_beta)
    assert not page.exception
    assert wacc_table_of(page).loc["Beta", "Value"] == "-0.30 (observed -0.95)"


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
    def with_prices(sales, ebitda, pe, ps=None, forward_pe=None):
        return {
            "price_ev_sales": sales, "price_ev_ebitda": ebitda, "price_pe": pe, "price_ps": ps,
            "price_forward_pe": forward_pe,
        }

    assert app.middle_price_label(with_prices(1, 2, 3, 4, 5)) == "Middle of the five prices"
    assert app.middle_price_label(with_prices(1, 2, 3, 4)) == "Middle of the four prices"
    assert app.middle_price_label(with_prices(1, 2, None, 4, 5)) == "Middle of the four prices"      # forward P/E counts too
    assert app.middle_price_label(with_prices(1, 2, 3)) == "Middle of the three prices"
    assert app.middle_price_label(with_prices(1, 2, None, 4)) == "Middle of the three prices"        # P/S counts too
    assert app.middle_price_label(with_prices(None, None, 3, 4)) == "Average of two prices"
    assert app.middle_price_label(with_prices(1, None, 3)) == "Average of two prices"
    assert app.middle_price_label(with_prices(None, None, 3)) == "The only price"
    assert app.middle_price_label(with_prices(None, None, None)) == "Middle of the prices"


def test_a_company_with_no_analyst_estimate_says_so_instead_of_a_forward_pe_price(monkeypatch):
    page = run_example_page(monkeypatch, forward_eps=None)
    assert_footer_and_no_crash(page)
    assert metrics(page)["Forward P/E price"] == "No estimate"
    assert "Middle of the four prices" in metrics(page)               # the other four prices still make a middle
    assert peer_table_of(page).loc["EXMP (this company)", "Forward P/E"] == "–"


def test_a_forward_pe_price_needs_enough_peers_with_a_forward_pe(monkeypatch):
    page = run_example_page(monkeypatch)
    peer_box(page).set_value("LOSS, AAA").run()                       # only AAA has a forward P/E: no middle
    assert metrics(page)["Forward P/E price"] == "Not enough peers"


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
    table = peer_table_of(page)
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
    assert peer_table_of(page).loc["Peer median", "P/E"] == "19.8x"


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
    assert set(peer_table_of(page)["Flag"]) == {""}
    assert not any(c.startswith("⚠") for c in texts(page.caption))
    assert not any("Flagged peers still count" in c for c in texts(page.caption))


def test_adobes_page_flags_synopsys_for_its_pe(monkeypatch):
    page = run_page(monkeypatch)
    table = peer_table_of(page)
    assert table.loc["SNPS", "Flag"] == "⚠ P/E outlier"                      # 82.6x is 3.1 times the peers' middle
    assert table.loc["ADSK", "Flag"] == ""
    import statistics
    middle = f"{statistics.median([32.73, 20.72, 20.97, 82.62]):.1f}x"       # all four peers' P/Es
    assert any(c.startswith(f"⚠ SNPS: its P/E of 82.6x is far from the peers' middle ({middle})") for c in texts(page.caption))
    assert "Middle of the five prices" in metrics(page)                      # Adobe has all five prices


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
    assert subheaders.index("Discounted cash flow (DCF)") < subheaders.index("What the market price implies")       # both in the DCF tab
    assert subheaders.index("Overview") < subheaders.index("Discounted cash flow (DCF)")                          # the Overview tab comes first
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
    assert "market price of \\$" in caption and "the base case, \\$" in caption
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
    own = peer_table_of(page).loc["ADBE (this company)"]
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
    assert peer_table_of(page).index.tolist()[1:-1] == ["AAA", "SEC1", "SEC2"]      # the table shows all three


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
    [caption] = [c for c in texts(page.caption) if c.startswith("Return on invested capital, cash conversion")]
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
    assert market_price_of(page) == "$251.47"                                # the frozen snapshot's price


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
    assert market_price_of(page) == "$250.00"                                # FMP's price, not the snapshot's


def test_adobe_warns_that_neither_provider_answered_when_it_falls_to_the_snapshot(monkeypatch):
    page = run_page_with_yahoo_down(monkeypatch, profile=[dict(FMP_PROFILE[0], price=None)])
    assert_footer_and_no_crash(page)
    assert any("Neither Yahoo Finance nor Financial Modeling Prep could be reached" in w for w in texts(page.warning))
    assert market_price_of(page) == "$251.47"


def test_another_company_is_valued_from_fmp_when_yahoo_is_not_answering(monkeypatch):
    page = run_page_with_yahoo_down(monkeypatch, ticker="exmp")
    assert_footer_and_no_crash(page)
    assert not page.error
    assert "All figures are from Financial Modeling Prep's latest annual statements." in texts(page.caption)
    assert "Share price and beta are live from Yahoo Finance." not in texts(page.caption)


def test_the_wacc_table_and_history_name_fmp_when_it_supplied_them(monkeypatch):
    page = run_page_with_yahoo_down(monkeypatch, ticker="exmp")
    [wacc_table] = [table.value for table in page.table if "Beta" in table.value.index]
    assert wacc_table.loc["Beta", "Value"] == "1.33 (observed 1.50)"
    assert wacc_table.loc["Beta", "Where it comes from"].startswith("Financial Modeling Prep, 5-year monthly, adjusted")
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
# Scenarios: bear, base and bull
# ---------------------------------------------------------------------------

def scenario_rows(page):
    """Return the scenarios table as {"Bear": {...}, "Base": {...}, "Bull": {...}}."""
    [table] = [table.value for table in page.table if list(table.value.index) == ["Bear", "Base", "Bull"]]
    return table.to_dict("index")


def dollars_to_number(text):
    return float(text.replace("$", "").replace(",", ""))


def test_the_page_has_a_scenarios_section_with_a_row_for_each_case(monkeypatch):
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    assert "Scenarios" in texts(page.subheader)
    rows = scenario_rows(page)
    assert rows["Bear"]["Operating margin"] == "-5.0 points" and rows["Bear"]["Revenue growth"] == "-2.0 points"
    assert rows["Base"]["Operating margin"] == "+0.0 points" and rows["Base"]["Probability"] == "50%"
    assert rows["Bull"]["Operating margin"] == "+5.0 points" and rows["Bull"]["Revenue growth"] == "+2.0 points"


def test_the_base_scenario_is_the_dcf_price_on_the_page(monkeypatch):
    page = run_page(monkeypatch)
    assert scenario_rows(page)["Base"]["Price"] == metrics(page)["DCF implied price"]


def test_the_bear_price_is_below_the_base_and_the_bull_above(monkeypatch):
    rows = scenario_rows(run_page(monkeypatch))
    bear, base, bull = (dollars_to_number(rows[name]["Price"]) for name in ("Bear", "Base", "Bull"))
    assert bear < base < bull


def test_the_weighted_price_is_the_probabilities_times_the_prices(monkeypatch):
    page = run_page(monkeypatch)
    rows = scenario_rows(page)
    bear, base, bull = (dollars_to_number(rows[name]["Price"]) for name in ("Bear", "Base", "Bull"))
    assert dollars_to_number(metrics(page)["Probability-weighted price"]) == pytest.approx(
        0.25 * bear + 0.5 * base + 0.25 * bull, abs=0.02              # each price on the page is rounded to the cent
    )
    assert "Weighted price vs market" in metrics(page)


def test_the_scenario_boxes_start_at_the_defaults_in_assumptions(monkeypatch):
    page = run_page(monkeypatch)
    assert page.sidebar.number_input(key="scenario_bear_margin").value == assumptions.SCENARIO_BEAR_MARGIN_POINTS
    assert page.sidebar.number_input(key="scenario_bull_growth").value == assumptions.SCENARIO_BULL_GROWTH_POINTS
    chances = [page.sidebar.number_input(key=f"scenario_{name}_chance").value for name in ("bear", "base", "bull")]
    assert chances == assumptions.SCENARIO_PROBABILITIES_PERCENT


def test_a_bear_case_cannot_be_set_above_no_change_nor_a_bull_case_below(monkeypatch):
    page = run_page(monkeypatch)
    assert page.sidebar.number_input(key="scenario_bear_margin").max == 0.0
    assert page.sidebar.number_input(key="scenario_bull_margin").min == 0.0


def test_changing_the_bear_case_changes_its_price_and_the_weighted_price(monkeypatch):
    page = run_page(monkeypatch)
    before = scenario_rows(page)["Bear"]["Price"], metrics(page)["Probability-weighted price"]
    page.sidebar.number_input(key="scenario_bear_margin").set_value(-10.0).run()
    after = scenario_rows(page)["Bear"]["Price"], metrics(page)["Probability-weighted price"]
    assert dollars_to_number(after[0]) < dollars_to_number(before[0])
    assert dollars_to_number(after[1]) < dollars_to_number(before[1])


def test_probabilities_that_do_not_add_to_100_give_a_plain_warning_and_no_prices(monkeypatch):
    page = run_page(monkeypatch)
    page.sidebar.number_input(key="scenario_bear_chance").set_value(40).run()      # 40 + 50 + 25 = 115
    assert not page.exception
    assert any("add up to 100%, not 115.0%" in warning for warning in texts(page.warning))
    assert "Probability-weighted price" not in metrics(page)
    assert app.FOOTER_TEXT in texts(page.caption)                                    # the rest of the page still draws


def test_scenarios_move_with_the_sliders_because_the_base_is_the_current_dcf(monkeypatch):
    page = run_page(monkeypatch)
    before = dollars_to_number(scenario_rows(page)["Base"]["Price"])
    page.sidebar.slider[0].set_value(2.0).run()                                      # growth +2 points
    after = dollars_to_number(scenario_rows(page)["Base"]["Price"])
    assert after > before
    assert scenario_rows(page)["Base"]["Price"] == metrics(page)["DCF implied price"]


def test_another_company_gets_scenarios_too(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp")
    assert_footer_and_no_crash(page)
    assert scenario_rows(page)["Base"]["Price"] == metrics(page)["DCF implied price"]


def test_scenarios_sit_right_after_what_the_market_price_implies(monkeypatch):
    headings = texts(run_page(monkeypatch).subheader)
    assert headings.index("Scenarios") == headings.index("What the market price implies") + 1


# ---------------------------------------------------------------------------
# A normal tax rate when last year's was negative, and the adjusted beta
# ---------------------------------------------------------------------------

def negative_tax_company():
    """A stand-in for Yahoo's reply about a company that got a tax benefit last year (as Pfizer did)."""
    income = dict(ADOBE_YAHOO_INCOME, **{"Tax Provision": (-266e6, 1371e6), "Pretax Income": (7520e6, 6931e6)})
    return fake_statements_ticker(income=income, info=dict(ADOBE_YAHOO_INFO, longName="Example Corp"))


def test_a_negative_tax_rate_is_replaced_and_the_page_says_so(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=negative_tax_company())
    assert_footer_and_no_crash(page)
    assert any(
        "tax rate last year was -3.54%" in warning and "normal rate of 21.00%" in warning
        for warning in texts(page.warning)
    )
    wacc = wacc_table_of(page)
    assert wacc.loc["Tax rate", "Value"] == "21.00%"
    assert wacc.loc["Tax rate", "Where it comes from"].startswith("The normal US rate, because last year's was negative")


def test_a_positive_tax_rate_is_left_alone_and_there_is_no_tax_warning(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert not any("tax rate last year" in warning for warning in texts(page.warning))
    assert wacc_table_of(page).loc["Tax rate", "Where it comes from"].startswith("Last year's rate")


def test_the_forecast_uses_the_normal_tax_rate_for_a_company_with_a_tax_benefit():
    company = data.get_company_data("ADBE")
    company = dict(company, ticker="PFE", income_tax=-266.0, income_before_tax=7520.0, prior_year_revenue=21505.0)
    assert app.forecast_assumptions(company)["tax_rate"] == assumptions.NORMAL_TAX_RATE


def test_another_company_uses_the_adjusted_beta_and_the_table_shows_both(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())          # observed beta 1.383
    wacc = wacc_table_of(page)
    adjusted = 2 / 3 * 1.383 + 1 / 3
    assert wacc.loc["Beta", "Value"] == f"{adjusted:.2f} (observed 1.38)"
    assert "adjusted" in wacc.loc["Beta", "Where it comes from"]


def test_adobe_keeps_its_observed_beta(monkeypatch):
    page = run_page(monkeypatch)
    wacc = wacc_table_of(page)
    assert wacc.loc["Beta", "Value"] == "1.38"
    assert "adjusted" not in wacc.loc["Beta", "Where it comes from"]


def test_the_model_beta_is_the_observed_one_for_adobe_and_adjusted_for_others():
    adobe = dict(data.get_company_data("ADBE"), beta=1.5)
    assert app.model_beta(adobe) == 1.5
    assert app.model_beta(dict(adobe, ticker="PFE", beta=0.3)) == pytest.approx(2 / 3 * 0.3 + 1 / 3)


def test_the_adjusted_beta_lifts_a_low_beta_companys_wacc_and_lowers_a_high_beta_companys(monkeypatch):
    for observed_beta, lifted in ((0.3, True), (2.0, False)):
        monkeypatch.setattr("yfinance.Ticker", fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, beta=observed_beta)))
        company = data.get_company_data("EXMP", source="yahoo")
        used = app.build_dcf_inputs(company, 0.0, 0.0)
        unadjusted = dict(used, beta=observed_beta)
        assert (app.model_wacc(used) > app.model_wacc(unadjusted)) is lifted


# ---------------------------------------------------------------------------
# The cash flow check: the model's free cash flow against the reported one
# ---------------------------------------------------------------------------

def adobe_with_reported_free_cash_flow(latest):
    """Yahoo's reply for Adobe with four years, but with this reported free cash flow ($) for the latest year."""
    base = adobe_with_four_years()

    class Fake(base):
        def __init__(self, ticker):
            super().__init__(ticker)
            if hasattr(self, "cashflow") and "Free Cash Flow" in self.cashflow.index:
                self.cashflow = self.cashflow.copy()
                self.cashflow.loc["Free Cash Flow", self.cashflow.columns[0]] = latest

    return Fake


def cash_flow_warnings(page):
    return [warning for warning in texts(page.warning) if "free cash flow" in warning and "above what the company reports" in warning]


def test_the_page_warns_when_the_models_cash_flow_is_far_above_the_reported_one(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_reported_free_cash_flow(3000e6))
    assert_footer_and_no_crash(page)
    [warning] = cash_flow_warnings(page)
    assert "Adobe Inc.'s last year" in warning and "$3,000m" in warning
    assert "adjust operating income in the sidebar" in warning


def test_the_warning_says_how_far_above_it_is(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_reported_free_cash_flow(3000e6))
    model_figure = app.company_overview(data.get_company_data("ADBE"))["free_cash_flow"]
    expected = f"{(model_figure / 3000 - 1) * 100:.0f}% above"
    assert expected in cash_flow_warnings(page)[0]


def test_the_page_is_quiet_when_the_two_cash_flows_agree(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_reported_free_cash_flow(9852e6))
    assert not cash_flow_warnings(page)


def test_the_limit_is_the_one_in_assumptions_and_is_not_below_one():
    assert assumptions.FREE_CASH_FLOW_RATIO_WARNING == 1.25
    assert assumptions.FREE_CASH_FLOW_RATIO_WARNING >= 1


def test_the_warning_function_gives_nothing_when_the_overview_has_no_model_cash_flow():
    history = {"free_cash_flow": [None, 9000.0]}
    assert app.free_cash_flow_warning(history, {"free_cash_flow": None}, "Example Corp") is None


def test_the_warning_function_names_both_figures_and_the_gap():
    history = {"free_cash_flow": [None, 9075.0]}
    text = app.free_cash_flow_warning(history, {"free_cash_flow": 16632.0}, "Pfizer")
    assert "Pfizer's last year ($16,632m) is 83% above what the company reports ($9,075m)" in text


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
    assert not [box for box in page.sidebar.number_input if box.key.startswith("oneoff_")]
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
    for label in ("P/E", "Cash conversion", "Revenue growth", "EV/Sales", "WACC"):
        assert metrics(adjusted)[label] == metrics(plain)[label], label
    assert market_price_of(adjusted) == market_price_of(plain)
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


# ---------------------------------------------------------------------------
# News and management: headlines and top officers under every company
# ---------------------------------------------------------------------------

def headline(title, provider="Zacks", published="2026-11-20", url="https://finance.yahoo.com/news/a.html"):
    """A headline as data.fetch_yahoo_news hands it to the page."""
    return {"title": title, "publisher": provider, "published": published, "url": url}


def yahoo_with_news(headlines, officers, info=None, income=None):
    """Yahoo's reply for an Adobe-like company that also has the given headlines (as yfinance's raw news items) and
    officers.
    """
    base = fake_statements_ticker(
        income=income, info=dict(ADOBE_YAHOO_INFO if info is None else info, companyOfficers=officers)
    )

    class WithNews(base):
        @property
        def news(self):
            if headlines is None:
                raise ConnectionError("no internet")
            return [
                {"content": {
                    "title": item["title"], "pubDate": item["published"] + "T10:00:00Z",
                    "provider": {"displayName": item["publisher"]}, "canonicalUrl": {"url": item["url"]},
                }}
                for item in headlines
            ]

    return WithNews


def test_text_from_outside_is_made_safe_for_markdown():
    assert app.plain_text_for_markdown("Profit up $5 to [a] *record*") == r"Profit up \$5 to \[a\] \*record\*"
    assert app.plain_text_for_markdown("abc ABC 123") == "abc ABC 123"              # letters, digits and spaces: unchanged
    assert app.plain_text_for_markdown("") == ""


def test_a_headline_is_a_link_with_its_publisher_and_date():
    assert app.headline_line(headline("Adobe wins")) == (
        "- [Adobe wins](https://finance.yahoo.com/news/a.html) (Zacks, 20 Nov 2026)"
    )


def test_a_headline_without_a_safe_link_is_plain_text_and_loses_missing_parts():
    assert app.headline_line(headline("No link", url=None, provider=None, published=None)) == "- No link"
    assert app.headline_line(headline("Just the date", url=None, provider=None)) == "- Just the date (20 Nov 2026)"


def test_a_bracket_in_a_link_address_cannot_end_the_link_early():
    line = app.headline_line(headline("x", url="https://example.com/a(b)"))
    assert "(https://example.com/a%28b%29)" in line


def test_a_date_that_is_not_a_real_date_is_shown_as_it_came():
    assert app.headline_line(headline("x", url=None, provider=None, published="soon")).endswith("(soon)")


def test_an_officer_is_a_bold_name_and_a_title():
    assert app.officer_line({"name": "Mr. Jane Doe", "title": "Chairman & CEO"}) == r"- **Mr\. Jane Doe**, Chairman \& CEO"
    assert app.officer_line({"name": "Ms. No Title", "title": None}) == r"- **Ms\. No Title**"


def test_the_page_shows_headlines_and_officers_for_adobe(monkeypatch):
    yahoo = yahoo_with_news(
        [headline("Adobe launches Firefly 5", "Simply Wall St.", "2026-11-19")],
        [{"name": "Mr. Shantanu  Narayen", "title": "Chairman & CEO"}],
    )
    page = run_page(monkeypatch, yahoo=yahoo)
    assert_footer_and_no_crash(page)
    assert "News and management" in texts(page.subheader)
    shown = "\n".join(texts(page.markdown)).splitlines()          # each list is one markdown block of bullet lines
    # The full stop in "St." gets a backslash, which markdown shows as a plain full stop.
    assert r"- [Adobe launches Firefly 5](https://finance.yahoo.com/news/a.html) (Simply Wall St\., 19 Nov 2026)" in shown
    assert any(line.startswith("- **Mr\\. Shantanu Narayen**, Chairman") for line in shown)


def test_the_section_is_at_the_end_of_the_overview_tab_and_the_footer_is_last_on_the_page(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_news([headline("A")], []))
    subheaders = texts(page.subheader)
    overview_sections = subheaders[subheaders.index("Where the price sits"):subheaders.index("Discounted cash flow (DCF)")]
    assert overview_sections[-1] == "News and management"            # the last section of the Overview tab
    assert page.main.caption[-1].value == app.FOOTER_TEXT          # the main area only: the sidebar has captions too


def test_only_the_newest_few_headlines_and_officers_are_shown(monkeypatch):
    many = [headline(f"Story number {number}") for number in range(1, 9)]
    officers = [{"name": f"Officer {number}", "title": "VP"} for number in range(1, 9)]
    page = run_page(monkeypatch, yahoo=yahoo_with_news(many, officers))
    shown = "\n".join(texts(page.markdown))
    assert f"Story number {assumptions.NEWS_ITEMS_SHOWN}" in shown
    assert f"Story number {assumptions.NEWS_ITEMS_SHOWN + 1}" not in shown
    assert f"Officer {assumptions.OFFICERS_SHOWN}" in shown and f"Officer {assumptions.OFFICERS_SHOWN + 1}" not in shown


def test_a_headline_with_a_dollar_sign_and_a_bracket_is_shown_as_written(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_news([headline("Stock jumps $5 [update] *now*")], []))
    assert any(r"[Stock jumps \$5 \[update\] \*now\*](" in line for line in texts(page.markdown))


def test_no_headlines_and_no_officers_say_so_instead_of_leaving_a_hole(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_news([], []))
    assert_footer_and_no_crash(page)
    captions = texts(page.caption)
    assert "Yahoo Finance has no recent headlines for ADBE." in captions
    assert "Yahoo Finance lists no officers for ADBE." in captions


def test_headlines_that_cannot_be_fetched_still_leave_the_officers(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_news(None, [{"name": "Ms. Jane Doe", "title": "CFO"}]))
    assert_footer_and_no_crash(page)
    assert "The headlines could not be fetched right now." in texts(page.caption)
    assert any("Jane Doe" in line for line in texts(page.markdown))


def test_when_yahoo_is_busy_the_section_says_so_and_the_rest_of_the_page_still_works(monkeypatch):
    monkeypatch.setattr("data._yahoo_busy_until", 10**12)         # Adobe then comes from its snapshot, without Yahoo
    page = AppTest.from_file(APP_FILE, default_timeout=60).run()
    assert_footer_and_no_crash(page)
    assert any(caption.startswith("The news and the officers are not available right now.") for caption in texts(page.caption))
    assert "DCF implied price" in metrics(page)                 # the valuation is unaffected (Adobe's snapshot)


def test_a_company_that_lost_money_still_gets_news_and_management(monkeypatch):
    loss = dict(ADOBE_YAHOO_INCOME, **{"Pretax Income": (-100e6, 50e6)})
    yahoo = yahoo_with_news([headline("Loss maker restructures")], [{"name": "Mr. Boss", "title": "CEO"}], income=loss)
    page = run_page(monkeypatch, ticker="loss", yahoo=yahoo)
    assert_footer_and_no_crash(page)
    assert "Could not value LOSS." in texts(page.error)[0]
    assert "News and management" in texts(page.subheader)
    assert any("Loss maker restructures" in line for line in texts(page.markdown))


def test_a_ticker_that_cannot_be_found_gets_no_news_section(monkeypatch):
    nothing = fake_statements_ticker(income={}, cash_flow={}, balance={}, info={})
    monkeypatch.setattr("data._start_yahoo_cooldown", lambda: None)
    page = run_page(monkeypatch, ticker="nope", yahoo=nothing)
    assert "News and management" not in texts(page.subheader)


# ---------------------------------------------------------------------------
# The "answer first" header: name, verdict, four cards and a price sparkline (redesign, Phase 2)
# ---------------------------------------------------------------------------

def yahoo_with_prices(info=None, income=None, closes=None):
    """Yahoo's reply for an Adobe-like company that also has a year of closing prices (two days by default)."""
    base = fake_statements_ticker(income=income, info=info)
    prices = {"2026-11-19": 200.0, "2026-11-20": 210.0} if closes is None else closes

    class WithHistory(base):
        def history(self, period):
            return pd.DataFrame({"Close": list(prices.values())}, index=pd.to_datetime(list(prices)))

    return WithHistory


def card_values(header):
    """The headline cards of a header as {label: value}, read back out of the HTML."""
    import re
    return dict(re.findall(
        r'class="vl-kpi-label">([^<]+)(?:<span[^>]*>\?</span>)?</div><div class="vl-kpi-value[^"]*">([^<]+)</div>', header
    ))


def test_the_header_cards_agree_with_the_dcf_tab_and_with_each_other(monkeypatch):
    page = run_page(monkeypatch)
    cards = card_values(header_of(page))
    shown = metrics(page)
    assert cards["DCF value per share"] == shown["DCF implied price"]                  # the DCF tab's own card
    price, dcf_price = (float(cards[label].lstrip("$").replace(",", "")) for label in ("Current price", "DCF value per share"))
    assert cards["Upside / downside"] == theme.change_text(dcf_price / price - 1)       # the upside follows from the two prices
    assert list(cards) == ["Current price", "DCF value per share", "Upside / downside", "Multiples value"]


def test_the_header_multiples_value_is_the_middle_of_the_multiples_prices(monkeypatch):
    page = run_page(monkeypatch)
    middle_label = next(label for label in metrics(page) if label.startswith("Middle of the"))
    assert card_values(header_of(page))["Multiples value"] == metrics(page)[middle_label]


def test_a_big_upside_is_undervalued_in_the_up_colour(monkeypatch):
    header = header_of(run_page(monkeypatch))
    assert "▲ UNDERVALUED" in header and "vl-badge vl-badge-up" in header
    assert 'class="vl-kpi-value vl-up">▲ +' in header


def test_a_price_far_above_the_dcf_value_is_overvalued_in_the_down_colour(monkeypatch):
    page = run_page(monkeypatch, yahoo=fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, currentPrice=900.0)))
    header = header_of(page)
    assert "▼ OVERVALUED" in header and "vl-badge vl-badge-down" in header
    assert 'class="vl-kpi-value vl-down">▼ -' in header


def test_a_price_close_to_the_dcf_value_is_fairly_valued_with_no_colour_on_the_upside(monkeypatch):
    page = run_page(monkeypatch, yahoo=fake_statements_ticker(info=dict(ADOBE_YAHOO_INFO, currentPrice=290.0)))
    header = header_of(page)
    assert "● FAIRLY VALUED" in header
    assert 'class="vl-badge"' in header                           # grey: neither the up nor the down class


def test_the_header_says_what_the_verdict_rests_on_and_that_it_is_not_advice(monkeypatch):
    header = header_of(run_page(monkeypatch))
    assert "with 15% either way" in header and "not investment advice" in header


def test_without_a_dcf_the_header_has_no_verdict_and_the_cards_that_need_one_say_so(monkeypatch):
    loss = dict(ADOBE_YAHOO_INCOME, **{"Pretax Income": (-100e6, 50e6)})
    page = run_page(monkeypatch, ticker="loss", yahoo=fake_statements_ticker(income=loss))
    assert_footer_and_no_crash(page)
    header = header_of(page)
    cards = card_values(header)
    assert "NO VERDICT" in header and "No DCF could be built for this company" in header
    assert cards["Current price"].startswith("$")                 # the price is still there
    assert cards["DCF value per share"] == cards["Upside / downside"] == cards["Multiples value"] == "Not available"
    assert header.count("vl-muted") == 3                          # the three empty cards are muted


def test_a_company_without_peers_has_no_multiples_value_but_a_dcf_value(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    header = header_of(page)
    cards = card_values(header)
    assert cards["Multiples value"] == "Not available" and "No peer figures" in header
    assert cards["DCF value per share"].startswith("$")


def test_the_company_name_from_yahoo_is_shown_as_text_and_can_never_become_page_code(monkeypatch):
    nasty = dict(ADOBE_YAHOO_INFO, longName='<script>alert("x")</script> & Co')
    page = run_page(monkeypatch, ticker="evil", yahoo=fake_statements_ticker(info=nasty))
    header = header_of(page)
    assert "<script>" not in header
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; Co" in header


def test_the_header_follows_the_sliders(monkeypatch):
    page = run_page(monkeypatch)
    before = card_values(header_of(page))["DCF value per share"]
    page.sidebar.slider[1].set_value(-2.0).run()                  # an operating margin 2 points lower, every year
    after = card_values(header_of(page))["DCF value per share"]
    assert after != before
    assert after == metrics(page)["DCF implied price"]


def test_the_price_sparkline_is_drawn_when_yahoo_has_the_prices(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_prices())
    assert_footer_and_no_crash(page)
    assert "Share price, last 12 months" in texts(page.caption)
    assert len(page.get("plotly_chart")) == 11                    # the sparkline, the football field, the two history charts, the three behind the number, the two heatmaps and the two peer charts


def test_without_price_history_the_header_still_draws_and_just_leaves_the_chart_out(monkeypatch):
    page = run_page(monkeypatch)                                  # the usual fake has no history() at all
    assert_footer_and_no_crash(page)
    assert "Share price, last 12 months" not in texts(page.caption)
    assert len(page.get("plotly_chart")) == 10                    # no sparkline; the other ten remain
    assert "▲ UNDERVALUED" in header_of(page)


def test_the_sparkline_has_no_axes_and_shows_the_date_and_price_on_hover():
    figure = app.price_sparkline([
        {"date": "2026-11-18", "close": 100.0}, {"date": "2026-11-19", "close": 120.0}, {"date": "2026-11-20", "close": 110.0},
    ])
    assert figure.layout.xaxis.visible is False and figure.layout.yaxis.visible is False
    assert list(figure.data[0].y) == [100.0, 120.0, 110.0]
    assert figure.data[0].line.color == theme.ACCENT
    assert "%{x|%d %b %Y}" in figure.data[0].hovertemplate and "$%{y:,.2f}" in figure.data[0].hovertemplate
    low, high = figure.layout.yaxis.range
    assert low < 100.0 and high > 120.0                           # a little air above and below the line


def test_a_flat_price_line_still_gets_a_sensible_range():
    figure = app.price_sparkline([{"date": "2026-11-19", "close": 50.0}, {"date": "2026-11-20", "close": 50.0}])
    low, high = figure.layout.yaxis.range
    assert low < 50.0 < high


# ---------------------------------------------------------------------------
# The charts: football field, waterfall, free cash flow and the terminal value ring (redesign, Phase 3a)
# ---------------------------------------------------------------------------

FIELD_ROWS = [
    {"label": "52-week", "kind": "trading", "low": 199.5, "middle": None, "high": 324.19},
    {"label": "DCF", "kind": "dcf", "low": 253.0, "middle": 305.6, "high": 390.1},
    {"label": "EV/Sales", "kind": "multiple", "low": 272.9, "middle": 333.6, "high": 437.2},
]

DCF_RESULT = {
    "pv_of_forecast": 37_767.0, "pv_of_terminal_value": 88_882.0, "enterprise_value": 126_649.0,
    "net_debt": -385.0, "equity_value": 127_034.0, "implied_share_price": 307.59,
    "free_cash_flows": [9_000.0, 10_000.0, 11_000.0, 12_000.0, 13_000.0],
}

HISTORY = {
    "years": ["FY2024", "FY2025"], "revenue": [21_505.0, 23_769.0], "operating_income": [7_741.0, 8_706.0],
    "free_cash_flow": [7_000.0, 9_852.0], "net_income": [5_560.0, 7_130.0], "diluted_shares": [450.0, 440.0],
}


def test_the_football_field_headline_counts_the_methods_above_the_price():
    assert app.football_field_headline("Adobe Inc.", 6, 6) == "Adobe Inc. trades below the middle value of every valuation method."
    assert app.football_field_headline("Adobe Inc.", 0, 6) == "Adobe Inc. trades above the middle value of every valuation method."
    assert app.football_field_headline("Adobe Inc.", 2, 6) == "Adobe Inc. trades below the middle value of 2 of 6 valuation methods."
    assert app.football_field_headline("Adobe Inc.", 1, 1) == "Adobe Inc. trades below the middle value of every valuation method."
    assert app.football_field_headline("Adobe Inc.", 0, 0) is None


def test_the_football_field_has_one_bar_per_method_from_its_low_to_its_high():
    figure = app.football_field_figure(FIELD_ROWS, 217.71)
    bars = figure.data[0]
    assert list(bars.y) == ["52-week", "DCF", "EV/Sales"]
    assert list(bars.base) == [199.5, 253.0, 272.9]
    assert list(bars.x) == pytest.approx([324.19 - 199.5, 390.1 - 253.0, 437.2 - 272.9])
    assert bars.orientation == "h"


def test_only_the_dcf_bar_is_in_the_accent_colour_and_every_other_bar_is_grey():
    bars = app.football_field_figure(FIELD_ROWS, 217.71).data[0]
    assert list(bars.marker.color) == [theme.GREY, theme.ACCENT, theme.GREY]


def test_a_white_tick_marks_the_middle_of_every_method_that_has_one():
    ticks = app.football_field_figure(FIELD_ROWS, 217.71).data[1]
    assert list(ticks.y) == ["DCF", "EV/Sales"]                       # the 52-week range has no middle
    assert list(ticks.x) == [305.6, 333.6]
    assert ticks.marker.color == theme.TEXT


def test_a_dashed_line_marks_the_market_price_and_the_axis_covers_every_bar_and_the_line():
    figure = app.football_field_figure(FIELD_ROWS, 217.71)
    [line] = figure.layout.shapes
    assert line.x0 == line.x1 == 217.71 and line.line.dash == "dash"
    assert any("Market price $217.71" in annotation.text for annotation in figure.layout.annotations)
    low, high = figure.layout.xaxis.range
    assert low < 199.5 and high > 437.2


def test_a_market_price_below_every_bar_still_fits_on_the_axis():
    low, high = app.football_field_figure(FIELD_ROWS, 50.0).layout.xaxis.range
    assert low < 50.0 and high > 437.2


def test_the_first_row_is_drawn_at_the_top_and_the_bars_show_the_range_on_hover():
    figure = app.football_field_figure(FIELD_ROWS, 217.71)
    assert figure.layout.yaxis.autorange == "reversed"
    assert "$%{customdata[0]:,.2f} to $%{customdata[1]:,.2f}" in figure.data[0].hovertemplate


def test_the_waterfall_adds_the_two_present_values_then_net_cash_to_reach_the_equity_value():
    figure = app.valuation_waterfall(DCF_RESULT)
    waterfall = figure.data[0]
    assert list(waterfall.x) == ["Years 1-5", "Terminal value", "Enterprise value", "Net cash", "Equity value"]
    assert list(waterfall.measure) == ["relative", "relative", "total", "relative", "total"]
    assert list(waterfall.y) == pytest.approx([37.767, 88.882, 126.649, 0.385, 127.034])       # $ billions
    assert list(waterfall.text) == ["$37.8B", "$88.9B", "$126.6B", "$385M", "$127.0B"]
    assert figure.layout.yaxis.tickprefix == "$" and figure.layout.yaxis.ticksuffix == "B"


def test_the_waterfall_takes_net_debt_away_and_says_net_debt():
    in_debt = dict(DCF_RESULT, net_debt=8_468.0, equity_value=118_181.0)
    waterfall = app.valuation_waterfall(in_debt).data[0]
    assert waterfall.x[3] == "Net debt" and waterfall.y[3] == pytest.approx(-8.468)
    assert waterfall.text[3] == "-$8.5B"


def test_the_waterfall_colours_mean_something():
    waterfall = app.valuation_waterfall(DCF_RESULT).data[0]
    assert waterfall.increasing.marker.color == theme.ACCENT          # adds value
    assert waterfall.decreasing.marker.color == theme.DOWN            # takes value away
    assert waterfall.totals.marker.color == theme.TEXT                # the results


def test_the_waterfall_headline_says_how_enterprise_value_becomes_a_share_price():
    assert app.waterfall_headline(DCF_RESULT) == (
        "$126.6B of enterprise value plus $385M of net cash is $127.0B of equity, or $307.59 a share."
    )
    in_debt = dict(DCF_RESULT, net_debt=8_468.0, equity_value=118_181.0, implied_share_price=100.0)
    assert app.waterfall_headline(in_debt) == (
        "$126.6B of enterprise value less $8.5B of net debt is $118.2B of equity, or $100.00 a share."
    )


def test_dollar_signs_in_a_headline_are_escaped_so_streamlit_does_not_read_a_formula():
    assert app.dollar_text_for_markdown("$126.6B less $8.5B") == r"\$126.6B less \$8.5B"
    assert app.dollar_text_for_markdown("no money here") == "no money here"


def test_the_cash_flow_chart_has_grey_reported_bars_blue_forecast_bars_and_a_margin_line():
    figure = app.cash_flow_figure(["Year 1", "Year 2", "Year 3", "Year 4", "Year 5"], DCF_RESULT, [0.37, 0.38, 0.38, 0.39, 0.39], HISTORY)
    reported, forecast, margin = figure.data
    assert reported.marker.color == theme.GREY and forecast.marker.color == theme.ACCENT
    assert list(reported.x) == ["FY2024", "FY2025"] and list(reported.y) == pytest.approx([7.0, 9.852])      # $ billions
    assert list(forecast.y) == pytest.approx([9.0, 10.0, 11.0, 12.0, 13.0])
    assert list(margin.x) == ["FY2024", "FY2025", "Year 1", "Year 2", "Year 3", "Year 4", "Year 5"]
    assert list(margin.y) == pytest.approx([7741 / 21505, 8706 / 23769, 0.37, 0.38, 0.38, 0.39, 0.39])
    assert margin.yaxis == "y2"                                         # the right-hand axis
    assert figure.layout.showlegend is True


def test_without_history_the_cash_flow_chart_has_only_the_forecast_and_the_margin_line():
    figure = app.cash_flow_figure(["Year 1", "Year 2", "Year 3", "Year 4", "Year 5"], DCF_RESULT, [0.4] * 5, None)
    forecast, margin = figure.data
    assert forecast.marker.color == theme.ACCENT and list(margin.x) == list(forecast.x)


def test_a_year_without_a_reported_figure_is_a_gap_not_a_zero():
    missing = dict(HISTORY, free_cash_flow=[None, 9_852.0])
    figure = app.cash_flow_figure(["Year 1"], dict(DCF_RESULT, free_cash_flows=[9_000.0]), [0.4], missing)
    assert list(figure.data[0].y)[0] is None


def test_the_cash_flow_headline_says_whether_free_cash_flow_grows_or_falls_from_the_last_reported_year():
    assert app.cash_flow_headline(DCF_RESULT, HISTORY) == (
        "Free cash flow is forecast to grow from $9.9B (last reported year) to $13.0B in year 5."
    )
    shrinking = dict(DCF_RESULT, free_cash_flows=[9_000.0, 8_000.0, 7_000.0, 6_000.0, 5_000.0])
    assert "fall from $9.9B (last reported year) to $5.0B" in app.cash_flow_headline(shrinking, HISTORY)
    assert app.cash_flow_headline(DCF_RESULT, None) == "Free cash flow is forecast to reach $13.0B in year 5."
    assert app.cash_flow_headline(DCF_RESULT, dict(HISTORY, free_cash_flow=[7_000.0, None])) == (
        "Free cash flow is forecast to reach $13.0B in year 5."
    )


def test_the_terminal_value_ring_shows_the_share_in_the_middle_and_stays_blue_below_the_warning_limit():
    ring = app.terminal_value_donut(DCF_RESULT)           # 88,882 of 126,649 is 70%
    pie = ring.data[0]
    assert list(pie.values) == [37_767.0, 88_882.0] and list(pie.labels) == ["Years 1-5", "Terminal value"]
    assert list(pie.marker.colors) == [theme.GREY, theme.ACCENT]
    assert "70%" in ring.layout.annotations[0].text


def test_the_terminal_value_ring_turns_red_above_the_warning_limit():
    top_heavy = dict(DCF_RESULT, pv_of_forecast=20_000.0, pv_of_terminal_value=80_000.0, enterprise_value=100_000.0)
    pie = app.terminal_value_donut(top_heavy).data[0]                    # 80% is above 75%
    assert list(pie.marker.colors) == [theme.GREY, theme.DOWN]
    exactly_at_limit = dict(DCF_RESULT, pv_of_forecast=25_000.0, pv_of_terminal_value=75_000.0, enterprise_value=100_000.0)
    assert list(app.terminal_value_donut(exactly_at_limit).data[0].marker.colors) == [theme.GREY, theme.ACCENT]


def test_adobes_page_has_the_football_field_with_a_headline_and_the_charts_behind_the_number(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_prices())
    assert_footer_and_no_crash(page)
    subheaders = texts(page.subheader)
    assert subheaders.index("Where the price sits") < subheaders.index("Discounted cash flow (DCF)")
    markdown = texts(page.markdown)
    assert any(line.startswith("**Adobe Inc. trades ") and "valuation method" in line for line in markdown)
    assert any(line.startswith("**") and "of enterprise value" in line for line in markdown)       # the waterfall headline
    assert any(line.startswith("**Free cash flow is forecast to") for line in markdown)
    assert any(line.startswith("**") and "of the value comes from after year 5." in line for line in markdown)
    assert len(page.get("plotly_chart")) == 11


def test_the_headline_dollar_signs_reach_the_page_escaped(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_prices())
    waterfall = next(line for line in texts(page.markdown) if "of enterprise value" in line)
    assert r"\$" in waterfall and "$" not in waterfall.replace(r"\$", "")


def test_a_company_with_no_peers_still_gets_a_football_field_with_its_dcf(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert "Where the price sits" in texts(page.subheader)
    assert any(line.startswith("**Example Corp trades ") for line in texts(page.markdown))


def test_a_company_whose_dcf_cannot_be_built_has_no_football_field_and_no_charts_behind_the_number(monkeypatch):
    loss = dict(ADOBE_YAHOO_INCOME, **{"Pretax Income": (-100e6, 50e6)})
    page = run_page(monkeypatch, ticker="loss", yahoo=fake_statements_ticker(income=loss))
    assert_footer_and_no_crash(page)
    assert "Where the price sits" not in texts(page.subheader) and "Behind the number" not in texts(page.subheader)


def test_a_very_low_wacc_still_gets_a_dcf_bar_from_the_cells_that_have_an_answer(monkeypatch):
    # Some cells of the table have no answer at this WACC, but the rest do, so the DCF bar covers those.
    low_beta = yahoo_with_prices(info=dict(ADOBE_YAHOO_INFO, beta=-0.95))
    page = run_page(monkeypatch, ticker="lowb", yahoo=low_beta)
    assert_footer_and_no_crash(page)
    assert "Where the price sits" in texts(page.subheader)
    assert not any(caption.startswith("The DCF bar is left out") for caption in texts(page.caption))


def test_when_nothing_is_left_to_draw_the_football_field_section_is_left_out_altogether(monkeypatch):
    # No peers, no price history, and no combination in the table has an answer: no bars at all.
    def impossible(*args, **kwargs):
        raise ValueError("No pairing has an answer.")

    monkeypatch.setattr("valuation.sensitivity_table", impossible)
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert_footer_and_no_crash(page)
    assert "Where the price sits" not in texts(page.subheader)


# ---------------------------------------------------------------------------
# The sensitivity heatmaps and the peer charts (redesign, Phase 3b)
# ---------------------------------------------------------------------------

HEAT_PRICES = [[150.0, 120.0, None], [100.0, 80.0, 50.0]]          # against a market price of 100; one blank cell
HEAT_ROWS = ["10.00%", "11.00%"]
HEAT_COLUMNS = ["1.5%", "2.0%", "2.5%"]


def a_heatmap(**changes):
    arguments = dict(
        row_labels=HEAT_ROWS, column_labels=HEAT_COLUMNS, prices=HEAT_PRICES, share_price=100.0, base_cell=(1, 1),
        row_title="WACC", column_title="Terminal growth",
    )
    arguments.update(changes)
    return app.sensitivity_heatmap(**arguments)


def test_the_cell_colour_is_the_card_colour_at_the_market_price_and_moves_to_green_above_and_red_below():
    surface = theme.hex_to_rgb(theme.SURFACE)
    assert app.heat_colour(0.0) == surface
    above, below = app.heat_colour(0.25), app.heat_colour(-0.25)
    assert above[1] > surface[1] and below[0] > surface[0]
    assert app.heat_colour(0.5) == app.heat_colour(2.0) and app.heat_colour(-0.5) == app.heat_colour(-2.0)    # capped


def test_the_table_tint_is_built_from_the_same_colours_as_the_heatmap():
    red, green, blue = app.heat_colour(0.3)
    assert f"background-color: rgb({red}, {green}, {blue})" in app.tint(130.0, 100.0)


def test_the_heatmap_colour_scale_runs_red_card_green_with_the_card_colour_at_the_market_price():
    low, middle, high = app.heatmap_colourscale()
    assert [low[0], middle[0], high[0]] == [0.0, 0.5, 1.0]
    assert middle[1] == f"rgb{theme.hex_to_rgb(theme.SURFACE)}"
    assert low[1] == f"rgb{app.heat_colour(-0.5)}" and high[1] == f"rgb{app.heat_colour(0.5)}"


def test_every_heatmap_cell_shows_its_price_and_upside_with_an_arrow_and_a_blank_cell_stays_empty():
    heat = a_heatmap().data[0]
    assert [list(row) for row in heat.text] == [
        ["$150<br>▲ +50%", "$120<br>▲ +20%", ""],
        ["$100<br>0%", "$80<br>▼ -20%", "$50<br>▼ -50%"],
    ]
    assert heat.z[0][0] == pytest.approx(0.5) and heat.z[1][1] == pytest.approx(-0.2) and heat.z[0][2] is None
    assert heat.zmin == -app.HEATMAP_FULL_TINT_GAP and heat.zmax == app.HEATMAP_FULL_TINT_GAP
    assert heat.hoverongaps is False


def test_the_heatmap_hover_names_the_row_the_column_the_price_and_the_upside():
    heat = a_heatmap().data[0]
    price, gap, row_label, column_label = heat.customdata[1][1]
    assert price == 80.0 and gap == pytest.approx(-0.2) and (row_label, column_label) == ("11.00%", "2.0%")
    assert "WACC: %{customdata[2]}" in heat.hovertemplate and "Terminal growth: %{customdata[3]}" in heat.hovertemplate
    assert "$%{customdata[0]:,.2f}" in heat.hovertemplate and "%{customdata[1]:+.1%}" in heat.hovertemplate


def test_a_dashed_line_runs_where_the_model_equals_the_market_price():
    contour = a_heatmap().data[1]
    assert contour.contours.start == 0 and contour.contours.end == 0 and contour.contours.coloring == "none"
    assert contour.line.dash == "dash" and contour.line.color == theme.TEXT


def test_a_blue_frame_marks_the_base_case_cell():
    [frame] = a_heatmap(base_cell=(1, 0)).layout.shapes
    assert (frame.x0, frame.x1, frame.y0, frame.y1) == (-0.5, 0.5, 0.5, 1.5)
    assert frame.line.color == theme.ACCENT


def test_the_heatmap_axes_carry_the_labels_and_the_first_row_is_at_the_top():
    figure = a_heatmap()
    assert list(figure.layout.xaxis.ticktext) == HEAT_COLUMNS and list(figure.layout.yaxis.ticktext) == HEAT_ROWS
    assert figure.layout.xaxis.title.text == "Terminal growth" and figure.layout.yaxis.title.text == "WACC"
    assert figure.layout.yaxis.autorange == "reversed"


def test_the_sensitivity_headline_counts_the_combinations_above_the_market_price():
    assert app.sensitivity_headline(HEAT_PRICES, 100.0) == (
        "2 of 5 combinations give a price above today's market price; the dashed line shows where the model equals it."
    )
    assert app.sensitivity_headline([[120.0, 130.0]], 100.0).startswith("All 2 combinations give a price above today's market price")
    assert app.sensitivity_headline([[80.0, 90.0]], 100.0) == "None of the 2 combinations reaches today's market price."


def test_adobes_page_has_both_heatmaps_with_a_sentence_and_the_numbers_in_a_closed_box(monkeypatch):
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    markdown = texts(page.markdown)
    assert any(line.startswith("**") and "of 35 combinations" in line for line in markdown)       # 7 WACCs by 5 growth rates
    assert any(line.startswith("**") and "of 25 combinations" in line for line in markdown)       # 5 margins by 5 growth rates
    assert len(page.expander) >= 2
    assert sum(1 for expander in page.expander if expander.label == "Show the numbers as a table") == 2


def test_the_wacc_heatmap_now_spans_three_points_each_way_and_its_base_cell_is_the_dcf_price(monkeypatch):
    page = run_page(monkeypatch)
    wacc_table = next(element.value for element in page.dataframe if element.value.index.name == "WACC")
    assert wacc_table.shape == (7, 5)
    base_row = assumptions.HEATMAP_WACC_OFFSETS.index(0.0)
    base_column = assumptions.HEATMAP_TERMINAL_GROWTH_RATES.index(assumptions.TERMINAL_GROWTH_RATE)
    assert app.dollars(wacc_table.iloc[base_row, base_column]) == metrics(page)["DCF implied price"]
    rates = [float(label.rstrip("%")) / 100 for label in wacc_table.index]
    assert rates[base_row] - rates[0] == pytest.approx(0.03, abs=1e-4) and rates[-1] - rates[base_row] == pytest.approx(0.03, abs=1e-4)


def test_the_sliders_move_both_heatmaps(monkeypatch):
    page = run_page(monkeypatch)
    before = next(element.value for element in page.dataframe if element.value.index.name == "WACC").iloc[3, 2]
    page.sidebar.slider[1].set_value(-2.0).run()
    after = next(element.value for element in page.dataframe if element.value.index.name == "WACC").iloc[3, 2]
    assert after < before and app.dollars(after) == metrics(page)["DCF implied price"]


def test_peer_bar_headline_says_whether_the_company_is_below_or_above_the_peer_median():
    assert app.peer_bar_headline("EV/EBITDA", "NVIDIA", 14.9, 28.5) == "NVIDIA's EV/EBITDA of 14.9x is below the peer median of 28.5x."
    assert app.peer_bar_headline("P/E", "Adobe", 30.0, 26.8) == "Adobe's P/E of 30.0x is above the peer median of 26.8x."
    assert app.peer_bar_headline("P/E", "Adobe", 26.8, 26.8) == "Adobe's P/E of 26.8x is the same as the peer median."


def test_peer_bar_headline_explains_when_there_is_nothing_to_compare():
    assert "no usable P/E" in app.peer_bar_headline("P/E", "Ford", None, 20.0)
    assert "no usable P/E" in app.peer_bar_headline("P/E", "Ford", -5.0, 20.0)
    assert app.peer_bar_headline("P/S", "Ford", 2.0, None).startswith("Too few peers have a usable P/S")


def test_the_peer_bars_are_sorted_highest_first_with_the_company_in_the_accent_colour():
    figure = app.peer_bar_figure("EV/EBITDA", "ME (this company)", 14.9, ["A", "B", "C"], [28.5, 61.9, 5.8], 28.5)
    bars = figure.data[0]
    assert list(bars.y) == ["B", "A", "ME (this company)", "C"] and list(bars.x) == [61.9, 28.5, 14.9, 5.8]
    assert list(bars.marker.color) == [theme.GREY, theme.GREY, theme.ACCENT, theme.GREY]
    assert list(bars.text) == ["61.9x", "28.5x", "14.9x", "5.8x"]
    assert figure.layout.yaxis.autorange == "reversed"


def test_the_peer_bars_draw_the_median_as_a_dashed_line_and_leave_room_for_the_longest_label():
    figure = app.peer_bar_figure("EV/EBITDA", "ME", 14.9, ["A", "B"], [28.5, 61.9], 28.5)
    [line] = figure.layout.shapes
    assert line.x0 == line.x1 == 28.5 and line.line.dash == "dash"
    assert any("Peer median 28.5x" in annotation.text for annotation in figure.layout.annotations)
    assert figure.layout.xaxis.range[0] == 0 and figure.layout.xaxis.range[1] > 61.9
    assert figure.data[0].cliponaxis is False


def test_a_figure_that_is_missing_or_not_a_real_multiple_is_left_off_the_peer_bars():
    figure = app.peer_bar_figure("P/E", "ME", None, ["A", "B", "C", "D"], [20.0, None, -3.0, float("nan")], None)
    assert list(figure.data[0].y) == ["A"]
    assert not figure.layout.shapes                               # no median, no line


def test_the_scatter_headline_tells_the_four_stories():
    cheap_good = app.peer_scatter_headline("NVIDIA", 14.9, 0.652, 28.5, 0.617)
    assert cheap_good == (
        "NVIDIA trades at 14.9x EBITDA against the peers' 28.5x, with an operating margin of 65.2% against 61.7%: "
        "cheaper than the typical peer while more profitable."
    )
    assert "less profitable, so the discount may be deserved" in app.peer_scatter_headline("X", 10.0, 0.10, 20.0, 0.30)
    assert "dearer than the typical peer, but more profitable, so the premium has some support" in app.peer_scatter_headline("X", 30.0, 0.40, 20.0, 0.30)
    assert app.peer_scatter_headline("X", 30.0, 0.10, 20.0, 0.30).endswith("dearer than the typical peer while less profitable.")


def test_the_scatter_headline_is_none_when_a_figure_is_missing_or_the_company_has_no_real_multiple():
    assert app.peer_scatter_headline("X", None, 0.2, 20.0, 0.3) is None
    assert app.peer_scatter_headline("X", 10.0, None, 20.0, 0.3) is None
    assert app.peer_scatter_headline("X", 10.0, 0.2, None, 0.3) is None
    assert app.peer_scatter_headline("X", 10.0, 0.2, 20.0, None) is None
    assert app.peer_scatter_headline("X", -4.0, 0.2, 20.0, 0.3) is None


def test_the_scatter_puts_the_company_in_the_accent_colour_and_the_peers_in_grey_with_median_lines():
    figure = app.peer_scatter_figure("ME", 14.9, 0.652, ["A", "B"], [28.5, 61.9], [0.49, 0.178], 28.5, 0.617)
    peers, company = figure.data
    assert list(peers.text) == ["A", "B"] and list(peers.x) == [0.49, 0.178] and list(peers.y) == [28.5, 61.9]
    assert peers.marker.color == theme.GREY and company.marker.color == theme.ACCENT
    assert company.marker.size > peers.marker.size and list(company.x) == [0.652] and list(company.y) == [14.9]
    assert len(figure.layout.shapes) == 2 and all(shape.line.dash == "dash" for shape in figure.layout.shapes)


def test_a_peer_missing_its_margin_or_a_real_multiple_is_left_off_the_scatter():
    figure = app.peer_scatter_figure(
        "ME", 14.9, 0.652, ["A", "B", "C", "D"], [28.5, 61.9, -3.0, 10.0], [None, 0.178, 0.3, float("nan")], None, None
    )
    assert list(figure.data[0].text) == ["B"]
    assert not figure.layout.shapes                               # no medians, no lines


def test_a_company_with_no_real_ebitda_multiple_is_left_off_the_scatter_but_the_peers_stay():
    figure = app.peer_scatter_figure("ME", None, 0.2, ["A"], [28.5], [0.4], 28.5, 0.4)
    assert len(figure.data) == 1 and list(figure.data[0].text) == ["A"]


def test_adobes_page_has_the_peer_bars_with_a_switch_under_a_sentence(monkeypatch):
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    switch = page.radio(key="peer_chart_multiple")
    assert switch.value == "EV/EBITDA" and list(switch.options) == ["EV/Sales", "EV/EBITDA", "P/E", "P/S", "Forward P/E"]
    assert any(
        line.startswith("**") and "EV/EBITDA of" in line and "the peer median of" in line for line in texts(page.markdown)
    )


def test_the_scatter_has_a_sentence_when_the_peers_margins_are_known(monkeypatch):
    # Example Corp's made-up peers have operating margins (-25%, 30%, 20%, 10%); Adobe's fake peers here have none.
    page = run_example_page(monkeypatch)
    assert any(line.startswith("**Example Corp trades at ") and "EBITDA against the peers'" in line for line in texts(page.markdown))


def test_without_peer_margins_the_scatter_has_no_sentence_but_the_bars_still_do(monkeypatch):
    page = run_page(monkeypatch)
    assert not any("EBITDA against the peers'" in line for line in texts(page.markdown))
    assert any("the peer median of" in line for line in texts(page.markdown))


def test_choosing_another_multiple_redraws_the_bar_chart_and_its_sentence(monkeypatch):
    page = run_example_page(monkeypatch)
    page.radio(key="peer_chart_multiple").set_value("P/E").run()
    assert_footer_and_no_crash(page)
    assert any(line.startswith("**Example Corp's P/E of") for line in texts(page.markdown))


def test_the_peer_charts_come_before_the_peer_table_and_a_company_without_peers_has_neither(monkeypatch):
    page = run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert not [radio for radio in page.radio if radio.key == "peer_chart_multiple"]        # no switch without peers
    assert not any("EV/EBITDA of" in line for line in texts(tab_named(page, "Multiples").markdown))


# ---------------------------------------------------------------------------
# The tabs, the grouped overview, the Explanations tab and the sidebar headings (redesign, Phase 4a)
# ---------------------------------------------------------------------------

def tab_named(page, label):
    """One tab of the page, found by its label."""
    [tab] = [tab for tab in page.tabs if tab.label == label]
    return tab


def test_the_page_has_five_tabs_in_this_order(monkeypatch):
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    assert [tab.label for tab in page.tabs] == ["Overview", "DCF", "Multiples", "Sensitivity", "Explanations"]
    assert app.PAGE_TABS == [tab.label for tab in page.tabs]


def test_each_section_is_in_its_own_tab(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_prices())
    assert texts(tab_named(page, "Overview").subheader) == ["Where the price sits", "Overview", "History", "News and management"]
    assert texts(tab_named(page, "DCF").subheader) == [
        "Discounted cash flow (DCF)", "What the market price implies", "Scenarios", "What the model assumes",
        "How the WACC is built", "Behind the number",
    ]
    assert texts(tab_named(page, "Multiples").subheader) == ["Peer multiples"]
    assert texts(tab_named(page, "Sensitivity").subheader) == [
        "Sensitivity: price at different WACC and terminal growth", "Sensitivity: price at different margins and growth",
    ]
    assert texts(tab_named(page, "Explanations").subheader) == ["Explanations"]


def test_the_header_and_the_footer_sit_outside_the_tabs(monkeypatch):
    page = run_page(monkeypatch)
    tab_html = [block.value for tab in page.tabs for block in tab.get("html")]
    assert not any('class="vl-header"' in block for block in tab_html)           # the header is above the tabs...
    assert header_of(page)                                                      # ...but it is on the page
    tab_captions = [caption for tab in page.tabs for caption in texts(tab.caption)]
    assert app.FOOTER_TEXT not in tab_captions and app.FOOTER_TEXT in texts(page.main.caption)


def test_the_charts_are_spread_over_the_tabs(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_prices())
    assert len(tab_named(page, "Overview").get("plotly_chart")) == 3                # the football field and the two history charts
    assert len(tab_named(page, "DCF").get("plotly_chart")) == 3                     # the waterfall, free cash flow and the ring
    assert len(tab_named(page, "Multiples").get("plotly_chart")) == 2               # the peer bars and the scatter
    assert len(tab_named(page, "Sensitivity").get("plotly_chart")) == 2             # the two heatmaps
    assert len(page.get("plotly_chart")) == 11                                      # with the sparkline in the header


def test_the_peer_table_is_in_the_multiples_tab(monkeypatch):
    page = run_page(monkeypatch)
    [table] = tab_named(page, "Multiples").dataframe
    assert "Flag" in table.value.columns and "Forward P/E" in table.value.columns


def test_the_sensitivity_tab_holds_the_two_numbers_tables(monkeypatch):
    page = run_page(monkeypatch)
    assert [element.value.index.name for element in tab_named(page, "Sensitivity").dataframe] == [
        "WACC", "Average operating margin",
    ]


def test_a_company_whose_dcf_cannot_be_built_gets_only_the_overview_and_the_explanations_tabs(monkeypatch):
    loss = dict(ADOBE_YAHOO_INCOME, **{"Pretax Income": (-100e6, 50e6)})
    page = run_page(monkeypatch, ticker="loss", yahoo=fake_statements_ticker(income=loss))
    assert_footer_and_no_crash(page)
    assert [tab.label for tab in page.tabs] == ["Overview", "Explanations"]
    assert "Could not value LOSS." in texts(tab_named(page, "Overview").error)[0]
    assert texts(tab_named(page, "Overview").subheader) == ["Overview", "History", "News and management"]


def test_a_ticker_that_cannot_be_found_has_no_tabs_at_all(monkeypatch):
    nothing = fake_statements_ticker(income={}, cash_flow={}, balance={}, info={})
    monkeypatch.setattr("data._start_yahoo_cooldown", lambda: None)
    page = run_page(monkeypatch, ticker="nope", yahoo=nothing)
    assert not page.tabs
    assert_footer_and_no_crash(page)


def test_the_overview_groups_its_numbers_by_what_they_say(monkeypatch):
    page = run_page(monkeypatch)
    overview = tab_named(page, "Overview")
    labels = texts(overview.markdown)
    group_positions = [labels.index(f"**{name}**") for name in ("What the market pays", "Growth and profitability", "Cash, debt and shareholders")]
    assert group_positions == sorted(group_positions)
    assert [metric.label for metric in overview.metric] == [
        "EV/Sales", "EV/EBITDA", "P/E", "P/S", "Forward P/E",
        "Revenue growth", "Operating margin", "ROIC",
        "Free cash flow yield", "Net debt ÷ EBITDA", "Interest cover", "Cash conversion", "Share count change",
    ]


def test_the_overview_now_shows_price_to_sales_and_forward_pe(monkeypatch):
    page = run_page(monkeypatch)
    shown = {metric.label: metric.value for metric in tab_named(page, "Overview").metric}
    assert shown["P/S"].endswith("x") and shown["Forward P/E"].endswith("x")
    assert shown["Forward P/E"] == app.multiple_or_note(240.74 / 27.41)          # the page's price over Adobe's 27.41 EPS


def test_a_company_with_no_analyst_estimate_has_no_forward_pe_in_the_overview(monkeypatch):
    page = run_example_page(monkeypatch, forward_eps=None)
    assert {metric.label: metric.value for metric in tab_named(page, "Overview").metric}["Forward P/E"] == app.NOT_MEANINGFUL


def test_every_overview_number_still_has_its_help_mark(monkeypatch):
    page = run_page(monkeypatch)
    assert all(metric.help for metric in tab_named(page, "Overview").metric)


def test_the_explanations_tab_has_every_term_of_the_glossary_exactly_once(monkeypatch):
    page = run_page(monkeypatch)
    text = "\n".join(texts(tab_named(page, "Explanations").markdown))
    for title, body in app.explanations.EXPLANATIONS.values():
        assert text.count(f"**{title}**  \n{body}") == 1


def test_the_explanations_tab_groups_the_terms_under_the_sections_they_belong_to(monkeypatch):
    page = run_page(monkeypatch)
    markdown = texts(tab_named(page, "Explanations").markdown)
    headings = [line for line in markdown if line.startswith("##### ")]
    assert headings == ["##### The DCF", "##### Behind the number", "##### Sensitivity", "##### Multiples", "##### Reading the page"]
    assert markdown.index("**Discounted cash flow (DCF)**  \n" + app.explanations.EXPLANATIONS["dcf"][1]) < markdown.index("##### Behind the number")


def test_a_term_that_is_in_no_section_is_added_after_the_sections_under_more_terms(monkeypatch):
    monkeypatch.setitem(app.explanations.EXPLANATIONS, "gross_margin", ("Gross margin", "Sales less the cost of making them."))
    page = run_page(monkeypatch)
    markdown = texts(tab_named(page, "Explanations").markdown)
    more = markdown.index("##### More terms")
    assert markdown[more + 1] == "**Gross margin**  \nSales less the cost of making them."
    assert markdown.index("##### Multiples") < more < markdown.index("##### Reading the page")


def test_the_sidebar_has_its_headings_in_order(monkeypatch):
    page = run_page(monkeypatch)
    assert texts(page.sidebar.header) == ["Company", "Assumptions"]                       # Adobe has no peer box
    other = run_example_page(monkeypatch)
    assert texts(other.sidebar.header) == ["Company", "Assumptions", "Peers", "One-off items"]


# ---------------------------------------------------------------------------
# A ? on every multiple, card and chart, and the old closed boxes gone (redesign, Phase 4b)
# ---------------------------------------------------------------------------

def markdown_starting(container, start):
    """The one markdown element of a page or tab whose text starts with `start`."""
    [element] = [element for element in container.markdown if element.value.startswith(start)]
    return element


def test_the_four_header_cards_and_the_verdict_badge_have_a_question_mark(monkeypatch):
    header = header_of(run_page(monkeypatch))
    assert header.count('class="vl-help"') == 4
    import html as html_module
    for key in ("current_price", "implied_share_price", "upside_vs_market", "multiples_value"):
        assert f'title="{html_module.escape(app.explanations.help_text(key), quote=True)}"' in header
    assert 'class="vl-badge vl-badge-up" title="' in header and "not investment advice" in header


def test_the_header_cards_still_read_back_with_their_marks(monkeypatch):
    cards = card_values(header_of(run_page(monkeypatch)))
    assert list(cards) == ["Current price", "DCF value per share", "Upside / downside", "Multiples value"]


def test_the_share_price_chart_caption_has_a_question_mark(monkeypatch):
    page = run_page(monkeypatch, yahoo=yahoo_with_prices())
    [caption] = [caption for caption in page.caption if caption.value == "Share price, last 12 months"]
    assert caption.help == app.explanations.help_text("sparkline")


def test_the_dcf_cards_use_the_glossary_wording_and_do_not_repeat_the_header(monkeypatch):
    page = run_page(monkeypatch)
    helps = {metric.label: metric.help for metric in tab_named(page, "DCF").metric}
    assert helps["DCF implied price"] == app.explanations.EXPLANATIONS["implied_share_price"][1]
    assert helps["WACC"] == app.explanations.EXPLANATIONS["wacc"][1]
    assert helps["Terminal growth"] == app.explanations.EXPLANATIONS["terminal_growth_rate"][1]
    assert "Market price" not in helps and "Upside vs market" not in helps                # those two are in the header only


def test_every_price_box_on_the_multiples_tab_has_a_question_mark(monkeypatch):
    page = run_page(monkeypatch)
    helps = {metric.label: metric.help for metric in tab_named(page, "Multiples").metric}
    assert helps["EV/Sales price"] == app.explanations.help_text("ev_sales_price")
    assert helps["EV/EBITDA price"] == app.explanations.help_text("ev_ebitda_price")
    assert helps["P/E price"] == app.explanations.help_text("pe_price")
    assert helps["P/S price"] == app.explanations.help_text("ps_price")
    assert helps["Forward P/E price"] == app.explanations.help_text("forward_pe_price")
    assert helps["Middle of the five prices"] == app.explanations.help_text("middle_price")
    assert helps["DCF vs multiples"] == app.explanations.EXPLANATIONS["dcf_vs_multiples"][1]
    assert all(helps.values())


def test_the_overview_multiples_use_haavards_glossary_wording(monkeypatch):
    page = run_page(monkeypatch)
    helps = {metric.label: metric.help for metric in tab_named(page, "Overview").metric}
    for label, term in [("EV/Sales", "ev_sales"), ("EV/EBITDA", "ev_ebitda"), ("P/E", "pe"), ("P/S", "ps"), ("Forward P/E", "forward_pe")]:
        assert helps[label] == app.explanations.EXPLANATIONS[term][1]
    assert helps["P/S"].startswith("P/S shows how much investors are paying for each dollar")
    assert helps["Forward P/E"].startswith("Forward P/E shows the share price compared with the earnings analysts expect")


def test_the_football_field_headline_has_a_question_mark(monkeypatch):
    page = run_page(monkeypatch)
    headline = markdown_starting(tab_named(page, "Overview"), "**Adobe Inc. trades ")
    assert headline.help == app.explanations.help_text("football_field")


def test_the_charts_behind_the_number_each_have_a_question_mark(monkeypatch):
    dcf_tab = tab_named(run_page(monkeypatch), "DCF")
    waterfall = next(element for element in dcf_tab.markdown if "of enterprise value" in element.value)
    cash_flow = markdown_starting(dcf_tab, "**Free cash flow is forecast to")
    ring = next(element for element in dcf_tab.markdown if "of the value comes from after year 5." in element.value)
    assert waterfall.help == app.explanations.help_text("waterfall")
    assert cash_flow.help == app.explanations.help_text("cash_flow_chart")
    assert ring.help == app.explanations.help_text("terminal_value_ring")


def test_both_heatmaps_have_a_question_mark_that_explains_the_dashed_line_and_the_frame(monkeypatch):
    sensitivity = tab_named(run_page(monkeypatch), "Sensitivity")
    wacc, margin = [element for element in sensitivity.markdown if "combinations" in element.value]
    assert wacc.help == app.explanations.help_text("heatmap_wacc")
    assert margin.help == app.explanations.help_text("heatmap_margin")
    for help_text in (wacc.help, margin.help):
        assert "dashed line" in help_text and "blue frame" in help_text


def test_the_peer_bars_and_the_scatter_each_have_a_question_mark(monkeypatch):
    multiples = tab_named(run_example_page(monkeypatch), "Multiples")
    bars = next(element for element in multiples.markdown if "the peer median" in element.value)
    scatter = markdown_starting(multiples, "**Example Corp trades at ")
    assert bars.help == app.explanations.help_text("peer_bars")
    assert scatter.help == app.explanations.help_text("peer_scatter")


def test_the_old_closed_boxes_with_the_glossary_are_gone_from_every_section(monkeypatch):
    page = run_page(monkeypatch)
    assert "What do these terms mean?" not in [expander.label for expander in page.expander]
    assert not hasattr(app, "draw_explanations")
    assert "What do these terms mean?" not in APP_SOURCE_TEXT


APP_SOURCE_TEXT = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")


def test_the_explanations_tab_has_a_reading_the_page_section_with_every_help_text(monkeypatch):
    markdown = texts(tab_named(run_page(monkeypatch), "Explanations").markdown)
    assert "##### Reading the page" in markdown
    after = markdown[markdown.index("##### Reading the page") + 1:]
    for key, (title, _raw) in app.explanations.HELP_TEXTS.items():
        assert f"**{title}**  \n{app.explanations.help_text(key)}" in after


def test_the_two_new_glossary_terms_are_in_the_explanations_tab_with_haavards_words(monkeypatch):
    text = "\n".join(texts(tab_named(run_page(monkeypatch), "Explanations").markdown))
    assert "**P/S (Price to Sales)**  \nP/S shows how much investors are paying for each dollar of a company’s revenue." in text
    assert "**Forward P/E**  \nForward P/E shows the share price compared with the earnings analysts expect over the next year." in text


def test_a_company_with_no_dcf_still_has_the_explanations_with_reading_the_page(monkeypatch):
    loss = dict(ADOBE_YAHOO_INCOME, **{"Pretax Income": (-100e6, 50e6)})
    page = run_page(monkeypatch, ticker="loss", yahoo=fake_statements_ticker(income=loss))
    assert "##### Reading the page" in texts(tab_named(page, "Explanations").markdown)
    assert header_of(page).count('class="vl-help"') == 4


# ---------------------------------------------------------------------------
# Polish: loading messages, a helpful not-found page, no doubled cards, the History charts, the sources line (Phase 5)
# ---------------------------------------------------------------------------

class SpinnerLog:
    """A stand-in for st.spinner that records every message it was given and shows nothing."""
    def __init__(self):
        self.messages = []

    def __call__(self, message="", **kwargs):
        self.messages.append(message)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_a_company_that_loads_shows_a_loading_message_for_the_company_and_another_for_its_history(monkeypatch):
    log = SpinnerLog()
    monkeypatch.setattr(st, "spinner", log)
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    assert log.messages == ["Loading ADBE…", "Loading the history and the last twelve months…"]


def test_the_loading_message_names_the_company_the_reader_asked_for(monkeypatch):
    log = SpinnerLog()
    monkeypatch.setattr(st, "spinner", log)
    run_page(monkeypatch, ticker="exmp", yahoo=other_company())
    assert log.messages[-2:] == ["Loading EXMP…", "Loading the history and the last twelve months…"]   # after the first run, which loads Adobe


def test_a_company_that_cannot_be_found_only_shows_the_first_loading_message(monkeypatch):
    log = SpinnerLog()
    monkeypatch.setattr(st, "spinner", log)
    nothing = fake_statements_ticker(income={}, cash_flow={}, balance={}, info={})
    monkeypatch.setattr("data._start_yahoo_cooldown", lambda: None)
    run_page(monkeypatch, ticker="nope", yahoo=nothing)
    # The first run loads Adobe (both messages); the typed ticker is not found, so it shows only the first message.
    assert log.messages == ["Loading ADBE…", "Loading the history and the last twelve months…", "Loading NOPE…"]


def test_the_page_has_a_title_and_an_icon_in_the_browser_tab(monkeypatch):
    recorded = {}
    real = st.set_page_config
    monkeypatch.setattr(st, "set_page_config", lambda **kwargs: (recorded.update(kwargs), real(**kwargs))[1])
    run_page(monkeypatch)
    assert recorded == {"page_title": "Valuation Lab", "page_icon": "📈"}


def not_found_page(monkeypatch, ticker="appl"):
    nothing = fake_statements_ticker(income={}, cash_flow={}, balance={}, info={})
    monkeypatch.setattr("data._start_yahoo_cooldown", lambda: None)
    return run_page(monkeypatch, ticker=ticker, yahoo=nothing)


def hints_of(page):
    [card] = [element.value for element in page.get("html") if 'class="vl-hints"' in element.value]
    return card


def test_a_company_that_cannot_be_found_keeps_its_message_and_gets_a_list_of_things_to_check(monkeypatch):
    page = not_found_page(monkeypatch)
    assert_footer_and_no_crash(page)
    [error] = texts(page.error)
    assert error.startswith("Could not value APPL.") and "Yahoo Finance has no figures for APPL" in error
    card = hints_of(page)
    assert "Things to check" in card and "Is APPL the ticker" in card
    assert "Apple is AAPL, Microsoft is MSFT and Coca-Cola is KO" in card
    assert "AKER.OL for Oslo" in card
    assert "Try one of these: ADBE, AAPL, MSFT, KO, NVDA." in card


def test_the_suggested_tickers_are_real_looking_tickers_and_the_list_is_short():
    assert 3 <= len(app.EXAMPLE_TICKERS) <= 6
    assert all(ticker.isalpha() and ticker.isupper() for ticker in app.EXAMPLE_TICKERS)
    assert app.DEFAULT_TICKER in app.EXAMPLE_TICKERS


def test_when_yahoo_is_not_answering_the_hints_say_it_is_not_the_tickers_fault(monkeypatch):
    class BrokenTicker:
        def __init__(self, ticker):
            raise ConnectionError("no internet")

    page = run_page(monkeypatch, ticker="exmp", yahoo=BrokenTicker)
    assert_footer_and_no_crash(page)
    card = hints_of(page)
    assert "What you can do" in card and "This is not about the ticker" in card
    assert "Wait a few minutes" in card and "Things to check" not in card
    assert "Try one of these" not in card


def test_what_the_reader_typed_cannot_become_page_code_in_the_not_found_page(monkeypatch):
    page = not_found_page(monkeypatch, ticker="<img src=x onerror=alert(1)>")
    card = hints_of(page)
    assert "<img" not in card and "&lt;IMG SRC=X ONERROR=ALERT(1)&gt;" in card


def test_the_error_hints_depend_on_what_went_wrong():
    unknown = app.error_hints("APPL", ValueError("not found"))
    busy = app.error_hints("APPL", data.SourceUnavailable("busy"))
    assert any("Apple is AAPL" in hint for hint in unknown) and not any("Apple is AAPL" in hint for hint in busy)
    assert any("Wait a few minutes" in hint for hint in busy)
    assert len(unknown) == len(busy) == 3


def test_every_page_ends_with_the_sources_and_then_the_not_advice_note(monkeypatch):
    for page in (
        run_page(monkeypatch),
        not_found_page(monkeypatch),
        run_page(monkeypatch, ticker="loss", yahoo=fake_statements_ticker(income=dict(ADOBE_YAHOO_INCOME, **{"Pretax Income": (-100e6, 50e6)}))),
    ):
        captions = texts(page.main.caption)
        assert captions[-2:] == [app.SOURCES_TEXT, app.FOOTER_TEXT]


def test_the_sources_line_names_every_source_and_matches_the_wacc_table(monkeypatch):
    for name in ("Yahoo Finance", "Financial Modeling Prep", "Damodaran, 1 Nov 2026", "10-K"):
        assert name in app.SOURCES_TEXT
    page = run_page(monkeypatch)
    assert "Damodaran, 1 Nov 2026" in " ".join(wacc_table_of(page)["Where it comes from"])


def test_the_dcf_tab_shows_the_terminal_growth_in_use_and_it_follows_the_slider(monkeypatch):
    page = run_page(monkeypatch)
    assert {metric.label: metric.value for metric in tab_named(page, "DCF").metric}["Terminal growth"] == "2.5%"
    page.sidebar.slider[2].set_value(0.03).run()
    assert {metric.label: metric.value for metric in tab_named(page, "DCF").metric}["Terminal growth"] == "3.0%"


def test_the_dcf_tab_has_three_top_cards_and_what_the_market_implies_has_two(monkeypatch):
    labels = [metric.label for metric in tab_named(run_page(monkeypatch), "DCF").metric]
    assert labels[:3] == ["DCF implied price", "WACC", "Terminal growth"]
    assert labels[3:5] == ["Operating margin it implies", "Revenue growth it implies"]
    assert "Market price" not in labels and "Upside vs market" not in labels


def test_the_verdict_line_under_the_name_is_one_short_sentence(monkeypatch):
    header = header_of(run_page(monkeypatch))
    line = header.split('class="vl-basis">')[1].split("</div>")[0]
    assert line == "The model&#x27;s DCF price against today&#x27;s market price, with 15% either way. The model&#x27;s output, not investment advice."
    assert len(line) < 160


def test_the_starting_point_caveat_is_a_calm_note_for_other_companies_and_absent_for_adobe(monkeypatch):
    assert not run_page(monkeypatch).info
    [note] = texts(run_page(monkeypatch, ticker="exmp", yahoo=other_company()).info)
    assert note.startswith("Starting point, not a forecast") and len(note) < 200


LONG_HISTORY = dict(HISTORY, years=["FY2022", "FY2023", "FY2024", "FY2025"],
               revenue=[17_606.0, 19_409.0, 21_505.0, 23_769.0], operating_income=[6_098.0, 6_650.0, 7_741.0, 8_706.0],
               free_cash_flow=[7_396.0, 6_942.0, 7_873.0, 9_852.0], net_income=[4_756.0, 5_428.0, 5_560.0, 7_130.0],
               diluted_shares=[471.0, 459.0, 450.0, 427.0])


def test_first_and_last_skip_missing_years_and_need_two_figures():
    assert app.first_and_last([None, 5.0, 6.0, None, 9.0, None]) == (1, 4)
    assert app.first_and_last([1.0, 2.0]) == (0, 1)
    assert app.first_and_last([None, 5.0, None]) is None and app.first_and_last([]) is None
    assert app.first_and_last([float("nan"), 3.0, 4.0]) == (1, 2)


def test_the_history_headlines_say_where_revenue_cash_flow_and_margins_went():
    assert app.history_amounts_headline(LONG_HISTORY) == (
        "Revenue went from $17.6B in FY2022 to $23.8B in FY2025; reported free cash flow went from $7.4B in FY2022 to $9.9B in FY2025."
    )
    assert app.history_margins_headline(LONG_HISTORY) == (
        "The operating margin went from 34.6% in FY2022 to 36.6% in FY2025; the free cash flow margin went from 42.0% in FY2022 to 41.4% in FY2025."
    )


def test_a_headline_leaves_out_what_has_no_two_years_of_figures_and_is_none_when_nothing_is_left():
    no_cash_flow = dict(LONG_HISTORY, free_cash_flow=[None, None, None, 9_852.0])
    assert app.history_amounts_headline(no_cash_flow) == "Revenue went from $17.6B in FY2022 to $23.8B in FY2025."
    nothing = dict(LONG_HISTORY, revenue=[None] * 4, free_cash_flow=[None] * 4, operating_income=[None] * 4)
    assert app.history_amounts_headline(nothing) is None and app.history_margins_headline(nothing) is None


def test_the_history_amounts_chart_has_blue_revenue_and_grey_reported_free_cash_flow_in_billions():
    figure = app.history_amounts_figure(LONG_HISTORY)
    revenue, cash = figure.data
    assert revenue.marker.color == theme.ACCENT and cash.marker.color == theme.GREY
    assert list(revenue.x) == LONG_HISTORY["years"] and list(revenue.y) == pytest.approx([17.606, 19.409, 21.505, 23.769])
    assert list(cash.y) == pytest.approx([7.396, 6.942, 7.873, 9.852])
    assert figure.layout.yaxis.tickprefix == "$" and figure.layout.yaxis.ticksuffix == "B" and figure.layout.showlegend is True


def test_a_missing_year_is_a_gap_in_the_history_amounts_chart_not_a_zero():
    figure = app.history_amounts_figure(dict(LONG_HISTORY, free_cash_flow=[None, 6_942.0, 7_873.0, 9_852.0]))
    assert figure.data[1].y[0] is None


def test_the_history_margins_chart_has_a_blue_operating_margin_and_a_grey_free_cash_flow_margin():
    figure = app.history_margins_figure(LONG_HISTORY)
    operating, fcf = figure.data
    assert operating.line.color == theme.ACCENT and fcf.line.color == theme.GREY
    assert list(operating.y) == pytest.approx([6098 / 17606 * 100, 6650 / 19409 * 100, 7741 / 21505 * 100, 8706 / 23769 * 100])
    assert figure.layout.yaxis.ticksuffix == "%" and figure.layout.showlegend is True


def test_the_history_section_has_its_two_charts_with_headlines_and_a_question_mark(monkeypatch):
    page = run_page(monkeypatch, yahoo=adobe_with_four_years())
    overview = tab_named(page, "Overview")
    amounts = next(element for element in overview.markdown if element.value.startswith("**Revenue went from"))
    margins = next(element for element in overview.markdown if element.value.startswith("**The operating margin went from"))
    assert amounts.help == app.explanations.help_text("history_amounts")
    assert margins.help == app.explanations.help_text("history_margins")
    assert len(overview.get("plotly_chart")) == 3


def test_without_a_history_the_section_says_so_and_draws_no_history_charts(monkeypatch):
    monkeypatch.setattr("data.get_history_any", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("no history")))
    page = run_page(monkeypatch)
    assert_footer_and_no_crash(page)
    assert any(caption.startswith("The history is not available right now.") for caption in texts(page.caption))
    assert len(tab_named(page, "Overview").get("plotly_chart")) == 1                   # only the football field
