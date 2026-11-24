"""The Valuation Lab page: shows a company's DCF and its peer multiples.

This file only draws. It fetches the figures with data.py, takes the assumptions from
assumptions.py, hands both to valuation.py, and puts what comes back on the page (guard
rail 5). Run it with: streamlit run app.py
"""

import datetime
import math
import os
import re
import textwrap

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import assumptions
import data
import explanations
import theme
import valuation

# The company the page opens on, and the only one with hand-chosen assumptions and peer multiples.
DEFAULT_TICKER = assumptions.BASE_CASE_TICKER

# How far a heatmap cell moves from the card colour towards green (above the market price) or red (below it).
# A price at the market price keeps the card colour; prices 50% or more away get the strongest tint. The colours
# themselves are theme.UP and theme.DOWN.
HEATMAP_FULL_TINT_GAP = 0.5
HEATMAP_STRONGEST_TINT = 0.4        # low enough that the text stays readable on every cell (4.5 contrast, checked in test_theme.py)
# The tint grows slowly near the market price and faster further away (the gap to the power 1.5), so cells close to
# the market price stay almost the card colour and only the far-off cells stand out (polish, 24 Nov 2026).
HEATMAP_TINT_CURVE = 1.5
HEATMAP_SCALE_STEPS = 10            # colour stops on each side of the market price, so Plotly's scale follows that curve
# The two lines of type in a heatmap cell: the price, larger and in the medium weight, and its upside, smaller and in the
# regular weight. Both are the cream text, because a green or red number fails the 4.5 contrast check on the strongest tints.
HEATMAP_PRICE_SIZE = 13             # px, the "table" step of the type scale
HEATMAP_UPSIDE_SIZE = 11            # px, the "label" step of the type scale
# Room on the left of a heatmap for its row labels and the row title in the corner above them: about 7 px for each
# character of the 11 px axis labels, plus a little space before the cells. The corner title wraps to the width of the
# longest row label, so it never needs more room than the labels themselves.
HEATMAP_LABEL_CHARACTER_WIDTH = 7   # px
HEATMAP_LABEL_GAP = 16              # px
HEATMAP_KEY_PREFIX = theme.HEATMAP_KEY_PREFIX   # the boxes round the two heatmaps, so theme.py's phone CSS can find them

# Every table is a plain st.table with lines between the rows only: no lines down the columns and no box round it, the
# way the best finance products lay out data (polish, 24 Nov 2026). theme.py's CSS does the type and the alignment.
TABLE_BORDER = "horizontal"

# The label of the small closed box that holds a section's notes on method (polish C, 24 Nov 2026).
READING_NOTES_LABEL = "How to read this"

# The six figures that make up a company's peers in a data package.
PEER_KEYS = ["peer_tickers", "peer_ev_sales", "peer_ev_ebitda", "peer_pe", "peer_ps", "peer_forward_pe"]

# Guard rail 13: the footer every page of the app must show.
FOOTER_TEXT = "Valuation Lab is a learning project, not investment advice."

# Where the numbers come from, shown just above the footer line. The risk-free rate and the equity risk premium are the
# figures typed in by hand in data.py (the WACC table says the same), Adobe's base case is its own hand-checked set.
SOURCES_TEXT = (
    "Sources: share prices, financial statements, peers and news from Yahoo Finance (Financial Modeling Prep as a "
    "backup when Yahoo is not answering); risk-free rate and equity risk premium from Damodaran, 1 Nov 2026; interest-rate and inflation numbers from FRED; "
    "Adobe's base case from its FY2025 10-K."
)

# A few tickers to suggest when a company cannot be found.
EXAMPLE_TICKERS = ["ADBE", "AAPL", "MSFT", "KO", "NVDA"]

# How long the page remembers Yahoo's answer. Streamlit reruns the whole page on every
# slider move, so without this each move would ask Yahoo again. 15 minutes is a judgment
# call agreed with Haavard, not a rule from Yahoo.
LIVE_DATA_CACHE_SECONDS = 15 * 60

# How long the page remembers what changes only when a company reports, or hardly ever: the history, the
# last twelve months, and the suggested peers (which cost the most requests: up to 50 lookups for one
# company). Remembering them for hours instead of minutes means far fewer requests to Yahoo, which
# sometimes limits the app's shared server. Chosen with Haavard on 20 Nov 2026. Since 24 Nov 2026 (Haavard chose
# "save answers longer") the name search, the analysts' view, the one-year price chart and the news use it too.
# The share price and the peers' multiples, which move with the market, keep the shorter time above.
SLOW_DATA_CACHE_SECONDS = 6 * 60 * 60


def dollars(amount):
    """Write a number as a dollar price with two decimals, for example $305.60, and a negative one as −$12.50
    (the true minus sign in front of the dollar sign)."""
    return f"{theme.MINUS}${-amount:,.2f}" if amount < 0 else f"${amount:,.2f}"


def percent(rate):
    """Write a decimal rate as a percentage with one decimal, for example 0.215 as 21.5%. A rate
    too small to show is written 0.0%, never -0.0%.
    """
    text = f"{rate:.1%}"
    return "0.0%" if text == "-0.0%" else theme.with_true_minus(text)


def precise_percent(rate):
    """Write a decimal rate as a percentage with two decimals, for example 0.1093 as 10.93%. A rate
    too small to show is written 0.00%, never -0.00%.
    """
    text = f"{rate:.2%}"
    return "0.00%" if text == "-0.00%" else theme.with_true_minus(text)


def shift_from_points(points):
    """Turn a slider's percentage points into the decimal the model uses (1.5 points is 0.015),
    making sure a zero is a plain zero and never a negative one.
    """
    return points / 100 + 0.0



def is_base_case(company):
    """Say whether this is the company the hand-chosen assumptions were made for (Adobe)."""
    return company["ticker"] == assumptions.BASE_CASE_TICKER


def forecast_assumptions(company):
    """Pick the forecast assumptions for a company: Adobe's hand-chosen ones, or, for any
    other company, a starting point worked out from its own last reported year.

    Returns growth rates, operating margins, tax rate, D&A %, capex % and working capital %
    in the shapes the DCF takes. Stops with a plain error if the starting point cannot be
    worked out, for example when the company made no profit before tax.
    """
    if is_base_case(company):
        return dict(
            growth_rates=assumptions.GROWTH_RATES,
            operating_margins=assumptions.OPERATING_MARGINS,
            tax_rate=assumptions.TAX_RATE,
            da_pcts=assumptions.DA_PCTS,
            capex_pcts=assumptions.CAPEX_PCTS,
            wc_pcts=assumptions.WC_PCTS,
        )
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
    return valuation.starting_point_assumptions(
        ratios, assumptions.TERMINAL_GROWTH_RATE, assumptions.STARTING_POINT_YEARS,
        normal_tax_rate=assumptions.NORMAL_TAX_RATE,
    )


def last_year_tax_rate(company):
    """Return last year's tax rate for a company other than Adobe (income tax divided by pre-tax income),
    or None for Adobe or when there was no pre-tax profit to divide by.
    """
    if is_base_case(company):
        return None
    return valuation.ratio_or_none(company["income_tax"], company["income_before_tax"])


def tax_rate_was_replaced(company):
    """Say whether the forecast uses the normal tax rate because last year's was negative."""
    rate = last_year_tax_rate(company)
    return rate is not None and rate < 0


def model_beta(company):
    """Return the beta the model uses: Adobe's observed beta as it is, and for every other company the
    adjusted beta, pulled part of the way towards the market's beta of 1.
    """
    if is_base_case(company):
        return company["beta"]
    return valuation.adjusted_beta(company["beta"], assumptions.BETA_WEIGHT_ON_OBSERVED, assumptions.MARKET_BETA)


def cost_of_debt(company):
    """Use the cost of debt from the company's debt notes if its figures have one (Adobe),
    otherwise estimate it from interest expense and debt.
    """
    if "pre_tax_cost_of_debt" in company:
        return company["pre_tax_cost_of_debt"]
    return valuation.estimate_pre_tax_cost_of_debt(company["interest_expense"], company["debt"])


def build_dcf_inputs(company, growth_shift, margin_shift):
    """Gather every input the DCF needs except the terminal growth rate and the WACC.

    The growth and margin shifts move every forecast year by the same amount (0 means the
    base case). The same inputs feed both the headline DCF and the heatmap.
    """
    base = forecast_assumptions(company)
    return dict(
        base_revenue=company["revenue"],
        growth_rates=valuation.shift_rates(base["growth_rates"], growth_shift),
        operating_margins=valuation.shift_rates(base["operating_margins"], margin_shift),
        tax_rate=base["tax_rate"],
        da_pcts=base["da_pcts"],
        capex_pcts=base["capex_pcts"],
        wc_pcts=base["wc_pcts"],
        risk_free_rate=company["risk_free_rate"],
        beta=model_beta(company),
        equity_risk_premium=company["equity_risk_premium"],
        pre_tax_cost_of_debt=cost_of_debt(company),
        share_price=company["share_price"],
        shares=company["shares"],
        debt=company["debt"],
        cash_and_investments=company["cash_and_investments"],
    )


def run_valuation(company, dcf_inputs, terminal_growth_rate, wacc_override=None):
    """Run the DCF and the multiples comparison for one company's figures.

    Leave wacc_override out to use the model's own WACC, or give a rate to use that instead.
    Returns the DCF results and the multiples results, each as a dictionary of named
    numbers; the multiples are None for a company without peer figures. The multiples need
    the DCF's net debt and implied price, so the DCF runs first.
    """
    dcf = valuation.run_full_dcf(
        **dcf_inputs, terminal_growth_rate=terminal_growth_rate, wacc_override=wacc_override
    )
    if "peer_ev_sales" not in company:
        return dcf, None
    multiples = valuation.run_multiples(
        revenue=company["revenue"],
        ebit=company["ebit"],
        depreciation_and_amortisation=company["depreciation_and_amortisation"],
        net_income=company["net_income"],
        net_debt_amount=dcf["net_debt"],
        shares=company["shares"],
        peer_ev_sales=company["peer_ev_sales"],
        peer_ev_ebitda=company["peer_ev_ebitda"],
        peer_pe=company["peer_pe"],
        peer_ps=company["peer_ps"],
        forward_eps=company.get("forward_eps"),
        peer_forward_pe=company["peer_forward_pe"],
        dcf_price=dcf["implied_share_price"],
        minimum_peers=assumptions.MINIMUM_PEERS,
    )
    return dcf, multiples


def model_wacc(dcf_inputs):
    """Find the model's own WACC, worked out from the company's figures, ignoring any WACC
    the user has set with the slider. The heatmap stays centred on this one.
    """
    return valuation.run_full_dcf(
        **dcf_inputs, terminal_growth_rate=assumptions.TERMINAL_GROWTH_RATE
    )["wacc"]


# ---------------------------------------------------------------------------
# The shareable link: the page's address holds the company and the settings, so a link opens the same view
# ---------------------------------------------------------------------------

# The keys of the boxes that the link remembers (the ticker box's key is TICKER_BOX_KEY, further down). The peers and
# the one-off amount have one box per company, whose key is the name below with the ticker after it.
GROWTH_KEY = "growth_shift"
MARGIN_KEY = "margin_shift"
TERMINAL_GROWTH_KEY = "terminal_growth"
WACC_TICK_KEY = "wacc_tick"
WACC_KEY = "wacc_value"
PEERS_KEY_START = "peers_"
ONE_OFF_KEY_START = "oneoff_"
LINK_LOADED_KEY = "link_loaded"
COMPARE_KEY = "compare_ticker"          # the box in the Compare tab where the second company is typed
SOURCE_NOTE_KEY = "source_note"        # the box under the header that says where the figures came from (CSS class st-key-source_note)
STORY_KEY = "price_story"            # the box under the headline cards with the plain sentence (see price_story)
STRIP_KEY = "assumption_strip"          # the bordered strip of sliders under the header (its CSS class is st-key-assumption_strip)
SEARCH_BAR_KEY = theme.SEARCH_BAR_KEY   # the app's name, the ticker box and the name search, side by side at the top
TOOLS_KEY = "strip_tools"               # the row of buttons under the sliders: WACC and rates, Scenarios, Peers, One-off items
LIVE_RF_KEY = "live_risk_free"          # the tick box that swaps in today's 10-year Treasury yield

LINK_TICKER_PATTERN = re.compile(r"[A-Za-z0-9.^=\-]+")
LINK_PEERS_PATTERN = re.compile(r"[A-Za-z0-9.^=\-, ]+")


def number_from_link(text, low, high, step):
    """Read a number from the address and make it fit a slider: None when it is not a plain number or lies outside
    low..high, otherwise the number moved to the nearest step the slider has.
    """
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not low - 1e-9 <= value <= high + 1e-9:
        return None
    return round(round(value / step) * step, 6)


def settings_from_link(params):
    """Turn the words after the ? in the page's address (a dictionary of text) into the settings it holds: "ticker", "compare"
    (the second company), "live_rf" (True when today's 10-year yield is used as the risk-free rate), "growth" and "margin" (in points), "terminal_growth" and "wacc" (decimals), "oneoff" ($ millions a year) and "peers" (text). The
    address is typed by anyone, so a setting that is missing, is not a number, lies outside what the sliders can show or has
    odd characters in it is simply left out, and the page starts that setting at its usual value.
    """
    settings = {}
    for name in ("ticker", "compare"):
        ticker = params.get(name, "")
        if ticker and len(ticker) <= assumptions.LINK_TICKER_MAX_CHARACTERS and LINK_TICKER_PATTERN.fullmatch(ticker):
            settings[name] = ticker.upper()
    for name, low, high, step in (
        ("growth", assumptions.GROWTH_SHIFT_MIN_POINTS, assumptions.GROWTH_SHIFT_MAX_POINTS, assumptions.GROWTH_SHIFT_STEP_POINTS),
        ("margin", assumptions.MARGIN_SHIFT_MIN_POINTS, assumptions.MARGIN_SHIFT_MAX_POINTS, assumptions.MARGIN_SHIFT_STEP_POINTS),
    ):
        value = number_from_link(params.get(name), low, high, step)
        if value is not None:
            settings[name] = value
    for name, low, high, step in (
        ("terminal_growth", assumptions.TERMINAL_GROWTH_MIN, assumptions.TERMINAL_GROWTH_MAX, assumptions.TERMINAL_GROWTH_STEP),
        ("wacc", assumptions.WACC_SLIDER_MIN, assumptions.WACC_SLIDER_MAX, assumptions.WACC_SLIDER_STEP),
    ):
        # In the address these are percentages ("2.5"); the sliders hold decimals (0.025).
        try:
            decimal = float(params.get(name)) / 100
        except (TypeError, ValueError):
            continue
        value = number_from_link(decimal, low, high, step)
        if value is not None:
            settings[name] = value
    if params.get("live_rf") == "1":
        settings["live_rf"] = True
    limit = assumptions.LINK_ONE_OFF_LIMIT_MILLIONS
    one_off = number_from_link(params.get("oneoff"), -limit, limit, 1)
    if one_off is not None:
        settings["oneoff"] = one_off
    peers = params.get("peers", "")
    if peers and len(peers) <= assumptions.LINK_PEERS_MAX_CHARACTERS and LINK_PEERS_PATTERN.fullmatch(peers):
        settings["peers"] = peers
    return settings


def link_from_state(state):
    """Write the settings in `state` (the page's boxes, by key) as the words for the address, as text. Only a setting that
    differs from its usual value is written, so the plain page has a plain address. The peers and the one-off amount are
    those of the company in the ticker box.
    """
    def number(value):
        return f"{value:g}"

    ticker = str(state.get(TICKER_BOX_KEY, "")).strip().upper() or DEFAULT_TICKER
    params = {}
    if ticker != DEFAULT_TICKER:
        params["ticker"] = ticker
    compare = str(state.get(COMPARE_KEY, "")).strip().upper()
    if compare:
        params["compare"] = compare
    if state.get(LIVE_RF_KEY):
        params["live_rf"] = "1"
    for name, key in (("growth", GROWTH_KEY), ("margin", MARGIN_KEY)):
        if state.get(key, 0.0) != 0.0:
            params[name] = number(state[key])
    if state.get(TERMINAL_GROWTH_KEY, assumptions.TERMINAL_GROWTH_RATE) != assumptions.TERMINAL_GROWTH_RATE:
        params["terminal_growth"] = number(round(state[TERMINAL_GROWTH_KEY] * 100, 4))
    if state.get(WACC_TICK_KEY) and WACC_KEY in state:
        params["wacc"] = number(round(state[WACC_KEY] * 100, 4))
    if state.get(ONE_OFF_KEY_START + ticker, 0.0) != 0.0:
        params["oneoff"] = number(state[ONE_OFF_KEY_START + ticker])
    if state.get(PEERS_KEY_START + ticker):
        params["peers"] = state[PEERS_KEY_START + ticker]
    return params


def load_link():
    """When a visit begins (and only then, so a reader's later changes are never undone), put the settings held in the page's
    address into the boxes. It runs before the boxes are drawn, which is the one moment a box's value may be set.
    """
    if st.session_state.get(LINK_LOADED_KEY):
        return
    st.session_state[LINK_LOADED_KEY] = True
    settings = settings_from_link(dict(st.query_params))
    ticker = settings.get("ticker", DEFAULT_TICKER)
    if "ticker" in settings:
        st.session_state[TICKER_BOX_KEY] = ticker
    if "compare" in settings:
        st.session_state[COMPARE_KEY] = settings["compare"]
    if "live_rf" in settings:
        st.session_state[LIVE_RF_KEY] = True
    for name, key in (
        ("growth", GROWTH_KEY), ("margin", MARGIN_KEY), ("terminal_growth", TERMINAL_GROWTH_KEY), ("wacc", WACC_KEY),
    ):
        if name in settings:
            st.session_state[key] = settings[name]
    if "wacc" in settings:
        st.session_state[WACC_TICK_KEY] = True
    if "oneoff" in settings:
        st.session_state[ONE_OFF_KEY_START + ticker] = settings["oneoff"]
    if "peers" in settings:
        st.session_state[PEERS_KEY_START + ticker] = settings["peers"]


def write_link():
    """Write the page's current settings into its address, so copying the address from the browser shares this view."""
    params = link_from_state(st.session_state)
    if dict(st.query_params) != params:
        st.query_params.from_dict(params)


LINK_NOTE = "To share this view, copy the page's address from your browser: it holds the company and every setting on the page."


def draw_sliders():
    """Draw the assumption strip under the header and return what it is set to: the growth shift, the margin shift, the
    terminal growth rate, the WACC the user chose (None when the box is unticked, meaning the model uses its own) and
    today's risk-free rate when that box is ticked (None otherwise). Three sliders sit side by side; the WACC and the
    risk-free rate are behind a "WACC and rates" button, because they are changed less often. Each starts at the base case.
    Also returns the row of buttons under the sliders, where the Scenarios, Peers and One-off items buttons go too.
    """
    strip = st.container(border=True, key=STRIP_KEY)
    growth_column, margin_column, terminal_column = strip.columns(3, gap="large", vertical_alignment="bottom")
    growth_points = growth_column.slider(
        "Revenue growth, every year",
        min_value=assumptions.GROWTH_SHIFT_MIN_POINTS,
        max_value=assumptions.GROWTH_SHIFT_MAX_POINTS,
        value=0.0,
        step=assumptions.GROWTH_SHIFT_STEP_POINTS,
        key=GROWTH_KEY,
        format="%+.1f pts",
        help="Adds this many percentage points to every forecast year's growth. 0 is the base case; the table 'What the model assumes' shows the result.",
    )
    margin_points = margin_column.slider(
        "Operating margin, every year",
        min_value=assumptions.MARGIN_SHIFT_MIN_POINTS,
        max_value=assumptions.MARGIN_SHIFT_MAX_POINTS,
        value=0.0,
        step=assumptions.MARGIN_SHIFT_STEP_POINTS,
        key=MARGIN_KEY,
        format="%+.1f pts",
        help="Adds this many percentage points to every forecast year's operating margin. 0 is the base case; the table 'What the model assumes' shows the result.",
    )
    terminal_growth_rate = terminal_column.slider(
        "Terminal growth",
        min_value=assumptions.TERMINAL_GROWTH_MIN,
        max_value=assumptions.TERMINAL_GROWTH_MAX,
        value=assumptions.TERMINAL_GROWTH_RATE,
        step=assumptions.TERMINAL_GROWTH_STEP,
        key=TERMINAL_GROWTH_KEY,
        format="percent",
        help="How fast cash flow is assumed to grow forever after year 5. The base case is 2.5%.",
    )
    tools = strip.container(horizontal=True, key=TOOLS_KEY)
    rates = tools.popover("WACC and rates")
    wacc_override = None
    if rates.checkbox(
        "Set the WACC myself",
        key=WACC_TICK_KEY,
        help="Unticked, the model works out its own WACC from the company's figures. Ticked, the slider sets it.",
    ):
        wacc_override = rates.slider(
            "WACC",
            min_value=assumptions.WACC_SLIDER_MIN,
            max_value=assumptions.WACC_SLIDER_MAX,
            value=assumptions.WACC_SLIDER_START,
            step=assumptions.WACC_SLIDER_STEP,
            key=WACC_KEY,
            format="percent",
            help="The rate that cash flows are discounted at. Higher means a lower price.",
        )
    live_risk_free = draw_live_risk_free(rates)
    return (
        shift_from_points(growth_points), shift_from_points(margin_points), terminal_growth_rate, wacc_override, live_risk_free,
        tools,
    )


