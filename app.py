"""The Valuation Lab page: shows a company's DCF and its peer multiples.

This file only draws. It fetches the figures with data.py, takes the assumptions from
assumptions.py, hands both to valuation.py, and puts what comes back on the page (guard
rail 5). Run it with: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import assumptions
import data
import explanations
import valuation

# The company the page opens on, and the only one with hand-chosen assumptions and peer multiples.
DEFAULT_TICKER = assumptions.BASE_CASE_TICKER

# Heatmap colours, as red/green/blue numbers. Chosen for a calm, professional look: a price
# at the market price is white, and the further above it the greener, the further below it
# the redder. Prices 50% or more away from the market price get the full tint.
HEATMAP_GREEN = (46, 139, 87)
HEATMAP_RED = (192, 57, 43)
HEATMAP_FULL_TINT_GAP = 0.5
HEATMAP_STRONGEST_TINT = 0.7        # below 1 so the numbers stay easy to read on top

# Chart colours: the theme blue from .streamlit/config.toml, and a lighter blue to sit beside it.
CHART_BLUE = "#2E5077"
CHART_LIGHT_BLUE = "#8FB0D1"

# The four figures that make up a company's peers in a data package.
PEER_KEYS = ["peer_tickers", "peer_ev_sales", "peer_ev_ebitda", "peer_pe"]

# Guard rail 13: the footer every page of the app must show.
FOOTER_TEXT = "Valuation Lab is a learning project, not investment advice."

# How long the page remembers Yahoo's answer. Streamlit reruns the whole page on every
# slider move, so without this each move would ask Yahoo again. 15 minutes is a judgment
# call agreed with Haavard, not a rule from Yahoo.
LIVE_DATA_CACHE_SECONDS = 15 * 60


def dollars(amount):
    """Write a number as a dollar price with two decimals, for example $305.60."""
    return f"${amount:,.2f}"


def percent(rate):
    """Write a decimal rate as a percentage with one decimal, for example 0.215 as 21.5%. A rate
    too small to show is written 0.0%, never -0.0%.
    """
    text = f"{rate:.1%}"
    return "0.0%" if text == "-0.0%" else text


def precise_percent(rate):
    """Write a decimal rate as a percentage with two decimals, for example 0.1093 as 10.93%. A rate
    too small to show is written 0.00%, never -0.00%.
    """
    text = f"{rate:.2%}"
    return "0.00%" if text == "-0.00%" else text


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
        ratios, assumptions.TERMINAL_GROWTH_RATE, assumptions.STARTING_POINT_YEARS
    )


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
        beta=company["beta"],
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


def draw_sliders():
    """Draw the sliders in the sidebar and return what they are set to: the growth shift,
    the margin shift, the terminal growth rate and the WACC the user chose (None when the
    box is unticked, meaning the model uses its own). Each starts at the base case.
    """
    st.sidebar.header("Change the assumptions")
    growth_points = st.sidebar.slider(
        "Revenue growth: change every year by",
        min_value=assumptions.GROWTH_SHIFT_MIN_POINTS,
        max_value=assumptions.GROWTH_SHIFT_MAX_POINTS,
        value=0.0,
        step=assumptions.GROWTH_SHIFT_STEP_POINTS,
        format="%+.1f pts",
        help="Adds this many percentage points to every forecast year's growth. 0 is the base case; the table 'What the model assumes' shows the result.",
    )
    margin_points = st.sidebar.slider(
        "Operating margin: change every year by",
        min_value=assumptions.MARGIN_SHIFT_MIN_POINTS,
        max_value=assumptions.MARGIN_SHIFT_MAX_POINTS,
        value=0.0,
        step=assumptions.MARGIN_SHIFT_STEP_POINTS,
        format="%+.1f pts",
        help="Adds this many percentage points to every forecast year's operating margin. 0 is the base case; the table 'What the model assumes' shows the result.",
    )
    terminal_growth_rate = st.sidebar.slider(
        "Terminal growth",
        min_value=assumptions.TERMINAL_GROWTH_MIN,
        max_value=assumptions.TERMINAL_GROWTH_MAX,
        value=assumptions.TERMINAL_GROWTH_RATE,
        step=assumptions.TERMINAL_GROWTH_STEP,
        format="percent",
        help="How fast cash flow is assumed to grow forever after year 5. The base case is 2.5%.",
    )
    wacc_override = None
    if st.sidebar.checkbox(
        "Set the WACC myself",
        help="Unticked, the model works out its own WACC from the company's figures. Ticked, the slider sets it.",
    ):
        wacc_override = st.sidebar.slider(
            "WACC",
            min_value=assumptions.WACC_SLIDER_MIN,
            max_value=assumptions.WACC_SLIDER_MAX,
            value=assumptions.WACC_SLIDER_START,
            step=assumptions.WACC_SLIDER_STEP,
            format="percent",
            help="The rate that cash flows are discounted at. Higher means a lower price.",
        )
    return shift_from_points(growth_points), shift_from_points(margin_points), terminal_growth_rate, wacc_override


def draw_explanations(section):
    """Draw a closed box that explains, in plain language, the terms used in one section of
    the page. The wording comes from explanations.py.
    """
    with st.expander("What do these terms mean?"):
        for term in explanations.SECTION_TERMS[section]:
            title, text = explanations.EXPLANATIONS[term]
            st.markdown(f"**{title}**  \n{text}")


def draw_dcf(company, dcf, wacc_is_set_by_user):
    """Draw the DCF section: the implied price next to the market price, the upside, and WACC
    (labelled as the user's own when it comes from the slider).
    """
    st.subheader("Discounted cash flow (DCF)")
    price_column, market_column, upside_column, wacc_column = st.columns(4)
    price_column.metric("DCF implied price", dollars(dcf["implied_share_price"]))
    market_column.metric("Market price", dollars(company["share_price"]))
    upside_column.metric("Upside vs market", percent(dcf["upside"]))
    wacc_column.metric("WACC (your setting)" if wacc_is_set_by_user else "WACC", percent(dcf["wacc"]))
    draw_explanations("dcf")


def tint(price, market_price):
    """Pick a background colour for one heatmap cell: white at the market price, greener the
    further above it, redder the further below it.
    """
    gap = (price - market_price) / market_price
    strength = min(abs(gap) / HEATMAP_FULL_TINT_GAP, 1) * HEATMAP_STRONGEST_TINT
    target = HEATMAP_GREEN if gap >= 0 else HEATMAP_RED
    red, green, blue = (round(255 + (colour - 255) * strength) for colour in target)
    return f"background-color: rgb({red}, {green}, {blue}); color: #262730"


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
    )


def percent_or_note(rate):
    """Write a rate as a percentage, or say it is not meaningful when it could not be worked out."""
    return NOT_MEANINGFUL if rate is None else percent(rate)


def multiple_or_note(multiple, decimals=1):
    """Write a multiple such as 14.6x, or say it is not meaningful when it could not be worked out."""
    return NOT_MEANINGFUL if multiple is None else f"{multiple:.{decimals}f}x"


def draw_overview(overview):
    """Draw the overview: how fast the company is growing, what it earns, how much cash it
    makes for its price and how heavy its debt is, then what the market pays for it.
    """
    st.subheader("Overview")
    growth, margin, cash_yield, leverage = st.columns(4)
    growth.metric("Revenue growth", percent_or_note(overview["revenue_growth"]), help="Last full year's revenue compared with the year before.")
    margin.metric("Operating margin", percent_or_note(overview["operating_margin"]), help="Operating profit (EBIT) as a share of revenue, last full year.")
    cash_yield.metric("Free cash flow yield", percent_or_note(overview["free_cash_flow_yield"]), help="Last full year's free cash flow divided by what the market says the company is worth.")
    leverage.metric("Net debt ÷ EBITDA", multiple_or_note(overview["net_debt_to_ebitda"], 2), help="Years of operating profit (before depreciation) needed to pay off net debt. Below 0 means more cash than debt.")
    sales, ebitda, pe = st.columns(3)
    sales.metric("EV/Sales", multiple_or_note(overview["ev_sales"]), help="Enterprise value (what the whole business is worth at today's price) divided by revenue.")
    ebitda.metric("EV/EBITDA", multiple_or_note(overview["ev_ebitda"]), help="Enterprise value divided by operating profit before depreciation and amortisation.")
    pe.metric("P/E", multiple_or_note(overview["pe"]), help="What the market pays for each dollar of the last full year's net income.")
    st.caption(
        "Worked out from the company's last full year of figures and today's share price. A number "
        "that would mean nothing (no P/E for a company that lost money) says so."
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
    return f"{shift * 100 + 0.0:+.1f} points"


def draw_assumptions(company, dcf_inputs, year_labels, dcf, terminal_growth_rate, wacc_is_set_by_user, growth_shift, margin_shift):
    """Draw "What the model assumes": the table of the numbers the DCF really uses, then one line
    with the terminal growth rate, the WACC and what the sliders are changing, so a slider's
    value is never mistaken for the assumption itself.
    """
    st.subheader("What the model assumes")
    st.dataframe(assumptions_table(dcf_inputs, year_labels))
    if is_base_case(company):
        where_from = "Adobe's assumptions are hand-chosen (the Projection sheet in the Excel model)."
    else:
        where_from = (
            "These are a starting point worked out from the company's own last reported year, "
            "not a forecast (see the note under the title)."
        )
    whose_wacc = "the WACC you set" if wacc_is_set_by_user else "the model's own WACC"
    st.caption(
        f"{where_from} After year 5, cash flow grows {precise_percent(terminal_growth_rate)} a "
        f"year for ever, discounted at {precise_percent(dcf['wacc'])} ({whose_wacc}). The sliders "
        f"are changing growth by {points_text(growth_shift)} and operating margin by "
        f"{points_text(margin_shift)} in every year; at +0.0 points the table is the base case."
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


def draw_charts(dcf, year_labels, terminal_growth_rate):
    """Draw the two charts behind the headline price: the five-year forecast of revenue and
    free cash flow (one label per forecast year), and the two parts that enterprise value is
    built from, with a caution when the price rests mostly on the far future.
    """
    st.subheader("Behind the number")
    forecast_column, build_column = st.columns([3, 2])

    forecast = pd.DataFrame(
        {"Revenue": dcf["revenues"], "Free cash flow": dcf["free_cash_flows"]},
        index=year_labels,
    )
    forecast_column.markdown("**Forecast: revenue and free cash flow**")
    forecast_column.bar_chart(
        forecast,
        stack=False,
        color=[CHART_BLUE, CHART_LIGHT_BLUE],
        y_label="$ millions",
    )

    build = pd.DataFrame(
        {"Present value ($ millions)": [dcf["pv_of_forecast"], dcf["pv_of_terminal_value"]]},
        index=["Years 1-5", "Terminal"],
    )
    build_column.markdown("**What the company is worth today**")
    build_column.bar_chart(
        build,
        sort=False,
        color=CHART_BLUE,
        y_label="$ millions",
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
    draw_explanations("behind_the_number")


def draw_heatmap(company, dcf_inputs, base_wacc):
    """Draw the sensitivity heatmap: the implied share price at different WACCs (down the
    side) and terminal growth rates (along the top), coloured against the market price.
    """
    st.subheader("Sensitivity: price at different WACC and terminal growth")
    try:
        table = valuation.sensitivity_table(
            dcf_inputs,
            base_wacc,
            assumptions.HEATMAP_WACC_OFFSETS,
            assumptions.HEATMAP_TERMINAL_GROWTH_RATES,
        )
    except ValueError:
        # A low WACC (for a company with a low beta) can sit within a point of the highest
        # terminal growth rate, where the formula has no answer. The headline DCF is fine.
        st.caption(
            f"This table cannot be drawn: this company's WACC ({percent(base_wacc)}) is too close to "
            "the terminal growth rates in the table for the formula to give an answer."
        )
        return
    prices = pd.DataFrame(
        table["prices"],
        index=pd.Index([precise_percent(rate) for rate in table["wacc_rates"]], name="WACC"),
        columns=pd.Index(
            [percent(rate) for rate in table["terminal_growth_rates"]], name="Terminal growth"
        ),
    )
    base_row = assumptions.HEATMAP_WACC_OFFSETS.index(0.0)
    base_column = assumptions.HEATMAP_TERMINAL_GROWTH_RATES.index(assumptions.TERMINAL_GROWTH_RATE)

    def style_cells(values):
        """Colour every cell and put the base case in bold."""
        styles = values.map(lambda price: tint(price, company["share_price"]))
        styles.iloc[base_row, base_column] += "; font-weight: bold"
        return styles

    st.dataframe(
        prices.style.apply(style_cells, axis=None).format(dollars),
        width="stretch",
    )
    st.caption(
        f"Green means above today's market price of {dollars(company['share_price'])}, red below it. "
        "The bold price is the base case. The growth and margin sliders move the whole table."
    )
    draw_explanations("sensitivity")


def price_or_note(price):
    """Write a price in dollars, or say there were not enough peers to work one out."""
    return "Not enough peers" if price is None else dollars(price)


def peer_table(peers, own_label, overview, multiples):
    """Make the table of the peers and what each one has: three multiples and an operating
    margin, as text. The company itself comes first, so it can be compared at a glance, and the
    peer medians come last.

    A peer multiple that is missing, or zero or negative, shows as a dash because it is left out
    of the median; an operating margin shows as a dash only when it is missing, since a negative
    margin is real information. `multiples` is the result of run_multiples, which holds the medians.
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
            "Op. margin": (
                [show_margin(overview["operating_margin"])]
                + [show_margin(margin) for margin in peers["peer_operating_margin"]]
                + [show_margin(median_margin)]
            ),
        },
        index=pd.Index(rows, name="Company"),
    )


