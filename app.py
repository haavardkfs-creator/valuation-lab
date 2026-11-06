"""The Valuation Lab page: shows Adobe's DCF and multiples results.

This file only draws. It fetches the figures with data.py, takes the assumptions from
assumptions.py, hands both to valuation.py, and puts what comes back on the page (guard
rail 5). Run it with: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import assumptions
import data
import valuation

# The company on the page. Phase 4 shows one company; choosing a ticker comes later.
TICKER = "ADBE"

# Heatmap colours, as red/green/blue numbers. Chosen for a calm, professional look: a price
# at the market price is white, and the further above it the greener, the further below it
# the redder. Prices 50% or more away from the market price get the full tint.
HEATMAP_GREEN = (46, 139, 87)
HEATMAP_RED = (192, 57, 43)
HEATMAP_FULL_TINT_GAP = 0.5
HEATMAP_STRONGEST_TINT = 0.7        # below 1 so the numbers stay easy to read on top

# Guard rail 13: the footer every page of the app must show.
FOOTER_TEXT = "Valuation Lab is a learning project, not investment advice."


def dollars(amount):
    """Write a number as a dollar price with two decimals, for example $305.60."""
    return f"${amount:,.2f}"


def percent(rate):
    """Write a decimal rate as a percentage with one decimal, for example 0.215 as 21.5%."""
    return f"{rate:.1%}"


def precise_percent(rate):
    """Write a decimal rate as a percentage with two decimals, for example 0.1093 as 10.93%."""
    return f"{rate:.2%}"


def build_dcf_inputs(company, growth_shift, margin_shift):
    """Gather every input the DCF needs except the terminal growth rate and the WACC.

    The growth and margin shifts move every forecast year by the same amount (0 means the
    base case). The same inputs feed both the headline DCF and the heatmap.
    """
    return dict(
        base_revenue=company["revenue"],
        growth_rates=valuation.shift_rates(assumptions.GROWTH_RATES, growth_shift),
        operating_margins=valuation.shift_rates(assumptions.OPERATING_MARGINS, margin_shift),
        tax_rate=assumptions.TAX_RATE,
        da_pcts=assumptions.DA_PCTS,
        capex_pcts=assumptions.CAPEX_PCTS,
        wc_pcts=assumptions.WC_PCTS,
        risk_free_rate=company["risk_free_rate"],
        beta=company["beta"],
        equity_risk_premium=company["equity_risk_premium"],
        pre_tax_cost_of_debt=company["pre_tax_cost_of_debt"],
        share_price=company["share_price"],
        shares=company["shares"],
        debt=company["debt"],
        cash_and_investments=company["cash_and_investments"],
    )


def run_valuation(company, dcf_inputs, terminal_growth_rate):
    """Run the DCF and the multiples comparison for one company's figures.

    Returns the DCF results and the multiples results, each as a dictionary of named
    numbers. The multiples need the DCF's net debt and implied price, so the DCF runs first.
    """
    dcf = valuation.run_full_dcf(**dcf_inputs, terminal_growth_rate=terminal_growth_rate)
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


def draw_sliders():
    """Draw the three sliders in the sidebar and return what they are set to: the growth
    shift, the margin shift and the terminal growth rate. Each starts at the base case.
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
    return growth_shift, margin_shift, terminal_growth_rate


def draw_dcf(company, dcf):
    """Draw the DCF section: the implied price next to the market price, the upside, and WACC."""
    st.subheader("Discounted cash flow (DCF)")
    price_column, market_column, upside_column, wacc_column = st.columns(4)
    price_column.metric("DCF implied price", dollars(dcf["implied_share_price"]))
    market_column.metric("Market price", dollars(company["share_price"]))
    upside_column.metric("Upside vs market", percent(dcf["upside"]))
    wacc_column.metric("WACC", percent(dcf["wacc"]))


def tint(price, market_price):
    """Pick a background colour for one heatmap cell: white at the market price, greener the
    further above it, redder the further below it.
    """
    gap = (price - market_price) / market_price
    strength = min(abs(gap) / HEATMAP_FULL_TINT_GAP, 1) * HEATMAP_STRONGEST_TINT
    target = HEATMAP_GREEN if gap >= 0 else HEATMAP_RED
    red, green, blue = (round(255 + (colour - 255) * strength) for colour in target)
    return f"background-color: rgb({red}, {green}, {blue}); color: #262730"


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


def draw_page():
    """Draw the whole page: sliders, title, DCF section, heatmap, multiples section and footer."""
    company = data.get_company_data(TICKER)
    growth_shift, margin_shift, terminal_growth_rate = draw_sliders()
    dcf_inputs = build_dcf_inputs(company, growth_shift, margin_shift)
    dcf, multiples = run_valuation(company, dcf_inputs, terminal_growth_rate)

    st.title("Valuation Lab")
    st.write(f"{company['company_name']} ({company['ticker']})")
    draw_dcf(company, dcf)
    draw_heatmap(company, dcf_inputs, dcf["wacc"])
    draw_multiples(multiples)
    st.divider()
    st.caption(FOOTER_TEXT)


st.set_page_config(page_title="Valuation Lab")
draw_page()