def draw_live_risk_free(box):
    """Draw, in `box`, the tick box "Use today's 10-year Treasury yield as the risk-free rate" under the WACC controls and return what to
    use: {"rate", "date"} when it is ticked and FRED answered, otherwise None (the model's own typed-in rate stays). When ticked
    it says what changes, and that Damodaran's equity risk premium was worked out with the older rate. When FRED cannot give
    the yield it says so and the model's own rate is used.
    """
    ticked = box.checkbox(
        "Use today's 10-year Treasury yield as the risk-free rate", key=LIVE_RF_KEY,
        help=explanations.help_text("live_risk_free"),
    )
    if not ticked:
        return None
    try:
        live = data.risk_free_from_macro(load_macro_backdrop())
    except ValueError as error:
        box.warning(f"Today's yield is not available ({error}) so the model's own risk-free rate is used.")
        return None
    box.caption(
        f"Risk-free rate {precise_percent(live['rate'])} (the 10-year yield on {day_text(live['date'])}, "
        f"from FRED) instead of {precise_percent(data.RISK_FREE_RATE)} (Damodaran). His {precise_percent(data.EQUITY_RISK_PREMIUM)} equity risk "
        "premium was worked out with the older rate, so the two do not quite fit together."
    )
    return live


def apply_live_risk_free(company, live):
    """Put today's 10-year yield into a company's figures as its risk-free rate (nothing changes when `live` is None). A company
    whose cost of debt was estimated as the risk-free rate plus a credit spread gets that estimate redone with the new rate.
    Marks the company so the WACC table can say where the rate came from.
    """
    if live is None:
        return company
    changed = dict(company, risk_free_rate=live["rate"], risk_free_is_live=True, risk_free_date=live["date"])
    if company.get("cost_of_debt_is_fallback"):
        changed["pre_tax_cost_of_debt"] = valuation.fallback_pre_tax_cost_of_debt(live["rate"], data.CREDIT_SPREAD)
    return changed


# The Explanations tab groups the glossary by where its terms appear on the page: the heading and the section of
# explanations.SECTION_TERMS it takes its terms from.
EXPLANATION_TOPICS = [
    ("The DCF", "dcf"),
    ("Behind the number", "behind_the_number"),
    ("Sensitivity", "sensitivity"),
    ("Multiples", "multiples"),
]


def draw_explanations_tab():
    """Draw the Explanations tab: every term in the glossary (explanations.py), in plain language, grouped by where
    it is used on the page. A term that belongs to several sections is shown once, under the first. Any term that is
    in no section is added at the end, so nothing in the glossary is ever left out of the tab.
    """
    st.subheader("Explanations")
    st.caption("Every term the page uses, in plain language, grouped by where it appears.")
    shown = []
    for heading, section in EXPLANATION_TOPICS:
        terms = [term for term in explanations.SECTION_TERMS[section] if term not in shown]
        if not terms:
            continue
        st.markdown(f"##### {heading}")
        for term in terms:
            title, text = explanations.EXPLANATIONS[term]
            st.markdown(f"**{title}**  \n{text}")
            shown.append(term)
    others = [term for term in explanations.EXPLANATIONS if term not in shown]
    if others:
        st.markdown("##### More terms")
        for term in others:
            title, text = explanations.EXPLANATIONS[term]
            st.markdown(f"**{title}**  \n{text}")
    st.markdown("##### Reading the page")
    st.caption("What the cards, price boxes and charts show: the same texts as the ? next to them.")
    for key, (title, _text) in explanations.HELP_TEXTS.items():
        st.markdown(f"**{title}**  \n{explanations.help_text(key)}")


def draw_dcf(company, dcf, wacc_is_set_by_user, terminal_growth_rate):
    """Draw the top of the DCF tab: the DCF price, the WACC (labelled as the user's own when it comes from the slider)
    and the terminal growth rate in use. The market price and the upside are in the header and are not repeated.
    """
    st.subheader("Discounted cash flow (DCF)")
    price_column, wacc_column, growth_column = st.columns(3)
    price_column.metric(
        "DCF implied price", dollars(dcf["implied_share_price"]), help=explanations.help_text("implied_share_price")
    )
    wacc_column.metric(
        "WACC (your setting)" if wacc_is_set_by_user else "WACC", percent(dcf["wacc"]),
        help=explanations.help_text("wacc"),
    )
    growth_column.metric(
        "Terminal growth", percent(terminal_growth_rate), help=explanations.help_text("terminal_growth_rate")
    )


def heat_colour(gap):
    """Work out the colour of a heatmap cell from how far its price is above (positive) or below (negative) the
    market price, as red, green and blue numbers: the card colour at the market price, moving towards green above it
    and red below it (slowly at first, see HEATMAP_TINT_CURVE), as far as HEATMAP_STRONGEST_TINT when the gap reaches
    HEATMAP_FULL_TINT_GAP.
    """
    strength = min(abs(gap) / HEATMAP_FULL_TINT_GAP, 1) ** HEATMAP_TINT_CURVE * HEATMAP_STRONGEST_TINT
    start = theme.hex_to_rgb(theme.SURFACE)
    target = theme.hex_to_rgb(theme.UP if gap >= 0 else theme.DOWN)
    return tuple(round(begin + (end - begin) * strength) for begin, end in zip(start, target))


def tint(price, market_price):
    """Pick a background colour for one heatmap cell: the card colour at the market price, greener the
    further above it, redder the further below it, with whichever text colour reads best on top.
    """
    red, green, blue = heat_colour((price - market_price) / market_price)
    text_colour = theme.readable_text_on(f"#{red:02X}{green:02X}{blue:02X}")
    return f"background-color: rgb({red}, {green}, {blue}); color: {text_colour}"


def heatmap_colourscale():
    """The colours of a heatmap as Plotly wants them: red-tinted at the lowest gap it shows, the card colour at the
    market price and green-tinted at the highest, with enough steps in between to follow the same curve as the
    tables (see heat_colour).
    """
    steps = 2 * HEATMAP_SCALE_STEPS
    positions = [step / steps for step in range(steps + 1)]
    return [[position, f"rgb{heat_colour((2 * position - 1) * HEATMAP_FULL_TINT_GAP)}"] for position in positions]


def heatmap_cell_text(price, gap):
    """The text inside one heatmap cell: the price on top, larger and in the medium weight, and its upside with an
    arrow underneath, smaller. A blank cell (no answer) stays empty.
    """
    if price is None:
        return ""
    return (
        f"<span style='font-size:{HEATMAP_PRICE_SIZE}px;font-weight:{theme.WEIGHT_MEDIUM}'>${price:,.0f}</span><br>"
        f"<span style='font-size:{HEATMAP_UPSIDE_SIZE}px'>{theme.change_text(gap, digits=0)}</span>"
    )


def break_even_edges(upsides):
    """Find the cell edges that separate a price above the market price from one below it, as the x and y points of a
    line Plotly can draw (None breaks the line between edges). The line then runs between cells, never across their
    numbers. A blank cell has no side, so no edge is drawn next to it.
    """
    xs, ys = [], []

    def above(row, column):
        """Whether a cell's price is at or above the market price (None for a blank cell)."""
        gap = upsides[row][column]
        return None if gap is None else gap >= 0

    for row in range(len(upsides)):
        for column in range(len(upsides[row])):
            here = above(row, column)
            if here is None:
                continue
            if column + 1 < len(upsides[row]) and above(row, column + 1) not in (None, here):
                xs += [column + 0.5, column + 0.5, None]
                ys += [row - 0.5, row + 0.5, None]
            if row + 1 < len(upsides) and above(row + 1, column) not in (None, here):
                xs += [column - 0.5, column + 0.5, None]
                ys += [row + 0.5, row + 0.5, None]
    return xs, ys


def base_label(label):
    """A row or column label in the gold of the base-case frame, so the base case can be found from the edges too."""
    return f"<span style='color:{theme.ACCENT}'>{label}</span>"


def sensitivity_headline(prices, share_price):
    """Say in one sentence how many of the combinations in a sensitivity table give a price above today's market price,
    and what the dashed line means. Blank cells are not counted.
    """
    above, total = valuation.cells_above_price(prices, share_price)
    if above == total:
        return f"All {total} combinations give a price above today's market price, so no assumption in this table brings the model down to it."
    if above == 0:
        return f"None of the {total} combinations reaches today's market price."
    return f"{above} of {total} combinations give a price above today's market price; the dashed line shows where the model equals it."


def sensitivity_heatmap(row_labels, column_labels, prices, share_price, base_cell, row_title, column_title):
    """Draw a sensitivity table as a heatmap laid out like a banker's spreadsheet: the column labels along the top,
    the row title in the top-left corner, and the base case's row and column labels in gold. Every cell shows its
    price and, smaller, its upside against the market price (with an arrow and a sign), tinted green above the
    market price and red below it. A dashed line runs along the cell edges where the price crosses the market price,
    and a gold frame marks the base case. A blank cell (no answer) stays empty. `base_cell` is the (row, column)
    position of the base case.
    """
    upsides = valuation.upside_grid(prices, share_price)
    rows, columns = range(len(row_labels)), range(len(column_labels))
    base_row, base_column = base_cell
    # A long label such as "4.10% (−4 pts)" goes on two lines, so the column labels fit side by side even on a phone
    # and the row labels leave more room for the cells.
    column_lines = [label.replace(" (", "<br>(") for label in column_labels]
    row_lines = [label.replace(" (", "<br>(") for label in row_labels]
    text = [[heatmap_cell_text(price, gap) for price, gap in zip(price_row, gap_row)] for price_row, gap_row in zip(prices, upsides)]
    customdata = [
        [[price, gap, row_labels[row], column_labels[column]] for column, (price, gap) in enumerate(zip(price_row, gap_row))]
        for row, (price_row, gap_row) in enumerate(zip(prices, upsides))
    ]
    figure = go.Figure(go.Heatmap(
        z=upsides, x=list(columns), y=list(rows),
        zmin=-HEATMAP_FULL_TINT_GAP, zmax=HEATMAP_FULL_TINT_GAP, colorscale=heatmap_colourscale(), showscale=False,
        text=text, texttemplate="%{text}", textfont={"color": theme.TEXT, "size": HEATMAP_PRICE_SIZE},
        customdata=customdata, hoverongaps=False, xgap=2, ygap=2,
        hovertemplate=(
            f"{row_title}: %{{customdata[2]}}<br>{column_title}: %{{customdata[3]}}<br>"
            "Price $%{customdata[0]:,.2f}<br>%{customdata[1]:+.1%} against the market price<extra></extra>"
        ),
    ))
    edge_xs, edge_ys = break_even_edges(upsides)
    figure.add_trace(go.Scatter(
        x=edge_xs, y=edge_ys, mode="lines", hoverinfo="skip", connectgaps=False,
        line={"color": theme.TEXT, "width": 2, "dash": "dash"},
    ))
    figure.add_shape(
        type="rect", x0=base_column - 0.5, x1=base_column + 0.5, y0=base_row - 0.5, y1=base_row + 0.5,
        line={"color": theme.ACCENT, "width": 2},
    )
    figure.update_xaxes(
        tickvals=list(columns), side="top", showgrid=False, zeroline=False,
        ticktext=[base_label(label) if column == base_column else label for column, label in enumerate(column_lines)],
        tickangle=0,
        title={"text": column_title, "font": {"size": HEATMAP_UPSIDE_SIZE, "color": theme.GREY}},
    )
    figure.update_yaxes(
        tickvals=list(rows), showgrid=False, zeroline=False, autorange="reversed", automargin=True,
        ticktext=[base_label(label) if row == base_row else label for row, label in enumerate(row_lines)],
    )
    # The row title sits in the top-left corner, beside the column labels, instead of turned on its side.
    label_texts = [line for label in row_lines for line in label.split("<br>")] + row_title.split()
    label_length = max(len(text) for text in label_texts)
    figure.add_annotation(
        text="<br>".join(textwrap.wrap(row_title, label_length)), xref="paper", yref="paper", x=0, y=1, xanchor="right", yanchor="bottom", showarrow=False,
        xshift=-8, align="right", font={"size": HEATMAP_UPSIDE_SIZE, "color": theme.GREY},
    )
    theme.style_figure(figure, height=110 + 56 * len(row_labels))
    figure.update_layout(margin={"l": label_length * HEATMAP_LABEL_CHARACTER_WIDTH + HEATMAP_LABEL_GAP, "r": 0, "t": 0, "b": 0})
    return figure


NOT_MEANINGFUL = "Not meaningful"       # shown when a number would mean nothing (no P/E for a loss)


def company_overview(company):
    """Work out the eight overview numbers for a company from its last full year and today's
    share price (see valuation.stock_overview).
    """
    return valuation.stock_overview(
        share_price=company["share_price"],
        shares=company["shares"],
        debt=company["debt"],
        cash_and_investments=company["cash_and_investments"],
        revenue=company["revenue"],
        prior_year_revenue=company["prior_year_revenue"],
        ebit=company["ebit"],
        depreciation_and_amortisation=company["depreciation_and_amortisation"],
        net_income=company["net_income"],
        income_tax=company["income_tax"],
        income_before_tax=company["income_before_tax"],
        capex=company["capex"],
        cash_from_working_capital=company["cash_from_working_capital"],
        forward_eps=company.get("forward_eps"),
    )


def apply_ttm(overview, company, ttm, ttm_error=None):
    """Put the numbers a reader compares with peers (EV/Sales, EV/EBITDA, P/E and the operating
    margin) on the company's last twelve months, like the peers', and leave the rest on its last
    fiscal year. Adds "ttm_period_end" (when the latest quarter ended; None if the last twelve
    months are not available, and then every number stays on the fiscal year) and "ttm_error".
    """
    if ttm is None:
        return dict(overview, ttm_period_end=None, ttm_error=ttm_error)
    recent = valuation.ttm_overview(
        share_price=company["share_price"],
        shares=company["shares"],
        debt=ttm["debt"],
        cash_and_investments=ttm["cash_and_investments"],
        revenue=ttm["revenue"],
        operating_income=ttm["operating_income"],
        depreciation_and_amortisation=ttm["depreciation_and_amortisation"],
        net_income=ttm["net_income"],
    )
    return dict(
        overview,
        ev_sales=recent["ev_sales"],
        ev_ebitda=recent["ev_ebitda"],
        pe=recent["pe"],
        ps=recent["ps"],
        operating_margin=recent["operating_margin"],
        ttm_period_end=ttm["period_end"],
        ttm_error=None,
    )


def apply_quality(overview, company, history):
    """Add the four quality numbers to the overview, for the last fiscal year: the return on invested
    capital, cash conversion (reported free cash flow over net income, from the history), interest
    cover, and the change in the share count over the history. A number that cannot be worked out is
    None. The interest expense itself is kept too, because "no interest" and "not known" read
    differently.
    """
    reported_free_cash_flow = None if history is None else history["free_cash_flow"][-1]
    shares_by_year = [] if history is None else history["diluted_shares"]
    quality = valuation.quality_numbers(
        ebit=company["ebit"],
        income_tax=company["income_tax"],
        income_before_tax=company["income_before_tax"],
        debt=company["debt"],
        equity=company.get("stockholders_equity"),
        cash_and_investments=company["cash_and_investments"],
        free_cash_flow=reported_free_cash_flow,
        net_income=company["net_income"],
        interest_expense=company.get("interest_expense"),
        shares_by_year=shares_by_year,
    )
    return dict(
        overview,
        roic=quality["roic"],
        cash_conversion=quality["cash_conversion"],
        interest_cover=quality["interest_cover"],
        interest_expense=company.get("interest_expense"),
        share_count_change=quality["share_count_change"],
        share_count_years=quality["share_count_years"],
    )


def interest_cover_text(overview):
    """Write the interest cover: a multiple such as 33.1x, "No interest" for a company that pays
    none, or "Not available" when Yahoo has no interest figure.
    """
    if overview.get("interest_expense") is None:
        return "Not available"
    if overview["interest_expense"] == 0:
        return "No interest"
    return multiple_or_note(overview["interest_cover"], 1)


def share_count_text(overview):
    """Write the change in the share count as a value and a note under it: for example -9.3% and
    "over 3 years". The value is "Not available", with no note, when the history has too few years of
    share counts.
    """
    if overview.get("share_count_change") is None:
        return "Not available", None
    years = overview["share_count_years"]
    return percent(overview["share_count_change"]), f"over {years} year{'' if years == 1 else 's'}"


def percent_or_note(rate):
    """Write a rate as a percentage, or say it is not meaningful when it could not be worked out."""
    return NOT_MEANINGFUL if rate is None else percent(rate)


def multiple_or_note(multiple, decimals=1):
    """Write a multiple such as 14.6x, or say it is not meaningful when it could not be worked out."""
    return NOT_MEANINGFUL if multiple is None else f"{multiple:.{decimals}f}x"


def history_range_clause(label, implied, values):
    """Set an implied figure against the company's own history: say what range the figure had over
    the years and whether the implied one is above the best year, below the worst, or within the
    range. Returns an empty string when the history has no figure to compare with.
    """
    known = [value for value in values if value is not None]
    if not known:
        return ""
    best, worst = max(known), min(known)
    if implied > best:
        verdict = "above its best year"
    elif implied < worst:
        verdict = "below its worst year"
    else:
        verdict = "within that range"
    return (
        f" In its history {label} ranged from {percent(worst)} to {percent(best)}, so the implied "
        f"figure is {verdict}."
    )


def implied_margin_sentence(market_price, answer, history):
    """Say what operating margin the market price implies: the average over the five forecast
    years against the model's, with revenue growth as modelled, and how that compares with the
    company's history. Says so plainly when no margin within the search range reaches the price.
    """
    if answer is None:
        return (
            f"No operating margin within {assumptions.REVERSE_DCF_SEARCH_RANGE * 100:.0f} points of the "
            f"model's makes the DCF equal the market price of {dollars(market_price)}."
        )
    sentence = (
        f"To justify the market price of {dollars(market_price)}, the market is pricing in an average "
        f"operating margin of {percent(answer['implied_average'])} over the five forecast years, against "
        f"{percent(answer['model_average'])} in the model, with revenue growth as modelled."
    )
    if history is not None:
        margins = valuation.ratios_by_year(history["operating_income"], history["revenue"])
        sentence += history_range_clause("the operating margin", answer["implied_average"], margins)
    return sentence


def implied_growth_sentence(market_price, answer, history):
    """Say what revenue growth the market price implies: the average a year over the five forecast
    years against the model's, with the margin as modelled, and how that compares with the
    company's history. Says so plainly when no growth within the search range reaches the price.
    """
    if answer is None:
        return (
            f"No revenue growth within {assumptions.REVERSE_DCF_SEARCH_RANGE * 100:.0f} points of the "
            f"model's makes the DCF equal the market price of {dollars(market_price)}."
        )
    sentence = (
        f"Or, holding the margin as modelled, an average revenue growth of {percent(answer['implied_average'])} "
        f"a year, against {percent(answer['model_average'])} in the model."
    )
    if history is not None:
        sentence += history_range_clause("revenue growth", answer["implied_average"], valuation.yearly_growth(history["revenue"]))
    return sentence