def draw_multiples(multiples, peers, notes, peers_are_suggested, own_label, overview):
    """Draw the multiples section: the price each peer multiple gives, their middle value, how
    far the DCF price is from it, and the table of peers behind them.

    `multiples` is None when there are no peers to compare with, and then the section says how
    to add some. A price that could not be worked out (too few peers with that multiple) says
    so. `notes` are the messages from the peer box, and peers_are_suggested says whether to
    point out that the peers were suggested by Yahoo's industry list. `own_label` and `overview`
    put the company itself in the table.
    """
    st.subheader("Peer multiples")
    for kind, text in notes:
        (st.warning if kind == "warning" else st.caption)(text)
    if multiples is None:
        draw_explanations("multiples")
        return
    sales_column, ebitda_column, pe_column = st.columns(3)
    sales_column.metric("EV/Sales price", price_or_note(multiples["price_ev_sales"]))
    ebitda_column.metric("EV/EBITDA price", price_or_note(multiples["price_ev_ebitda"]))
    pe_column.metric("P/E price", price_or_note(multiples["price_pe"]))
    median_column, gap_column = st.columns(2)
    median_column.metric("Middle of the prices", price_or_note(multiples["median_price"]))
    gap = multiples["dcf_vs_multiples"]
    gap_column.metric("DCF vs multiples", "Not available" if gap is None else percent(gap))
    st.dataframe(peer_table(peers, own_label, overview, multiples))
    st.caption(
        f"Each multiple needs at least {assumptions.MINIMUM_PEERS} peers with a usable figure; "
        "a peer with no figure (a dash) is left out of that multiple only. A negative operating "
        "margin counts, because a loss is real information. The company's own row comes from its "
        "last full year and today's price; the peers' figures are Yahoo's trailing twelve months, "
        "so small differences are expected."
    )
    if peers_are_suggested:
        st.caption(
            "Peers suggested from Yahoo's industry list, closest in size. Closest in size is "
            "not the same as most similar business, so change them in the sidebar if you know better."
        )
    draw_explanations("multiples")


