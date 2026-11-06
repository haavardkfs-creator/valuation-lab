"""The Valuation Lab page: shows a company's DCF (and, for Adobe, its multiples results).

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
    """Write a decimal rate as a percentage with one decimal, for example 0.215 as 21.5%."""
    return f"{rate:.1%}"


def precise_percent(rate):
    """Write a decimal rate as a percentage with two decimals, for example 0.1093 as 10.93%."""
    return f"{rate:.2%}"


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
    growth_shift = st.sidebar.slider(
        "Revenue growth, every year",
        min_value=assumptions.GROWTH_SHIFT_MIN,
        max_value=assumptions.GROWTH_SHIFT_MAX,
        value=0.0,
        step=assumptions.GROWTH_SHIFT_STEP,
        format="percent",
        help="Moves every forecast year's growth up or down by the same amount. 0% is the base case.",
    )
    margin_shift = st.sidebar.slider(
        "Operating margin, every year",
        min_value=assumptions.MARGIN_SHIFT_MIN,
        max_value=assumptions.MARGIN_SHIFT_MAX,
        value=0.0,
        step=assumptions.MARGIN_SHIFT_STEP,
        format="percent",
        help="Moves every forecast year's operating margin up or down by the same amount. 0% is the base case.",
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
    return growth_shift, margin_shift, terminal_growth_rate, wacc_override


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


def draw_charts(dcf, year_labels):
    """Draw the two charts behind the headline price: the five-year forecast of revenue and
    free cash flow (one label per forecast year), and the two parts that enterprise value is
    built from.
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
        f"terminal value (\\${dcf['pv_of_terminal_value']:,.0f} million), both discounted to today."
    )
    draw_explanations("behind_the_number")


def draw_heatmap(company, dcf_inputs, base_wacc):
    """Draw the sensitivity heatmap: the implied share price at different WACCs (down the
    side) and terminal growth rates (along the top), coloured against the market price.
    """
    table = valuation.sensitivity_table(
        dcf_inputs,
        base_wacc,
        assumptions.HEATMAP_WACC_OFFSETS,
        assumptions.HEATMAP_TERMINAL_GROWTH_RATES,
    )
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

    st.subheader("Sensitivity: price at different WACC and terminal growth")
    st.dataframe(
        prices.style.apply(style_cells, axis=None).format(dollars),
        width="stretch",
    )
    st.caption(
        f"Green means above today's market price of {dollars(company['share_price'])}, red below it. "
        "The bold price is the base case. The growth and margin sliders move the whole table."
    )
    draw_explanations("sensitivity")


def draw_multiples(multiples):
    """Draw the multiples section: the price each peer multiple gives, their middle value,
    and how far the DCF price is from it.
    """
    st.subheader("Peer multiples")
    sales_column, ebitda_column, pe_column = st.columns(3)
    sales_column.metric("EV/Sales price", dollars(multiples["price_ev_sales"]))
    ebitda_column.metric("EV/EBITDA price", dollars(multiples["price_ev_ebitda"]))
    pe_column.metric("P/E price", dollars(multiples["price_pe"]))
    median_column, gap_column = st.columns(2)
    median_column.metric("Middle of the three", dollars(multiples["median_price"]))
    gap_column.metric("DCF vs multiples", percent(multiples["dcf_vs_multiples"]))
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


def draw_ticker_box():
    """Draw the company ticker box at the top of the sidebar and return the ticker typed in,
    in capitals. An empty box means the default company.
    """
    typed = st.sidebar.text_input(
        "Company ticker",
        value=DEFAULT_TICKER,
        help="A US stock ticker, for example MSFT. Adobe (ADBE) has hand-chosen assumptions and peer multiples; any other company gets a starting point from its own last reported year.",
    )
    return typed.strip().upper() or DEFAULT_TICKER


def draw_source_note(company, source_used):
    """Tell the reader where the figures came from and, for any company other than Adobe,
    that this is a starting point and not a forecast.

    Adobe: a quiet line when the share price and beta are live, a visible warning when the
    page had to fall back to the frozen snapshot. Other companies: a quiet line, and a visible
    warning that the forecast is only a starting point.
    """
    if source_used == "yahoo":
        st.caption("All figures are from Yahoo Finance's latest annual statements.")
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
    """Draw the whole page: ticker box, sliders, title, DCF section, charts, heatmap, multiples
    (Adobe only) and footer. If the company cannot be valued, draw the reason instead.
    """
    ticker = draw_ticker_box()
    growth_shift, margin_shift, terminal_growth_rate, wacc_override = draw_sliders()
    try:
        company, source_used = load_company(ticker)
        dcf_inputs = build_dcf_inputs(company, growth_shift, margin_shift)
        dcf, multiples = run_valuation(company, dcf_inputs, terminal_growth_rate, wacc_override)
        base_wacc = model_wacc(dcf_inputs)
    except ValueError as error:
        draw_error(ticker, error)
        return

    st.title("Valuation Lab")
    st.write(f"{company['company_name']} ({company['ticker']})")
    draw_source_note(company, source_used)
    draw_dcf(company, dcf, wacc_override is not None)
    year_labels = assumptions.FORECAST_YEAR_LABELS if is_base_case(company) else assumptions.GENERIC_YEAR_LABELS
    draw_charts(dcf, year_labels)
    draw_heatmap(company, dcf_inputs, base_wacc)
    if multiples is not None:
        draw_multiples(multiples)
    st.divider()
    st.caption(FOOTER_TEXT)


st.set_page_config(page_title="Valuation Lab")
draw_page()