def draw_reverse_dcf(company, dcf_inputs, terminal_growth_rate, wacc_override, history):
    """Draw "What the market price implies": the operating margin, and separately the revenue
    growth, that would make the DCF equal today's market price, each against the model's and the
    company's history. It uses the page's current sliders, terminal growth and WACC.
    """
    st.subheader("What the market price implies")
    answers = valuation.reverse_dcf(
        dcf_inputs, company["share_price"], terminal_growth_rate, wacc_override,
        assumptions.REVERSE_DCF_SEARCH_RANGE, assumptions.REVERSE_DCF_TOLERANCE,
    )
    margin_column, growth_column = st.columns(2)
    margin_column.metric(
        "Operating margin it implies",
        "No answer" if answers["margin"] is None else percent(answers["margin"]["implied_average"]),
        help="The average operating margin over the five forecast years at which the DCF equals the market price, holding revenue growth as modelled.",
    )
    growth_column.metric(
        "Revenue growth it implies",
        "No answer" if answers["growth"] is None else percent(answers["growth"]["implied_average"]),
        help="The average revenue growth a year over the five forecast years at which the DCF equals the market price, holding the margin as modelled.",
    )
    # Each dollar sign is escaped with a backslash, because Streamlit reads text between two
    # unescaped dollar signs as a maths formula.
    st.caption(implied_margin_sentence(company["share_price"], answers["margin"], history).replace("$", "\\$"))
    st.caption(implied_growth_sentence(company["share_price"], answers["growth"], history).replace("$", "\\$"))
    with reading_notes("reverse_dcf"):
        st.caption(
            "Each answer changes one thing and holds the other as modelled. They use the page's current "
            "settings (the sliders, the terminal growth and the WACC), so they move when you move those."
        )


def draw_scenario_boxes(tools):
    """Draw the scenario boxes behind a "Scenarios" button in `tools` (the row under the sliders) and return what they
    are set to: for the
    bear, base and bull cases, the shift in every year's operating margin and in every year's revenue
    growth (decimals; the base case is always no shift, so it is the DCF itself) and the probability
    of each (decimals). The boxes start at the defaults in assumptions.py.
    """
    limit = assumptions.SCENARIO_SHIFT_LIMIT_POINTS

    def shift_box(label, key, start, low, high):
        return st.number_input(
            label, min_value=low, max_value=high, value=start, step=assumptions.SCENARIO_SHIFT_STEP_POINTS,
            format="%+.1f", key=key,
        )

    def chance_box(label, key, start):
        return st.number_input(label, min_value=0, max_value=100, value=start, step=5, key=key)

    with tools.popover("Scenarios"):
        # Plain text rather than a caption: on an error page the strip is hidden but still drawn after the footer,
        # and the footer must stay the page's last caption.
        st.markdown(
            "Each scenario moves every forecast year's operating margin and revenue growth, in percentage "
            "points, on top of the sliders. The base case is the DCF itself."
        )
        bear_margin = shift_box("Bear: operating margin (points)", "scenario_bear_margin", assumptions.SCENARIO_BEAR_MARGIN_POINTS, -limit, 0.0)
        bear_growth = shift_box("Bear: revenue growth (points)", "scenario_bear_growth", assumptions.SCENARIO_BEAR_GROWTH_POINTS, -limit, 0.0)
        bull_margin = shift_box("Bull: operating margin (points)", "scenario_bull_margin", assumptions.SCENARIO_BULL_MARGIN_POINTS, 0.0, limit)
        bull_growth = shift_box("Bull: revenue growth (points)", "scenario_bull_growth", assumptions.SCENARIO_BULL_GROWTH_POINTS, 0.0, limit)
        bear_chance, base_chance, bull_chance = (
            chance_box(f"{name} probability (%)", f"scenario_{name.lower()}_chance", start)
            for name, start in zip(("Bear", "Base", "Bull"), assumptions.SCENARIO_PROBABILITIES_PERCENT)
        )
    return {
        "margin_shifts": [bear_margin / 100, 0.0, bull_margin / 100],
        "growth_shifts": [bear_growth / 100, 0.0, bull_growth / 100],
        "probabilities": [bear_chance / 100, base_chance / 100, bull_chance / 100],
    }


def reading_notes(name):
    """A small closed "How to read this" box under a section, holding the notes on method (what the colours mean, where
    the figures come from), so the numbers stay in front and the explanations are one click away. `name` keeps each
    box apart.
    """
    return st.expander(READING_NOTES_LABEL, key=f"{theme.READING_NOTES_KEY_PREFIX}{name}")


def draw_table(table, key=None):
    """Draw a table of figures in the page's one table style: lines between the rows only, numbers on the right. A
    `key` (theme.WACC_TABLE_KEY or theme.PEER_TABLE_KEY) puts it in a named box, so theme.py can mark its total row.
    """
    if key is None:
        st.table(table, border=TABLE_BORDER)
        return
    with st.container(key=key):
        st.table(table, border=TABLE_BORDER)


def change_colour(text):
    """The text colour for a change written with its arrow: sage for "▲" (up), terracotta for "▼" (down), nothing
    for no change. The arrow and the sign still say it without colour."""
    if text.startswith("▲"):
        return f"color: {theme.UP}"
    if text.startswith("▼"):
        return f"color: {theme.DOWN}"
    return ""


def scenario_table(scenarios, settings):
    """Lay the scenarios out as a table, one row each for bear, base and bull: how far the margin and
    growth move, how likely it is, the price it gives and how far that is from the market price.
    """
    rows = {}
    for number, name in enumerate(("Bear", "Base", "Bull")):
        rows[name] = {
            "Operating margin": points_text(settings["margin_shifts"][number]),
            "Revenue growth": points_text(settings["growth_shifts"][number]),
            "Probability": f"{settings['probabilities'][number]:.0%}",
            "Price": dollars(scenarios["prices"][number]),
            "vs market price": theme.change_text(scenarios["upsides"][number]),
        }
    return pd.DataFrame(rows).T


def draw_scenarios(company, dcf_inputs, terminal_growth_rate, wacc_override, settings):
    """Draw "Scenarios": the price in a bear, base and bull case and the probability-weighted price
    against today's market price. The cases and weights come from the Scenarios button under the sliders; the
    probabilities must add up to 100%, or the section says so instead of showing prices.
    """
    st.subheader("Scenarios")
    try:
        scenarios = valuation.run_scenarios(
            dcf_inputs, terminal_growth_rate, wacc_override, settings["margin_shifts"],
            settings["growth_shifts"], settings["probabilities"], company["share_price"],
            assumptions.SCENARIO_PROBABILITY_TOLERANCE,
        )
    except ValueError as error:
        st.warning(f"{error} Change the probabilities under Scenarios, beside the sliders.")
        return
    table = scenario_table(scenarios, settings)
    draw_table(table.style.map(change_colour, subset=["vs market price"]))
    weighted_column, gap_column = st.columns(2)
    weighted_column.metric(
        "Probability-weighted price", dollars(scenarios["weighted_price"]),
        help="Each scenario's price times its probability, added up.",
    )
    gap_column.metric(
        "Weighted price vs market", percent(scenarios["weighted_vs_market"]),
        help="The weighted price divided by today's market price, minus 1. Above 0% means the weighted price is higher than the market's.",
    )
    with reading_notes("scenarios"):
        st.caption(
            "Each scenario moves every year's operating margin and revenue growth by the amounts shown, "
            "on top of the sliders; the WACC and terminal growth are the same in all three. The weights are "
            "your judgment, not a fact: change them under Scenarios, beside the sliders."
        )


def draw_overview(overview):
    """Draw the overview: how fast the company is growing, what it earns, how much cash it
    makes for its price and how heavy its debt is, then what the market pays for it.
    """
    st.subheader("Overview")
    st.markdown("**What the market pays**")
    sales, ebitda, pe = st.columns(3)
    ps, forward_pe, _spare = st.columns(3)
    sales.metric("EV/Sales", multiple_or_note(overview["ev_sales"]), help=explanations.help_text("ev_sales"))
    ebitda.metric("EV/EBITDA", multiple_or_note(overview["ev_ebitda"]), help=explanations.help_text("ev_ebitda"))
    pe.metric("P/E", multiple_or_note(overview["pe"]), help=explanations.help_text("pe"))
    ps.metric("P/S", multiple_or_note(overview["ps"]), help=explanations.help_text("ps"))
    forward_pe.metric(
        "Forward P/E", multiple_or_note(overview["forward_pe"]), help=explanations.help_text("forward_pe"),
    )
    st.markdown("**Growth and profitability**")
    growth, margin, roic = st.columns(3)
    growth.metric("Revenue growth", percent_or_note(overview["revenue_growth"]), help="Last full year's revenue compared with the year before.")
    margin.metric("Operating margin", percent_or_note(overview["operating_margin"]), help="Operating profit (EBIT) as a share of revenue, last full year.")
    roic.metric(
        "ROIC", percent_or_note(overview.get("roic")),
        help="Return on invested capital: operating profit after tax divided by the money put into the business (debt plus equity, less cash), last fiscal year.",
    )
    st.markdown("**Cash, debt and shareholders**")
    cash_yield, leverage, cover = st.columns(3)
    conversion, shares_changed, _spare = st.columns(3)
    cash_yield.metric("Free cash flow yield", percent_or_note(overview["free_cash_flow_yield"]), help="Last full year's free cash flow divided by what the market says the company is worth.")
    leverage.metric("Net debt ÷ EBITDA", multiple_or_note(overview["net_debt_to_ebitda"], 2), help="Years of operating profit (before depreciation) needed to pay off net debt. Below 0 means more cash than debt.")
    cover.metric(
        "Interest cover", interest_cover_text(overview),
        help="Operating profit (EBIT) divided by the interest expense, last fiscal year: how many times profit pays the interest.",
    )
    conversion.metric(
        "Cash conversion", multiple_or_note(overview.get("cash_conversion"), 2),
        help="Free cash flow as the company reports it divided by net income, last fiscal year. Above 1.00x means more cash than profit.",
    )
    share_value, share_note = share_count_text(overview)
    shares_changed.metric(
        "Share count change", share_value, delta=share_note, delta_color="off", delta_arrow="off",
        help="The change in the diluted average number of shares over the years in the history. A fall means buybacks.",
    )
    if overview.get("ttm_period_end"):
        basis = (
            f"EV/Sales, EV/EBITDA, P/E, P/S and the operating margin are for the last twelve months (the four "
            f"quarters to {overview['ttm_period_end']}), like the peers'; the others are for the last fiscal "
            "year. All use today's share price."
        )
    elif overview.get("ttm_error"):
        basis = (
            f"Worked out from the last fiscal year and today's share price: the last twelve months are "
            f"not available ({overview['ttm_error']})."
        )
    else:
        basis = "Worked out from the last fiscal year and today's share price."
    st.caption(f"{basis} A number that would mean nothing (no P/E for a company that lost money) says so.")
    with reading_notes("overview"):
        st.caption(
            "Return on invested capital, cash conversion, interest cover and the share count change are for the last "
            "fiscal year. Return on invested capital counts a tax benefit as no tax, and is pushed up by buybacks that "
            "shrink equity; where equity is negative it is not meaningful. Cash conversion uses the free cash flow the "
            "company reports."
        )


def assumptions_table(dcf_inputs, year_labels):
    """Make the table of the assumptions the DCF really uses, one row per forecast year: revenue
    growth, operating margin, tax rate, and D&A, capex and working capital as a share of revenue
    (working capital is positive when it brings cash in). They are the figures after the sliders
    have moved them, as text with two decimals.
    """
    years = len(year_labels)
    return pd.DataFrame(
        {
            "Revenue growth": [precise_percent(rate) for rate in dcf_inputs["growth_rates"]],
            "Operating margin": [precise_percent(rate) for rate in dcf_inputs["operating_margins"]],
            "Tax rate": [precise_percent(dcf_inputs["tax_rate"])] * years,
            "D&A % of revenue": [precise_percent(rate) for rate in dcf_inputs["da_pcts"]],
            "Capex % of revenue": [precise_percent(rate) for rate in dcf_inputs["capex_pcts"]],
            "Working capital % of revenue": [precise_percent(rate) for rate in dcf_inputs["wc_pcts"]],
        },
        index=pd.Index(year_labels, name="Year"),
    )


def points_text(shift):
    """Write a decimal shift as percentage points with a sign, for example 0.015 as +1.5 points
    and 0 as +0.0 points.
    """
    return theme.with_true_minus(f"{shift * 100 + 0.0:+.1f} points")


def draw_assumptions(company, dcf_inputs, year_labels, dcf, terminal_growth_rate, wacc_is_set_by_user, growth_shift, margin_shift):
    """Draw "What the model assumes": the table of the numbers the DCF really uses, then one line
    with the terminal growth rate, the WACC and what the sliders are changing, so a slider's
    value is never mistaken for the assumption itself.
    """
    st.subheader("What the model assumes")
    draw_table(assumptions_table(dcf_inputs, year_labels))
    if is_base_case(company):
        where_from = "Adobe's assumptions are hand-chosen (the Projection sheet in the Excel model)."
    else:
        where_from = (
            "These are a starting point worked out from the company's own last reported year, "
            "not a forecast (see the note under the title)."
        )
    whose_wacc = "the WACC you set" if wacc_is_set_by_user else "the model's own WACC"
    with reading_notes("assumptions"):
        st.caption(
            f"{where_from} After year 5, cash flow grows {precise_percent(terminal_growth_rate)} a "
            f"year for ever, discounted at {precise_percent(dcf['wacc'])} ({whose_wacc}). The sliders "
            f"are changing growth by {points_text(growth_shift)} and operating margin by "
            f"{points_text(margin_shift)} in every year; at +0.0 points the table is the base case."
        )


def provider_name(source_used):
    """Name the provider behind a source: "yahoo" and "live" are Yahoo Finance, "fmp" and "live_fmp"
    are Financial Modeling Prep. The frozen snapshot has no provider, so it gets Yahoo Finance, whose
    figures it was copied from.
    """
    return data.FMP_NAME if source_used in ("fmp", "live_fmp") else "Yahoo Finance"


def bridge_fmp_key():
    """Copy the Financial Modeling Prep key from Streamlit's private settings (the secrets file on
    this computer, or the Secrets box on Streamlit Cloud) into the environment, where data.py looks
    for it. With no key the backup is simply switched off. The key is never shown or stored here.
    """
    try:
        key = st.secrets["FMP_API_KEY"]
    except Exception:           # no secrets at all, or no such key: the backup stays off
        return
    if key:
        os.environ.setdefault("FMP_API_KEY", str(key))


def bridge_fred_key():
    """Copy the FRED key from Streamlit's private settings (the secrets file on this computer, or the Secrets box on
    Streamlit Cloud) into the environment, where data.py looks for it. With no key the macro section says it is
    not available. The key is never shown or stored here.
    """
    try:
        key = st.secrets["FRED_API_KEY"]
    except Exception:           # no secrets at all, or no such key: the macro section stays off
        return
    if key:
        os.environ.setdefault("FRED_API_KEY", str(key))


def wacc_sources(company, source_used):
    """Say, in plain words, where each input to the WACC comes from: typed in by hand, from
    Yahoo Finance today, from the frozen snapshot of the Excel model, or estimated. Returns a
    dictionary with one entry per input that has a source.
    """
    live = source_used != data.FALLBACK_SOURCE            # a provider today, not the snapshot
    provider = provider_name(source_used)
    snapshot_note = "Frozen snapshot of the Excel model"
    if company.get("cost_of_debt_is_fallback"):
        cost_of_debt = f"Estimate: the risk-free rate plus a typical credit spread ({provider} has no interest expense)"
    elif "pre_tax_cost_of_debt" in company:
        cost_of_debt = "The weighted average interest rate in the 10-K's debt notes"
    else:
        cost_of_debt = "Estimate: last year's interest expense divided by debt"
    return {
        "risk_free_rate": (
            f"Today's 10-year US Treasury yield from FRED, {day_text(company['risk_free_date'])}"
            if company.get("risk_free_is_live") else f"{data.MARKET_FIGURES_SOURCE} (typed in by hand)"
        ),
        "beta": (
            f"{provider}, 5-year monthly" if live else f"{snapshot_note} (Yahoo Finance, 5-year monthly)"
        ) + ("" if is_base_case(company) else ", adjusted: two-thirds of the observed beta plus one-third of the market's beta of 1"),
        "equity_risk_premium": f"{data.MARKET_FIGURES_SOURCE} (typed in by hand)",
        "pre_tax_cost_of_debt": cost_of_debt,
        "tax_rate": (
            "The forecast tax rate (the Projection sheet)" if is_base_case(company)
            else f"The normal US rate, because last year's was negative ({precise_percent(last_year_tax_rate(company))})"
            if tax_rate_was_replaced(company)
            else "Last year's rate: income tax divided by pre-tax income"
        ),
        "market_value_of_equity": (
            f"Today's share price from {provider}, times shares" if live
            else f"{snapshot_note}: share price times shares"
        ),
        "debt": (
            "The 10-K: current plus long-term debt" if is_base_case(company)
            else f"{provider}: current plus long-term debt"
        ),
    }


def beta_text(company, beta_used):
    """Write the beta the model uses; for a company whose beta was adjusted, add the observed one, for
    example 0.53 (observed 0.30).
    """
    if is_base_case(company):
        return f"{beta_used:.2f}"
    return f"{beta_used:.2f} (observed {company['beta']:.2f})"


def wacc_table(company, dcf_inputs, source_used):
    """Make the table that shows how the WACC is built, one step per row: the three inputs of
    the cost of equity, the cost of equity itself, the cost of debt and tax rate, the cost of
    debt after tax, the market values and weights of equity and debt, and the WACC. Returns the
    table and the breakdown behind it.
    """
    build = valuation.wacc_breakdown(
        share_price=dcf_inputs["share_price"],
        shares=dcf_inputs["shares"],
        debt=dcf_inputs["debt"],
        risk_free_rate=dcf_inputs["risk_free_rate"],
        beta=dcf_inputs["beta"],
        equity_risk_premium=dcf_inputs["equity_risk_premium"],
        pre_tax_cost_of_debt=dcf_inputs["pre_tax_cost_of_debt"],
        tax_rate=dcf_inputs["tax_rate"],
    )
    source = wacc_sources(company, source_used)
    rows = [
        ("Risk-free rate", precise_percent(dcf_inputs["risk_free_rate"]), source["risk_free_rate"]),
        ("Beta", beta_text(company, dcf_inputs["beta"]), source["beta"]),
        ("Equity risk premium", precise_percent(dcf_inputs["equity_risk_premium"]), source["equity_risk_premium"]),
        ("Cost of equity", precise_percent(build["cost_of_equity"]), "Risk-free rate + beta × equity risk premium"),
        ("Pre-tax cost of debt", precise_percent(dcf_inputs["pre_tax_cost_of_debt"]), source["pre_tax_cost_of_debt"]),
        ("Tax rate", precise_percent(dcf_inputs["tax_rate"]), source["tax_rate"]),
        ("Cost of debt after tax", precise_percent(build["after_tax_cost_of_debt"]), "Pre-tax cost of debt × (1 − tax rate)"),
        ("Market value of equity", f"${build['market_value_of_equity']:,.0f}m", source["market_value_of_equity"]),
        ("Debt", f"${build['debt']:,.0f}m", source["debt"]),
        ("Weight of equity", precise_percent(build["weight_of_equity"]), "Equity ÷ (equity + debt)"),
        ("Weight of debt", precise_percent(build["weight_of_debt"]), "Debt ÷ (equity + debt)"),
        ("WACC", precise_percent(build["wacc"]), "Weight of equity × cost of equity + weight of debt × cost of debt after tax"),
    ]
    table = pd.DataFrame(rows, columns=["Step", "Value", "Where it comes from"]).set_index("Step")
    return table, build


def wacc_explanation(build, used_wacc, wacc_is_set_by_user):
    """Say in one or two sentences why the WACC is what it is: how much of the funding is equity
    and what it costs, how much is debt and what it costs after tax, and the blend. If the reader
    set their own WACC, say that the DCF uses that instead.
    """
    if build["weight_of_debt"] == 0:
        sentence = (
            f"The company has no debt, so the WACC is just its cost of equity, "
            f"{precise_percent(build['cost_of_equity'])}."
        )
    else:
        sentence = (
            f"{build['weight_of_equity']:.0%} of the funding is equity, costing "
            f"{precise_percent(build['cost_of_equity'])}; {build['weight_of_debt']:.0%} is debt, costing "
            f"{precise_percent(build['after_tax_cost_of_debt'])} after tax. Blended, that is "
            f"{precise_percent(build['wacc'])}."
        )
    if wacc_is_set_by_user:
        sentence += (
            f" You have set the WACC to {precise_percent(used_wacc)}, so the DCF uses that instead "
            f"of the model's own {precise_percent(build['wacc'])}."
        )
    return sentence


def draw_wacc_build(company, dcf_inputs, source_used, dcf, wacc_is_set_by_user):
    """Draw "How the WACC is built": the table of steps with where each input comes from, and
    a sentence that says why the number is what it is.
    """
    st.subheader("How the WACC is built")
    table, build = wacc_table(company, dcf_inputs, source_used)
    draw_table(table, key=theme.WACC_TABLE_KEY)
    st.caption(wacc_explanation(build, dcf["wacc"], wacc_is_set_by_user))