@st.cache_data(ttl=LIVE_DATA_CACHE_SECONDS, show_spinner=False)
def load_company(ticker):
    """Fetch a company's figures and remember them for LIVE_DATA_CACHE_SECONDS, so moving a
    slider does not ask Yahoo again.

    Adobe comes from the live source, falling back to the snapshot if Yahoo fails. Any other
    company comes from Yahoo's statements, with no fallback. Returns the package of figures
    and the name of the source that supplied it; stops with a plain error if it cannot.
    """
    if ticker == assumptions.BASE_CASE_TICKER:
        return data.get_company_data_with_fallback(ticker)
    return data.get_company_data(ticker, source="yahoo"), "yahoo"


@st.cache_data(ttl=LIVE_DATA_CACHE_SECONDS, show_spinner=False)
def load_suggested_peers(ticker, market_value):
    """Ask Yahoo for suggested peers for a company and remember the answer for
    LIVE_DATA_CACHE_SECONDS. The market value is in $ millions. Stops with a plain error if
    Yahoo cannot be reached.
    """
    return data.suggest_peers(
        ticker,
        market_value,
        assumptions.PEER_CANDIDATES_TO_CHECK,
        assumptions.PEER_BIGGEST_SIZE_GAP,
        assumptions.SUGGESTED_PEERS,
    )


