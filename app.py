"""The Valuation Lab page: shows Adobe's DCF and multiples results.

This file only draws. It fetches the figures with data.py, takes the assumptions from
assumptions.py, hands both to valuation.py, and puts what comes back on the page (guard
rail 5). Run it with: streamlit run app.py
"""

import streamlit as st

import assumptions
import data
import valuation

# The company on the page. Phase 4 shows one company; choosing a ticker comes later.
TICKER = "ADBE"

# Guard rail 13: the footer every page of the app must show.
FOOTER_TEXT = "Valuation Lab is a learning project, not investment advice."


def dollars(amount):
    """Write a number as a dollar price with two decimals, for example $305.60."""
    return f"${amount:,.2f}"


def percent(rate):
    """Write a decimal rate as a percentage with one decimal, for example 0.215 as 21.5%."""
    return f"{rate:.1%}"


def run_valuation(company):
    """Run the DCF and the multiples comparison for one company's figures.

    Returns the DCF results and the multiples results, each as a dictionary of named
    numbers. The multiples need the DCF's net debt and implied price, so the DCF runs first.
    """
    dcf = valuation.run_full_dcf(
        base_revenue=company["revenue"],
        growth_rates=assumptions.GROWTH_RATES,
        operating_margins=assumptions.OPERATING_MARGINS,
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
        terminal_growth_rate=assumptions.TERMINAL_GROWTH_RATE,
    )
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


def draw_dcf(company, dcf):
    """Draw the DCF section: the implied price next to the market price, the upside, and WACC."""
    st.subheader("Discounted cash flow (DCF)")
    price_column, market_column, upside_column, wacc_column = st.columns(4)
    price_column.metric("DCF implied price", dollars(dcf["implied_share_price"]))
    market_column.metric("Market price", dollars(company["share_price"]))
    upside_column.metric("Upside vs market", percent(dcf["upside"]))
    wacc_column.metric("WACC", percent(dcf["wacc"]))


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
    """Draw the whole page: title, DCF section, multiples section and the footer."""
    company = data.get_company_data(TICKER)
    dcf, multiples = run_valuation(company)

    st.title("Valuation Lab")
    st.write(f"{company['company_name']} ({company['ticker']})")
    draw_dcf(company, dcf)
    draw_multiples(multiples)
    st.divider()
    st.caption(FOOTER_TEXT)


st.set_page_config(page_title="Valuation Lab")
draw_page()