def millions_text(amount):
    """Write a dollar amount in millions, for example $23,769m or −$281m, or a dash if missing."""
    if amount is None:
        return "–"
    return f"{theme.MINUS}${-amount:,.0f}m" if amount < 0 else f"${amount:,.0f}m"


def rate_text(rate):
    """Write a rate as a percentage, or a dash if it is missing."""
    return "–" if rate is None else percent(rate)


def multiple_or_dash(multiple):
    """Write a multiple with two decimals such as 1.38x, or a dash if it is missing."""
    return "–" if multiple is None else f"{multiple:.2f}x"


def history_ratios(history):
    """Work out the history's year-by-year ratios: revenue growth, operating margin, free cash
    flow margin, cash conversion (free cash flow over net income) and the yearly change in diluted
    shares (a fall means buybacks).
    """
    return {
        "revenue_growth": valuation.yearly_growth(history["revenue"]),
        "operating_margin": valuation.ratios_by_year(history["operating_income"], history["revenue"]),
        "fcf_margin": valuation.ratios_by_year(history["free_cash_flow"], history["revenue"]),
        "cash_conversion": [
            valuation.cash_conversion(free_cash_flow, net_income)
            for free_cash_flow, net_income in zip(history["free_cash_flow"], history["net_income"])
        ],
        "share_change": valuation.yearly_growth(history["diluted_shares"]),
    }


def history_table(history):
    """Make the history table, one column per year (oldest first) and one row per figure, as
    text, with a dash where Yahoo has no figure.
    """
    ratios = history_ratios(history)
    rows = {
        "Revenue": [millions_text(amount) for amount in history["revenue"]],
        "Revenue growth": [rate_text(rate) for rate in ratios["revenue_growth"]],
        "Operating income": [millions_text(amount) for amount in history["operating_income"]],
        "Operating margin": [rate_text(rate) for rate in ratios["operating_margin"]],
        "Net income": [millions_text(amount) for amount in history["net_income"]],
        "Free cash flow (reported)": [millions_text(amount) for amount in history["free_cash_flow"]],
        "Free cash flow margin": [rate_text(rate) for rate in ratios["fcf_margin"]],
        "Cash conversion (FCF ÷ net income)": [multiple_or_dash(value) for value in ratios["cash_conversion"]],
        "Diluted average shares": [
            "–" if shares is None else f"{shares:,.0f}m" for shares in history["diluted_shares"]
        ],
        "Yearly change in shares": [rate_text(rate) for rate in ratios["share_change"]],
    }
    return pd.DataFrame(rows, index=pd.Index(history["years"], name="Year")).T


def history_chart_data(history):
    """Make the data for the two history charts: revenue and reported free cash flow in $
    millions, and the operating margin and free cash flow margin ("FCF margin", short so the
    chart's legend fits) in percent of revenue. Years with no figure are left blank.
    """
    ratios = history_ratios(history)
    index = pd.Index(history["years"], name="Year")
    amounts = pd.DataFrame(
        {"Revenue": history["revenue"], "Free cash flow (reported)": history["free_cash_flow"]},
        index=index, dtype=float,
    )
    margins = pd.DataFrame(
        {
            "Operating margin": [None if rate is None else rate * 100 for rate in ratios["operating_margin"]],
            "FCF margin": [None if rate is None else rate * 100 for rate in ratios["fcf_margin"]],
        },
        index=index, dtype=float,
    )
    return amounts, margins


def first_and_last(values):
    """Find the positions of the first and the last figure that is not missing in a list, as (first, last), or None when
    fewer than two figures exist (there is no movement to describe).
    """
    positions = [position for position, value in enumerate(values) if value is not None and value == value]
    return (positions[0], positions[-1]) if len(positions) >= 2 else None


def history_amounts_headline(history):
    """Say in one sentence how revenue and reported free cash flow moved over the years in the history, from the first
    year that has a figure to the last. None when neither has two years of figures.
    """
    parts = []
    for name, key in (("Revenue", "revenue"), ("reported free cash flow", "free_cash_flow")):
        span = first_and_last(history[key])
        if span:
            first, last = span
            parts.append(
                f"{name} went from {theme.money_short(history[key][first])} in {history['years'][first]} to "
                f"{theme.money_short(history[key][last])} in {history['years'][last]}"
            )
    return "; ".join(parts) + "." if parts else None


def history_margins_headline(history):
    """Say in one sentence how the operating margin and the free cash flow margin moved over the history. None when
    neither has two years of figures.
    """
    ratios = history_ratios(history)
    parts = []
    for name, key in (("The operating margin", "operating_margin"), ("the free cash flow margin", "fcf_margin")):
        span = first_and_last(ratios[key])
        if span:
            first, last = span
            parts.append(
                f"{name} went from {ratios[key][first]:.1%} in {history['years'][first]} to {ratios[key][last]:.1%} "
                f"in {history['years'][last]}"
            )
    return "; ".join(parts) + "." if parts else None


def history_amounts_figure(history):
    """Draw revenue (the accent colour) and reported free cash flow (brown) for each year of the history, as bars in
    $ billions, in the same style as the other charts.
    """
    amounts, _margins = history_chart_data(history)
    figure = go.Figure([
        go.Bar(
            x=list(amounts.index), y=[None if value != value else value / 1000 for value in amounts[column]],
            name=name, marker={"color": colour},
            hovertemplate=f"<b>%{{x}}</b><br>{name} $%{{y:,.1f}} billion<extra></extra>",
        )
        for column, name, colour in (
            ("Revenue", "Revenue", theme.ACCENT), ("Free cash flow (reported)", "Reported free cash flow", theme.COMPARISON),
        )
    ])
    figure.update_yaxes(tickprefix="$", ticksuffix="B", tickformat=",.0f", gridcolor=theme.BORDER, zeroline=False)
    figure.update_xaxes(showgrid=False)
    theme.style_figure(figure, height=300)
    figure.update_layout(
        barmode="group", showlegend=True, legend={"orientation": "h", "y": 1.15, "x": 0},
        margin={"l": 0, "r": 0, "t": 30, "b": 0},
    )
    return figure


def history_margins_figure(history):
    """Draw the operating margin (the accent colour) and the free cash flow margin (grey) for each year of the history
    as lines, in percent of revenue, in the same style as the other charts.
    """
    _amounts, margins = history_chart_data(history)
    figure = go.Figure([
        go.Scatter(
            x=list(margins.index), y=[None if value != value else value for value in margins[column]],
            name=name, mode="lines+markers", line={"color": colour, "width": 2}, marker={"size": 6},
            hovertemplate=f"<b>%{{x}}</b><br>{name} %{{y:.1f}}%<extra></extra>",
        )
        for column, name, colour in (
            ("Operating margin", "Operating margin", theme.ACCENT), ("FCF margin", "Free cash flow margin", theme.GREY),
        )
    ])
    figure.update_yaxes(ticksuffix="%", gridcolor=theme.BORDER, zeroline=False, rangemode="tozero")
    figure.update_xaxes(showgrid=False)
    theme.style_figure(figure, height=300)
    figure.update_layout(
        showlegend=True, legend={"orientation": "h", "y": 1.15, "x": 0}, margin={"l": 0, "r": 0, "t": 30, "b": 0},
    )
    return figure


def free_cash_flow_note(history, overview, company_name):
    """Explain how the history's free cash flow (as the company reports it: cash from operations
    minus capital spending) differs from the model's, which is built from operating profit after
    tax, depreciation, capex and working capital. When both are known for the last year, quote them.
    """
    note = (
        "Free cash flow here is as the company reports it: cash from operations minus capital "
        "spending. The model builds its own free cash flow differently (operating profit after tax, "
        "plus depreciation, minus capex, plus working capital), so the two differ"
    )
    reported = history["free_cash_flow"][-1]
    modelled = overview["free_cash_flow"]
    if reported is not None and modelled is not None:
        note += f": for {company_name}'s last year, {millions_text(reported)} reported against {millions_text(modelled)} in the model."
    else:
        note += "."
    return note


def free_cash_flow_warning(history, overview, company_name):
    """Warn, in plain words, when the model's free cash flow for the last year is much higher than the
    one the company reports, which means something between operating profit and cash (interest, one-off
    costs) is left out of the model. Returns the sentence, or None when there is nothing to warn about.
    """
    check = valuation.free_cash_flow_check(
        overview["free_cash_flow"], history["free_cash_flow"][-1], assumptions.FREE_CASH_FLOW_RATIO_WARNING
    )
    if check is None or not check["warn"]:
        return None
    return (
        f"The model's free cash flow for {company_name}'s last year ({millions_text(overview['free_cash_flow'])}) "
        f"is {(check['ratio'] - 1) * 100:.0f}% above what the company reports "
        f"({millions_text(history['free_cash_flow'][-1])}). The model starts from operating profit, so costs "
        "between operating profit and cash (interest, one-off charges) may be missing from it: check them in the "
        "company's annual report before trusting the price, or adjust operating income under One-off items, beside the sliders."
    )


def margin_history_warnings(history, company_name):
    """Warn, in plain words, when the latest year's operating margin may not be typical: when it
    is far above or below the average of the earlier years (it may be a peak or a bottom), and when
    the margin has swung widely between its best and worst year (one year is a poor guide).
    Returns a list of sentences, empty when the margin looks steady or there are too few years.
    """
    margins = history_ratios(history)["operating_margin"]
    check = valuation.history_check(margins, assumptions.MINIMUM_HISTORY_YEARS)
    if check is None:
        return []
    warnings = []
    if abs(check["gap"]) > assumptions.MARGIN_VS_HISTORY_WARNING:
        above = check["gap"] > 0
        warnings.append(
            f"{company_name}'s latest operating margin ({percent(check['latest'])}) is "
            f"{abs(check['gap']) * 100:.1f} points {'above' if above else 'below'} the average of the earlier "
            f"years ({percent(check['earlier_average'])}). This year may be a {'peak' if above else 'bottom'}, so a "
            f"forecast that holds it flat could be too {'optimistic' if above else 'pessimistic'}."
        )
    if check["swing"] > assumptions.MARGIN_SWING_WARNING:
        known = [margin for margin in margins if margin is not None]
        warnings.append(
            f"The operating margin has swung by {check['swing'] * 100:.1f} points between its best "
            f"({percent(max(known))}) and worst ({percent(min(known))}) year. One year is a poor guide "
            "for a margin like that, so look at the whole history."
        )
    return warnings


def draw_history(history, error, overview, company_name):
    """Draw the history: yellow warnings when the latest margin may be a peak or a bottom, a table of
    the last few years (as many as Yahoo has, 4 or 5), two small charts, and notes on what the free
    cash flow and the share count mean here. If the history
    could not be fetched, say why instead; the rest of the page does not depend on it.
    """
    st.subheader("History")
    if history is None:
        st.caption(f"The history is not available right now. {error}")
        return
    for warning in margin_history_warnings(history, company_name):
        st.warning(warning)
    cash_flow_warning = free_cash_flow_warning(history, overview, company_name)
    if cash_flow_warning:
        # Each dollar sign is escaped with a backslash, because Streamlit reads text between two
        # unescaped dollar signs as a maths formula.
        st.warning(cash_flow_warning.replace("$", "\\$"))
    draw_table(history_table(history))
    amounts_column, margins_column = st.columns(2)
    amounts_headline = history_amounts_headline(history)
    if amounts_headline:
        amounts_column.markdown(
            f"**{dollar_text_for_markdown(amounts_headline)}**", help=explanations.help_text("history_amounts")
        )
    amounts_column.plotly_chart(history_amounts_figure(history), width="stretch", config=CHART_CONFIG)
    margins_headline = history_margins_headline(history)
    if margins_headline:
        margins_column.markdown(f"**{margins_headline}**", help=explanations.help_text("history_margins"))
    margins_column.plotly_chart(history_margins_figure(history), width="stretch", config=CHART_CONFIG)
    # Each dollar sign is escaped with a backslash, because Streamlit reads text between two
    # unescaped dollar signs as a maths formula.
    st.caption(free_cash_flow_note(history, overview, company_name).replace("$", "\\$"))
    with reading_notes("history"):
        st.caption(
            f"{provider_name(history.get('source'))} gives {len(history['years'])} years of figures for this company. Shares are "
            "the diluted average over each year, not the number outstanding that the valuation uses; a "
            "fall means buybacks. One year can be a peak or a bottom, so look at the direction, not "
            "just the latest number."
        )


def terminal_value_cautions(dcf, terminal_growth_rate):
    """List, in plain words, the reasons to treat this price with care because it rests mostly
    on the far future. Returns an empty list when neither check (the terminal value's share of
    enterprise value, and the gap between WACC and terminal growth) is past its limit.
    """
    cautions = []
    share = valuation.terminal_value_share(dcf["pv_of_terminal_value"], dcf["enterprise_value"])
    if share > assumptions.TERMINAL_VALUE_SHARE_WARNING:
        cautions.append(
            f"{share:.0%} of this company's value comes from after year 5 (the terminal value). "
            "The more a price rests on the far future, the less it can be trusted: small changes "
            "in the assumptions can move it a lot."
        )
    gap = valuation.wacc_minus_terminal_growth(dcf["wacc"], terminal_growth_rate)
    if gap < assumptions.WACC_GAP_WARNING:
        cautions.append(
            f"The WACC ({precise_percent(dcf['wacc'])}) is only {gap * 100:.1f} points above "
            f"terminal growth ({precise_percent(terminal_growth_rate)}). With a gap this small the "
            "terminal value is very sensitive: a small change in either number can move the price a lot."
        )
    return cautions


def football_field_headline(company_name, above, total):
    """Say in one sentence what the football field shows: how many valuation methods have a middle value above
    today's market price. None when there are no methods to count.
    """
    if total == 0:
        return None
    if above == total:
        return f"{company_name} trades below the middle value of every valuation method."
    if above == 0:
        return f"{company_name} trades above the middle value of every valuation method."
    return f"{company_name} trades below the middle value of {above} of {total} valuation methods."


def football_field_figure(rows, share_price):
    """Draw the football field: one horizontal bar per method from its low to its high price (the DCF in the
    accent colour, everything else in brown), a tick at its middle value, and a dashed vertical line at today's
    market price. `rows` is what valuation.football_field gives, top row first.
    """
    figure = go.Figure(go.Bar(
        y=[row["label"] for row in rows],
        x=[row["high"] - row["low"] for row in rows],
        base=[row["low"] for row in rows],
        orientation="h",
        width=0.5,
        marker={"color": [theme.ACCENT if row["kind"] == "dcf" else theme.COMPARISON for row in rows]},
        customdata=[[row["low"], row["high"]] for row in rows],
        hovertemplate="<b>%{y}</b><br>$%{customdata[0]:,.2f} to $%{customdata[1]:,.2f}<extra></extra>",
    ))
    with_middle = [row for row in rows if row["middle"] is not None]
    figure.add_trace(go.Scatter(
        x=[row["middle"] for row in with_middle],
        y=[row["label"] for row in with_middle],
        mode="markers",
        marker={"symbol": "line-ns", "size": 24, "color": theme.TEXT, "line": {"width": 3, "color": theme.TEXT}},
        hovertemplate="<b>%{y}</b><br>Middle value $%{x:,.2f}<extra></extra>",
    ))
    figure.add_vline(x=share_price, line={"color": theme.TEXT, "width": 2, "dash": "dash"})
    figure.add_annotation(
        x=share_price, y=1, yref="paper", yanchor="bottom", showarrow=False,
        text=f"Market price ${share_price:,.2f}", font={"color": theme.TEXT, "size": 12},
    )
    everything = [row["low"] for row in rows] + [row["high"] for row in rows] + [share_price]
    figure.update_xaxes(
        range=[min(everything) * 0.9, max(everything) * 1.05], tickprefix="$", tickformat=",.0f",
        gridcolor=theme.BORDER, zeroline=False,
    )
    figure.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    theme.style_figure(figure, height=90 + 48 * len(rows))
    figure.update_layout(margin={"l": 0, "r": 10, "t": 30, "b": 0})
    return figure


def draw_football_field(company, dcf, multiples, dcf_inputs, base_wacc, prices, analysts=None):
    """Draw the football field, the main chart: every way the page has of valuing the company, as a price range,
    against today's market price, with a sentence that says what it shows. The DCF bar covers the prices that have an
    answer when the WACC is moved 1 point either way and the terminal growth runs from 1.5% to 3.5% (the workbook's table, not
    the wider heatmap); each multiples bar covers the middle half of the peers. The 52-week range is included when the price history is there,
    and the analysts' price targets when `analysts` (see data.get_analyst_view) has them.
    """
    try:
        table = valuation.sensitivity_table(
            dcf_inputs, base_wacc, assumptions.FOOTBALL_FIELD_WACC_OFFSETS, assumptions.HEATMAP_TERMINAL_GROWTH_RATES,
            blank_impossible=True,
        )
        dcf_range = valuation.table_range(table["prices"])
    except ValueError:
        dcf_range = None            # no combination in the table has an answer at all: see draw_heatmap
    trading = None if prices is None else valuation.trading_range([price["close"] for price in prices])
    targets = None if analysts is None or analysts["targets"] is None else (
        analysts["targets"]["low"], analysts["targets"]["mean"], analysts["targets"]["high"]
    )
    rows = valuation.football_field(dcf_range, dcf["implied_share_price"], multiples, trading, targets)
    if not rows:
        return
    st.subheader("Where the price sits")
    if dcf_range is None:
        st.caption(
            f"The DCF bar is left out: this company's WACC ({percent(base_wacc)}) is too close to the terminal growth "
            "rates in the table for any of its prices to be worked out."
        )
    headline = football_field_headline(company["company_name"], *valuation.methods_above_price(rows, company["share_price"]))
    if headline:
        st.markdown(f"**{headline}**", help=explanations.help_text("football_field"))
    st.plotly_chart(football_field_figure(rows, company["share_price"]), width="stretch", config=CHART_CONFIG)
    with reading_notes("football_field"):
        st.caption(
            "Each bar is a way of valuing the company: the gold bar is the DCF with the WACC a point either way and terminal growth from 1.5% to 3.5%, "
            "the brown bars cover the middle half of the peers' multiples (25th to 75th percentile), the analysts' price "
            "targets (when Yahoo Finance has them) and the share's own 52-week range. The cream tick is the middle value "
            "(the mean, for the analysts), and the dashed line is today's market price."
        )


def analyst_headline(company_name, view, share_price, dcf_price):
    """Say in one sentence what analysts think: the consensus rating and how many analysts, and where their mean price
    target is against today's market price, then (when there is a DCF) whether the model's DCF value is above or below
    that target. Gives only the parts Yahoo has, and None when it has neither a rating nor a target.
    """
    parts = []
    rating = view["rating"]
    if rating:
        count = f" ({view['analysts']} analysts)" if view["analysts"] else ""
        parts.append(f"Analysts rate {company_name} {rating.lower()}{count}")
    targets = view["targets"]
    if targets:
        gap = targets["mean"] / share_price - 1
        direction = "above" if gap > 0 else "below" if gap < 0 else "the same as"
        target = f"their mean price target of {dollars(targets['mean'])} is {percent(abs(gap)) + ' ' if gap else ''}{direction} today's price"
        parts.append(target if parts else f"Analysts' mean price target for {company_name} of {dollars(targets['mean'])} is {percent(abs(gap)) + ' ' if gap else ''}{direction} today's price")
    if not parts:
        return None
    sentence = "; ".join(parts) + "."
    if targets and dcf_price is not None:
        relation = "above" if dcf_price > targets["mean"] else "below" if dcf_price < targets["mean"] else "the same as"
        sentence += f" The model's DCF value of {dollars(dcf_price)} is {relation} that target."
    return sentence


def target_range_text(low, high):
    """Write the range of the analysts' price targets in the space of a small card, for example "$140 – 373": whole dollars
    from 100 up, cents below that (where they matter), and one dollar sign only, because Streamlit reads text between
    two unescaped dollar signs as a maths formula.
    """
    decimals = 0 if high >= 100 else 2
    return f"{dollars(low) if decimals else f'${low:,.0f}'} – {high:,.{decimals}f}"