@st.cache_data(ttl=LIVE_DATA_CACHE_SECONDS, show_spinner=False)
def load_peer_multiples(tickers):
    """Fetch the multiples of the peers in the box (a tuple of tickers) and remember them for
    LIVE_DATA_CACHE_SECONDS. Stops with a plain error if Yahoo cannot be reached.
    """
    return data.peer_multiples(list(tickers))


def load_adobe_peer_margins(tickers):
    """Get the operating margins of Adobe's hand-chosen peers from Yahoo (its snapshot of the
    Excel model has none). Returns a list in the same order, or all blanks if Yahoo cannot be
    reached, so the table still draws.
    """
    try:
        return load_peer_multiples(tuple(tickers))["peer_operating_margin"]
    except ValueError:
        return [None] * len(tickers)


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


def draw_peer_box(company):
    """Draw the peer ticker box in the sidebar, filled in with suggestions from Yahoo's
    industry list the first time a company is shown (the reader can change them), and fetch
    the multiples of the peers in it.

    Returns the peers' figures (None when the box is empty or Yahoo failed) and a list of notes
    for the multiples section, each a pair: "warning" or "caption", and its text.
    """
    notes = []
    market_value = round(company["share_price"] * company["shares"])
    try:
        suggested = load_suggested_peers(company["ticker"], market_value)["peer_tickers"]
    except ValueError as error:
        suggested = []
        notes.append(("warning", f"{error} Type peer tickers in the sidebar yourself."))

    st.sidebar.header("Peers")
    typed = st.sidebar.text_input(
        "Peer tickers",
        value=", ".join(suggested),
        key=f"peers_{company['ticker']}",      # one box per company, so peers are not carried over
        help=(
            "Companies to compare with, separated by commas. Suggested from Yahoo's industry "
            f"list, closest in size; change them as you like (up to {assumptions.MAX_TYPED_PEERS})."
        ),
    )
    tickers, cut_off = parse_peer_tickers(typed, company["ticker"], assumptions.MAX_TYPED_PEERS)
    if cut_off:
        notes.append(("caption", f"Only the first {assumptions.MAX_TYPED_PEERS} peers are used."))
    if not tickers:
        if not any(kind == "warning" for kind, _ in notes):
            notes.append((
                "caption",
                "No suitable peers were found in Yahoo's industry list for this company. "
                "Type at least 2 peer tickers in the sidebar to compare with peers.",
            ))
        return None, notes
    try:
        figures = load_peer_multiples(tuple(tickers))
    except ValueError as error:
        notes.append(("warning", str(error)))
        return None, notes
    unknown = [
        ticker
        for ticker, sales, ebitda, pe in zip(
            figures["peer_tickers"], figures["peer_ev_sales"], figures["peer_ev_ebitda"], figures["peer_pe"]
        )
        if sales is None and ebitda is None and pe is None
    ]
    if unknown:
        notes.append((
            "caption",
            f"Yahoo Finance has no multiples for {', '.join(unknown)}. Check the ticker.",
        ))
    return figures, notes


