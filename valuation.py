"""All valuation maths for Valuation Lab.

Every formula here follows docs/model.md and is checked against excel/valuation-lab.xlsx
in test_valuation.py. Nothing in this file is hard-coded: every number a function needs
is handed to it, so the same functions work for any company.

Conventions: money is in $ millions, shares are in millions, and rates and percentages
are decimals (0.09 means 9%).
"""

import statistics


# ---------------------------------------------------------------------------
# Forecast (docs/model.md: "The forecast" and "Free cash flow")
# ---------------------------------------------------------------------------

def project_revenue(base_revenue, growth_rates):
    """Grow revenue year by year from the base year, one growth rate per forecast year.

    Returns a list with one revenue figure per forecast year.
    """
    revenues = []
    revenue = base_revenue
    for growth in growth_rates:
        revenue = revenue * (1 + growth)
        revenues.append(revenue)
    return revenues


def free_cash_flow_for_one_year(revenue, operating_margin, tax_rate, da_pct, capex_pct, wc_pct):
    """Work out one year's free cash flow: the cash left after tax and after paying for
    the investments the business needs.

    The working capital percentage is positive when the business collects cash (an inflow).
    """
    ebit = revenue * operating_margin
    nopat = ebit * (1 - tax_rate)
    depreciation_and_amortisation = revenue * da_pct
    capex = revenue * capex_pct
    cash_from_working_capital = revenue * wc_pct
    return nopat + depreciation_and_amortisation - capex + cash_from_working_capital


def free_cash_flows(revenues, operating_margins, tax_rate, da_pcts, capex_pcts, wc_pcts):
    """Work out free cash flow for every forecast year by repeating the one-year recipe.

    All the lists must have one entry per forecast year; the tax rate is the same each year.
    """
    lengths = {len(revenues), len(operating_margins), len(da_pcts), len(capex_pcts), len(wc_pcts)}
    if len(lengths) != 1:
        raise ValueError(
            "Revenues, margins, D&A %, capex % and working capital % must all have one "
            "entry per forecast year."
        )
    return [
        free_cash_flow_for_one_year(revenue, margin, tax_rate, da_pct, capex_pct, wc_pct)
        for revenue, margin, da_pct, capex_pct, wc_pct
        in zip(revenues, operating_margins, da_pcts, capex_pcts, wc_pcts)
    ]


# ---------------------------------------------------------------------------
# Discount rate (docs/model.md: "Discount rate (WACC)")
# ---------------------------------------------------------------------------

def cost_of_equity(risk_free_rate, beta, equity_risk_premium):
    """Estimate the return shareholders expect, using CAPM: the risk-free rate plus beta
    times the extra return investors demand for owning shares.
    """
    return risk_free_rate + beta * equity_risk_premium


def after_tax_cost_of_debt(pre_tax_cost_of_debt, tax_rate):
    """Work out what borrowing really costs after the tax saving, because interest is
    tax-deductible.
    """
    return pre_tax_cost_of_debt * (1 - tax_rate)


def wacc(share_price, shares, debt, cost_of_equity_rate, after_tax_cost_of_debt_rate):
    """Blend the cost of equity and the after-tax cost of debt into one discount rate,
    weighting each by how much of the company's market value it funds.

    Equity is valued at share price times shares; debt is financial debt only. The result
    is not rounded.
    """
    market_value_of_equity = share_price * shares
    total_capital = market_value_of_equity + debt
    weight_of_equity = market_value_of_equity / total_capital
    weight_of_debt = debt / total_capital
    return weight_of_equity * cost_of_equity_rate + weight_of_debt * after_tax_cost_of_debt_rate


# ---------------------------------------------------------------------------
# Enterprise value (docs/model.md: "Terminal value" and "From enterprise value...")
# ---------------------------------------------------------------------------

def discount_factor(discount_rate, year):
    """Say what one dollar received in a given year is worth today (year 1 is the first
    forecast year).

    This is a small helper shared by the two present-value functions below.
    """
    return 1 / (1 + discount_rate) ** year


def present_value_of_forecast(cash_flows, discount_rate):
    """Convert each forecast year's free cash flow into today's money and add them up."""
    return sum(
        cash_flow * discount_factor(discount_rate, year)
        for year, cash_flow in enumerate(cash_flows, start=1)
    )


def terminal_value(final_year_cash_flow, discount_rate, terminal_growth_rate):
    """Estimate what all cash flows after the forecast are worth at the end of the last
    forecast year, assuming they grow at a steady rate forever (the Gordon growth model).

    Stops with an error if the growth rate is not below the discount rate, because the
    formula gives nonsense in that case.
    """
    if terminal_growth_rate >= discount_rate:
        raise ValueError(
            "The terminal growth rate must be lower than the discount rate (WACC); "
            "otherwise the terminal value is meaningless."
        )
    next_year_cash_flow = final_year_cash_flow * (1 + terminal_growth_rate)
    return next_year_cash_flow / (discount_rate - terminal_growth_rate)