def analyst_split_figure(counts):
    """Draw how analysts split as one stacked bar: Buy (strong buy and buy, green), Hold (grey) and Sell (sell and strong sell,
    red), each labelled with its number. Hovering gives the exact counts of the five ratings. The words and the
    numbers say it too, so the colours are never the only signal.
    """
    groups = [
        ("Buy", counts["strong_buy"] + counts["buy"], theme.UP, f"Strong buy {counts['strong_buy']}, buy {counts['buy']}"),
        ("Hold", counts["hold"], theme.GREY, f"Hold {counts['hold']}"),
        ("Sell", counts["sell"] + counts["strong_sell"], theme.DOWN, f"Sell {counts['sell']}, strong sell {counts['strong_sell']}"),
    ]
    figure = go.Figure([
        go.Bar(
            y=[""], x=[number], name=name, orientation="h", marker={"color": colour},
            text=[f"{name} {number}" if number else ""], textposition="inside", insidetextanchor="middle",
            textfont={"color": theme.CANVAS},
            hovertemplate=f"<b>{name}</b><br>{detail}<extra></extra>",
        )
        for name, number, colour, detail in groups
    ])
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    theme.style_figure(figure, height=90)
    figure.update_layout(barmode="stack", showlegend=False, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    return figure


def draw_analyst_view(company, analysts, dcf_price):
    """Draw "Analyst view": what other analysts say, from Yahoo Finance: the consensus rating, the mean price target against
    today's price, the range of targets, how the analysts split, and a sentence that says it, with the model's DCF value
    beside it. A company with no coverage, or a search that could not be made, says so. These are other people's opinions,
    and the section says that.
    """
    st.subheader("Analyst view")
    if analysts is None:
        st.caption("The analysts' view is not available right now.")
        return
    if not data.has_analyst_coverage(analysts):
        st.caption(f"There is no analyst coverage of {company['company_name']} on Yahoo Finance.")
        return
    rating_column, target_column, range_column = st.columns(3)
    rating_column.metric(
        "Consensus rating", analysts["rating"] or "No consensus",
        delta=f"{analysts['analysts']} analysts" if analysts["analysts"] else None, delta_color="off", delta_arrow="off",
        help=explanations.help_text("analyst_rating"),
    )
    targets = analysts["targets"]
    if targets:
        target_column.metric(
            "Mean price target", dollars(targets["mean"]),
            delta=theme.change_text(targets["mean"] / company["share_price"] - 1),
            delta_color="off", delta_arrow="off", help=explanations.help_text("analyst_target"),
        )
        range_column.metric(
            "Target range", target_range_text(targets["low"], targets["high"]),
            delta="lowest to highest", delta_color="off", delta_arrow="off", help=explanations.help_text("analyst_range"),
        )
    else:
        target_column.metric("Mean price target", NOT_AVAILABLE, help=explanations.help_text("analyst_target"))
    headline = analyst_headline(company["company_name"], analysts, company["share_price"], dcf_price)
    if headline:
        st.markdown(f"**{dollar_text_for_markdown(headline)}**", help=explanations.help_text("analyst_split"))
    if analysts["counts"]:
        st.plotly_chart(analyst_split_figure(analysts["counts"]), width="stretch", config=CHART_CONFIG)
    with reading_notes("analysts"):
        st.caption(
            "Other analysts' opinions, from Yahoo Finance, not this app's advice. Price targets are set for about a year ahead "
            "and tend to run optimistic, so they are a comparison for the model, not a prediction."
        )


def waterfall_headline(dcf):
    """Say in one sentence how the enterprise value becomes a price per share: the net debt (or net cash) comes
    off (or on), and what is left is split across the shares.
    """
    net_debt = dcf["net_debt"]
    sentence = (
        f"{theme.money_short(dcf['enterprise_value'])} of enterprise value "
        f"{'plus' if net_debt < 0 else 'less'} {theme.money_short(abs(net_debt))} of net "
        f"{'cash' if net_debt < 0 else 'debt'} is {theme.money_short(dcf['equity_value'])} of equity, "
        f"or {dollars(dcf['implied_share_price'])} a share."
    )
    return sentence


def valuation_waterfall(dcf):
    """Draw how the DCF value is built: the present value of the five forecast years and of the terminal value
    add up to the enterprise value, net cash adds (or net debt takes away) and what is left is the equity value.
    Bars are in $ billions; the gold steps add, the red one subtracts, and the light sand bars are the totals.
    """
    net_debt = dcf["net_debt"]
    steps = [
        ("Years 1-5", dcf["pv_of_forecast"], "relative"),
        ("Terminal value", dcf["pv_of_terminal_value"], "relative"),
        ("Enterprise value", dcf["enterprise_value"], "total"),
        ("Net cash" if net_debt < 0 else "Net debt", -net_debt, "relative"),
        ("Equity value", dcf["equity_value"], "total"),
    ]
    figure = go.Figure(go.Waterfall(
        x=[label for label, _amount, _kind in steps],
        y=[amount / 1000 for _label, amount, _kind in steps],
        measure=[kind for _label, _amount, kind in steps],
        text=[theme.money_short(amount) for _label, amount, _kind in steps],
        textposition="outside",
        textfont={"color": theme.TEXT},
        increasing={"marker": {"color": theme.ACCENT}},
        decreasing={"marker": {"color": theme.DOWN}},
        totals={"marker": {"color": theme.SAND}},
        connector={"line": {"color": theme.GREY, "width": 1}},
        hovertemplate="<b>%{x}</b><br>$%{y:,.1f} billion<extra></extra>",
    ))
    figure.update_yaxes(tickprefix="$", ticksuffix="B", tickformat=",.0f", gridcolor=theme.BORDER, zeroline=False)
    figure.update_xaxes(showgrid=False)
    theme.style_figure(figure, height=320)
    figure.update_layout(margin={"l": 0, "r": 0, "t": 20, "b": 0})
    return figure


def cash_flow_headline(dcf, history):
    """Say in one sentence where free cash flow is forecast to go: from the last year the company reported (when
    the history is there and has it) to the fifth forecast year.
    """
    last_reported = None if history is None else history["free_cash_flow"][-1]
    final = theme.money_short(dcf["free_cash_flows"][-1])
    if last_reported is None:
        return f"Free cash flow is forecast to reach {final} in year 5."
    direction = "grow" if dcf["free_cash_flows"][-1] > last_reported else "fall"
    return (
        f"Free cash flow is forecast to {direction} from {theme.money_short(last_reported)} "
        f"(last reported year) to {final} in year 5."
    )


def cash_flow_figure(year_labels, dcf, operating_margins, history):
    """Draw free cash flow year by year: the company's reported figures in brown, the model's forecast in the
    accent colour (bars, in $ billions), and the operating margin as a line on the right-hand axis. With no
    history only the forecast is drawn.
    """
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    history_labels = [] if history is None else list(history["years"])
    if history is not None:
        figure.add_trace(go.Bar(
            x=history_labels,
            y=[None if value is None else value / 1000 for value in history["free_cash_flow"]],
            name="Reported free cash flow", marker={"color": theme.COMPARISON},
            hovertemplate="<b>%{x}</b><br>Reported free cash flow $%{y:,.1f} billion<extra></extra>",
        ), secondary_y=False)
    figure.add_trace(go.Bar(
        x=list(year_labels), y=[value / 1000 for value in dcf["free_cash_flows"]],
        name="Forecast free cash flow", marker={"color": theme.ACCENT},
        hovertemplate="<b>%{x}</b><br>Forecast free cash flow $%{y:,.1f} billion<extra></extra>",
    ), secondary_y=False)
    margins = ([] if history is None else history_ratios(history)["operating_margin"]) + list(operating_margins)
    figure.add_trace(go.Scatter(
        x=history_labels + list(year_labels), y=margins, mode="lines+markers", name="Operating margin",
        line={"color": theme.TEXT, "width": 2}, marker={"size": 6},
        hovertemplate="<b>%{x}</b><br>Operating margin %{y:.1%}<extra></extra>",
    ), secondary_y=True)
    figure.update_yaxes(tickprefix="$", ticksuffix="B", tickformat=",.0f", gridcolor=theme.BORDER, zeroline=False,
                        secondary_y=False)
    figure.update_yaxes(tickformat=".1%", showgrid=False, secondary_y=True)     # margins sit close together: 37.0%, 37.5%, never 37%, 37%
    figure.update_xaxes(showgrid=False)
    theme.style_figure(figure, height=320)
    figure.update_layout(
        showlegend=True, legend={"orientation": "h", "y": 1.15, "x": 0}, margin={"l": 0, "r": 0, "t": 30, "b": 0},
        barmode="group",
    )
    return figure


def terminal_value_donut(dcf):
    """Draw how much of the enterprise value comes from the terminal value (everything after year 5) against the
    five forecast years: a ring with the percentage in the middle. The terminal slice turns red above
    TERMINAL_VALUE_SHARE_WARNING, the same limit the caution under the charts uses.
    """
    share = valuation.terminal_value_share(dcf["pv_of_terminal_value"], dcf["enterprise_value"])
    figure = go.Figure(go.Pie(
        labels=["Years 1-5", "Terminal value"],
        values=[dcf["pv_of_forecast"], dcf["pv_of_terminal_value"]],
        hole=0.65,
        sort=False,
        direction="clockwise",
        marker={"colors": [theme.COMPARISON, theme.DOWN if share > assumptions.TERMINAL_VALUE_SHARE_WARNING else theme.ACCENT],
                "line": {"color": theme.CANVAS, "width": 2}},
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f} million (%{percent})<extra></extra>",
    ))
    figure.add_annotation(
        text=f"<b>{share:.0%}</b><br>terminal value", x=0.5, y=0.5, showarrow=False,
        font={"color": theme.TEXT, "size": 16},
    )
    theme.style_figure(figure, height=320)
    figure.update_layout(showlegend=True, legend={"orientation": "h", "y": -0.05, "x": 0.1})
    return figure


def draw_charts(dcf, year_labels, terminal_growth_rate, operating_margins, history):
    """Draw the charts behind the headline price, each under a sentence that says what it shows: how the DCF value
    is built (a waterfall from the five forecast years and the terminal value to the equity value), how free cash
    flow is forecast to move from the reported years, and how much of the value is the terminal value, with a
    caution when the price rests mostly on the far future.
    """
    st.subheader("Behind the number")
    st.markdown(f"**{dollar_text_for_markdown(waterfall_headline(dcf))}**", help=explanations.help_text("waterfall"))
    st.plotly_chart(valuation_waterfall(dcf), width="stretch", config=CHART_CONFIG)
    cash_flow_column, donut_column = st.columns([3, 2])
    cash_flow_column.markdown(
        f"**{dollar_text_for_markdown(cash_flow_headline(dcf, history))}**", help=explanations.help_text("cash_flow_chart")
    )
    cash_flow_column.plotly_chart(
        cash_flow_figure(year_labels, dcf, operating_margins, history), width="stretch", config=CHART_CONFIG
    )
    share = valuation.terminal_value_share(dcf["pv_of_terminal_value"], dcf["enterprise_value"])
    donut_column.markdown(
        f"**{share:.0%} of the value comes from after year 5.**", help=explanations.help_text("terminal_value_ring")
    )
    donut_column.plotly_chart(terminal_value_donut(dcf), width="stretch", config=CHART_CONFIG)
    with reading_notes("forecast_charts"):
        st.caption(
            "Brown bars are free cash flow as the company reports it; gold bars are the model's forecast, which starts from "
            "operating profit, so the two are not built the same way."
        )
    # Each dollar sign is escaped with a backslash, because Streamlit reads text between two
    # unescaped dollar signs as a maths formula.
    st.caption(
        f"Enterprise value of \\${dcf['enterprise_value']:,.0f} million is the five forecast "
        f"years (\\${dcf['pv_of_forecast']:,.0f} million) plus everything after year 5, the "
        f"terminal value (\\${dcf['pv_of_terminal_value']:,.0f} million), both discounted to today. "
        f"The terminal value is "
        f"{valuation.terminal_value_share(dcf['pv_of_terminal_value'], dcf['enterprise_value']):.0%} "
        "of the enterprise value."
    )
    for caution in terminal_value_cautions(dcf, terminal_growth_rate):
        st.warning(caution)


def draw_sensitivity_numbers(prices_frame, share_price, base_cell):
    """Under a sensitivity heatmap, a closed box with the same prices as a plain table, so the exact figures are
    always there to read or copy. Cells are tinted like the heatmap and the base case is in the medium weight; a blank cell
    (no answer) shows a dash.
    """
    base_row, base_column = base_cell

    def style_cells(values):
        """Colour every cell and put the base case in the medium weight (the page uses no bold)."""
        styles = values.map(lambda price: "" if pd.isna(price) else tint(price, share_price))
        styles.iloc[base_row, base_column] += f"; font-weight: {theme.WEIGHT_MEDIUM}"
        return styles

    with st.expander("Show the numbers as a table"):
        draw_table(prices_frame.style.apply(style_cells, axis=None).format(dollars, na_rep="–"))


def draw_heatmap(company, dcf_inputs, base_wacc):
    """Draw the sensitivity heatmap: the implied share price (and its upside) at different WACCs (down the
    side) and terminal growth rates (along the top), coloured against the market price, with a dashed line where
    the model equals it. A pairing whose growth rate is not below its WACC has no answer and stays blank.
    """
    st.subheader("Sensitivity: price at different WACC and terminal growth")
    try:
        table = valuation.sensitivity_table(
            dcf_inputs,
            base_wacc,
            assumptions.HEATMAP_WACC_OFFSETS,
            assumptions.HEATMAP_TERMINAL_GROWTH_RATES,
            blank_impossible=True,
        )
    except ValueError:
        # A very low WACC can sit below every terminal growth rate in the table, where the formula has no
        # answer anywhere. The headline DCF is fine.
        st.caption(
            f"This table cannot be drawn: this company's WACC ({percent(base_wacc)}) is too close to "
            "the terminal growth rates in the table for the formula to give an answer."
        )
        return
    row_labels = [precise_percent(rate) for rate in table["wacc_rates"]]
    column_labels = [percent(rate) for rate in table["terminal_growth_rates"]]
    base_cell = (
        assumptions.HEATMAP_WACC_OFFSETS.index(0.0),
        assumptions.HEATMAP_TERMINAL_GROWTH_RATES.index(assumptions.TERMINAL_GROWTH_RATE),
    )
    st.markdown(
        f"**{sensitivity_headline(table['prices'], company['share_price'])}**", help=explanations.help_text("heatmap_wacc")
    )
    with st.container(key=f"{HEATMAP_KEY_PREFIX}wacc"):
        st.plotly_chart(
            sensitivity_heatmap(
                row_labels, column_labels, table["prices"], company["share_price"], base_cell, "WACC", "Terminal growth"
            ),
            width="stretch", config=CHART_CONFIG,
        )
    prices = pd.DataFrame(
        table["prices"],
        index=pd.Index(row_labels, name="WACC"),
        columns=pd.Index(column_labels, name="Terminal growth"),
    )
    draw_sensitivity_numbers(prices, company["share_price"], base_cell)
    blank_note = (
        " A blank cell has no answer: its growth rate is at or above its WACC."
        if any(price is None for row in table["prices"] for price in row) else ""
    )
    with reading_notes("heatmap_wacc"):
        st.caption(
            f"Each cell shows the price and how far it is above (▲, green) or below (▼, red) today's market price of "
            f"{dollars(company['share_price'])}. The dashed line runs where the model equals the market price, and the gold frame is "
            "the base case. The growth and margin sliders move the whole table.".replace("$", "\\$") + blank_note
        )


def shift_label(average, shift):
    """Label one row or column of the margin and growth table: the average the shift gives, with two
    decimals like the "What the model assumes" table, and the shift beside it, or "base" when there
    is no shift (for example 27.65% (-10 pts), or 37.65% (base)).
    """
    if shift == 0:
        return f"{precise_percent(average)} (base)"
    return f"{precise_percent(average)} ({theme.with_true_minus(f'{shift * 100:+.0f}')} pts)"


def draw_margin_growth_table(company, dcf_inputs, dcf, terminal_growth_rate, wacc_override):
    """Draw the second sensitivity table: the implied share price at different operating margins
    (down the side) and revenue growth (along the top), coloured against the market price like
    the WACC table. It uses the WACC the DCF uses, so the middle cell is the DCF price above.
    """
    st.subheader("Sensitivity: price at different margins and growth")
    table = valuation.margin_growth_table(
        dcf_inputs,
        terminal_growth_rate,
        wacc_override,
        assumptions.MARGIN_GROWTH_TABLE_MARGIN_SHIFTS,
        assumptions.MARGIN_GROWTH_TABLE_GROWTH_SHIFTS,
    )
    row_labels = [shift_label(average, shift) for average, shift in zip(table["margin_averages"], table["margin_shifts"])]
    column_labels = [shift_label(average, shift) for average, shift in zip(table["growth_averages"], table["growth_shifts"])]
    base_cell = (
        assumptions.MARGIN_GROWTH_TABLE_MARGIN_SHIFTS.index(0.0),
        assumptions.MARGIN_GROWTH_TABLE_GROWTH_SHIFTS.index(0.0),
    )
    st.markdown(
        f"**{sensitivity_headline(table['prices'], company['share_price'])}**", help=explanations.help_text("heatmap_margin")
    )
    with st.container(key=f"{HEATMAP_KEY_PREFIX}margin"):
        st.plotly_chart(
            sensitivity_heatmap(
                row_labels, column_labels, table["prices"], company["share_price"], base_cell,
                "Average operating margin", "Average revenue growth",
            ),
            width="stretch", config=CHART_CONFIG,
        )
    prices = pd.DataFrame(
        table["prices"],
        index=pd.Index(row_labels, name="Average operating margin"),
        columns=pd.Index(column_labels, name="Average revenue growth"),
    )
    draw_sensitivity_numbers(prices, company["share_price"], base_cell)
    # Each dollar sign is escaped with a backslash, because Streamlit reads text between two
    # unescaped dollar signs as a maths formula.
    with reading_notes("heatmap_margin"):
        st.caption(
            (
                f"Each cell moves the operating margin and the revenue growth of every forecast year by the "
                f"points shown, and shows the price and how far it is above (▲, green) or below (▼, red) today's market "
                f"price of {dollars(company['share_price'])}. The dashed line runs where the model equals the market price, "
                f"and the gold frame is the base case, {dollars(dcf['implied_share_price'])}, the DCF above. The "
                "table uses the WACC and terminal growth in use, and the sliders move it."
            ).replace("$", "\\$")
        )


def forward_price_text(price, company_forward_pe):
    """Write the forward P/E price: in dollars, "No estimate" when the company has no usable analyst
    estimate of next year's earnings (none given, or not above zero), or "Not enough peers" when it has
    one but too few peers have a forward P/E.
    """
    if price is None and company_forward_pe is None:
        return "No estimate"
    return price_or_note(price)


def price_or_note(price):
    """Write a price in dollars, or say there were not enough peers to work one out."""
    return "Not enough peers" if price is None else dollars(price)


FLAG_NAMES = {
    "low_margin": "Low margin",
    "ev_sales": "EV/Sales outlier",
    "ev_ebitda": "EV/EBITDA outlier",
    "pe": "P/E outlier",
    "ps": "P/S outlier",
    "forward_pe": "Forward P/E outlier",
}


def peer_flags(peers):
    """For each peer, in order, list the reasons its figures may distort the comparison (see
    valuation.flag_peers), using the page's agreed limits.
    """
    return valuation.flag_peers(
        peers,
        assumptions.DEPRESSED_PEER_MARGIN,
        assumptions.PEER_OUTLIER_FACTOR,
        assumptions.MINIMUM_PEERS,
    )


def flag_text(reasons):
    """Write a peer's reasons as short text for the table, for example "⚠ Low margin, P/E outlier",
    or nothing if the peer has none.
    """
    return "⚠ " + ", ".join(FLAG_NAMES[reason] for reason in reasons) if reasons else ""


def flag_explanations(peers):
    """Explain, one sentence per flagged peer, why it was flagged: depressed earnings inflate its
    multiples, or a multiple is far from the other peers' middle (often a one-off). Returns an
    empty list when no peer is flagged.
    """
    columns = {"ev_sales": ("EV/Sales", "peer_ev_sales"), "ev_ebitda": ("EV/EBITDA", "peer_ev_ebitda"), "pe": ("P/E", "peer_pe"), "ps": ("P/S", "peer_ps"), "forward_pe": ("forward P/E", "peer_forward_pe")}
    sentences = []
    for position, reasons in enumerate(peer_flags(peers)):
        ticker = peers["peer_tickers"][position]
        parts = []
        if "low_margin" in reasons:
            margin = peers["peer_operating_margin"][position]
            parts.append(
                f"its operating margin ({percent(margin)}) is below {assumptions.DEPRESSED_PEER_MARGIN:.0%}, "
                "so its earnings are depressed and its multiples look inflated"
            )
        for reason in ("ev_sales", "ev_ebitda", "pe", "ps", "forward_pe"):
            if reason in reasons:
                label, key = columns[reason]
                middle = valuation.median_of_usable_multiples(peers[key], assumptions.MINIMUM_PEERS)
                parts.append(
                    f"its {label} of {peers[key][position]:.1f}x is far from the peers' middle "
                    f"({middle:.1f}x), which is often a one-off gain or loss"
                )
        if parts:
            sentences.append(f"{ticker}: " + "; ".join(parts) + ".")
    return sentences