def draw_ticker_box():
    """Draw the company ticker box at the top of the sidebar and return the ticker typed in,
    in capitals. An empty box means the default company.
    """
    typed = st.sidebar.text_input(
        "Company ticker",
        value=DEFAULT_TICKER,
        help="A US stock ticker, for example MSFT. Adobe (ADBE) has hand-chosen assumptions and peers; any other company gets a starting point from its own last reported year and suggested peers.",
    )
    return typed.strip().upper() or DEFAULT_TICKER


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
    if source_used == "yahoo":
        st.caption("All figures are from Yahoo Finance's latest annual statements.")
        conversion = currency_note(company)
        if conversion:
            st.caption(conversion)
        if company.get("cost_of_debt_is_fallback"):
            st.warning(
                f"Yahoo Finance has no interest expense for {company['company_name']}, so its cost "
                f"of debt ({precise_percent(company['pre_tax_cost_of_debt'])}) is an estimate: the "
                f"risk-free rate plus a typical credit spread of {precise_percent(data.CREDIT_SPREAD)}."
            )
        st.warning(
            f"Starting point, not a forecast: this starts from {company['company_name']}'s own "
            "last reported year and holds its margins flat. A DCF suits stable, cash-generating "
            "companies, and is a poor fit for banks, loss-making and early-stage ones."
        )
    elif source_used == data.PREFERRED_SOURCE:
        st.caption("Share price and beta are live from Yahoo Finance.")
    else:
        st.warning(
            "Yahoo Finance could not be reached, so share price and beta come from a "
            "frozen snapshot."
        )