def present_value_of_terminal_value(terminal_value_amount, discount_rate, forecast_years):
    """Convert the terminal value into today's money, using the discount factor of the
    last forecast year.
    """
    return terminal_value_amount * discount_factor(discount_rate, forecast_years)


def enterprise_value(pv_of_forecast, pv_of_terminal_value):
    """Add the present value of the forecast cash flows and of the terminal value to get
    the value of the whole business, before looking at debt and cash.
    """
    return pv_of_forecast + pv_of_terminal_value


# ---------------------------------------------------------------------------
# From enterprise value to a share price
# ---------------------------------------------------------------------------

def net_debt(debt, cash_and_investments):
    """Subtract cash and investments from debt; a negative answer means the company has
    more cash than debt.
    """
    return debt - cash_and_investments


def implied_share_price(enterprise_value_amount, net_debt_amount, shares):
    """Turn enterprise value into a value per share: take off net debt to get equity
    value, then divide by the number of shares.

    Returns two numbers, the equity value and then the price per share.
    """
    equity_value = enterprise_value_amount - net_debt_amount
    return equity_value, equity_value / shares


def upside(implied_price, current_price):
    """Say how far the implied price is above (positive) or below (negative) the price
    the market is paying now, as a decimal.
    """
    return implied_price / current_price - 1


# ---------------------------------------------------------------------------
# Multiples (docs/model.md: "Multiples")
# ---------------------------------------------------------------------------

def peer_median(multiples):
    """Find the middle value of the peers' multiples, so one extreme peer cannot pull the
    answer up or down the way an average would.
    """
    return statistics.median(multiples)


def ebitda(ebit, depreciation_and_amortisation):
    """Work out earnings before interest, tax, depreciation and amortisation: operating
    profit plus D&A.
    """
    return ebit + depreciation_and_amortisation


def price_from_ev_multiple(metric, multiple, net_debt_amount, shares):
    """Value a company from an enterprise-value multiple such as EV/Sales or EV/EBITDA:
    metric times multiple gives enterprise value, then net debt comes off and the rest is
    split across the shares.
    """
    enterprise_value_amount = metric * multiple
    equity_value = enterprise_value_amount - net_debt_amount
    return equity_value / shares


def price_from_pe(net_income, pe_multiple, shares):
    """Value a company from the price-to-earnings multiple: net income times the multiple
    is already equity value, so it only needs splitting across the shares.
    """
    return net_income * pe_multiple / shares


def dcf_vs_multiples(dcf_price, multiples_price):
    """Say how far the DCF price is above (positive) or below (negative) the price the
    multiples give, as a decimal.
    """
    return dcf_price / multiples_price - 1


# ---------------------------------------------------------------------------
# The whole DCF in one go
# ---------------------------------------------------------------------------

def run_full_dcf(
    base_revenue,
    growth_rates,
    operating_margins,
    tax_rate,
    da_pcts,
    capex_pcts,
    wc_pcts,
    risk_free_rate,
    beta,
    equity_risk_premium,
    pre_tax_cost_of_debt,
    share_price,
    shares,
    debt,
    cash_and_investments,
    terminal_growth_rate,
):
    """Run every step of the DCF in order, from revenue forecast to implied share price.

    Returns a dictionary holding every intermediate number as well as the final answer,
    so a page can show any of them.
    """
    revenues = project_revenue(base_revenue, growth_rates)
    cash_flows = free_cash_flows(revenues, operating_margins, tax_rate, da_pcts, capex_pcts, wc_pcts)

    equity_cost = cost_of_equity(risk_free_rate, beta, equity_risk_premium)
    debt_cost = after_tax_cost_of_debt(pre_tax_cost_of_debt, tax_rate)
    discount_rate = wacc(share_price, shares, debt, equity_cost, debt_cost)

    pv_of_forecast = present_value_of_forecast(cash_flows, discount_rate)
    terminal = terminal_value(cash_flows[-1], discount_rate, terminal_growth_rate)
    pv_of_terminal = present_value_of_terminal_value(terminal, discount_rate, len(cash_flows))
    enterprise = enterprise_value(pv_of_forecast, pv_of_terminal)

    net_debt_amount = net_debt(debt, cash_and_investments)
    equity, price = implied_share_price(enterprise, net_debt_amount, shares)

    return {
        "revenues": revenues,
        "free_cash_flows": cash_flows,
        "cost_of_equity": equity_cost,
        "after_tax_cost_of_debt": debt_cost,
        "wacc": discount_rate,
        "pv_of_forecast": pv_of_forecast,
        "terminal_value": terminal,
        "pv_of_terminal_value": pv_of_terminal,
        "enterprise_value": enterprise,
        "net_debt": net_debt_amount,
        "equity_value": equity,
        "implied_share_price": price,
        "upside": upside(price, share_price),
    }