def margin_gap_warning(company_name, company_margin, peers):
    """Warn, in one sentence, when the company's operating margin is far from its peers' middle
    margin, because multiples (EV/Sales most of all) do not compare well between companies with
    different margins. Returns None when the gap is within the limit or cannot be worked out.
    """
    gap = valuation.margin_gap(company_margin, peers["peer_operating_margin"], assumptions.MINIMUM_PEERS)
    if gap is None or abs(gap) <= assumptions.PEER_MARGIN_GAP_WARNING:
        return None
    middle = company_margin - gap
    direction = "above" if gap > 0 else "below"
    return (
        f"{company_name}'s operating margin ({percent(company_margin)}) is {abs(gap) * 100:.1f} points "
        f"{direction} its peers' middle ({percent(middle)}). Multiples, EV/Sales most of all, compare "
        "badly between companies with different margins, so lean more on EV/EBITDA and P/E."
    )


def middle_price_label(multiples):
    """Name the middle price honestly: with five, four or three prices it is a middle (with four, the
    average of the two in the middle), with two it is only their average, with one it is just that price.
    """
    prices = [
        multiples[key]
        for key in ("price_ev_sales", "price_ev_ebitda", "price_pe", "price_ps", "price_forward_pe")
        if multiples[key] is not None
    ]
    return {
        5: "Middle of the five prices",
        4: "Middle of the four prices",
        3: "Middle of the three prices",
        2: "Average of two prices",
        1: "The only price",
    }.get(len(prices), "Middle of the prices")


def peer_table(peers, own_label, overview, multiples):
    """Make the table of the peers and what each one has: five multiples and an operating
    margin, as text. The company itself comes first, so it can be compared at a glance, and the
    peer medians come last.

    A peer multiple that is missing, or zero or negative, shows as a dash because it is left out
    of the median; an operating margin shows as a dash only when it is missing, since a negative
    margin is real information. A last column flags peers whose figures may distort the comparison
    (see flag_explanations). `multiples` is the result of run_multiples, which holds the medians.
    """
    def show_multiple(multiple):
        return f"{multiple:.1f}x" if valuation.usable_multiples([multiple]) else "–"

    def show_margin(margin):
        return "–" if margin is None or margin != margin else f"{margin:.1%}"      # margin != margin: NaN

    median_margin = valuation.median_of_available(peers["peer_operating_margin"], assumptions.MINIMUM_PEERS)
    rows = (
        [own_label]
        + list(peers["peer_tickers"])
        + ["Peer median"]
    )
    return pd.DataFrame(
        {
            "EV/Sales": (
                [show_multiple(overview["ev_sales"])]
                + [show_multiple(multiple) for multiple in peers["peer_ev_sales"]]
                + [show_multiple(multiples["median_ev_sales"])]
            ),
            "EV/EBITDA": (
                [show_multiple(overview["ev_ebitda"])]
                + [show_multiple(multiple) for multiple in peers["peer_ev_ebitda"]]
                + [show_multiple(multiples["median_ev_ebitda"])]
            ),
            "P/E": (
                [show_multiple(overview["pe"])]
                + [show_multiple(multiple) for multiple in peers["peer_pe"]]
                + [show_multiple(multiples["median_pe"])]
            ),
            "P/S": (
                [show_multiple(overview["ps"])]
                + [show_multiple(multiple) for multiple in peers["peer_ps"]]
                + [show_multiple(multiples["median_ps"])]
            ),
            "Forward P/E": (
                [show_multiple(overview["forward_pe"])]
                + [show_multiple(multiple) for multiple in peers["peer_forward_pe"]]
                + [show_multiple(multiples["median_forward_pe"])]
            ),
            "Op. margin": (
                [show_margin(overview["operating_margin"])]
                + [show_margin(margin) for margin in peers["peer_operating_margin"]]
                + [show_margin(median_margin)]
            ),
            "Flag": [""] + [flag_text(reasons) for reasons in peer_flags(peers)] + [""],
        },
        index=pd.Index(rows, name="Company"),
    )


# The multiples the peer bar chart can show: the label, where each peer's figure is in the peers, where the company's own
# is in the overview, and where the peers' median is in run_multiples' result.
PEER_CHART_MULTIPLES = [
    ("EV/Sales", "peer_ev_sales", "ev_sales", "median_ev_sales"),
    ("EV/EBITDA", "peer_ev_ebitda", "ev_ebitda", "median_ev_ebitda"),
    ("P/E", "peer_pe", "pe", "median_pe"),
    ("P/S", "peer_ps", "ps", "median_ps"),
    ("Forward P/E", "peer_forward_pe", "forward_pe", "median_forward_pe"),
]


def peer_bar_headline(label, company_name, company_value, median):
    """Say in one sentence how the company's multiple compares with the peers' middle one, or why it cannot be
    compared (the company has no usable figure, or too few peers do).
    """
    if not valuation.usable_multiples([company_value]):
        return f"{company_name} has no usable {label} (a loss or a missing figure), so it is left off the chart."
    if median is None:
        return f"Too few peers have a usable {label} to give a middle value to compare {company_name} with."
    if company_value < median:
        relation = "below"
    elif company_value > median:
        relation = "above"
    else:
        return f"{company_name}'s {label} of {company_value:.1f}x is the same as the peer median."
    return f"{company_name}'s {label} of {company_value:.1f}x is {relation} the peer median of {median:.1f}x."


def peer_bar_figure(label, company_label, company_value, tickers, peer_values, median):
    """Draw one multiple as horizontal bars, highest at the top: the company in the accent colour, the peers in
    brown, and a dashed line at the peers' median. A figure that is missing, or zero or negative (no real multiple), is
    left off.
    """
    bars = [(company_label, company_value, True)] + [(ticker, value, False) for ticker, value in zip(tickers, peer_values)]
    bars = sorted((bar for bar in bars if valuation.usable_multiples([bar[1]])), key=lambda bar: bar[1], reverse=True)
    figure = go.Figure(go.Bar(
        y=[name for name, _value, _own in bars],
        x=[value for _name, value, _own in bars],
        orientation="h",
        marker={"color": [theme.ACCENT if own else theme.COMPARISON for _name, _value, own in bars]},
        text=[f"{value:.1f}x" for _name, value, _own in bars],
        textposition="outside",
        textfont={"color": theme.TEXT},
        cliponaxis=False,
        hovertemplate=f"<b>%{{y}}</b><br>{label} %{{x:.1f}}x<extra></extra>",
    ))
    if median is not None:
        figure.add_vline(x=median, line={"color": theme.TEXT, "width": 2, "dash": "dash"})
        figure.add_annotation(
            x=median, y=1, yref="paper", yanchor="bottom", showarrow=False, text=f"Peer median {median:.1f}x",
            font={"color": theme.TEXT, "size": 12},
        )
    longest = max([value for _name, value, _own in bars] + [median or 0], default=1)
    figure.update_xaxes(ticksuffix="x", gridcolor=theme.BORDER, zeroline=False, range=[0, longest * 1.15])    # room for the label on the longest bar
    figure.update_yaxes(autorange="reversed", showgrid=False, automargin=True)
    theme.style_figure(figure, height=90 + 38 * len(bars))
    figure.update_layout(margin={"l": 0, "r": 20, "t": 30, "b": 0})
    return figure


def peer_scatter_headline(company_name, company_multiple, company_margin, median_multiple, median_margin):
    """Say in one sentence where the company sits among its peers on price (EV/EBITDA) and on profitability
    (operating margin): cheaper or dearer than the typical peer, and with a higher or lower margin. None when any of the four
    figures is missing.
    """
    if None in (company_multiple, company_margin, median_multiple, median_margin) or not valuation.usable_multiples([company_multiple]):
        return None
    cheaper, richer = company_multiple < median_multiple, company_margin > median_margin
    facts = (
        f"{company_name} trades at {company_multiple:.1f}x EBITDA against the peers' {median_multiple:.1f}x, "
        f"with an operating margin of {company_margin:.1%} against {median_margin:.1%}"
    )
    if cheaper and richer:
        return f"{facts}: cheaper than the typical peer while more profitable."
    if cheaper:
        return f"{facts}: cheaper than the typical peer, but less profitable, so the discount may be deserved."
    if richer:
        return f"{facts}: dearer than the typical peer, but more profitable, so the premium has some support."
    return f"{facts}: dearer than the typical peer while less profitable."


def peer_scatter_figure(company_label, company_multiple, company_margin, tickers, peer_multiples, peer_margins,
                        median_multiple, median_margin):
    """Draw the peers as dots, EV/EBITDA up and operating margin across: the company in the accent colour (bigger), the
    peers in brown with their tickers, and dashed lines at the peers' median of each. A dot far below the middle of the
    cloud is cheap for its profitability. A peer missing either figure, or without a real multiple, is left off.
    """
    dots = [
        (ticker, margin, multiple)
        for ticker, margin, multiple in zip(tickers, peer_margins, peer_multiples)
        if margin is not None and margin == margin and valuation.usable_multiples([multiple])
    ]
    figure = go.Figure(go.Scatter(
        x=[margin for _t, margin, _m in dots], y=[multiple for _t, _x, multiple in dots],
        text=[ticker for ticker, _x, _m in dots], mode="markers+text", textposition="top center",
        textfont={"color": theme.TEXT, "size": 12}, marker={"color": theme.COMPARISON, "size": 12},
        hovertemplate="<b>%{text}</b><br>Operating margin %{x:.1%}<br>EV/EBITDA %{y:.1f}x<extra></extra>",
    ))
    if company_margin is not None and valuation.usable_multiples([company_multiple]):
        figure.add_trace(go.Scatter(
            x=[company_margin], y=[company_multiple], text=[company_label], mode="markers+text", textposition="top center",
            textfont={"color": theme.ACCENT, "size": 13}, marker={"color": theme.ACCENT, "size": 18},
            hovertemplate="<b>%{text}</b><br>Operating margin %{x:.1%}<br>EV/EBITDA %{y:.1f}x<extra></extra>",
        ))
    if median_multiple is not None:
        figure.add_hline(y=median_multiple, line={"color": theme.GREY, "width": 1, "dash": "dash"})
    if median_margin is not None:
        figure.add_vline(x=median_margin, line={"color": theme.GREY, "width": 1, "dash": "dash"})
    figure.update_xaxes(title="Operating margin", tickformat=".0%", gridcolor=theme.BORDER, zeroline=False)
    figure.update_yaxes(title="EV/EBITDA", ticksuffix="x", gridcolor=theme.BORDER, zeroline=False, rangemode="tozero")
    theme.style_figure(figure, height=380)
    figure.update_layout(margin={"l": 0, "r": 10, "t": 20, "b": 0})
    return figure


def draw_peer_charts(multiples, peers, own_label, overview, company_name):
    """Draw the two peer charts under the price boxes: one multiple at a time as sorted bars (chosen with a switch,
    EV/EBITDA to start) and a scatter of EV/EBITDA against operating margin, each under a sentence that says what it
    shows.
    """
    labels = [label for label, _peer, _own, _median in PEER_CHART_MULTIPLES]
    chosen = st.radio("Compare one multiple", labels, index=labels.index("EV/EBITDA"), horizontal=True, key="peer_chart_multiple")
    label, peer_key, own_key, median_key = next(entry for entry in PEER_CHART_MULTIPLES if entry[0] == chosen)
    st.markdown(
        f"**{peer_bar_headline(label, company_name, overview[own_key], multiples[median_key])}**",
        help=explanations.help_text("peer_bars"),
    )
    st.plotly_chart(
        peer_bar_figure(
            label, own_label, overview[own_key], peers["peer_tickers"], peers[peer_key], multiples[median_key]
        ),
        width="stretch", config=CHART_CONFIG,
    )
    median_margin = valuation.median_of_available(peers["peer_operating_margin"], assumptions.MINIMUM_PEERS)
    headline = peer_scatter_headline(
        company_name, overview["ev_ebitda"], overview["operating_margin"], multiples["median_ev_ebitda"], median_margin
    )
    if headline:
        st.markdown(f"**{headline}**", help=explanations.help_text("peer_scatter"))
    st.plotly_chart(
        peer_scatter_figure(
            own_label, overview["ev_ebitda"], overview["operating_margin"], peers["peer_tickers"],
            peers["peer_ev_ebitda"], peers["peer_operating_margin"], multiples["median_ev_ebitda"], median_margin,
        ),
        width="stretch", config=CHART_CONFIG,
    )
    with reading_notes("peer_charts"):
        st.caption(
            "Gold is this company, brown the peers, and dashed lines the peers' middle values. In the scatter, a dot low on "
            "the chart is cheap for its profitability, and one far to the right earns a high margin."
        )


def draw_multiples(multiples, peers, notes, peers_are_suggested, own_label, overview, company_name):
    """Draw the multiples section: the price each peer multiple gives, their middle value, how
    far the DCF price is from it, and the table of peers behind them.

    `multiples` is None when there are no peers to compare with, and then the section says how
    to add some. A price that could not be worked out (too few peers with that multiple) says
    so. `notes` are the messages from the peer box, and peers_are_suggested says whether to
    point out that the peers were suggested by Yahoo's industry list. `own_label`, `company_name`
    and `overview` put the company itself in the table and in the margin warning. A yellow
    warning says when the company's margin is far from its peers', or when the "middle" price is
    only the average of two; peers whose figures may distort the comparison are flagged.
    """
    st.subheader("Peer multiples")
    for kind, text in notes:
        (st.warning if kind == "warning" else st.caption)(text)
    if multiples is None:
        return
    margin_warning = margin_gap_warning(company_name, overview["operating_margin"], peers)
    if margin_warning:
        st.warning(margin_warning)
    # The answer first: the middle of the five prices and how far the DCF is from it, then the five prices behind it
    # in one even row (on a phone, Streamlit stacks them).
    median_column, gap_column = st.columns(2)
    median_column.metric(
        middle_price_label(multiples), price_or_note(multiples["median_price"]), help=explanations.help_text("middle_price")
    )
    gap = multiples["dcf_vs_multiples"]
    gap_column.metric(
        "DCF vs multiples", "Not available" if gap is None else percent(gap), help=explanations.help_text("dcf_vs_multiples")
    )
    with st.container(key=theme.MULTIPLE_PRICES_KEY):
        sales_column, ebitda_column, pe_column, ps_column, forward_pe_column = st.columns(5)
    sales_column.metric(
        "EV/Sales price", price_or_note(multiples["price_ev_sales"]), help=explanations.help_text("ev_sales_price")
    )
    ebitda_column.metric(
        "EV/EBITDA price", price_or_note(multiples["price_ev_ebitda"]), help=explanations.help_text("ev_ebitda_price")
    )
    pe_column.metric("P/E price", price_or_note(multiples["price_pe"]), help=explanations.help_text("pe_price"))
    ps_column.metric("P/S price", price_or_note(multiples["price_ps"]), help=explanations.help_text("ps_price"))
    forward_pe_column.metric(
        "Forward P/E price", forward_price_text(multiples["price_forward_pe"], overview["forward_pe"]),
        help=explanations.help_text("forward_pe_price"),
    )
    if middle_price_label(multiples) == "Average of two prices":
        st.warning(
            "Only two of the five multiples gave a price, so this is their average, not a middle: "
            "two numbers have no middle. Treat it with care, and see the table for which peers are missing."
        )
    draw_peer_charts(multiples, peers, own_label, overview, company_name)
    draw_table(peer_table(peers, own_label, overview, multiples), key=theme.PEER_TABLE_KEY)
    with reading_notes("multiples"):
        st.caption(
            f"Each multiple needs at least {assumptions.MINIMUM_PEERS} peers with a usable figure; "
            "a peer with no figure (a dash) is left out of that multiple only. A negative operating "
            "margin counts, because a loss is real information. The forward P/E uses analysts' estimate of next "
            "year's adjusted earnings per share (it leaves out things like share-based pay), so it is only "
            "compared with the peers' forward P/E, never with the ordinary P/E. "
            + (
                f"The company's own row is its last twelve months (to {overview['ttm_period_end']}) at "
                f"today's price, like the peers' figures from {provider_name(peers.get('peer_data_source'))}, so the two are like for like."
                if overview.get("ttm_period_end")
                else "The company's own row comes from its last fiscal year and today's price; the peers' "
                f"figures are {provider_name(peers.get('peer_data_source'))}'s trailing twelve months, so small differences are expected."
            )
        )
    for sentence in flag_explanations(peers):
        st.caption(f"⚠ {sentence}")
    if flag_explanations(peers):
        st.caption(
            "Flagged peers still count in the medians. To leave one out, remove it from the "
            "Peers box beside the sliders."
        )
    if peers_are_suggested:
        st.caption(
            (
                "Peers suggested from Financial Modeling Prep's peer list: the ones closest to the company in "
                "size, within a tenth to ten times. Size is only a rough sign of a similar business, so "
                "change them under Peers, beside the sliders, if you know better."
                if peers.get("peer_data_source") == "fmp"
                else "Peers suggested from Yahoo's industry list: those whose operating margin and revenue "
                "growth are closest to the company's, within a tenth to ten times its size. Similar margins "
                "and growth are only a rough sign of a similar business, so change them under Peers, beside the sliders, if "
                "you know better."
            )
        )


@st.cache_data(ttl=LIVE_DATA_CACHE_SECONDS, show_spinner=False)
def load_company(ticker):
    """Fetch a company's figures and remember them for LIVE_DATA_CACHE_SECONDS, so moving a
    slider does not ask Yahoo again.

    Adobe comes from Yahoo's live quote, then Financial Modeling Prep's, then the snapshot. Any other
    company comes from Yahoo's statements, or Financial Modeling Prep's if Yahoo is not answering, with
    no snapshot to fall back on. Returns the package of figures and the name of the source that
    supplied it; stops with a plain error if it cannot.
    """
    if ticker == assumptions.BASE_CASE_TICKER:
        return data.get_company_data_with_fallback(ticker)
    return data.get_other_company_data(ticker)


@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)
def load_suggested_peers(ticker, market_value):
    """Ask Yahoo for suggested peers for a company and remember the answer for
    SLOW_DATA_CACHE_SECONDS. The market value is in $ millions. Stops with a plain error if
    Yahoo cannot be reached.
    """
    return data.suggest_peers_any(
        ticker,
        market_value,
        assumptions.PEER_CANDIDATES_TO_CHECK,
        assumptions.PEER_BIGGEST_SIZE_GAP,
        assumptions.SUGGESTED_PEERS,
        assumptions.PEER_SECTOR_CANDIDATES_TO_CHECK,
        assumptions.MINIMUM_PEERS,
    )


@st.cache_data(ttl=LIVE_DATA_CACHE_SECONDS, show_spinner=False)
def load_peer_multiples(tickers):
    """Fetch the multiples of the peers in the box (a tuple of tickers) and remember them for
    LIVE_DATA_CACHE_SECONDS. Stops with a plain error if Yahoo cannot be reached.
    """
    return data.peer_multiples_any(list(tickers))


def load_adobe_peer_margins(tickers):
    """Get the operating margins of Adobe's hand-chosen peers from Yahoo (its snapshot of the
    Excel model has none). Returns a list in the same order, or all blanks if Yahoo cannot be
    reached, so the table still draws.
    """
    try:
        return load_peer_multiples(tuple(tickers))["peer_operating_margin"]
    except ValueError:
        return [None] * len(tickers)


@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)
def load_analyst_view(ticker, usd_per_unit):
    """Fetch the analysts' consensus rating and price targets (in US dollars) and remember them for
    SLOW_DATA_CACHE_SECONDS (analysts change their views every few weeks, not every few minutes). Stops with a plain error if Yahoo is busy or could not be asked.
    """
    return data.get_analyst_view(ticker, usd_per_unit)


@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)
def load_company_matches(query):
    """Search Yahoo Finance for the companies matching a name and remember the answer for SLOW_DATA_CACHE_SECONDS (company names do not change). Stops
    with a plain error if Yahoo is busy or cannot be reached.
    """
    return data.search_companies(
        query, assumptions.SEARCH_RESULTS_SHOWN, assumptions.SEARCH_MIN_CHARACTERS, assumptions.SEARCH_MATCHES_ASKED
    )