def draw_error(ticker, error):
    """Show why a company could not be valued, in plain words, and still show the footer."""
    st.title("Valuation Lab")
    st.error(f"Could not value {ticker}. {error}")
    st.divider()
    st.caption(FOOTER_TEXT)


def draw_page():
    """Draw the whole page: ticker box, sliders, peer box (companies other than Adobe), title,
    DCF section, overview, assumptions, charts, heatmap, multiples and footer. If the company cannot be valued, draw
    the reason instead.
    """
    ticker = draw_ticker_box()
    growth_shift, margin_shift, terminal_growth_rate, wacc_override = draw_sliders()
    try:
        company, source_used = load_company(ticker)
        if is_base_case(company):
            peers, peer_notes = {key: company[key] for key in PEER_KEYS}, []      # Adobe's own peers
            peers["peer_operating_margin"] = load_adobe_peer_margins(peers["peer_tickers"])
        else:
            peers, peer_notes = draw_peer_box(company)
            if peers is not None:
                company = dict(company, **peers)
        dcf_inputs = build_dcf_inputs(company, growth_shift, margin_shift)
        dcf, multiples = run_valuation(company, dcf_inputs, terminal_growth_rate, wacc_override)
        base_wacc = model_wacc(dcf_inputs)
        overview = company_overview(company)
    except ValueError as error:
        draw_error(ticker, error)
        return

    st.title("Valuation Lab")
    st.write(f"{company['company_name']} ({company['ticker']})")
    draw_source_note(company, source_used)
    draw_dcf(company, dcf, wacc_override is not None)
    draw_overview(overview)
    year_labels = assumptions.FORECAST_YEAR_LABELS if is_base_case(company) else assumptions.GENERIC_YEAR_LABELS
    draw_assumptions(
        company, dcf_inputs, year_labels, dcf, terminal_growth_rate, wacc_override is not None,
        growth_shift, margin_shift,
    )
    draw_charts(dcf, year_labels, terminal_growth_rate)
    draw_heatmap(company, dcf_inputs, base_wacc)
    draw_multiples(
        multiples, peers, peer_notes, peers_are_suggested=not is_base_case(company),
        own_label=f"{company['ticker']} (this company)", overview=overview,
    )
    st.divider()
    st.caption(FOOTER_TEXT)


st.set_page_config(page_title="Valuation Lab")
draw_page()