@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)
def load_price_history(ticker, usd_per_unit):
    """Fetch a share's closing prices over the last year (in US dollars) and remember them for
    SLOW_DATA_CACHE_SECONDS (a year of daily closes hardly changes within a day; the price itself stays fresh). Stops with a plain error if Yahoo is busy or has none.
    """
    return data.get_price_history(ticker, usd_per_unit)


@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)
def load_company_context(ticker):
    """Fetch a company's recent headlines and top officers and remember them for SLOW_DATA_CACHE_SECONDS
    (a few hours late is fine for five headlines, and it saves requests). Stops with a plain error if Yahoo is busy or gave neither.
    """
    return data.get_company_context(ticker)


@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)
def load_macro_backdrop():
    """Fetch the macro numbers (they change once a day at most) and remember them for SLOW_DATA_CACHE_SECONDS.
    Stops with a plain error if FRED has no key or could not be reached.
    """
    return data.get_macro_backdrop()


@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)
def load_history(ticker, usd_per_unit):
    """Fetch a company's yearly history (in US dollars) and remember it for
    SLOW_DATA_CACHE_SECONDS. Stops with a plain error if Yahoo cannot be reached or has none.
    """
    return data.get_history_any(ticker, usd_per_unit)


@st.cache_data(ttl=SLOW_DATA_CACHE_SECONDS, show_spinner=False)
def load_ttm(ticker, usd_per_unit):
    """Fetch a company's last twelve months (in US dollars) and remember them for
    SLOW_DATA_CACHE_SECONDS. Stops with a plain error if Yahoo cannot be reached or lacks them.
    """
    return data.get_ttm_any(ticker, usd_per_unit)


def parse_peer_tickers(text, own_ticker, how_many):
    """Turn what was typed in the peer box into a list of tickers: split at commas and spaces,
    in capitals, no repeats, without the company's own ticker, and no more than how_many.

    Returns the tickers, and whether some were left out for being more than how_many.
    """
    tickers = []
    for word in text.replace(",", " ").split():
        ticker = word.upper()
        if ticker != own_ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers[:how_many], len(tickers) > how_many


def draw_adjustment_box(company, tools):
    """Draw the one-off adjustment box behind a "One-off items" button in `tools` (the row under the sliders) and
    return the amount typed in, in $ millions
    a year (0 when left alone; negative to take out a gain such as a tax credit, positive to add back
    a one-off cost). There is one box per company, so an amount is not carried over.
    """
    return float(
        tools.popover("One-off items").number_input(
            "Adjust operating income by ($ millions a year)",
            value=0.0,
            step=100.0,
            format="%.0f",
            key=ONE_OFF_KEY_START + company["ticker"],
            help=(
                "Add or take off a yearly amount from operating income, in US dollars: for example -1000 "
                "to take out a tax credit that flatters the profit. It is applied to the last fiscal year "
                "and to the last twelve months, so the DCF, the margins and the EV/EBITDA agree. Net income "
                "and the P/E stay as reported."
            ),
        )
    )


def apply_adjustment(company, amount):
    """Return the company's figures with the last fiscal year's operating income (EBIT) adjusted by
    the amount. Everything worked out from EBIT afterwards, such as the starting point's margin, uses
    the adjusted figure; net income, income tax and the tax rate stay as reported.
    """
    return dict(company, ebit=company["ebit"] + amount)


def apply_adjustment_to_ttm(ttm, amount):
    """Return the last twelve months with operating income adjusted by the same yearly amount, or
    None if the last twelve months are not available.
    """
    return None if ttm is None else dict(ttm, operating_income=ttm["operating_income"] + amount)


def adjustment_note(amount):
    """Say, when an adjustment is active, what it changes and what stays as reported. Returns None when
    there is no adjustment.
    """
    if amount == 0:
        return None
    return (
        f"You have adjusted operating income by {millions_text(amount)} a year, for the last fiscal year and for "
        "the last twelve months. The DCF, the margins, EV/EBITDA, net debt ÷ EBITDA, free cash flow yield, ROIC, "
        "interest cover, the reverse DCF and both sensitivity tables use the adjusted figure. The History, the P/E, "
        "cash conversion and revenue growth are as reported, and the peers' figures are Yahoo's."
    )


def draw_peer_box(company, tools):
    """Draw the peer ticker box behind a "Peers" button in `tools` (the row under the sliders), filled in with
    suggestions from Yahoo's
    industry list the first time a company is shown (the reader can change them), and fetch
    the multiples of the peers in it.

    Returns the peers' figures (None when the box is empty or Yahoo failed) and a list of notes
    for the multiples section, each a pair: "warning" or "caption", and its text.
    """
    notes = []
    market_value = round(company["share_price"] * company["shares"])
    suggested_source = None
    try:
        suggestion = load_suggested_peers(company["ticker"], market_value)
        suggested, suggested_source = suggestion["peer_tickers"], suggestion["peer_source"]
    except ValueError as error:
        suggested = []
        notes.append(("warning", f"{error} Type peer tickers under Peers, beside the sliders."))

    typed = tools.popover("Peers").text_input(
        "Peer tickers",
        value=", ".join(suggested),
        key=PEERS_KEY_START + company["ticker"],      # one box per company, so peers are not carried over
        help=(
            "Companies to compare with, separated by commas. Suggested from Yahoo's industry "
            f"list, the closest in margin and growth; change them as you like (up to {assumptions.MAX_TYPED_PEERS})."
        ),
    )
    tickers, cut_off = parse_peer_tickers(typed, company["ticker"], assumptions.MAX_TYPED_PEERS)
    if suggested_source == "sector" and tickers == suggested:
        notes.append((
            "caption",
            "This company's industry had too few suitable peers, so some or all of these come from its "
            "wider sector. They are the closest in margin and growth, but check that they fit.",
        ))
    if cut_off:
        notes.append(("caption", f"Only the first {assumptions.MAX_TYPED_PEERS} peers are used."))
    if not tickers:
        if not any(kind == "warning" for kind, _ in notes):
            notes.append((
                "caption",
                "No suitable peers were found in Yahoo's industry list for this company. "
                "Type at least 2 peer tickers under Peers, beside the sliders, to compare with peers.",
            ))
        return None, notes
    try:
        figures = load_peer_multiples(tuple(tickers))
    except ValueError as error:
        notes.append(("warning", str(error)))
        return None, notes
    unknown = [
        ticker
        for ticker, sales, ebitda, pe, ps, forward_pe in zip(
            figures["peer_tickers"], figures["peer_ev_sales"], figures["peer_ev_ebitda"], figures["peer_pe"],
            figures["peer_ps"], figures["peer_forward_pe"],
        )
        if sales is None and ebitda is None and pe is None and ps is None and forward_pe is None
    ]
    if unknown:
        notes.append((
            "caption",
            f"Yahoo Finance has no multiples for {', '.join(unknown)}. Check the ticker.",
        ))
    return figures, notes


# The keys of the two search boxes at the top: a click on a match writes the chosen ticker into the first and clears the second.
TICKER_BOX_KEY = "ticker_box"
NAME_SEARCH_KEY = "name_search"


def choose_ticker(ticker):
    """Run when the reader clicks a match: put its ticker in the ticker box (so the page loads that company) and clear the
    search box. It runs before the page is drawn again, which is the one moment a box's value may be set.
    """
    st.session_state[TICKER_BOX_KEY] = ticker
    st.session_state[NAME_SEARCH_KEY] = ""


def match_label(match):
    """Write one match as the text of its button: the name, the ticker and the exchange, for example
    "Apple Inc. · AAPL · NASDAQ". The text comes from Yahoo, so it is made safe for markdown first.
    """
    parts = [plain_text_for_markdown(match["name"]), plain_text_for_markdown(match["ticker"])]
    if match["exchange"]:
        parts.append(plain_text_for_markdown(match["exchange"]))
    return " · ".join(parts)


def find_matches(query):
    """Look up the companies whose name matches `query`: a list of matches (empty when nothing matches), or None when the
    search could not be made (Yahoo is busy or cannot be reached). It never stops the page.
    """
    try:
        return load_company_matches(query)
    except ValueError:
        return None


def draw_match_buttons(container, matches, key_prefix):
    """Draw each match as a button in `container` (under the search bar, or in the page); clicking one loads that company. The keys
    start with `key_prefix`, so the same company can be offered in two places at once without clashing.
    """
    for match in matches:
        container.button(
            match_label(match), key=f"{key_prefix}_{match['ticker']}", on_click=choose_ticker, args=(match["ticker"],),
            width="stretch",
        )


def draw_search_bar():
    """Draw the search bar at the top of the page, the app's name, the ticker box and the name search side by side, and return the
    ticker typed in. Every serious finance site puts its search here, where a reader looks first.
    """
    bar = st.container(key=SEARCH_BAR_KEY)
    name_column, ticker_column, search_column = bar.columns([1.2, 1, 2], vertical_alignment="bottom")
    name_column.html(theme.topbar_html())
    ticker = draw_ticker_box(ticker_column)
    draw_name_search(search_column, bar)
    return ticker


def draw_ticker_box(box):
    """Draw the company ticker box in `box` and return the ticker typed in, in capitals. An empty box means the
    default company.
    """
    st.session_state.setdefault(TICKER_BOX_KEY, DEFAULT_TICKER)
    typed = box.text_input(
        "Company ticker",
        key=TICKER_BOX_KEY,
        help="A US stock ticker, for example MSFT. Adobe (ADBE) has hand-chosen assumptions and peers; any other company gets a starting point from its own last reported year and suggested peers.",
    )
    return typed.strip().upper() or DEFAULT_TICKER


def draw_name_search(box, results):
    """Draw the "Search by company name" box in `box`, beside the ticker box, and, once something is typed, the
    matching companies as buttons in `results` (under the search bar). It is how a reader finds a ticker without knowing it.
    """
    query = box.text_input(
        "Search by company name", key=NAME_SEARCH_KEY, placeholder="For example Microsoft",
        help="Type part of a company's name and press Enter. Click a match to load it.",
    ).strip()
    if not query:
        return
    if len(query) < assumptions.SEARCH_MIN_CHARACTERS:
        results.caption(f"Type at least {assumptions.SEARCH_MIN_CHARACTERS} characters.")
        return
    matches = find_matches(query)
    if matches is None:
        results.caption("The search is not available right now. Type the ticker instead.")
    elif not matches:
        results.caption(f"No company found for {plain_text_for_markdown(query)}.")
    else:
        draw_match_buttons(results, matches, "match")


def currency_note(company):
    """Say in one line which currency the figures were converted from, and at what rate.

    Returns None for a company that reports and trades in US dollars, so there is nothing
    to say.
    """
    statements = company.get("statement_currency")
    price = company.get("price_currency")
    if statements in (None, "USD") and price in (None, "USD"):
        return None
    statement_rate = f"1 {statements} = ${company['usd_per_statement_unit']:.4g}"
    price_rate = f"1 {price} = ${company['usd_per_price_unit']:.4g}"
    if statements == price:
        return f"Converted from {statements} to US dollars at today's exchange rate ({statement_rate})."
    parts = []
    if statements != "USD":
        parts.append(f"the statements from {statements} ({statement_rate})")
    if price != "USD":
        parts.append(f"the share price from {price} ({price_rate})")
    return "Converted to US dollars at today's exchange rates: " + " and ".join(parts) + "."


def draw_source_note(company, source_used):
    """Tell the reader where the figures came from and, for any company other than Adobe,
    that this is a starting point and not a forecast.

    Adobe: a quiet line when the share price and beta are live, a visible warning when the
    page had to fall back to the frozen snapshot. Other companies: a quiet line, and a visible
    warning that the forecast is only a starting point.
    """
    if source_used in ("yahoo", "fmp"):
        st.caption(f"All figures are from {provider_name(source_used)}'s latest annual statements.")
        conversion = currency_note(company)
        if conversion:
            st.caption(conversion)
        if company.get("cost_of_debt_is_fallback"):
            st.warning(
                f"{provider_name(source_used)} has no interest expense for {company['company_name']}, so its cost "
                f"of debt ({precise_percent(company['pre_tax_cost_of_debt'])}) is an estimate: the "
                f"risk-free rate plus a typical credit spread of {precise_percent(data.CREDIT_SPREAD)}."
            )
        if tax_rate_was_replaced(company):
            st.warning(
                f"{company['company_name']}'s tax rate last year was {precise_percent(last_year_tax_rate(company))} "
                "(a tax benefit), which cannot go on forever, so the forecast uses a normal rate of "
                f"{precise_percent(assumptions.NORMAL_TAX_RATE)} instead (the US federal rate)."
            )
        st.info(
            f"Starting point, not a forecast: this holds {company['company_name']}'s last reported margins flat. A DCF "
            "suits stable, cash-generating companies, not banks, loss-makers or early-stage ones."
        )
    elif source_used == data.PREFERRED_SOURCE:
        st.caption("Share price and beta are live from Yahoo Finance.")
    elif source_used == "live_fmp":
        st.caption(
            f"Share price and beta are live from {data.FMP_NAME}, because Yahoo Finance could not be reached."
        )
    else:
        st.warning(
            (
                f"Neither Yahoo Finance nor {data.FMP_NAME} could be reached"
                if data.fmp_available() else "Yahoo Finance could not be reached"
            )
            + ", so share price and beta come from a frozen snapshot."
        )


def draw_footer():
    """Draw the bottom of every page: a thin line, where the numbers come from, and (last, and discreetly) the note
    that this is a learning project and not investment advice.
    """
    st.divider()
    st.caption(LINK_NOTE)
    st.caption(SOURCES_TEXT)
    st.caption(FOOTER_TEXT)


def error_hints(ticker, error):
    """List what the reader can check when a company could not be valued. When Yahoo was not answering (a problem with
    the service, not the ticker) it says so and to wait; otherwise it helps with the ticker itself.
    """
    if isinstance(error, data.SourceUnavailable):
        return [
            "This is not about the ticker: the data source did not answer. Yahoo Finance sometimes limits shared servers.",
            "Wait a few minutes and try again.",
            "Adobe (ADBE) still works from a frozen snapshot while the sources are down.",
        ]
    return [
        f"Is {ticker} the ticker, the short code, and not the name? Apple is AAPL, Microsoft is MSFT and Coca-Cola is KO.",
        "US-listed companies work best. A share listed elsewhere needs its exchange ending, for example AKER.OL for Oslo.",
        "Try one of these: " + ", ".join(EXAMPLE_TICKERS) + ".",
    ]


def draw_error(ticker, error):
    """Show why a company could not be valued, in plain words, with a short list of things to check, and still show the
    footer.
    """
    st.error(f"Could not value {ticker}. {error}")
    busy = isinstance(error, data.SourceUnavailable)
    st.html(theme.hints_card_html("What you can do" if busy else "Things to check", error_hints(ticker, error)))
    matches = [] if busy else find_matches(ticker) or []             # no suggestions when the source is down or finds nothing
    if matches:
        st.markdown("**Did you mean one of these?**")
        draw_match_buttons(st, matches, "didyoumean")
    draw_footer()


MARKDOWN_SPECIAL_CHARACTERS = "\\`*_{}[]()#+-.!|<>$~&"      # each gets a backslash in front, so it shows as itself


def plain_text_for_markdown(text):
    """Make text from outside (a headline, a name) safe to put in a markdown line: every character that
    markdown or Streamlit could read as formatting (links, bold, a dollar sign starting a maths formula)
    gets a backslash, so it is shown exactly as written.
    """
    return "".join("\\" + character if character in MARKDOWN_SPECIAL_CHARACTERS else character for character in text)


def headline_line(item):
    """Write one headline as a markdown bullet: a link when it has a safe https address, plain text
    otherwise, followed by the publisher and the date when Yahoo gave them.
    """
    title = plain_text_for_markdown(item["title"])
    address = item["url"].replace("(", "%28").replace(")", "%29") if item["url"] else None   # a bracket would end the link early
    text = f"[{title}]({address})" if address else title
    details = [plain_text_for_markdown(item["publisher"])] if item["publisher"] else []
    if item["published"]:
        try:
            day = datetime.date.fromisoformat(item["published"])
            details.append(f"{day.day} {day.strftime('%b %Y')}")
        except ValueError:
            details.append(plain_text_for_markdown(item["published"]))
    return f"- {text}" + (f" ({', '.join(details)})" if details else "")


def officer_line(officer):
    """Write one officer as a markdown bullet: the name, then the title when Yahoo has one."""
    name = plain_text_for_markdown(officer["name"])
    return f"- **{name}**" + (f", {plain_text_for_markdown(officer['title'])}" if officer["title"] else "")


def draw_news_and_management(ticker):
    """Draw "News and management": the most recent headlines (as links) and the top officers, from Yahoo.
    A part Yahoo could not give, or has none of, says so, and if Yahoo is busy the whole section says so;
    nothing else on the page depends on it.
    """
    st.subheader("News and management")
    try:
        context = load_company_context(ticker)
    except ValueError as error:
        st.caption(f"The news and the officers are not available right now. {error}")
        return
    st.markdown("**Recent headlines**")
    if context["news"] is None:
        st.caption("The headlines could not be fetched right now.")
    elif not context["news"]:
        st.caption(f"Yahoo Finance has no recent headlines for {ticker}.")
    else:
        st.markdown("\n".join(headline_line(item) for item in context["news"][: assumptions.NEWS_ITEMS_SHOWN]))
    st.markdown("**Top officers**")
    if context["officers"] is None:
        st.caption("The officers could not be fetched right now.")
    elif not context["officers"]:
        st.caption(f"Yahoo Finance lists no officers for {ticker}.")
    else:
        st.markdown("\n".join(officer_line(officer) for officer in context["officers"][: assumptions.OFFICERS_SHOWN]))
    with reading_notes("news"):
        st.caption(
            "From Yahoo Finance. Headlines are written by outside publishers, not by this app, and Yahoo sometimes "
            "mixes in general market stories; nothing in the valuation depends on them. The officers are the team "
            "today: Yahoo does not say when anyone changed."
        )


def day_text(iso_date):
    """Write a date from FRED ("2026-11-19") the way the page writes dates, 19 Nov 2026; "date not given" if it is not one."""
    try:
        day = datetime.date.fromisoformat(iso_date)
    except (TypeError, ValueError):
        return "date not given"
    return f"{day.day} {day.strftime('%b %Y')}"


def macro_date_text(row):
    """Say how fresh a macro number is: "as of 19 Nov 2026" for a daily one, "as of Oct 2026" for a monthly one."""
    try:
        day = datetime.date.fromisoformat(row["date"])
    except (TypeError, ValueError):
        return "date not given"
    return f"as of {day.strftime('%b %Y')}" if row["monthly"] else f"as of {day_text(row['date'])}"


def draw_macro_backdrop():
    """Draw "Macro backdrop": three US numbers from FRED that sit behind every valuation (the 10-year Treasury yield, the
    Fed funds rate and inflation), each with its date and a ? that says what it means. A number FRED could not give says
    so, and with no key or no answer the whole section says so; nothing else on the page depends on it.
    """
    st.subheader("Macro backdrop")
    try:
        rows = load_macro_backdrop()
    except ValueError as error:
        st.caption(f"The macro numbers are not available right now. {error}")
        return
    help_texts = {
        "treasury_yield": explanations.help_text("macro_treasury_yield"),
        "fed_funds": explanations.help_text("macro_fed_funds"),
        "inflation": explanations.help_text("macro_inflation"),
    }
    for column, row in zip(st.columns(len(rows)), rows):
        column.metric(
            row["label"], f"{row['value']:.2f}%" if row["value"] is not None else NOT_AVAILABLE,
            delta=macro_date_text(row) if row["value"] is not None else None, delta_color="off", delta_arrow="off",
            help=help_texts[row["key"]],
        )
    with reading_notes("macro"):
        st.caption(
            "From FRED, the Federal Reserve Bank of St. Louis. These are US numbers: a company that lives on another country's "
            "rates (Aker on Norway's, for instance) is moved more by those. They are background for the valuation, not an input "
            "to it, unless you tick \"Use today's 10-year Treasury yield\" under \"WACC and rates\": the WACC's risk-free rate is otherwise typed in from Damodaran."
        )


NOT_AVAILABLE = "Not available"

# Plotly charts without its toolbar (zoom, download and so on): the hover is enough for a reader of this page.
CHART_CONFIG = {"displayModeBar": False}


def dollar_text_for_markdown(text):
    """Escape the dollar signs in a sentence, because Streamlit reads text between two unescaped dollar signs
    as a maths formula.
    """
    return text.replace("$", "\\$")


def verdict_basis_text(verdict):
    """Say, under the company name, what the verdict badge rests on, so nobody reads it as more than it is."""
    if verdict is None:
        return "No DCF could be built for this company, so there is no verdict. The cards show what can be said."
    limit = f"{assumptions.VERDICT_THRESHOLD:.0%}"
    return f"The model's DCF price against today's market price, with {limit} either way. The model's output, not investment advice."


def price_story(company_name, average_growth, average_margin, dcf_price, upside, market_price):
    """Say in one plain sentence what the model assumes and what it gets, for example "If Adobe Inc. grows revenue by
    8.10% a year for the next five years, with an average operating margin of 37.65%, the model says one share is worth
    $305.60, 21.5% above today's market price of $251.47." The averages have two decimals, like the "What the model
    assumes" table. The page redraws the sentence whenever a slider moves.
    """
    if average_growth < 0:
        growth = f"shrinks revenue by {precise_percent(-average_growth)} a year"
    else:
        growth = f"grows revenue by {precise_percent(average_growth)} a year"
    gap = percent(abs(upside))
    if gap == "0.0%":
        comparison = "the same as"
    else:
        comparison = f"{gap} {'above' if upside > 0 else 'below'}"
    return (
        f"If {company_name} {growth} for the next five years, with an average operating margin of "
        f"{precise_percent(average_margin)}, the model says one share is worth {dollars(dcf_price)}, {comparison} today's "
        f"market price of {dollars(market_price)}."
    )


def price_sparkline(prices):
    """Draw a small line chart of the share price over the last year, with no axes: just the shape, and the
    date and price when the reader hovers. `prices` is the list get_price_history gives.
    """
    closes = [price["close"] for price in prices]
    figure = go.Figure(go.Scatter(
        x=[price["date"] for price in prices],
        y=closes,
        mode="lines",
        line={"color": theme.ACCENT, "width": 2},
        fill="tozeroy",
        fillcolor=theme.with_opacity(theme.ACCENT, 0.12),
        hovertemplate="%{x|%d %b %Y}<br>$%{y:,.2f}<extra></extra>",
    ))
    padding = (max(closes) - min(closes)) * 0.1 or max(closes) * 0.05      # a little air above and below the line
    figure.update_yaxes(visible=False, range=[min(closes) - padding, max(closes) + padding])
    figure.update_xaxes(visible=False)
    return theme.style_figure(figure, height=120)


def price_history_or_none(company):
    """Get the company's share prices for the last year (see data.get_price_history), or None when Yahoo cannot
    give them: the charts that use them are then simply left out.
    """
    try:
        return load_price_history(company["ticker"], company.get("usd_per_price_unit") or 1.0)
    except ValueError:
        return None


def analyst_view_or_none(company):
    """Get what analysts say about the company (see data.get_analyst_view), or None when Yahoo could not be asked: the
    section and the football-field bar that use it are then left out or say so.
    """
    try:
        return load_analyst_view(company["ticker"], company.get("usd_per_price_unit") or 1.0)
    except ValueError:
        return None


def draw_header(company, dcf, multiples, prices, dcf_inputs=None):
    """Draw the top of the page, the answer first: the company's name and ticker, a verdict badge, one large number
    (the DCF value per share) with the upside or downside beside it, two quieter numbers to the right (the market price
    and the middle of the multiples prices), one plain sentence saying what the model assumes and gets (see price_story),
    and a small chart of the share price over the last year. When no DCF could be built (`dcf` is None)
    the badge says so, the cards that need it say "Not available" and there is no sentence. `prices` is the year of share
    prices, or None, and then the chart is left out; nothing else depends on it.
    """
    upside = None if dcf is None else dcf["upside"]
    verdict = valuation.verdict(upside, assumptions.VERDICT_THRESHOLD)
    middle = None if multiples is None else multiples["median_price"]
    hero_cards = [
        theme.kpi_card_html(
            "DCF value per share", NOT_AVAILABLE if dcf is None else dollars(dcf["implied_share_price"]),
            "Discounted cash flow", muted=dcf is None, help=explanations.help_text("implied_share_price"), size="hero",
        ),
        theme.kpi_card_html(
            "Upside / downside", NOT_AVAILABLE if upside is None else theme.change_text(upside),
            "DCF value against the market price", tone=None if upside is None else theme.tone_of(upside),
            muted=upside is None, help=explanations.help_text("upside_vs_market"), size="change",
        ),
    ]
    side_cards = [
        theme.kpi_card_html(
            "Current price", dollars(company["share_price"]), "Market price today",
            help=explanations.help_text("current_price"), size="stat",
        ),
        theme.kpi_card_html(
            "Multiples value", NOT_AVAILABLE if middle is None else dollars(middle),
            middle_price_label(multiples) if middle is not None else "No peer figures to work it out from",
            muted=middle is None, help=explanations.help_text("multiples_value"), size="stat",
        ),
    ]
    st.html(theme.header_html(
        company["company_name"], company["ticker"], verdict, hero_cards, verdict_basis_text(verdict),
        verdict_help=explanations.help_text("verdict"), side_cards=side_cards,
    ))
    if dcf is not None and dcf_inputs is not None:
        story = price_story(
            company["company_name"], valuation.average_rate(dcf_inputs["growth_rates"]),
            valuation.average_rate(dcf_inputs["operating_margins"]), dcf["implied_share_price"], upside,
            company["share_price"],
        )
        with st.container(key=STORY_KEY):
            st.markdown(dollar_text_for_markdown(story))
    if prices is None:
        return
    st.caption("Share price, last 12 months", help=explanations.help_text("sparkline"))
    st.plotly_chart(price_sparkline(prices), width="stretch", config=CHART_CONFIG)


def draw_dcf_unavailable(ticker, error):
    """Say, in plain words, that no DCF could be built for a company whose figures did load, and that the
    overview and history below still show what can be said about it.
    """
    st.error(
        f"Could not value {ticker}. {error} The overview and the history below do not need a valuation, "
        "so they are still shown."
    )


# The tabs under the header, in order: what each holds is set in draw_page.
# ---------------------------------------------------------------------------
# Compare: a second company next to the one on the page
# ---------------------------------------------------------------------------

# The ways of valuing a company that the comparison chart lines up: the label, and where the price is found.
COMPARE_METHODS = [
    ("DCF", "dcf"), ("EV/Sales", "price_ev_sales"), ("EV/EBITDA", "price_ev_ebitda"), ("P/E", "price_pe"),
    ("P/S", "price_ps"), ("Forward P/E", "price_forward_pe"),
]


def suggested_peer_figures(company):
    """Get the multiples of the peers Yahoo suggests for a company, the way the Peers box would fill itself in,
    without drawing a box. Returns None when there are no suitable peers or Yahoo could not be reached.
    """
    market_value = round(company["share_price"] * company["shares"])
    try:
        tickers = load_suggested_peers(company["ticker"], market_value)["peer_tickers"][: assumptions.MAX_TYPED_PEERS]
        return load_peer_multiples(tuple(tickers)) if tickers else None
    except ValueError:
        return None


def value_for_compare(ticker, growth_shift, margin_shift, terminal_growth_rate, wacc_override, live_risk_free=None):
    """Value a second company with the same sliders, the same typed-in WACC and the same risk-free rate as the page. Adobe uses its hand-chosen peers,
    any other company the peers Yahoo suggests, and there is no one-off adjustment. Returns {"company", "dcf", "multiples",
    "overview", "dcf_error"}: when a DCF cannot be built (a company that lost money) the DCF and the multiples are None and
    "dcf_error" says why. Stops with a plain error if the company itself cannot be found.
    """
    company, _source = load_company(ticker)
    peers = {key: company[key] for key in PEER_KEYS} if is_base_case(company) else suggested_peer_figures(company)
    if peers is not None:
        company = dict(company, **peers)
    company = apply_live_risk_free(company, live_risk_free)
    try:
        dcf, multiples = run_valuation(company, build_dcf_inputs(company, growth_shift, margin_shift), terminal_growth_rate, wacc_override)
        dcf_error = None
    except ValueError as error:
        dcf = multiples = None
        dcf_error = str(error)
    return {"company": company, "dcf": dcf, "multiples": multiples, "overview": company_overview(company), "dcf_error": dcf_error}


def compare_column(valued):
    """Write one company's side of the comparison table: a dictionary of row label to the text shown."""
    company, dcf, multiples, overview = valued["company"], valued["dcf"], valued["multiples"], valued["overview"]
    price = company["share_price"]
    middle = None if multiples is None else multiples["median_price"]
    upside = None if dcf is None else dcf["upside"]
    share = None if dcf is None else valuation.terminal_value_share(dcf["pv_of_terminal_value"], dcf["enterprise_value"])
    return {
        "Current price": dollars(price),
        "DCF value per share": NOT_AVAILABLE if dcf is None else dollars(dcf["implied_share_price"]),
        "DCF upside / downside": NOT_AVAILABLE if upside is None else theme.change_text(upside),
        "Verdict": theme.VERDICT_LOOKS[valuation.verdict(upside, assumptions.VERDICT_THRESHOLD)][0],
        "Multiples value": NOT_AVAILABLE if middle is None else dollars(middle),
        "Multiples upside / downside": NOT_AVAILABLE if middle is None else theme.change_text(valuation.upside(middle, price)),
        "WACC": NOT_AVAILABLE if dcf is None else precise_percent(dcf["wacc"]),
        "Terminal value share of the DCF": NOT_AVAILABLE if share is None else f"{share:.0%}",
        "Market value": theme.money_short(overview["market_value"]),
        "Operating margin (last year)": percent_or_note(overview["operating_margin"]),
        "Revenue growth (last year)": percent_or_note(overview["revenue_growth"]),
        "P/E": multiple_or_note(overview["pe"]),
        "EV/EBITDA": multiple_or_note(overview["ev_ebitda"]),
        "Free cash flow yield": percent_or_note(overview["free_cash_flow_yield"]),
    }


def comparison_table(first, second):
    """Lay the two companies side by side: one row for each number, one column for each company, named by ticker."""
    return pd.DataFrame({
        first["company"]["ticker"]: compare_column(first),
        second["company"]["ticker"]: compare_column(second),
    })


def method_upsides(valued):
    """For each way of valuing a company in COMPARE_METHODS, how far its price is above (positive) or below (negative) the
    market price, as (label, upside, price); upside and price are None for a method with no answer, so the chart can skip it.
    """
    prices = {"dcf": None if valued["dcf"] is None else valued["dcf"]["implied_share_price"]}
    for _label, key in COMPARE_METHODS[1:]:
        prices[key] = None if valued["multiples"] is None else valued["multiples"][key]
    share_price = valued["company"]["share_price"]
    return [
        (label, None if prices[key] is None else valuation.upside(prices[key], share_price), prices[key])
        for label, key in COMPARE_METHODS
    ]


def compare_figure(first, second):
    """Draw each way of valuing the two companies as a bar of how far its price is above (right) or below (left) the
    company's own market price. Because each bar is measured against its own company's price, a $50 stock and a $500 stock
    can be compared. The first company is gold (the one on the page), the second cream; the numbers are written on the
    bars and the exact prices are in the hover, so colour is never the only signal.
    """
    figure = go.Figure()
    for valued, colour in ((first, theme.ACCENT), (second, theme.TEXT)):
        rows = [row for row in method_upsides(valued) if row[1] is not None]
        figure.add_trace(go.Bar(
            y=[label for label, _upside, _price in rows], x=[upside for _label, upside, _price in rows],
            name=valued["company"]["ticker"], orientation="h", marker={"color": colour},
            text=[theme.change_text(upside, digits=0) for _label, upside, _price in rows], textposition="outside",
            customdata=[dollars(price) for _label, _upside, price in rows],
            hovertemplate="<b>%{y}</b><br>" + valued["company"]["ticker"] + ": %{x:+.1%} (price %{customdata})<extra></extra>",
        ))
    figure.update_xaxes(tickformat="+.0%", zeroline=True, zerolinecolor=theme.GREY)
    figure.update_yaxes(autorange="reversed")
    theme.style_figure(figure, height=60 + 70 * len(COMPARE_METHODS))
    figure.update_layout(barmode="group", legend={"orientation": "h", "y": 1.08, "x": 0})
    return figure


def draw_compare(company, dcf, multiples, growth_shift, margin_shift, terminal_growth_rate, wacc_override, live_risk_free=None):
    """Draw the Compare tab: a box for a second company, then the two side by side in a table and in a chart of how far each
    way of valuing them is from their own market prices. Both get the same sliders and the same typed-in WACC, each its own
    figures and its own peers. A second company that cannot be found, or is the same as the first, says so.
    """
    st.subheader("Compare with another company")
    typed = st.text_input(
        "Second company ticker", key=COMPARE_KEY, placeholder="For example MSFT",
        help="The company to put next to " + company["company_name"] + ". It gets the same sliders and the same typed-in WACC as this one, "
        "its own figures and its own peers (the ones Yahoo suggests).",
    ).strip().upper()
    if not typed:
        st.caption("Type a second ticker to see the two side by side.")
        return
    if typed == company["ticker"]:
        st.caption(f"{typed} is the company already on the page. Type a different one.")
        return
    with st.spinner(f"Loading {typed}…"):
        try:
            second = value_for_compare(typed, growth_shift, margin_shift, terminal_growth_rate, wacc_override, live_risk_free)
        except ValueError as error:
            st.caption(f"Could not load {typed}. {error}")
            return
    first = {"company": company, "dcf": dcf, "multiples": multiples, "overview": company_overview(company), "dcf_error": None}
    draw_table(comparison_table(first, second))
    if second["dcf_error"] is not None:
        st.caption(f"No DCF for {typed}: {second['dcf_error']}")
    st.markdown("**How far each way of valuing them is from their own market price**", help=explanations.help_text("compare_chart"))
    st.plotly_chart(compare_figure(first, second), width="stretch", config=CHART_CONFIG)
    with reading_notes("compare"):
        st.caption(
            "Both companies get the same sliders, the same typed-in WACC and the same risk-free rate (if you set them), each its own figures and peers. Numbers "
            "marked last year are from the last full fiscal year. A comparison of models' outputs, not a recommendation."
        )


# The tabs read as the questions an equity research note answers, in that order: answer first, then the evidence
# (polish G, 24 Nov 2026). The short name on the left is how the code and the tests refer to each tab.
TAB_LABELS = {
    "Overview": "Where does the price sit?",
    "DCF": "What is it worth?",
    "Multiples": "What do peers say?",
    "Sensitivity": "How sure are we?",
    "Compare": "How does it compare?",
    "Explanations": "What do the terms mean?",
}
PAGE_TABS = list(TAB_LABELS.values())


def draw_page():
    """Draw the whole page: the search bar at the top, the answer-first header, the strip of sliders with its buttons
    (WACC and rates, Scenarios, and for companies other than Adobe, Peers and One-off items), then the header's
    notes, then five tabs: Overview (the football field, the overview numbers, the history, news and management), DCF
    (the DCF, what the market implies, scenarios, assumptions, the WACC build, the charts behind the number), Multiples,
    Sensitivity (both heatmaps) and Explanations (the glossary), and the footer. If the company cannot be found, draw
    the reason instead. If it was found but a DCF cannot be built (it lost money), draw the header, the reason and
    only the Overview and Explanations tabs.
    """
    load_link()
    ticker = draw_search_bar()
    header_area = st.container()                       # filled once the numbers are known, so the header sits above the sliders
    growth_shift, margin_shift, terminal_growth_rate, wacc_override, live_risk_free, tools = draw_sliders()
    scenario_settings = draw_scenario_boxes(tools)
    adjustment = 0.0
    load_error = None
    with st.spinner(f"Loading {ticker}…"):            # shown while the company, and its suggested peers, are fetched
        try:
            company, source_used = load_company(ticker)
            if is_base_case(company):
                peers, peer_notes = {key: company[key] for key in PEER_KEYS}, []      # Adobe's own peers
                peers["peer_operating_margin"] = load_adobe_peer_margins(peers["peer_tickers"])
            else:
                peers, peer_notes = draw_peer_box(company, tools)
                if peers is not None:
                    company = dict(company, **peers)
                adjustment = draw_adjustment_box(company, tools)
                company = apply_adjustment(company, adjustment)
            company = apply_live_risk_free(company, live_risk_free)
        except ValueError as error:
            load_error = error
    if load_error is not None:
        with header_area:
            draw_error(ticker, load_error)
        # Nothing to move on this page, so the sliders are hidden; they are still drawn, so they keep their settings
        # for when a company is found again.
        st.html(f"<style>.st-key-{STRIP_KEY} {{ display: none; }}</style>")
        return
    try:
        dcf_inputs = build_dcf_inputs(company, growth_shift, margin_shift)
        dcf, multiples = run_valuation(company, dcf_inputs, terminal_growth_rate, wacc_override)
        base_wacc = model_wacc(dcf_inputs)
        dcf_error = None
    except ValueError as error:
        # The company itself loaded, but a DCF cannot be built from its figures (a company that lost money
        # has no tax rate to start from). The overview and the history do not need one, so they are still drawn.
        dcf_inputs = dcf = multiples = base_wacc = None
        dcf_error = error
    overview = company_overview(company)

    prices = price_history_or_none(company)
    analysts = analyst_view_or_none(company)
    with header_area:
        draw_header(company, dcf, multiples, prices, dcf_inputs)
        with st.container(key=SOURCE_NOTE_KEY):            # styled as small quiet notes under the header (see theme.py)
            draw_source_note(company, source_used)
    note = adjustment_note(adjustment)
    if note:
        st.warning(note)
    with st.spinner("Loading the history and the last twelve months…"):      # shown under the header while they are fetched
        try:
            ttm, ttm_error = load_ttm(company["ticker"], company.get("usd_per_statement_unit", 1.0)), None
        except ValueError as error:
            ttm, ttm_error = None, str(error)
        try:
            history, history_error = load_history(company["ticker"], company.get("usd_per_statement_unit", 1.0)), None
        except ValueError as error:
            history, history_error = None, str(error)
    overview = apply_ttm(overview, company, apply_adjustment_to_ttm(ttm, adjustment), ttm_error)
    overview = apply_quality(overview, company, history)
    year_labels = assumptions.FORECAST_YEAR_LABELS if is_base_case(company) else assumptions.GENERIC_YEAR_LABELS
    if dcf_error is not None:
        # No DCF to draw, so only the tabs that do not need one: the overview (with the reason on top) and the glossary.
        overview_tab, explanations_tab = st.tabs([TAB_LABELS["Overview"], TAB_LABELS["Explanations"]])
        with overview_tab:
            draw_dcf_unavailable(ticker, dcf_error)
            draw_analyst_view(company, analysts, None)
            draw_overview(overview)
            draw_history(history, history_error, overview, company["company_name"])
            draw_news_and_management(company["ticker"])
            draw_macro_backdrop()
        with explanations_tab:
            draw_explanations_tab()
        draw_footer()
        return
    overview_tab, dcf_tab, multiples_tab, sensitivity_tab, compare_tab, explanations_tab = st.tabs(PAGE_TABS)
    with overview_tab:
        draw_football_field(company, dcf, multiples, dcf_inputs, base_wacc, prices, analysts)
        draw_analyst_view(company, analysts, dcf["implied_share_price"])
        draw_overview(overview)
        draw_history(history, history_error, overview, company["company_name"])
        draw_news_and_management(company["ticker"])
        draw_macro_backdrop()
    with dcf_tab:
        draw_dcf(company, dcf, wacc_override is not None, terminal_growth_rate)
        draw_reverse_dcf(company, dcf_inputs, terminal_growth_rate, wacc_override, history)
        draw_scenarios(company, dcf_inputs, terminal_growth_rate, wacc_override, scenario_settings)
        draw_assumptions(
            company, dcf_inputs, year_labels, dcf, terminal_growth_rate, wacc_override is not None,
            growth_shift, margin_shift,
        )
        draw_wacc_build(company, dcf_inputs, source_used, dcf, wacc_override is not None)
        draw_charts(dcf, year_labels, terminal_growth_rate, dcf_inputs["operating_margins"], history)
    with multiples_tab:
        draw_multiples(
            multiples, peers, peer_notes, peers_are_suggested=not is_base_case(company),
            own_label=f"{company['ticker']} (this company)", overview=overview,
            company_name=company["company_name"],
        )
    with sensitivity_tab:
        draw_heatmap(company, dcf_inputs, base_wacc)
        draw_margin_growth_table(company, dcf_inputs, dcf, terminal_growth_rate, wacc_override)
    with compare_tab:
        draw_compare(company, dcf, multiples, growth_shift, margin_shift, terminal_growth_rate, wacc_override, live_risk_free)
    with explanations_tab:
        draw_explanations_tab()
    draw_footer()


st.set_page_config(page_title="Valuation Lab", page_icon="📈")
theme.inject_theme()
bridge_fmp_key()
bridge_fred_key()
draw_page()
write_link()
